import asyncio
import json
import os
import sys
import time
import hashlib
from contextlib import asynccontextmanager
from copy import copy
from datetime import datetime
from pathlib import Path
from typing import Any, Type, Tuple
from uuid import uuid4
import ast
from fastapi import status
from fastapi.logger import logger
from sqlalchemy import literal_column, or_
from sqlalchemy.orm import sessionmaker, defer
from sqlmodel import Session, select, col, delete, update, Integer, Float, Boolean, func, text
from sqlalchemy import String, cast, bindparam
import io
from sys import modules as sys_modules
import models.api as api
from models.api import Exception as API_Exception, Error as API_Error
import models.core as core
from models.enums import QueryType, LockAction, ResourceType, SortType
from data_adapters.sql.create_tables import (
    Entries,
    Histories,
    Permissions,
    Roles,
    Users,
    Spaces,
    Attachments,
    Locks,
    Sessions,
    Invitations,
    URLShorts,
    OTP,
)
from utils.helpers import (
    arr_remove_common,
    get_removed_items,
    camel_case, resolve_schema_references,
)
from utils.internal_error_code import InternalErrorCode
from utils.middleware import get_request_data
from utils.password_hashing import hash_password, verify_password
from utils.query_policies_helper import get_user_query_policies, generate_query_policies
from utils.settings import settings
from data_adapters.base_data_adapter import BaseDataAdapter, MetaChild
from data_adapters.sql.adapter_helpers import (
    set_results_from_aggregation, set_table_for_query, events_query,
    subpath_checker, parse_search_string,
    sqlite_aggregate_functions, mysql_aggregate_functions,
    postgres_aggregate_functions, transform_keys_to_sql,
    get_next_date_value, is_date_time_value,
    # build_query_filter_for_allowed_field_values
)
from data_adapters.helpers import get_nested_value, trans_magic_words
from jsonschema import Draft7Validator
from starlette.datastructures import UploadFile
from sqlalchemy import URL
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession


def query_attachment_aggregation(subpath):
    return select(
        literal_column("resource_type").label("resource_type"),
        func.count(text("*")).label("count")
    ).group_by(text("resource_type")) \
        .where(col(Attachments.subpath) == subpath)


def query_aggregation(table, query):
    aggregate_functions: list = []

    if "sqlite" in settings.database_driver:
        aggregate_functions = sqlite_aggregate_functions
    elif "mysql" in settings.database_driver:
        aggregate_functions = mysql_aggregate_functions
    elif "postgresql" in settings.database_driver:
        aggregate_functions = postgres_aggregate_functions

    def _normalize_json_path(path: str) -> str:
        if path.startswith("@"):
            path = path[1:]
        if path.startswith("body."):
            return f"payload.{path}"
        return path

    def _selectable_for_load(item: str):
        if item.startswith("@"):
            col_name = item.replace("@", "")
            return getattr(table, col_name)

        if hasattr(table, item):
            return getattr(table, item)

        json_path = _normalize_json_path(item)
        expr = transform_keys_to_sql(json_path)
        alias = item.replace(".", "_")
        return text(expr).label(alias)

    statement = select(*[_selectable_for_load(ll) for ll in query.aggregation_data.load])

    if bool(query.aggregation_data.group_by):
        group_by_exprs = []
        for gb in query.aggregation_data.group_by:
            if gb.startswith("@"):
                group_by_exprs.append(table.__dict__[gb.replace("@", "")])
            elif hasattr(table, gb):
                group_by_exprs.append(getattr(table, gb))
            else:
                json_path = _normalize_json_path(gb)
                expr = transform_keys_to_sql(json_path)
                group_by_exprs.append(text(expr))
        if group_by_exprs:
            statement = statement.group_by(*group_by_exprs)

    if bool(query.aggregation_data.reducers):
        agg_selects = []
        for reducer in query.aggregation_data.reducers:
            if reducer.reducer_name in aggregate_functions:
                field_expr_str: str
                if len(reducer.args) == 0:
                    field_expr_str = "*"
                else:
                    arg0 = reducer.args[0]
                    arg0 = _normalize_json_path(arg0)
                    base_arg = arg0
                    if hasattr(table, base_arg):
                        field = getattr(table, base_arg)
                        if field is None:
                            continue
                        if isinstance(field.type, Integer) or isinstance(field.type, Boolean):
                            field_expr_str = f"{field}::int"
                        elif isinstance(field.type, Float):
                            field_expr_str = f"{field}::float"
                        else:
                            field_expr_str = f"{field}::text"
                    else:
                        jp = transform_keys_to_sql(arg0)
                        if reducer.reducer_name in ("sum", "avg", "total"):
                            field_expr_str = f"({jp})::float"
                        elif reducer.reducer_name in ("count", "r_count"):
                            field_expr_str = "*"
                        elif reducer.reducer_name in ("min", "max", "group_concat"):
                            field_expr_str = f"({jp})::text"
                        else:
                            field_expr_str = f"({jp})"
                agg_selects.append(
                    getattr(func, reducer.reducer_name)(text(field_expr_str)).label(reducer.alias)
                )
        if agg_selects:
            cols = list(statement.selected_columns) + agg_selects
            statement = statement.with_only_columns(*cols)
    return statement


def string_to_list(input_str):
    if isinstance(input_str, list):
        return input_str
    try:
        result = ast.literal_eval(input_str)
        if isinstance(result, list):
            return result
    except (ValueError, SyntaxError):
        return [input_str]


def apply_acl_and_query_policies(statement, table, user_shortname, user_query_policies):
    if table not in [Attachments, Histories] and hasattr(table, 'query_policies'):
        access_conditions = [
            "owner_shortname = :user_shortname",
            "EXISTS (SELECT 1 FROM jsonb_array_elements(CASE WHEN jsonb_typeof(acl::jsonb) = 'array' THEN acl::jsonb ELSE '[]'::jsonb END) AS elem WHERE elem->>'user_shortname' = :user_shortname AND (elem->'allowed_actions') ? 'query')"
        ]

        if user_query_policies:
            raw_items = [str(p) for p in user_query_policies]
            patterns = []
            for item in raw_items:
                for part in str(item).split('|'):
                    part = part.strip()
                    if part:
                        patterns.append(part.replace('*', '%'))

            seen = set()
            dedup_patterns = []
            for pat in patterns:
                if pat not in seen:
                    seen.add(pat)
                    dedup_patterns.append(pat)

            if dedup_patterns:
                like_clauses = []
                like_params = {}
                for idx, pat in enumerate(dedup_patterns):
                    param_name = f"qp_like_{idx}"
                    like_clauses.append(f"qp LIKE :{param_name}")
                    like_params[param_name] = pat

                qp_exists = "EXISTS (SELECT 1 FROM unnest(query_policies) AS qp WHERE " + " OR ".join(like_clauses) + ")"
                access_conditions.insert(1, qp_exists)

                clause_str = "(" + " OR ".join(access_conditions) + ")"
                access_filter = text(clause_str)
                statement = statement.where(access_filter).params(
                    user_shortname=user_shortname,
                    **like_params
                )
            else:
                clause_str = "(" + " OR ".join(access_conditions) + ")"
                access_filter = text(clause_str)
                statement = statement.where(access_filter).params(user_shortname=user_shortname)
        else:
            clause_str = "(" + " OR ".join(access_conditions) + ")"
            access_filter = text(clause_str)
            statement = statement.where(access_filter).params(user_shortname=user_shortname)
    return statement


async def set_sql_statement_from_query(table, statement, query, is_for_count):
    try:
        if query.type == QueryType.attachments_aggregation and not is_for_count:
            return query_attachment_aggregation(query.subpath)

        if query.type == QueryType.aggregation and not is_for_count:
            statement = query_aggregation(table, query)

        if query.type == QueryType.tags and not is_for_count:
            if query.retrieve_json_payload:
                statement = select(
                    func.jsonb_array_elements_text(table.tags).label('tag'),
                    func.count('*').label('count')
                ).group_by('tag')
            else:
                statement = select(func.jsonb_array_elements_text(table.tags).label('tag')).distinct()

    except Exception as e:
        print("[!query]", e)
        raise api.Exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            error=api.Error(
                type="query",
                code=InternalErrorCode.SOMETHING_WRONG,
                message=str(e),
            ),
        )

    if query.space_name:
        statement = statement.where(table.space_name == query.space_name)
    if query.subpath and table in [Entries, Attachments]:
        if query.exact_subpath:
            statement = statement.where(table.subpath == query.subpath)
        else:
            # Use bind parameter for the ILIKE pattern to avoid string interpolation
            subpath_like = (f"{query.subpath}/%".replace('//', '/'))
            statement = statement.where(
                or_(
                    table.subpath == query.subpath,
                    text("subpath ILIKE :subpath_like").bindparams(bindparam("subpath_like"))
                )
            ).params(subpath_like=subpath_like)
    if query.search:
        if not query.search.startswith("@") and not query.search.startswith("-"):
            p = "shortname || ' ' || tags || ' ' || displayname || ' ' || description || ' ' || payload"
            if table is Users:
                p += " || ' ' || COALESCE(email, '') || ' ' || COALESCE(msisdn, '') || ' ' || roles"
            if table is Roles:
                p += " || ' ' || permissions"
            # Parameterize search string
            statement = statement.where(
                text("(" + p + ") ILIKE :search")
            ).params(search=f"%{query.search}%")
        else:
            search_tokens = parse_search_string(query.search)

            try:
                table_columns = set(c.name for c in table.__table__.columns)  # type: ignore[attr-defined]
            except Exception:
                table_columns = set()

            def _field_exists_in_table(_field: str) -> bool:
                if _field in table_columns:
                    return True
                if _field.startswith('payload.') and 'payload' in table_columns:
                    return True
                if _field.startswith('payload.body.') and 'payload' in table_columns:
                    return True
                return False

            for field, field_data in search_tokens.items():
                if not _field_exists_in_table(field):
                    continue
                values = field_data['values']
                operation = field_data['operation']
                negative = field_data.get('negative', False)
                value_type = field_data.get('value_type', 'string')
                format_strings = field_data.get('format_strings', {})

                if not values:
                    continue

                if field.startswith('payload.body.'):
                    payload_field = field.replace('payload.body.', '')
                    payload_path = '->'.join([f"'{part}'" for part in payload_field.split('.')])

                    payload_path_splited = payload_path.split('->')
                    if len(payload_path_splited) > 1:
                        _nested_no_last = '->'.join(payload_path_splited[:-1])
                        _last = payload_path_splited[-1]
                        _payload_text_extract = f"payload::jsonb->'body'->{_nested_no_last}->>{_last}"
                    else:
                        _payload_text_extract = f"payload::jsonb->'body'->>{payload_path}"
                    conditions = []

                    if value_type == 'numeric' and field_data.get('is_range', False) and len(
                            field_data.get('range_values', [])) == 2:
                        val1, val2 = field_data['range_values']
                        try:
                            num1 = float(val1)
                            num2 = float(val2)
                            if num1 > num2:
                                val1, val2 = val2, val1
                        except ValueError:
                            pass
                        if negative:
                            conditions.append(
                                f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'number' AND (payload::jsonb->'body'->>{payload_path})::float NOT BETWEEN {val1} AND {val2})")
                        else:
                            conditions.append(
                                f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'number' AND (payload::jsonb->'body'->>{payload_path})::float BETWEEN {val1} AND {val2})")

                    for value in values:
                        if value_type == 'datetime':
                            if field_data.get('is_range', False) and len(field_data.get('range_values', [])) == 2:
                                range_values = field_data['range_values']
                                val1, val2 = range_values
                                if is_date_time_value(val1)[0] and is_date_time_value(val2)[0]:
                                    fmt1 = format_strings.get(val1)
                                    fmt2 = format_strings.get(val2)
                                    if fmt1 and fmt2:
                                        if fmt1 == fmt2:
                                            if val1 > val2:
                                                val1, val2 = val2, val1
                                        else:
                                            try:
                                                from datetime import datetime
                                                dt1 = datetime.strptime(val1, fmt1.replace('YYYY', '%Y').replace('MM',
                                                                                                                 '%m').replace(
                                                    'DD', '%d').replace('"T"HH24', 'T%H').replace('MI', '%M').replace(
                                                    'SS', '%S').replace('US', '%f'))
                                                dt2 = datetime.strptime(val2, fmt2.replace('YYYY', '%Y').replace('MM',
                                                                                                                 '%m').replace(
                                                    'DD', '%d').replace('"T"HH24', 'T%H').replace('MI', '%M').replace(
                                                    'SS', '%S').replace('US', '%f'))
                                                if dt1 > dt2:
                                                    val1, val2 = val2, val1
                                            except Exception:
                                                if val1 > val2:
                                                    val1, val2 = val2, val1
                                else:
                                    if val1 > val2:
                                        val1, val2 = val2, val1

                                start_value, end_value = val1, val2
                                start_format = format_strings.get(start_value)
                                end_format = format_strings.get(end_value)

                                if start_format and end_format:
                                    if negative:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND TO_TIMESTAMP({_payload_text_extract}, '{start_format}') NOT BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}') AND TO_TIMESTAMP('{end_value}', '{end_format}'))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND ({_payload_text_extract})::text NOT BETWEEN '{start_value}' AND '{end_value}')"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                                    else:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND TO_TIMESTAMP({_payload_text_extract}, '{start_format}') BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}') AND TO_TIMESTAMP('{end_value}', '{end_format}'))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND ({_payload_text_extract})::text BETWEEN '{start_value}' AND '{end_value}')"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                            else:
                                format_string = format_strings.get(value)
                                if format_string:
                                    next_value = get_next_date_value(value, format_string)

                                    if negative:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND (TO_TIMESTAMP({_payload_text_extract}, '{format_string}') < TO_TIMESTAMP('{value}', '{format_string}') OR TO_TIMESTAMP({_payload_text_extract}, '{format_string}') >= TO_TIMESTAMP('{next_value}', '{format_string}')))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND (({_payload_text_extract})::text < '{value}' OR ({_payload_text_extract})::text >= '{next_value}'))"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                                    else:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND TO_TIMESTAMP({_payload_text_extract}, '{format_string}') >= TO_TIMESTAMP('{value}', '{format_string}') AND TO_TIMESTAMP({_payload_text_extract}, '{format_string}') < TO_TIMESTAMP('{next_value}', '{format_string}'))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND ({_payload_text_extract})::text >= '{value}' AND ({_payload_text_extract})::text < '{next_value}')"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                        elif value_type == 'boolean':
                            for value in values:
                                bool_value = value.lower()
                                if negative:
                                    bool_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'boolean' AND ({_payload_text_extract})::boolean != {bool_value})"
                                    string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND ({_payload_text_extract})::boolean != {bool_value})"
                                    conditions.append(f"({bool_condition} OR {string_condition})")
                                else:
                                    bool_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'boolean' AND ({_payload_text_extract})::boolean = {bool_value})"
                                    string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND ({_payload_text_extract})::boolean = {bool_value})"
                                    conditions.append(f"({bool_condition} OR {string_condition})")
                        else:
                            is_numeric = False
                            if value.isnumeric():
                                is_numeric = True

                            if negative:
                                array_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'array' AND NOT (payload::jsonb->'body'->{payload_path} @> '[\"{value}\"]'::jsonb))"
                                string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND {_payload_text_extract} != '{value}')"

                                if is_numeric:
                                    number_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'number' AND ({_payload_text_extract})::float != {value})"
                                    conditions.append(
                                        f"({array_condition} OR {string_condition} OR {number_condition})")
                                else:
                                    conditions.append(f"({array_condition} OR {string_condition})")
                            else:
                                array_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'array' AND payload::jsonb->'body'->{payload_path} @> '[\"{value}\"]'::jsonb)"
                                string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND {_payload_text_extract} = '{value}')"
                                direct_condition = f"(payload::jsonb->'body'->{payload_path} = '\"{value}\"'::jsonb)"

                                if is_numeric:
                                    number_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'number' AND ({_payload_text_extract})::float = {value})"
                                    conditions.append(
                                        f"({array_condition} OR {string_condition} OR {direct_condition} OR {number_condition})")
                                else:
                                    conditions.append(
                                        f"({array_condition} OR {string_condition} OR {direct_condition})")

                    if conditions:
                        if negative:
                            join_operator = " OR " if operation == 'AND' else " AND "
                        else:
                            join_operator = " AND " if operation == 'AND' else " OR "
                        statement = statement.where(text("(" + join_operator.join(conditions) + ")"))
                elif field.startswith('payload.'):
                    payload_field = field.replace('payload.', '')
                    payload_path = '->'.join([f"'{part}'" for part in payload_field.split('.')])

                    payload_path_splited = payload_path.split('->')
                    if len(payload_path_splited) > 1:
                        _nested_no_last = '->'.join(payload_path_splited[:-1])
                        _last = payload_path_splited[-1]
                        _payload_text_extract = f"payload::jsonb->{_nested_no_last}->>{_last}"
                    else:
                        _payload_text_extract = f"payload::jsonb->>{payload_path}"

                    conditions = []

                    if value_type == 'numeric' and field_data.get('is_range', False) and len(
                            field_data.get('range_values', [])) == 2:
                        val1, val2 = field_data['range_values']
                        try:
                            num1 = float(val1)
                            num2 = float(val2)
                            if num1 > num2:
                                val1, val2 = val2, val1
                        except ValueError:
                            pass
                        if negative:
                            conditions.append(
                                f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'number' AND ({_payload_text_extract})::float NOT BETWEEN {val1} AND {val2})")
                        else:
                            conditions.append(
                                f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'number' AND ({_payload_text_extract})::float BETWEEN {val1} AND {val2})")

                    for value in values:
                        if value_type == 'datetime':
                            if field_data.get('is_range', False) and len(field_data.get('range_values', [])) == 2:
                                range_values = field_data['range_values']
                                val1, val2 = range_values
                                if is_date_time_value(val1)[0] and is_date_time_value(val2)[0]:
                                    fmt1 = format_strings.get(val1)
                                    fmt2 = format_strings.get(val2)
                                    if fmt1 and fmt2:
                                        if fmt1 == fmt2:
                                            if val1 > val2:
                                                val1, val2 = val2, val1
                                        else:
                                            try:
                                                from datetime import datetime
                                                dt1 = datetime.strptime(val1, fmt1.replace('YYYY', '%Y').replace('MM',
                                                                                                                 '%m').replace(
                                                    'DD', '%d').replace('"T"HH24', 'T%H').replace('MI', '%M').replace(
                                                    'SS', '%S').replace('US', '%f'))
                                                dt2 = datetime.strptime(val2, fmt2.replace('YYYY', '%Y').replace('MM',
                                                                                                                 '%m').replace(
                                                    'DD', '%d').replace('"T"HH24', 'T%H').replace('MI', '%M').replace(
                                                    'SS', '%S').replace('US', '%f'))
                                                if dt1 > dt2:
                                                    val1, val2 = val2, val1
                                            except Exception:
                                                if val1 > val2:
                                                    val1, val2 = val2, val1
                                else:
                                    if val1 > val2:
                                        val1, val2 = val2, val1

                                start_value, end_value = val1, val2
                                start_format = format_strings.get(start_value)
                                end_format = format_strings.get(end_value)

                                if start_format and end_format:
                                    if negative:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND TO_TIMESTAMP({_payload_text_extract}, '{start_format}') NOT BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}') AND TO_TIMESTAMP('{end_value}', '{end_format}'))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND ({_payload_text_extract})::text NOT BETWEEN '{start_value}' AND '{end_value}')"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                                    else:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND TO_TIMESTAMP({_payload_text_extract}, '{start_format}') BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}') AND TO_TIMESTAMP('{end_value}', '{end_format}'))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND ({_payload_text_extract})::text BETWEEN '{start_value}' AND '{end_value}')"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                            else:
                                format_string = format_strings.get(value)
                                if format_string:
                                    next_value = get_next_date_value(value, format_string)

                                    if negative:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND (TO_TIMESTAMP({_payload_text_extract}, '{format_string}') < TO_TIMESTAMP('{value}', '{format_string}') OR TO_TIMESTAMP({_payload_text_extract}, '{format_string}') >= TO_TIMESTAMP('{next_value}', '{format_string}')))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND (({_payload_text_extract})::text < '{value}' OR ({_payload_text_extract})::text >= '{next_value}'))"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                                    else:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND TO_TIMESTAMP({_payload_text_extract}, '{format_string}') >= TO_TIMESTAMP('{value}', '{format_string}') AND TO_TIMESTAMP({_payload_text_extract}, '{format_string}') < TO_TIMESTAMP('{next_value}', '{format_string}'))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND ({_payload_text_extract})::text >= '{value}' AND ({_payload_text_extract})::text < '{next_value}')"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                        else:
                            is_numeric = False
                            if value.isnumeric():
                                is_numeric = True

                            if negative:
                                array_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'array' AND NOT (payload::jsonb->{payload_path} @> '[\"{value}\"]'::jsonb))"
                                if '*' in value:
                                    pattern = value.replace('*', '%')
                                    string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND {_payload_text_extract} NOT ILIKE '{pattern}')"
                                else:
                                    string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND {_payload_text_extract} != '{value}')"

                                if is_numeric:
                                    number_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'number' AND ({_payload_text_extract})::float != {value})"
                                    conditions.append(
                                        f"({array_condition} OR {string_condition} OR {number_condition})")
                                else:
                                    conditions.append(f"({array_condition} OR {string_condition})")
                            else:
                                array_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'array' AND payload::jsonb->{payload_path} @> '[\"{value}\"]'::jsonb)"
                                if '*' in value:
                                    pattern = value.replace('*', '%')
                                    string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND {_payload_text_extract} ILIKE '{pattern}')"
                                else:
                                    string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND {_payload_text_extract} = '{value}')"
                                direct_condition = f"(payload::jsonb->{payload_path} = '\"{value}\"'::jsonb)"

                                if is_numeric:
                                    number_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'number' AND ({_payload_text_extract})::float = {value})"
                                    conditions.append(
                                        f"({array_condition} OR {string_condition} OR {direct_condition} OR {number_condition})")
                                else:
                                    conditions.append(
                                        f"({array_condition} OR {string_condition} OR {direct_condition})")

                    if conditions:
                        if negative:
                            join_operator = " OR " if operation == 'AND' else " AND "
                        else:
                            join_operator = " AND " if operation == 'AND' else " OR "
                        statement = statement.where(text("(" + join_operator.join(conditions) + ")"))
                else:
                    try:
                        if hasattr(table, field):
                            field_obj = getattr(table, field)
                            if hasattr(field_obj, 'type') and str(field_obj.type).lower() == 'jsonb':
                                conditions = []
                                for value in values:
                                    if negative:
                                        array_condition = f"(jsonb_typeof({field}) = 'array' AND NOT ({field} @> '[\"{value}\"]'::jsonb))"
                                        object_condition = f"(jsonb_typeof({field}) = 'object' AND NOT ({field}::text ILIKE '%{value}%'))"
                                        conditions.append(f"({array_condition} OR {object_condition})")
                                    else:
                                        array_condition = f"(jsonb_typeof({field}) = 'array' AND {field} @> '[\"{value}\"]'::jsonb)"
                                        object_condition = f"(jsonb_typeof({field}) = 'object' AND {field}::text ILIKE '%{value}%')"
                                        conditions.append(f"({array_condition} OR {object_condition})")

                                if conditions:
                                    if negative:
                                        join_operator = " OR " if operation == 'AND' else " AND "
                                    else:
                                        join_operator = " AND " if operation == 'AND' else " OR "
                                    statement = statement.where(text("(" + join_operator.join(conditions) + ")"))
                            elif value_type == 'datetime':
                                conditions = []

                                if field_data.get('is_range', False) and len(field_data.get('range_values', [])) == 2:
                                    range_values = field_data['range_values']
                                    val1, val2 = range_values
                                    if is_date_time_value(val1)[0] and is_date_time_value(val2)[0]:
                                        fmt1 = format_strings.get(val1)
                                        fmt2 = format_strings.get(val2)
                                        if fmt1 and fmt2:
                                            if fmt1 == fmt2:
                                                if val1 > val2:
                                                    val1, val2 = val2, val1
                                            else:
                                                try:
                                                    from datetime import datetime
                                                    dt1 = datetime.strptime(val1,
                                                                            fmt1.replace('YYYY', '%Y').replace('MM',
                                                                                                               '%m').replace(
                                                                                'DD', '%d').replace('"T"HH24',
                                                                                                    'T%H').replace('MI',
                                                                                                                   '%M').replace(
                                                                                'SS', '%S').replace('US', '%f'))
                                                    dt2 = datetime.strptime(val2,
                                                                            fmt2.replace('YYYY', '%Y').replace('MM',
                                                                                                               '%m').replace(
                                                                                'DD', '%d').replace('"T"HH24',
                                                                                                    'T%H').replace('MI',
                                                                                                                   '%M').replace(
                                                                                'SS', '%S').replace('US', '%f'))
                                                    if dt1 > dt2:
                                                        val1, val2 = val2, val1
                                                except Exception:
                                                    if val1 > val2:
                                                        val1, val2 = val2, val1
                                    else:
                                        if val1 > val2:
                                            val1, val2 = val2, val1

                                    start_value, end_value = val1, val2
                                    start_format = format_strings.get(start_value)
                                    end_format = format_strings.get(end_value)

                                    if start_format and end_format:
                                        if negative:
                                            conditions.append(
                                                f"({field}::timestamp NOT BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}')::timestamp AND TO_TIMESTAMP('{end_value}', '{end_format}')::timestamp)")
                                        else:
                                            conditions.append(
                                                f"({field}::timestamp BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}')::timestamp AND TO_TIMESTAMP('{end_value}', '{end_format}')::timestamp)")
                                else:
                                    for value in values:
                                        format_string = format_strings.get(value)
                                        if format_string:
                                            next_value = get_next_date_value(value, format_string)

                                            if negative:
                                                conditions.append(
                                                    f"({field}::timestamp < TO_TIMESTAMP('{value}', '{format_string}')::timestamp OR {field}::timestamp >= TO_TIMESTAMP('{next_value}', '{format_string}')::timestamp)")
                                            else:
                                                conditions.append(
                                                    f"({field}::timestamp >= TO_TIMESTAMP('{value}', '{format_string}')::timestamp AND {field}::timestamp < TO_TIMESTAMP('{next_value}', '{format_string}')::timestamp)")

                                if conditions:
                                    if negative:
                                        join_operator = " OR " if operation == 'AND' else " AND "
                                    else:
                                        join_operator = " AND " if operation == 'AND' else " OR "
                                    statement = statement.where(text("(" + join_operator.join(conditions) + ")"))
                            elif value_type == 'numeric':
                                conditions = []

                                if field_data.get('is_range', False) and len(field_data.get('range_values', [])) == 2:
                                    range_values = field_data['range_values']
                                    val1, val2 = range_values
                                    try:
                                        num1 = float(val1)
                                        num2 = float(val2)
                                        if num1 > num2:
                                            val1, val2 = val2, val1
                                    except ValueError:
                                        pass

                                    if negative:
                                        conditions.append(f"(CAST({field} AS FLOAT) NOT BETWEEN {val1} AND {val2})")
                                    else:
                                        conditions.append(f"(CAST({field} AS FLOAT) BETWEEN {val1} AND {val2})")
                                else:
                                    for value in values:
                                        if negative:
                                            conditions.append(f"(CAST({field} AS FLOAT) != {value})")
                                        else:
                                            conditions.append(f"(CAST({field} AS FLOAT) = {value})")

                                if conditions:
                                    if negative:
                                        join_operator = " OR " if operation == 'AND' else " AND "
                                    else:
                                        join_operator = " AND " if operation == 'AND' else " OR "

                                    statement = statement.where(text("(" + join_operator.join(conditions) + ")"))
                            elif value_type == 'boolean':
                                conditions = []
                                for value in values:
                                    bool_value = value.lower()
                                    if negative:
                                        conditions.append(f"(CAST({field} AS BOOLEAN) != {bool_value})")
                                    else:
                                        conditions.append(f"(CAST({field} AS BOOLEAN) = {bool_value})")

                                if conditions:
                                    if negative:
                                        join_operator = " OR " if operation == 'AND' else " AND "
                                    else:
                                        join_operator = " AND " if operation == 'AND' else " OR "
                                    statement = statement.where(text(join_operator.join(conditions)))
                            else:
                                field_obj = getattr(table, field)
                                is_timestamp = hasattr(field_obj, 'type') and str(field_obj.type).lower().startswith(
                                    'timestamp')

                                if is_timestamp:
                                    conditions = []
                                    for value in values:
                                        if negative:
                                            conditions.append(f"{field}::text != '{value}'")
                                        else:
                                            conditions.append(f"{field}::text = '{value}'")

                                    join_operator = " AND " if operation == 'AND' else " OR "
                                    statement = statement.where(text("(" + join_operator.join(conditions) + ")"))
                                else:
                                    conditions = []
                                    for value in values:
                                        if '*' in value:
                                            pattern = value.replace('*', '%')
                                            if negative:
                                                conditions.append(f"{field} NOT ILIKE '{pattern}'")
                                            else:
                                                conditions.append(f"{field} ILIKE '{pattern}'")
                                        else:
                                            if negative:
                                                conditions.append(f"{field} != '{value}'")
                                            else:
                                                conditions.append(f"{field} = '{value}'")
                                    if negative:
                                        join_operator = ' AND '
                                    else:
                                        join_operator = ' AND ' if operation == 'AND' else ' OR '
                                    statement = statement.where(text('(' + join_operator.join(conditions) + ')'))
                        else:
                            conditions = []
                            for value in values:
                                if value_type == 'datetime':

                                    if field_data.get('is_range', False) and len(
                                            field_data.get('range_values', [])) == 2:
                                        range_values = field_data['range_values']
                                        val1, val2 = range_values
                                        if is_date_time_value(val1)[0] and is_date_time_value(val2)[0]:
                                            fmt1 = format_strings.get(val1)
                                            fmt2 = format_strings.get(val2)
                                            if fmt1 and fmt2:
                                                if fmt1 == fmt2:
                                                    if val1 > val2:
                                                        val1, val2 = val2, val1
                                                else:
                                                    try:
                                                        from datetime import datetime
                                                        dt1 = datetime.strptime(val1,
                                                                                fmt1.replace('YYYY', '%Y').replace('MM',
                                                                                                                   '%m').replace(
                                                                                    'DD', '%d').replace('"T"HH24',
                                                                                                        'T%H').replace(
                                                                                    'MI', '%M').replace('SS',
                                                                                                        '%S').replace(
                                                                                    'US', '%f'))
                                                        dt2 = datetime.strptime(val2,
                                                                                fmt2.replace('YYYY', '%Y').replace('MM',
                                                                                                                   '%m').replace(
                                                                                    'DD', '%d').replace('"T"HH24',
                                                                                                        'T%H').replace(
                                                                                    'MI', '%M').replace('SS',
                                                                                                        '%S').replace(
                                                                                    'US', '%f'))
                                                        if dt1 > dt2:
                                                            val1, val2 = val2, val1
                                                    except Exception:
                                                        if val1 > val2:
                                                            val1, val2 = val2, val1
                                        else:
                                            if val1 > val2:
                                                val1, val2 = val2, val1

                                        start_value, end_value = val1, val2
                                        start_format = format_strings.get(start_value)
                                        end_format = format_strings.get(end_value)

                                        if start_format and end_format:
                                            if negative:
                                                conditions.append(
                                                    f"(payload::jsonb->'{field}'::timestamp NOT BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}')::timestamp AND TO_TIMESTAMP('{end_value}', '{end_format}')::timestamp)")
                                            else:
                                                conditions.append(
                                                    f"(payload::jsonb->'{field}'::timestamp BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}')::timestamp AND TO_TIMESTAMP('{end_value}', '{end_format}')::timestamp)")
                                    else:
                                        format_string = format_strings.get(value)
                                        if format_string:
                                            next_value = get_next_date_value(value, format_string)

                                            if negative:
                                                conditions.append(
                                                    f"(payload::jsonb->'{field}'::timestamp < TO_TIMESTAMP('{value}', '{format_string}')::timestamp OR payload::jsonb->'{field}'::timestamp >= TO_TIMESTAMP('{next_value}', '{format_string}')::timestamp)")
                                            else:
                                                conditions.append(
                                                    f"(payload::jsonb->'{field}'::timestamp >= TO_TIMESTAMP('{value}', '{format_string}')::timestamp AND payload::jsonb->'{field}'::timestamp < TO_TIMESTAMP('{next_value}', '{format_string}')::timestamp)")
                                elif value_type == 'numeric':
                                    if field_data.get('is_range', False) and len(
                                            field_data.get('range_values', [])) == 2:
                                        range_values = field_data['range_values']
                                        val1, val2 = range_values
                                        try:
                                            num1 = float(val1)
                                            num2 = float(val2)
                                            if num1 > num2:
                                                val1, val2 = val2, val1
                                        except ValueError:
                                            pass

                                        if negative:
                                            conditions.append(
                                                f"(jsonb_typeof(payload::jsonb->'{field}') = 'number' AND (payload::jsonb->'{field}')::float NOT BETWEEN {val1} AND {val2})")
                                        else:
                                            conditions.append(
                                                f"(jsonb_typeof(payload::jsonb->'{field}') = 'number' AND (payload::jsonb->'{field}')::float BETWEEN {val1} AND {val2})")
                                elif value_type == 'boolean':
                                    bool_value = value.lower()
                                    if negative:
                                        conditions.append(
                                            f"(jsonb_typeof(payload::jsonb->'{field}') = 'boolean' AND (payload::jsonb->'{field}')::boolean != {bool_value})")
                                    else:
                                        conditions.append(
                                            f"(jsonb_typeof(payload::jsonb->'{field}') = 'boolean' AND (payload::jsonb->'{field}')::boolean = {bool_value})")
                                else:
                                    if '*' in value:
                                        pattern = value.replace('*', '%')
                                        if negative:
                                            conditions.append(f"(payload::jsonb->>'{field}') NOT ILIKE '{pattern}'")
                                        else:
                                            conditions.append(f"(payload::jsonb->>'{field}') ILIKE '{pattern}'")
                                    else:
                                        if negative:
                                            conditions.append(f"payload::jsonb->'{field}' != '\"{value}\"'::jsonb")
                                        else:
                                            conditions.append(f"payload::jsonb->'{field}' = '\"{value}\"'::jsonb")

                            if conditions:
                                if negative:
                                    join_operator = " OR " if operation == 'AND' else " AND "
                                else:
                                    join_operator = " AND " if operation == 'AND' else " OR "
                                statement = statement.where(text("(" + join_operator.join(conditions) + ")"))
                    except Exception as e:
                        print(f"Error handling field {field}: {e}")

    if query.filter_schema_names:
        if 'meta' in query.filter_schema_names:
            query.filter_schema_names.remove('meta')
        if query.filter_schema_names:
            statement = statement.where(
                text("(payload ->> 'schema_shortname') IN ({})".format(
                    ', '.join(f"'{item}'" for item in query.filter_schema_names)
                ))
            )
    if query.filter_shortnames:
        statement = statement.where(
            col(table.shortname).in_(query.filter_shortnames)
        )
    if query.filter_types:
        statement = statement.where(
            col(table.resource_type).in_(query.filter_types)
        )
    if query.filter_tags:
        statement = statement.where(
            col(table.tags).in_(query.filter_tags)
        )
    if query.from_date:
        statement = statement.where(table.created_at >= query.from_date)
    if query.to_date:
        statement = statement.where(table.created_at <= query.to_date)

    try:
        if not is_for_count:
            if query.sort_by:
                if query.sort_by.startswith('attributes.'):
                    query.sort_by = query.sort_by[11:]
                if "." in query.sort_by:
                    # Normalize JSON path for sorting as well (handle leading '@' and body.* shortcut)
                    sort_expression = transform_keys_to_sql(
                        query.sort_by.replace("@", "", 1) if query.sort_by.startswith("@") else (
                            f"payload.{query.sort_by}" if query.sort_by.startswith("body.") else query.sort_by))
                    sort_type = " DESC" if query.sort_type == SortType.descending else ""
                    sort_expression = f"CASE WHEN ({sort_expression}) ~ '^[0-9]+$' THEN ({sort_expression})::float END {sort_type}, ({sort_expression}) {sort_type}"
                    statement = statement.order_by(text(sort_expression))
                else:
                    if query.sort_type == SortType.ascending:
                        statement = statement.order_by(getattr(table, query.sort_by))
                    if query.sort_type == SortType.descending:
                        statement = statement.order_by(getattr(table, query.sort_by).desc())

    except Exception as e:
        print("[!set_sql_statement_from_query]", e)

    if not is_for_count:
        if query.offset:
            statement = statement.offset(query.offset)

        statement = statement.limit(query.limit)

    if query.type == QueryType.tags and not is_for_count and hasattr(table, 'tags'):
        if query.retrieve_json_payload:
            statement = select(
                func.jsonb_array_elements_text(col(table.tags)).label('tag'),
                func.count('*').label('count')
            ).where(col(table.uuid).in_(
                select(col(table.uuid)).where(statement.whereclause)  # type: ignore
            )).group_by('tag')
        else:
            statement = select(
                func.jsonb_array_elements_text(col(table.tags)).label('tag')
            ).where(col(table.uuid).in_(
                select(col(table.uuid)).where(statement.whereclause)  # type: ignore
            )).distinct()

    return statement


class SQLAdapter(BaseDataAdapter):
    _engine = None
    _async_session_factory = None
    session: Session
    async_session: sessionmaker
    engine: Any

    def locators_query(self, query: api.Query) -> tuple[int, list[core.Locator]]:
        locators: list[core.Locator] = []
        total: int = 0
        match query.type:
            case api.QueryType.subpath:
                pass
                # !TODO finsih...
        return total, locators

    def folder_path(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
    ) -> str:
        return ""

    async def otp_created_since(self, key: str) -> int | None:
        async with self.get_session() as session:
            result = await session.execute(select(OTP).where(OTP.key == key))
            otp_entry = result.scalar_one_or_none()

            if otp_entry:
                return int((datetime.now() - otp_entry.timestamp).total_seconds())

            return None

    async def save_otp(
            self,
            key: str,
            otp: str,
    ):
        try:
            async with self.get_session() as session:
                otp_entry = OTP(
                    key=key,
                    value={"otp": otp},
                    timestamp=datetime.now()
                )
                session.add(otp_entry)
        except Exception as e:
            async with self.get_session() as session:
                if "UniqueViolationError" in str(e) or "unique constraint" in str(e).lower():
                    await session.rollback()
                    statement = delete(OTP).where(col(OTP.key) == key)
                    await session.execute(statement)

                    otp_entry = OTP(
                        key=key,
                        value={"otp": otp},
                        timestamp=datetime.now()
                    )
                    session.add(otp_entry)
                else:
                    await session.rollback()
                    raise e

    async def get_otp(
            self,
            key: str,
    ):
        async with self.get_session() as session:
            result = await session.execute(select(OTP).where(OTP.key == key))
            otp_entry = result.scalar_one_or_none()

            if otp_entry:
                if (datetime.now() - otp_entry.timestamp).total_seconds() > settings.otp_token_ttl:
                    await session.delete(otp_entry)
                    return None
                return otp_entry.value.get("otp")
        return None

    async def delete_otp(self, key: str):
        async with self.get_session() as session:
            statement = delete(OTP).where(col(OTP.key) == key)
            await session.execute(statement)

    def metapath(self,
                 space_name: str,
                 subpath: str,
                 shortname: str,
                 class_type: Type[MetaChild],
                 schema_shortname: str | None = None,
                 ) -> tuple[Path, str]:
        return (Path(), "")

    def __init__(self):
        if SQLAdapter._engine is None:
            SQLAdapter._engine = create_async_engine(
                URL.create(
                    drivername=settings.database_driver,
                    host=settings.database_host,
                    port=settings.database_port,
                    username=settings.database_username,
                    password=settings.database_password,
                    database=settings.database_name,
                ),
                echo=False,
                pool_pre_ping=True,
                pool_size=settings.database_pool_size,
                max_overflow=settings.database_max_overflow,
                pool_timeout=settings.database_pool_timeout,
                pool_recycle=settings.database_pool_recycle,
            )
        self.engine = SQLAdapter._engine
        try:
            if SQLAdapter._async_session_factory is None:
                SQLAdapter._async_session_factory = sessionmaker(
                    self.engine, class_=AsyncSession, expire_on_commit=False
                )  # type: ignore
            self.async_session = SQLAdapter._async_session_factory
        except Exception as e:
            print("[!FATAL]", e)
            sys.exit(127)

    async def test_connection(self):
        try:
            async with self.get_session() as session:
                (await session.execute(text("SELECT 1"))).one_or_none()
        except Exception as e:
            print("[!FATAL]", e)
            sys.exit(127)

    @asynccontextmanager
    async def get_session(self):
        async_session = self.async_session()
        try:
            yield async_session
            await async_session.commit()
        finally:
            await async_session.close()  # type: ignore

    def get_table(
            self, class_type: Type[MetaChild]
    ) -> Type[Roles] | Type[Permissions] | Type[Users] | Type[Spaces] | Type[Locks] | Type[Attachments] | Type[Entries]:

        match class_type:
            case core.Role:
                return Roles
            case core.Permission:
                return Permissions
            case core.User:
                return Users
            case core.Space:
                return Spaces
            case core.Lock:
                return Locks
            case (
            core.Alteration
            | core.Media
            | core.Lock
            | core.Comment
            | core.Reply
            | core.Reaction
            | core.Json
            | core.DataAsset
            ):
                return Attachments
        return Entries

    def get_base_model(self, class_type: Type[MetaChild], data,
                       update=None) -> Roles | Permissions | Users | Spaces | Locks | Attachments | Entries:
        match class_type:
            case core.User:
                return Users.model_validate(data, update=update)
            case core.Role:
                return Roles.model_validate(data, update=update)
            case core.Permission:
                return Permissions.model_validate(data, update=update)
            case core.Space:
                return Spaces.model_validate(data, update=update)
            case (
            core.Alteration
            | core.Media
            | core.Lock
            | core.Comment
            | core.Reply
            | core.Reaction
            | core.Json
            | core.DataAsset
            ):
                if data.get("media", None) is None:
                    data["media"] = None
                return Attachments.model_validate(data, update=update)
        return Entries.model_validate(data, update=update)

    async def get_entry_attachments(
            self,
            subpath: str,
            attachments_path: Path,
            filter_types: list | None = None,
            include_fields: list | None = None,
            filter_shortnames: list | None = None,
            retrieve_json_payload: bool = False,
    ) -> dict:
        attachments_dict: dict[str, list] = {}
        async with self.get_session() as session:
            if not subpath.startswith("/"):
                subpath = f"/{subpath}"

            if str(settings.spaces_folder) in str(attachments_path):
                attachments_path = attachments_path.relative_to(settings.spaces_folder)
            space_name = attachments_path.parts[0]
            shortname = attachments_path.parts[-1]
            statement = (
                select(Attachments)
                .where(Attachments.space_name == space_name)
                .where(Attachments.subpath == f"{subpath}/{shortname}".replace('//', '/'))
            )
            results = list((await session.execute(statement)).all())

            if len(results) == 0:
                return attachments_dict

            for idx, item in enumerate(results):
                item = item[0]
                attachment_record = Attachments.model_validate(item)
                attachment_json = attachment_record.model_dump()
                attachment = {
                    "resource_type": attachment_json["resource_type"],
                    "uuid": attachment_json["uuid"],
                    "shortname": attachment_json["shortname"],
                    "subpath": "/".join(attachment_json["subpath"].split("/")[:-1])  # join(),
                }
                del attachment_json["resource_type"]
                del attachment_json["uuid"]
                del attachment_json["media"]
                del attachment_json["shortname"]
                del attachment_json["subpath"]
                del attachment_json["relationships"]
                del attachment_json["acl"]
                del attachment_json["space_name"]
                attachment["attributes"] = {**attachment_json}
                if attachment_record.resource_type in attachments_dict:
                    attachments_dict[attachment_record.resource_type].append(attachment)
                else:
                    attachments_dict[attachment_record.resource_type] = [attachment]

        return attachments_dict

    def payload_path(
            self,
            space_name: str,
            subpath: str,
            class_type: Type[MetaChild],
            schema_shortname: str | None = None, ) -> Path:
        """Construct the full path of the meta file"""
        path = settings.spaces_folder / space_name

        subpath = copy(subpath)
        if subpath[0] == "/":
            subpath = f".{subpath}"
        if issubclass(class_type, core.Attachment):
            [parent_subpath, parent_name] = subpath.rsplit("/", 1)
            # schema_shortname = (
            #     "." + dto.schema_shortname if dto.schema_shortname != "meta" else ""
            # )
            schema_shortname = ""
            attachment_folder = f"{parent_name}/attachments{schema_shortname}.{class_type.__name__.lower()}"
            path = path / parent_subpath / ".dm" / attachment_folder
        else:
            path = path / subpath
        return path

    async def db_load_or_none(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[MetaChild],
            user_shortname: str | None = None,
            schema_shortname: str | None = None,
    ) -> Attachments | Entries | Locks | Permissions | Roles | Spaces | Users | None:
        """Load a Meta Json according to the reuqested Class type"""
        if not subpath.startswith("/"):
            subpath = f"/{subpath}"

        shortname = shortname.replace("/", "")

        table = self.get_table(class_type)

        if table is Attachments:
            statement = select(table).options(defer(Attachments.media))  # type: ignore
        else:
            statement = select(table)
        statement = statement.where(col(table.space_name) == space_name).where(table.shortname == shortname)

        if table in [Entries, Attachments]:
            statement = statement.where(col(table.subpath) == subpath)

        try:
            async with self.get_session() as session:
                return (await session.execute(statement)).scalars().one_or_none() # type: ignore
        except Exception as e:
            print("[!load_or_none]", e)
            logger.error(f"Failed parsing an entry. Error: {e}")
            return None

    async def get_entry_by_criteria(self, criteria: dict, table: Any = None) -> core.Record | None:
        async with self.get_session() as session:
            if table is None:
                tables = [Entries, Users, Roles, Permissions, Spaces, Attachments]
                for _table in tables:
                    statement = select(_table)
                    for k, v in criteria.items():
                        # Prefer SQLAlchemy column expressions over raw text to avoid injection
                        if hasattr(_table, k):
                            column = getattr(_table, k)
                            if isinstance(v, str):
                                statement = statement.where(cast(column, String).like(bindparam(k)))
                                statement = statement.params(**{k: f"{v}%"})
                            else:
                                statement = statement.where(column == bindparam(k))
                                statement = statement.params(**{k: v})
                        else:
                            # Unknown column name; skip to avoid potential SQL injection via dynamic identifiers
                            continue

                    _result = (await session.execute(statement)).scalars().first()

                    if _result is None:
                        continue

                    core_model_class_1: core.Meta = getattr(sys.modules["models.core"],
                                                          camel_case(_result.resource_type))
                    result = core_model_class_1.model_validate(
                        _result.model_dump()
                    ).to_record(_result.subpath, _result.shortname)

                    result.attributes = {**result.attributes, "space_name": _result.space_name}

                    return result
                return None
            else:
                statement = select(table)
                for k, v in criteria.items():
                    if hasattr(table, k):
                        column = getattr(table, k)
                        if isinstance(v, str):
                            statement = statement.where(cast(column, String) == bindparam(k))
                            statement = statement.params(**{k: v})
                        else:
                            statement = statement.where(column == bindparam(k))
                            statement = statement.params(**{k: v})
                    else:
                        # Unknown column name; skip
                        continue

                _result = (await session.execute(statement)).scalars().first()

                if _result is None:
                    return None

                core_model_class_2: core.Meta = getattr(sys.modules["models.core"],
                                                      camel_case(_result.resource_type))

                result = core_model_class_2.model_validate(
                    _result.model_dump()
                ).to_record(_result.subpath, _result.shortname)
                result.attributes = {**result.attributes, "space_name": _result.space_name}

                return result

    async def get_latest_history(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
    ) -> Histories | None:
        async with self.get_session() as session:
            try:
                statement = select(Histories).where(
                    col(Histories.space_name) == space_name,
                    col(Histories.subpath) == subpath,
                    col(Histories.shortname) == shortname
                ).order_by(Histories.timestamp.desc()).limit(1)  # type: ignore
                result = await session.execute(statement)
                return result.scalars().first()  # type: ignore
            except Exception as _: # type: ignore
                return None

    async def query(
            self, query: api.Query, user_shortname: str | None = None
    ) -> Tuple[int, list[core.Record]]:
        total: int
        results: list

        if not query.subpath.startswith("/"):
            query.subpath = f"/{query.subpath}"
        if query.subpath == "//":
            query.subpath = "/"

        user_shortname = user_shortname if user_shortname else "anonymous"
        if user_shortname == "anonymous" and query.type in [QueryType.history, QueryType.events]:
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(
                    type="request",
                    code=InternalErrorCode.NOT_ALLOWED,
                    message="You don't have permission to this action",
                ),
            )
        user_query_policies = await get_user_query_policies(
            self, user_shortname, query.space_name, query.subpath, query.type == QueryType.spaces
        )
        if not query.exact_subpath:
            r = await get_user_query_policies(
                self, user_shortname, query.space_name, f'{query.subpath}/%'.replace('//', '/'),
                query.type == QueryType.spaces
            )
            user_query_policies.extend(r)

        if len(user_query_policies) == 0:
            return 0, []

        if query.type in [QueryType.attachments, QueryType.attachments_aggregation]:
            table = Attachments
            statement = select(table).options(defer(table.media))  # type: ignore
        else:
            table = set_table_for_query(query)
            statement = select(table)

        user_permissions = await self.get_user_permissions(user_shortname)
        filtered_policies = []

        _subpath_target_permissions = '/' if query.subpath == '/' else query.subpath.removeprefix('/')
        if query.filter_types:
            for ft in query.filter_types:
                target_permissions = f'{query.space_name}:{_subpath_target_permissions}:{ft}'
                filtered_policies = [policy for policy in user_query_policies if
                                     policy.startswith(target_permissions)]
        else:
            target_permissions = f'{query.space_name}:{_subpath_target_permissions}'
            filtered_policies = [policy for policy in user_query_policies if policy.startswith(target_permissions)]

        ffv_spaces, ffv_subpath, ffv_resource_type, ffv_query = [], [], [], []
        for user_query_policy in filtered_policies:
            for perm_key in user_permissions.keys():
                if user_query_policy.startswith(perm_key):
                    if ffv := user_permissions[perm_key]['filter_fields_values']:
                        if ffv not in ffv_query:
                            ffv_query.append(ffv)
                        perm_key_splited = perm_key.split(':')
                        ffv_spaces.append(perm_key_splited[0])
                        ffv_subpath.append(perm_key_splited[1])
                        ffv_resource_type.append(perm_key_splited[2])

        if len(ffv_spaces):
            perm_key_splited_query = f'@space_name:{"|".join(ffv_spaces)} @subpath:/{"|/".join(ffv_subpath)} @resource_type:{"|".join(ffv_resource_type)} {" ".join(ffv_query)}'
            if query.search:
                query.search += f' {perm_key_splited_query}'
            else:
                query.search = perm_key_splited_query
        if query.search:
            parts = [p for p in query.search.split(' ') if p]
            seen = set()
            deduped_parts = []
            for p in parts:
                if p not in seen:
                    seen.add(p)
                    deduped_parts.append(p)
            query.search = ' '.join(deduped_parts)
        statement_total = select(func.count(col(table.uuid)))

        if query and query.type == QueryType.events:
            try:
                return await events_query(query, user_shortname)
            except Exception as e:
                print(e)
                return 0, []

        if query and query.type == QueryType.tags:
            try:
                statement = await set_sql_statement_from_query(table, statement, query, False)
                statement_total = await set_sql_statement_from_query(table, statement_total, query, True)
                async with self.get_session() as session:
                    results = list((await session.execute(statement)).all())
                    if len(results) == 0:
                        return 0, []

                tags = []
                tag_counts = {}
                if query.retrieve_json_payload:
                    for result in results:
                        if result and len(result) > 1 and result[0]:
                            tag = result[0]
                            count = result[1]
                            tags.append(tag)
                            tag_counts[tag] = count
                else:
                    for result in results:
                        if result and len(result) > 0 and result[0]:
                            tags.append(result[0])
                async with self.get_session() as session:
                    _total = (await session.execute(statement_total)).one()
                    total = int(_total[0])

                attributes = {"tags": tags}
                if query.retrieve_json_payload and tag_counts:
                    attributes["tag_counts"] = tag_counts  # type: ignore

                return total, [core.Record(
                    resource_type=core.ResourceType.content,
                    shortname="tags",
                    subpath=query.subpath,
                    attributes=attributes,
                )]
            except Exception as e:
                print("[!!query_tags]", e)
                return 0, []

        is_fetching_spaces = False
        if (query.space_name
                and query.type == QueryType.spaces
                and query.space_name == "management"
                and query.subpath == "/"):
            is_fetching_spaces = True
            statement = select(Spaces)  # type: ignore
            statement_total = select(func.count(col(Spaces.uuid)))
        else:
            statement = await set_sql_statement_from_query(table, statement, query, False)
            statement_total = await set_sql_statement_from_query(table, statement_total, query, True)

        if query.type != QueryType.spaces:
            statement = apply_acl_and_query_policies(statement, table, user_shortname, user_query_policies)
            statement_total = apply_acl_and_query_policies(statement_total, table, user_shortname,
                                                           user_query_policies)

        try:
            if query.type == QueryType.aggregation and query.aggregation_data and bool(
                    query.aggregation_data.group_by):
                statement_total = select(
                    func.sum(statement_total.c["count"]).label('total_count')
                )

            async with self.get_session() as session:
                if query.retrieve_total:
                    _total = (await session.execute(statement_total)).one()
                    total = int(_total[0])
                else:
                    total = -1
                if query.type == QueryType.counters:
                    return total, []

                if query.type == QueryType.attachments_aggregation:
                    # For aggregation, we need tuples
                    results = list((await session.execute(statement)).all())
                    await session.close()
                    attributes = {}
                    for item in results:
                        attributes.update({item[0]: item[1]})
                    return 1, [core.Record(
                        resource_type=ResourceType.content,
                        uuid=uuid4(),
                        shortname='aggregation_result',
                        subpath=query.subpath,
                        attributes=attributes
                    )]
                elif query.type == QueryType.aggregation:
                    results = list((await session.execute(statement)).all())
                    await session.close()
                else:
                    # Non-aggregation: fetch ORM instances directly
                    results = (await session.execute(statement)).scalars().all()
                    await session.close()

            if is_fetching_spaces:
                from utils.access_control import access_control
                results = [result for result in results if await access_control.check_space_access(
                    user_shortname if user_shortname else "anonymous", result.shortname
                )]
            if len(results) == 0:
                return 0, []

            results = await self._set_query_final_results(query, results)

            if getattr(query, 'join', None):
                try:
                    results = await self._apply_client_joins(results, query.join, user_shortname or "anonymous") # type: ignore
                except Exception as e:
                    print("[!client_join]", e)

        except Exception as e:
            print("[!!query]", e)
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="query",
                    code=InternalErrorCode.SOMETHING_WRONG,
                    message=str(e),
                ),
            )
        return total, results

    async def _apply_client_joins(self, base_records: list[core.Record], joins: list[api.JoinQuery], user_shortname: str) -> list[core.Record]:
        def parse_join_on(expr: str) -> list[tuple[str, bool, str, bool]]:
            joins_list = []
            for part in expr.split(','):
                part = part.strip()
                if not part:
                    continue
                parts = [p.strip() for p in part.split(':', 1)]
                if len(parts) != 2:
                    raise ValueError(f"Invalid join_on expression: {expr}")
                left, right = parts[0], parts[1]
                _l_arr = left.endswith('[]')
                _r_arr = right.endswith('[]')
                if _l_arr:
                    left = left[:-2]
                if _r_arr:
                    right = right[:-2]
                joins_list.append((left, _l_arr, right, _r_arr))
            return joins_list

        def get_values_from_record(rec: core.Record, path: str, array_hint: bool) -> list:
            if path in ("shortname", "resource_type", "subpath", "uuid"):
                val = getattr(rec, path, None)
            elif path == "space_name":
                val = rec.attributes.get("space_name") if rec.attributes else None
            else:
                container = rec.attributes or {}
                val = get_nested_value(container, path)

            if val is None:
                return []
            if isinstance(val, list):
                out = []
                for item in val:
                    if isinstance(item, (str, int, float, bool)) or item is None:
                        out.append(item)
                return out

            if array_hint:
                return [val]
            return [val]

        for rec in base_records:
            if rec.attributes is None:
                rec.attributes = {}
            if rec.attributes.get('join') is None:
                rec.attributes['join'] = {}

        import models.api as api
        for join_item in joins:
            join_on = getattr(join_item, 'join_on', None)
            alias = getattr(join_item, 'alias', None)
            q = getattr(join_item, 'query', None)
            if not join_on or not alias or q is None:
                continue

            parsed_joins = parse_join_on(join_on)
            if not parsed_joins:
                continue

            sub_query = q if isinstance(q, api.Query) else api.Query.model_validate(q)
            q_raw = q if isinstance(q, dict) else q.model_dump(exclude_defaults=True)
            user_limit = q_raw.get('limit') or q_raw.get('limit_')
            sub_query.limit = settings.max_query_limit
            sub_query = copy(sub_query)

            search_terms = []
            possible_match = True

            for l_path, l_arr, r_path, r_arr in parsed_joins:
                left_values = set()
                for br in base_records:
                    l_vals = get_values_from_record(br, l_path, l_arr)
                    for v in l_vals:
                        if v is not None:
                            left_values.add(str(v))

                if not left_values:
                    possible_match = False
                    break

                search_val = "|".join(left_values)
                search_terms.append(f"@{r_path}:{search_val}")

            if not possible_match:
                right_records: list[core.Record] = []
            else:
                search_term = " ".join(search_terms)
                if sub_query.search:
                    sub_query.search = f"{sub_query.search} {search_term}"
                else:
                    sub_query.search = search_term

                _total, right_records = await self.query(sub_query, user_shortname)

            first_join = parsed_joins[0]
            l_path_0, l_arr_0, r_path_0, r_arr_0 = first_join

            right_index: dict[str, list[core.Record]] = {}
            for rr in right_records:
                r_vals = get_values_from_record(rr, r_path_0, r_arr_0)
                for v in r_vals:
                    if v is None:
                        continue
                    key = str(v)
                    right_index.setdefault(key, []).append(rr)

            for br in base_records:
                l_vals = get_values_from_record(br, l_path_0, l_arr_0)
                candidates: list[core.Record] = []
                for v in l_vals:
                    if v is None:
                        continue
                    key = str(v)
                    if key in right_index:
                        candidates.extend(right_index[key])

                seen = set()
                unique_candidates = []
                for c in candidates:
                    uid = f"{c.subpath}:{c.shortname}:{c.resource_type}"
                    if uid in seen:
                        continue
                    seen.add(uid)
                    unique_candidates.append(c)

                matched = []
                for cand in unique_candidates:
                    all_match = True
                    for i in range(1, len(parsed_joins)):
                        l_p, l_a, r_p, r_a = parsed_joins[i]
                        l_vs = set(str(x) for x in get_values_from_record(br, l_p, l_a) if x is not None)
                        r_vs = set(str(x) for x in get_values_from_record(cand, r_p, r_a) if x is not None)

                        if not l_vs.intersection(r_vs):
                            all_match = False
                            break

                    if all_match:
                        matched.append(cand)

                if user_limit:
                    matched = matched[:user_limit]

                br.attributes['join'][alias] = matched

        return base_records

    async def load_or_none(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[MetaChild],
            user_shortname: str | None = None,
            schema_shortname: str | None = None,
    ) -> MetaChild | None:

        result = await self.db_load_or_none(space_name, subpath, shortname, class_type, user_shortname,
                                            schema_shortname)
        if not result:
            return None

        try:
            if hasattr(result, 'payload') and result.payload and isinstance(result.payload, dict):
                if result.payload.get("body", None) is None:
                    result.payload["body"] = {}
                result.payload = core.Payload.model_validate(result.payload, strict=False)
        except Exception as e:
            print("[!load]", e)
            logger.error(f"Failed parsing an entry. Error: {e}")
        return class_type.model_validate(result.model_dump())

    async def load(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[MetaChild],
            user_shortname: str | None = None,
            schema_shortname: str | None = None,
    ) -> MetaChild:
        meta: MetaChild | None = await self.load_or_none(space_name, subpath, shortname, class_type, user_shortname,
                                                         schema_shortname)
        if meta is None:
            raise api.Exception(
                status_code=status.HTTP_404_NOT_FOUND,
                error=api.Error(
                    type="db",
                    code=InternalErrorCode.OBJECT_NOT_FOUND,
                    message=f"Request object is not available @{space_name}/{subpath}/{shortname} {class_type=} {schema_shortname=}",
                ),
            )

        return meta

    async def load_resource_payload(
            self,
            space_name: str,
            subpath: str,
            filename: str,
            class_type: Type[MetaChild],
            schema_shortname: str | None = None,
    ) -> dict[str, Any] | None:
        """Load a Meta class payload file"""
        async with self.get_session() as session:
            table = self.get_table(class_type)
            if not subpath.startswith("/"):
                subpath = f"/{subpath}"
            statement = select(table).where(table.space_name == space_name)

            if table in [Roles, Permissions, Users]:
                statement = statement.where(table.shortname == filename.replace('.json', ''))
            elif table in [Entries, Attachments, Histories]:
                statement = statement.where(table.subpath == subpath).where(
                    table.shortname == filename.replace('.json', '')
                )

            result = (await session.execute(statement)).one_or_none()
            if result is None:
                return None
            result = result[0]
            var: dict = result.model_dump().get("payload", {}).get("body", {})
            return var

    async def _validate_referential_integrity(self, meta: core.Meta):
        if isinstance(meta, core.User):
            if meta.roles:
                for role in meta.roles:
                    if not await self.load_or_none(settings.management_space, 'roles', role, core.Role):
                        raise api.Exception(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            error=api.Error(
                                type="validation",
                                code=InternalErrorCode.SHORTNAME_DOES_NOT_EXIST,
                                message=f"Role '{role}' does not exist",
                            ),
                        )
            if meta.groups:
                for group in meta.groups:
                    if not await self.load_or_none(settings.management_space, 'groups', group, core.Group):
                        raise api.Exception(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            error=api.Error(
                                type="validation",
                                code=InternalErrorCode.SHORTNAME_DOES_NOT_EXIST,
                                message=f"Group '{group}' does not exist",
                            ),
                        )
        elif isinstance(meta, core.Role):
            if meta.permissions:
                for permission in meta.permissions:
                    if not await self.load_or_none(settings.management_space, 'permissions', permission, core.Permission):
                        raise api.Exception(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            error=api.Error(
                                type="validation",
                                code=InternalErrorCode.SHORTNAME_DOES_NOT_EXIST,
                                message=f"Permission '{permission}' does not exist",
                            ),
                        )
        elif isinstance(meta, core.Group):
            if hasattr(meta, 'roles') and meta.roles:
                for role in meta.roles:
                    if not await self.load_or_none(settings.management_space, 'roles', role, core.Role):
                        raise api.Exception(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            error=api.Error(
                                type="validation",
                                code=InternalErrorCode.SHORTNAME_DOES_NOT_EXIST,
                                message=f"Role '{role}' does not exist",
                            ),
                        )

    async def _check_in_use(self, meta: core.Meta):
        async with self.get_session() as session:
            if isinstance(meta, core.Role):
                statement = select(Users.shortname).where(col(Users.roles).contains([meta.shortname]))
                result = await session.execute(statement)
                if result.first():
                    raise api.Exception(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=api.Error(
                            type="delete",
                            code=InternalErrorCode.CANNT_DELETE,
                            message=f"Role '{meta.shortname}' is in use by one or more users",
                        ),
                    )
            elif isinstance(meta, core.Group):
                statement = select(Users.shortname).where(col(Users.groups).contains([meta.shortname]))
                result = await session.execute(statement)
                if result.first():
                    raise api.Exception(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=api.Error(
                            type="delete",
                            code=InternalErrorCode.CANNT_DELETE,
                            message=f"Group '{meta.shortname}' is in use by one or more users",
                        ),
                    )
            elif isinstance(meta, core.Permission):
                statement = select(Roles.shortname).where(col(Roles.permissions).contains([meta.shortname]))
                result = await session.execute(statement)
                if result.first():
                    raise api.Exception(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=api.Error(
                            type="delete",
                            code=InternalErrorCode.CANNT_DELETE,
                            message=f"Permission '{meta.shortname}' is in use by one or more roles",
                        ),
                    )

    async def save(
            self, space_name: str, subpath: str, meta: core.Meta
    ) -> Any:
        """Save"""
        await self._validate_referential_integrity(meta)
        try:
            async with self.get_session() as session:
                entity = {
                    **meta.model_dump(),
                    "space_name": space_name,
                    "subpath": subpath,
                }

                if meta.__class__ is core.Folder:
                    if entity["subpath"] != "/":
                        if not entity["subpath"].startswith("/"):
                            entity["subpath"] = f'/{entity["subpath"]}'
                        if entity["subpath"].endswith("/"):
                            entity["subpath"] = entity["subpath"][:-1]

                if "subpath" in entity:
                    if entity["subpath"] != "/" and entity["subpath"].endswith("/"):
                        entity["subpath"] = entity["subpath"][:-1]
                    entity["subpath"] = subpath_checker(entity["subpath"])

                entity['resource_type'] = meta.__class__.__name__.lower()
                data = self.get_base_model(meta.__class__, entity)

                if not isinstance(data, Attachments) and not isinstance(data, Histories):
                    data.query_policies = generate_query_policies(
                        space_name=space_name,
                        subpath=subpath,
                        resource_type=entity['resource_type'],
                        is_active=entity['is_active'],
                        owner_shortname=entity.get('owner_shortname', 'dmart'),
                        owner_group_shortname=entity.get('owner_group_shortname', None),
                    )
                session.add(data)
                try:
                    await session.commit()
                    await session.refresh(data)
                except Exception as e:
                    await session.rollback()
                    raise e
                # Refresh authz MVs only when Users/Roles/Permissions changed
                # try:
                #     if isinstance(data, (Users, Roles, Permissions)):
                #         await self.ensure_authz_materialized_views_fresh()
                # except Exception as _e:
                #     logger.warning(f"AuthZ MV refresh after save skipped: {_e}")
                return data

        except Exception as e:
            print("[!save]", e)
            logger.error(f"Failed saving an entry. Error: {e}")
            raise api.Exception(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error=api.Error(
                    type="db",
                    code=InternalErrorCode.SOMETHING_WRONG,
                    message=f"Failed saving an entry. Error: {e}",
                ),
            )

    async def create(self, space_name: str, subpath: str, meta: core.Meta):
        result = await self.load_or_none(space_name, subpath, meta.shortname, meta.__class__)

        if result is not None:
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="create",
                    code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
                    message="already exists",
                ),
            )

        await self.save(space_name, subpath, meta)

    async def save_payload(
            self, space_name: str, subpath: str, meta: core.Meta, attachment
    ):
        if meta.__class__ != core.Content:
            media = await attachment.read()
            await self.update(
                space_name, subpath, meta,
                {}, {}, [],
                "", attachment_media=media
            )
        else:
            content = json.load(attachment.file)
            if meta.payload:
                meta.payload.body = content
                await self.update(
                    space_name, subpath, meta,
                    {}, {}, [],
                    ""
                )

    async def save_payload_from_json(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload_data: dict[str, Any],
    ):
        try:
            result = await self.db_load_or_none(space_name, subpath, meta.shortname, meta.__class__)
            if result is None:
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="create",
                        code=InternalErrorCode.MISSING_METADATA,
                        message="metadata is missing",
                    ),
                )
            if meta.payload:
                if isinstance(meta.payload.body, dict):
                    meta.payload.body = {
                        **meta.payload.body,
                        **payload_data,
                    }
                else:
                    meta.payload.body = payload_data
            
            await self._validate_referential_integrity(meta)
            result.sqlmodel_update(meta.model_dump())
            async with self.get_session() as session:
                session.add(result)
        except Exception as e:
            print("[!save_payload_from_json]", e)
            logger.error(f"Failed parsing an entry. Error: {e}")
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="update",
                    code=InternalErrorCode.SOMETHING_WRONG,
                    message="failed to update entry",
                ),
            )

    async def update(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            old_version_flattend: dict,
            new_version_flattend: dict,
            updated_attributes_flattend: list,
            user_shortname: str,
            schema_shortname: str | None = None,
            retrieve_lock_status: bool | None = False,
            attachment_media: Any | None = None,
    ) -> dict:
        """Update the entry, store the difference and return it"""
        await self._validate_referential_integrity(meta)

        try:
            result = await self.db_load_or_none(space_name, subpath, meta.shortname, meta.__class__)
            if result is None:
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="create",
                        code=InternalErrorCode.MISSING_METADATA,
                        message="metadata is missing",
                    ),
                )

            if isinstance(result, Users) and not result.is_active and meta.is_active:
                await self.set_failed_password_attempt_count(result.shortname, 0)

            result.sqlmodel_update(meta.model_dump())

            if hasattr(result, "subpath") and (not result.subpath.startswith("/")):
                result.subpath = f"/{result.subpath}"

            if isinstance(result, Attachments) and attachment_media:
                result.media = attachment_media
            if hasattr(result, 'query_policies'):
                result.query_policies = generate_query_policies(
                    space_name=space_name,
                    subpath=subpath,
                    resource_type=result.resource_type,  # type: ignore
                    is_active=result.is_active,  # type: ignore
                    owner_shortname=result.owner_shortname,
                    owner_group_shortname=result.owner_shortname,
                )

            if  meta.__class__ is not core.Lock or not isinstance(result, Locks):
                result.updated_at = datetime.now()
                new_version_flattend['updated_at'] = result.updated_at.isoformat() # type: ignore
                if "updated_at" not in updated_attributes_flattend:
                    updated_attributes_flattend.append("updated_at")
                if 'updated_at' in old_version_flattend:
                    old_version_flattend['updated_at'] = old_version_flattend['updated_at'].isoformat()

            async with self.get_session() as session:
                session.add(result)

            # try:
            #     if isinstance(result, (Users, Roles, Permissions)):
            #         await self.ensure_authz_materialized_views_fresh()
            # except Exception as _e:
            #     logger.warning(f"AuthZ MV refresh after update skipped: {_e}")
        except Exception as e:
            print("[!update]", e)
            logger.error(f"Failed parsing an entry. Error: {e}")
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="update",
                    code=InternalErrorCode.SOMETHING_WRONG,
                    message="failed to update entry",
                ),
            )

        history_diff = await self.store_entry_diff(
            space_name,
            subpath,
            meta.shortname,
            user_shortname,
            old_version_flattend,
            new_version_flattend,
            updated_attributes_flattend,
            meta.__class__,
        )
        return history_diff

    async def update_payload(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload_data: dict[str, Any],
            owner_shortname: str,
    ):
        if not meta.payload:
            meta.payload = core.Payload()
        meta.payload.body = payload_data
        await self.update(
            space_name, subpath, meta, {}, {}, [], owner_shortname
        )

    async def store_entry_diff(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            owner_shortname: str,
            old_version_flattend: dict,
            new_version_flattend: dict,
            updated_attributes_flattend: list,
            resource_type,
    ) -> dict:
        try:
            diff_keys = list(old_version_flattend.keys())
            diff_keys.extend(list(new_version_flattend.keys()))
            history_diff = {}
            for key in set(diff_keys):
                # if key in updated_attributes_flattend:
                old = copy(old_version_flattend.get(key, "null"))
                new = copy(new_version_flattend.get(key, "null"))

                if old != new:
                    if isinstance(old, list) and isinstance(new, list):
                        old, new = arr_remove_common(old, new)

                    history_diff[key] = {"old": old, "new": new}
            removed = get_removed_items(list(old_version_flattend.keys()),
                                        list(new_version_flattend.keys()))
            for r in removed:
                history_diff[r] = {
                    "old": old_version_flattend[r],
                    "new": None,
                }
            if not history_diff:
                return {}

            new_version_json = json.dumps(new_version_flattend, sort_keys=True, default=str)
            new_checksum = hashlib.sha1(new_version_json.encode()).hexdigest()

            history_obj = Histories(
                space_name=space_name,
                uuid=uuid4(),
                shortname=shortname,
                owner_shortname=owner_shortname or "__system__",
                timestamp=datetime.now(),
                request_headers=get_request_data().get("request_headers", {}),
                diff=history_diff,
                subpath=subpath,
                last_checksum_history=new_checksum,
            )

            async with self.get_session() as session:
                session.add(Histories.model_validate(history_obj))
                table = self.get_table(resource_type)
                await session.execute(
                    update(table).where(
                        col(table.space_name) == space_name,
                        col(table.subpath) == subpath,
                        col(table.shortname) == shortname
                    ).values(last_checksum_history=new_checksum)
                )

            return history_diff
        except Exception as e:
            print("[!store_entry_diff]", e, old_version_flattend, new_version_flattend)
            logger.error(f"Failed parsing an entry. Error: {e}")
            return {}

    async def move(
            self,
            src_space_name: str,
            src_subpath: str,
            src_shortname: str,
            dest_space_name: str,
            dest_subpath: str,
            dest_shortname: str,
            meta: core.Meta,
    ):
        """Move the file that match the criteria given, remove source folder if empty"""
        if not src_subpath.startswith("/"):
            src_subpath = f"/{src_subpath}"
        if dest_subpath and not dest_subpath.startswith("/"):
            dest_subpath = f"/{dest_subpath}"

        origin = await self.db_load_or_none(src_space_name, src_subpath, src_shortname, meta.__class__)
        if isinstance(origin, Locks):
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="move",
                    code=InternalErrorCode.NOT_ALLOWED,
                    message="Locks cannot be moved",
                ),
            )
        if origin is None:
            raise api.Exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="move",
                    code=InternalErrorCode.SHORTNAME_DOES_NOT_EXIST,
                    message="Entry does not exist",
                ),
            )

        async with self.get_session() as session:
            old_shortname = ""
            old_subpath = ""
            try:
                old_shortname = origin.shortname
                if hasattr(origin, 'subpath'):
                    old_subpath = origin.subpath
                table = self.get_table(meta.__class__)
                statement = select(table).where(table.space_name == dest_space_name)

                if table in [Roles, Permissions, Users, Spaces]:
                    statement = statement.where(table.shortname == dest_shortname)
                else:
                    statement = statement.where(table.subpath == dest_subpath).where(
                        table.shortname == dest_shortname
                    )

                target = (await session.execute(statement)).one_or_none()
                if target is not None:
                    raise api.Exception(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=api.Error(
                            type="move",
                            code=InternalErrorCode.SHORTNAME_ALREADY_EXIST,
                            message="already exists",
                        ),
                    )
                if dest_shortname:
                    origin.shortname = dest_shortname

                if hasattr(origin, 'subpath') and dest_subpath:
                    origin.subpath = dest_subpath

                if hasattr(origin, 'space_name') and dest_space_name:
                    origin.space_name = dest_space_name

                origin.query_policies = generate_query_policies(
                    space_name=dest_space_name,
                    subpath=dest_subpath,
                    resource_type=origin.resource_type if hasattr(origin,
                                                                  'resource_type') else origin.__class__.__name__.lower()[
                        :-1],
                    is_active=origin.is_active if hasattr(origin, 'is_active') else True,
                    owner_shortname=origin.owner_shortname,
                    owner_group_shortname=None,
                )

                session.add(origin)
                try:
                    if table is Spaces:
                        await session.execute(
                            update(Spaces)
                            .where(col(Spaces.space_name) == src_space_name)
                            .values(space_name=dest_shortname,shortname=dest_shortname)
                        )
                        await session.execute(
                            update(Entries)
                            .where(col(Entries.space_name) == src_space_name)
                            .values(space_name=dest_shortname)
                        )
                        await session.execute(
                            update(Attachments)
                            .where(col(Attachments.space_name) == src_space_name)
                            .values(space_name=dest_shortname)
                        )
                except Exception as e:
                    origin.shortname = old_shortname
                    if hasattr(origin, 'subpath'):
                        origin.subpath = old_subpath

                    session.add(origin)

                    print("[!move]", e)
                    logger.error(f"Failed parsing an entry. Error: {e}")
                    raise api.Exception(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        error=api.Error(
                            type="move",
                            code=InternalErrorCode.SOMETHING_WRONG,
                            message="failed to move entry",
                        ),
                    )
            except Exception as e:
                print("[!move]", e)
                logger.error(f"Failed parsing an entry. Error: {e}")
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="move",
                        code=InternalErrorCode.SOMETHING_WRONG,
                        message="failed to move entry",
                    ),
                )

    def delete_empty(self, path: Path):
        pass

    async def clone(
            self,
            src_space: str,
            dest_space: str,
            src_subpath: str,
            src_shortname: str,
            dest_subpath: str,
            dest_shortname: str,
            class_type: Type[MetaChild],
    ):
        pass

    async def is_entry_exist(self,
                             space_name: str,
                             subpath: str,
                             shortname: str,
                             resource_type: ResourceType,
                             schema_shortname: str | None = None, ) -> bool:
        async with self.get_session() as session:
            resource_cls = getattr(
                sys.modules["models.core"], camel_case(resource_type)
            )

            table = self.get_table(resource_cls)
            if not subpath.startswith("/"):
                subpath = f"/{subpath}"

            statement = select(table).where(table.space_name == space_name)

            if table in [Roles, Permissions, Users]:
                statement = statement.where(table.shortname == shortname)
            elif resource_cls in [
                core.Alteration,
                core.Media,
                core.Lock,
                core.Comment,
                core.Reply,
                core.Reaction,
                core.Json,
                core.DataAsset,
            ]:
                statement = statement.where(table.subpath == subpath).where(
                    table.shortname == shortname
                )

            else:
                statement = statement.where(table.subpath == subpath).where(
                    table.shortname == shortname
                )

            result = (await session.execute(statement)).fetchall()
            result = [result[0] for result in result]
            return False if len(result) == 0 else True

    async def delete(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            user_shortname: str,
            schema_shortname: str | None = None,
            retrieve_lock_status: bool | None = False,
    ):
        """Delete the file that match the criteria given, remove folder if empty"""
        await self._check_in_use(meta)
        async with self.get_session() as session:
            try:
                if not subpath.startswith("/"):
                    subpath = f"/{subpath}"

                result = await self.db_load_or_none(space_name, subpath, meta.shortname, meta.__class__)

                if meta.__class__ == core.User:
                    try:
                        await session.execute(update(Spaces).where(col(Spaces.owner_shortname) == meta.shortname).values(owner_shortname="anonymous"))
                        await session.execute(update(Entries).where(col(Entries.owner_shortname) == meta.shortname).values(owner_shortname="anonymous"))
                        await session.execute(update(Attachments).where(col(Attachments.owner_shortname) == meta.shortname).values(owner_shortname="anonymous"))
                        await session.execute(update(Roles).where(col(Roles.owner_shortname) == meta.shortname).values(owner_shortname="anonymous"))
                        await session.execute(update(Permissions).where(col(Permissions.owner_shortname) == meta.shortname).values(owner_shortname="anonymous"))

                        await session.execute(update(Locks).where(col(Locks.owner_shortname) == meta.shortname).values(owner_shortname="anonymous"))
                        await session.execute(update(Histories).where(col(Histories.owner_shortname) == meta.shortname).values(owner_shortname="anonymous"))

                        await session.execute(delete(Sessions).where(col(Sessions.shortname) == meta.shortname))
                    except Exception as _e:
                        logger.warning(f"Failed to reassign ownership to anonymous for user {meta.shortname}: {_e}")

                await session.delete(result)
                if meta.__class__ == core.Space:
                    statement2 = delete(Attachments).where(col(Attachments.space_name) == space_name)
                    await session.execute(statement2)
                    statement = delete(Entries).where(col(Entries.space_name) == space_name)
                    await session.execute(statement)
                if meta.__class__ == core.Folder:
                    _subpath = f"{subpath}/{meta.shortname}".replace('//', '/')
                    statement2 = delete(Attachments) \
                        .where(col(Attachments.space_name) == space_name) \
                        .where(col(Attachments.subpath).startswith(_subpath))
                    await session.execute(statement2)
                    statement = delete(Entries) \
                        .where(col(Entries.space_name) == space_name) \
                        .where(col(Entries.subpath).startswith(_subpath))
                    await session.execute(statement)
                elif isinstance(result, Entries):
                    entry_attachment_subpath = f"{subpath}/{meta.shortname}".replace('//', '/')
                    statement = delete(Attachments) \
                        .where(col(Attachments.space_name) == space_name) \
                        .where(col(Attachments.subpath).startswith(entry_attachment_subpath))
                    await session.execute(statement)

                # Refresh authz MVs only when Users/Roles/Permissions changed
                # try:
                #     if meta.__class__ in (core.User, core.Role, core.Permission):
                #         await self.ensure_authz_materialized_views_fresh()
                # except Exception as _e:
                #     logger.warning(f"AuthZ MV refresh after delete skipped: {_e}")
            except Exception as e:
                print("[!delete]", e)
                logger.error(f"Failed parsing an entry. Error: {e}")
                raise api.Exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error=api.Error(
                        type="delete",
                        code=InternalErrorCode.SOMETHING_WRONG,
                        message="failed to delete entry",
                    ),
                )

    async def lock_handler(self, space_name: str, subpath: str, shortname: str, user_shortname: str,
                           action: LockAction) -> dict | None:
        if not subpath.startswith("/"):
            subpath = f"/{subpath}"

        async with self.get_session() as session:
            match action:
                case LockAction.lock:
                    statement = select(Locks).where(Locks.space_name == space_name) \
                        .where(Locks.subpath == subpath) \
                        .where(Locks.shortname == shortname)
                    result = (await session.execute(statement)).one_or_none()
                    if result:
                        raise api.Exception(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            error=api.Error(
                                type="lock",
                                code=InternalErrorCode.LOCKED_ENTRY,
                                message="entry already locked already exists!",
                            )
                        )

                    lock = Locks(
                        uuid=uuid4(),
                        space_name=space_name,
                        subpath=subpath,
                        shortname=shortname,
                        owner_shortname=user_shortname,
                    )
                    session.add(lock)
                    await session.commit()
                    await session.refresh(lock)
                    return lock.model_dump()
                case LockAction.fetch:
                    lock_payload = (await self.load(
                        space_name=space_name,
                        subpath=subpath,
                        shortname=shortname,
                        class_type=core.Lock,
                        user_shortname=user_shortname,
                    )).model_dump()
                    return lock_payload
                case LockAction.unlock:
                    statement2 = delete(Locks) \
                        .where(col(Locks.space_name) == space_name) \
                        .where(col(Locks.subpath) == subpath) \
                        .where(col(Locks.shortname) == shortname)
                    await session.execute(statement2)
                    await session.commit()
        return None

    async def fetch_space(self, space_name: str) -> core.Space | None:
        try:
            return await self.load(space_name, "/", space_name, core.Space)
        except Exception as e:
            print("[!fetch_space]", e, space_name)
            return None

    async def set_user_session(self, user_shortname: str, token: str) -> bool:
        try:
            total, last_session = await self.get_user_session(user_shortname, token)

            if (settings.max_sessions_per_user == 1 and last_session is not None) \
                    or (settings.max_sessions_per_user != 0 and total >= settings.max_sessions_per_user):
                await self.remove_user_session(user_shortname)

            timestamp = datetime.now()
            async with self.get_session() as session:
                session.add(
                    Sessions(
                        uuid=uuid4(),
                        shortname=user_shortname,
                        token=hash_password(token),
                        timestamp=timestamp,
                    )
                )

            return True
        except Exception as e:
            print("[!set_sql_user_session]", e)
            return False

    async def get_user_session(self, user_shortname: str, token: str) -> Tuple[int, str | None]:
        async with self.get_session() as session:
            statement = select(Sessions) \
                .where(col(Sessions.shortname) == user_shortname)

            results = (await session.execute(statement)).all()
            results = [result[0] for result in results]

            if len(results) == 0:
                return 0, None

            for r in results:
                if settings.session_inactivity_ttl + r.timestamp.timestamp() < time.time():
                    await session.execute(delete(Sessions).where(col(Sessions.uuid) == r.uuid))
                    continue
                if verify_password(token, r.token):
                    r.timestamp = datetime.now()
                    session.add(r)
                    await session.commit()
                    return len(results), token
                # else:
                #     await session.execute(delete(Sessions).where(col(Sessions.uuid) == r.uuid))
        return len(results), None

    async def remove_user_session(self, user_shortname: str) -> bool:
        async with self.get_session() as session:
            try:
                statement = select(Sessions).where(col(Sessions.shortname) == user_shortname).order_by(
                    col(Sessions.timestamp).desc()
                ).offset(settings.max_sessions_per_user - 1)
                oldest_sessions = (await session.execute(statement)).all()
                oldest_sessions = [oldest_session[0] for oldest_session in oldest_sessions]
                for oldest_session in oldest_sessions:
                    await session.delete(oldest_session)
                await session.commit()
                return True
            except Exception as e:
                print("[!remove_sql_user_session]", e)
                return False

    async def set_invitation(self, invitation_token: str, invitation_value):
        async with self.get_session() as session:
            timestamp = datetime.now()
            try:
                session.add(
                    Invitations(
                        uuid=uuid4(),
                        invitation_token=invitation_token,
                        invitation_value=invitation_value,
                        timestamp=timestamp,
                    )
                )
            except Exception as e:
                print("[!set_invitation]", e)

    async def get_invitation(self, invitation_token: str) -> str | None:
        async with self.get_session() as session:
            statement = select(Invitations).where(col(Invitations.invitation_token) == invitation_token)

            result = (await session.execute(statement)).one_or_none()
            if result is None:
                return None
            result = result[0]
            user_session = Invitations.model_validate(result)

            return user_session.invitation_value

    async def delete_invitation(self, invitation_token: str) -> bool:
        async with self.get_session() as session:
            try:
                statement = delete(Invitations).where(col(Invitations.invitation_token) == invitation_token)
                await session.execute(statement)
                return True
            except Exception as e:
                print("[!remove_sql_user_session]", e)
                return False

    async def set_url_shortner(self, token_uuid: str, url: str):
        async with self.get_session() as session:
            try:
                session.add(
                    URLShorts(
                        uuid=uuid4(),
                        token_uuid=token_uuid,
                        url=url,
                        timestamp=datetime.now(),
                    )
                )
            except Exception as e:
                print("[!set_url_shortner]", e)

    async def get_url_shortner(self, token_uuid: str) -> str | None:
        async with self.get_session() as session:
            statement = select(URLShorts).where(URLShorts.token_uuid == token_uuid)

            result = (await session.execute(statement)).one_or_none()
            if result is None:
                return None
            result = result[0]
            url_shortner = URLShorts.model_validate(result)
            if settings.url_shorter_expires + url_shortner.timestamp.timestamp() < time.time():
                await self.delete_url_shortner(token_uuid)
                return None

            return url_shortner.url

    async def delete_url_shortner(self, token_uuid: str) -> bool:
        async with self.get_session() as session:
            try:
                statement = delete(URLShorts).where(col(URLShorts.token_uuid) == token_uuid)
                await session.execute(statement)
                return True
            except Exception as e:
                print("[!remove_sql_user_session]", e)
                return False

    async def delete_url_shortner_by_token(self, invitation_token: str) -> bool:
        async with self.get_session() as session:
            try:
                statement = delete(URLShorts).where(col(URLShorts.url).ilike(f"%{invitation_token}%"))
                await session.execute(statement)
                return True
            except Exception as e:
                print("[!delete_url_shortner_by_token]", e)
                return False

    async def _set_query_final_results(self, query, results):
        is_aggregation = query.type == QueryType.aggregation
        is_attachment_query = query.type == QueryType.attachments
        process_payload = query.type not in [QueryType.history, QueryType.events]

        # Case 1: Attachment query  → Direct conversion of all items
        if is_attachment_query:
            return [
                item.to_record(item.subpath, item.shortname)
                for item in results
            ]

        # Case 2: Aggregation query → delegate to existing aggregator
        if is_aggregation:
            for idx, item in enumerate(results):
                results = set_results_from_aggregation(query, item, results, idx)
            return results

        # Case 3: Standard query → convert and optionally fetch attachments
        attachment_tasks = []
        attachment_indices = []

        for idx, item in enumerate(results):
            rec = item.to_record(item.subpath, item.shortname)
            results[idx] = rec

            if process_payload:
                # Strip payload body early (if disabled)
                if not query.retrieve_json_payload:
                    payload = rec.attributes.get("payload", {})
                    if payload and payload.get("body"):
                        payload["body"] = None

                # Queue attachments if requested
                if query.retrieve_attachments:
                    attachment_tasks.append(
                        self.get_entry_attachments(
                            rec.subpath,
                            Path(f"{query.space_name}/{rec.shortname}"),
                            retrieve_json_payload=True,
                        )
                    )
                    attachment_indices.append(idx)

        # Run all attachment retrievals concurrently
        if attachment_tasks:
            attachments_list = await asyncio.gather(*attachment_tasks)
            for idx, attachments in zip(attachment_indices, attachments_list):
                results[idx].attachments = attachments

        return results

    async def clear_failed_password_attempts(self, user_shortname: str) -> bool:
        async with self.get_session() as session:
            try:
                statement = select(Users).where(Users.shortname == user_shortname)
                result = (await session.execute(statement)).one_or_none()
                if result is None:
                    return False
                result = result[0]
                result.attempt_count = 0
                session.add(result)
                return True
            except Exception as e:
                print("[!clear_failed_password_attempts]", e)
                return False

    async def get_failed_password_attempt_count(self, user_shortname: str) -> int:
        async with self.get_session() as session:
            statement = select(Users).where(col(Users.shortname) == user_shortname)

            result = (await session.execute(statement)).one_or_none()
            if result is None:
                return 0
            result = result[0]
            failed_login_attempt = Users.model_validate(result)
            return 0 if failed_login_attempt.attempt_count is None else failed_login_attempt.attempt_count

    async def set_failed_password_attempt_count(self, user_shortname: str, attempt_count: int) -> bool:
        async with self.get_session() as session:
            try:
                statement = select(Users).where(col(Users.shortname) == user_shortname)
                result = (await session.execute(statement)).one_or_none()
                if result is None:
                    return False
                result = result[0]
                result.attempt_count = attempt_count
                session.add(result)
                return True
            except Exception as e:
                print("[!set_failed_password_attempt_count]", e)
                return False

    async def get_spaces(self) -> dict:
        async with self.get_session() as session:
            statement = select(Spaces)
            results = (await session.execute(statement)).all()
            results = [result[0] for result in results]
            spaces = {}
            for idx, item in enumerate(results):
                space = Spaces.model_validate(item)
                spaces[space.shortname] = space.model_dump()
            return spaces

    async def get_media_attachment(self, space_name: str, subpath: str, shortname: str) -> io.BytesIO | None:
        if not subpath.startswith("/"):
            subpath = f"/{subpath}"

        async with self.get_session() as session:
            statement = select(Attachments.media) \
                .where(Attachments.space_name == space_name) \
                .where(Attachments.subpath == subpath) \
                .where(Attachments.shortname == shortname)

            result = (await session.execute(statement)).one_or_none()
            if result:
                result = result[0]
                return io.BytesIO(result)
        return None

    async def validate_uniqueness(
            self, space_name: str, record: core.Record, action: str = api.RequestType.create, user_shortname=None
    ) -> bool:
        """
        Get list of unique fields from entry's folder meta data
        ensure that each sub-list in the list is unique across all entries
        """
        parent_subpath, folder_shortname = os.path.split(record.subpath)
        folder_meta = None
        try:
            folder_meta = await self.load(space_name, parent_subpath, folder_shortname, core.Folder)
        except Exception:
            folder_meta = None

        if folder_meta is None or folder_meta.payload is None or not isinstance(folder_meta.payload.body,
                                                                                dict) or not isinstance(
            folder_meta.payload.body.get("unique_fields", None), list):  # type: ignore
            return True

        current_user = None
        if action is api.RequestType.update and record.resource_type is ResourceType.user:
            current_user = await self.load(space_name, record.subpath, record.shortname, core.User)

        for compound in folder_meta.payload.body["unique_fields"]:  # type: ignore
            query_string = ""
            for composite_unique_key in compound:
                value = get_nested_value(record.attributes, composite_unique_key)
                if value is None or value == "":
                    continue
                if current_user is not None and hasattr(current_user, composite_unique_key) \
                        and getattr(current_user, composite_unique_key) == value:
                    continue

                query_string += f"@{composite_unique_key}:{value} "

            if query_string == "":
                continue

            q = api.Query(
                space_name=space_name,
                subpath=record.subpath,
                type=QueryType.subpath,
                search=query_string
            )
            owner = record.attributes.get("owner_shortname", None) if user_shortname is None else user_shortname
            total, _ = await self.query(q, owner)

            if total != 0:
                raise API_Exception(
                    status.HTTP_400_BAD_REQUEST,
                    API_Error(
                        type="request",
                        code=InternalErrorCode.DATA_SHOULD_BE_UNIQUE,
                        message=f"Entry properties should be unique: {query_string}",
                    ),
                )
        return True

    async def validate_payload_with_schema(
            self,
            payload_data: UploadFile | dict,
            space_name: str,
            schema_shortname: str,
    ):
        if not isinstance(payload_data, (dict, UploadFile)):
            raise API_Exception(
                status.HTTP_400_BAD_REQUEST,
                API_Error(
                    type="request",
                    code=InternalErrorCode.INVALID_DATA,
                    message="Invalid payload.body",
                ),
            )

        if schema_shortname in ["folder_rendering", "meta_schema"]:
            space_name = "management"
        schema = await self.load(space_name, "/schema", schema_shortname, core.Schema)
        if schema.payload:
            schema = schema.payload.model_dump()['body']

        if not isinstance(payload_data, dict):
            data = json.load(payload_data.file)
            payload_data.file.seek(0)
        else:
            data = payload_data

        Draft7Validator(schema).validate(data)  # type: ignore

    async def get_schema(self, space_name: str, schema_shortname: str, owner_shortname: str) -> dict:
        schema_content = await self.load(
            space_name=space_name,
            subpath="/schema",
            shortname=schema_shortname,
            class_type=core.Schema,
            user_shortname=owner_shortname,
        )

        if schema_content and schema_content.payload and isinstance(schema_content.payload.body, dict):
            return resolve_schema_references(schema_content.payload.body)

        return {}

    async def check_uniqueness(self, unique_fields, search_str, redis_escape_chars) -> dict:
        for key, value in unique_fields.items():
            if value is None:
                continue
            if key == "email_unescaped":
                key = "email"

            result = await self.get_entry_by_criteria({key: value}, Users)

            if result is not None:
                return {"unique": False, "field": key}

        return {"unique": True}

    # async def ensure_authz_materialized_views_fresh(self) -> None:
    #     try:
    #         async with self.get_session() as session:
    #             latest_q = text(
    #                 """
    #                 SELECT GREATEST(
    #                     COALESCE((SELECT MAX(updated_at) FROM users), to_timestamp(0)),
    #                     COALESCE((SELECT MAX(updated_at) FROM roles), to_timestamp(0)),
    #                     COALESCE((SELECT MAX(updated_at) FROM permissions), to_timestamp(0))
    #                 ) AS max_ts
    #                 """
    #             )
    #             latest_ts_row = (await session.execute(latest_q)).one()
    #             max_ts = latest_ts_row[0]
    #
    #             meta_row = (
    #                 await session.execute(text("SELECT last_source_ts FROM authz_mv_meta WHERE id = 1"))).one_or_none()
    #             if meta_row is None or (meta_row[0] is None) or (max_ts is not None and max_ts > meta_row[0]):
    #                 await session.execute(text("REFRESH MATERIALIZED VIEW mv_user_roles"))
    #                 await session.execute(text("REFRESH MATERIALIZED VIEW mv_role_permissions"))
    #                 await session.execute(text("""
    #                     INSERT INTO authz_mv_meta(id, last_source_ts, refreshed_at)
    #                     VALUES (1, :ts, now())
    #                     ON CONFLICT (id)
    #                     DO UPDATE SET last_source_ts = EXCLUDED.last_source_ts,
    #                                   refreshed_at = now()
    #                 """), {"ts": max_ts})
    #     except Exception as e:
    #         logger.warning(f"AuthZ MV refresh failed or skipped: {e}")
    #
    # async def _bulk_load_by_shortnames(self, class_type: Type[MetaChild], shortnames: list[str]) -> dict[
    #     str, MetaChild]:
    #     if not shortnames:
    #         return {}
    #     table = self.get_table(class_type)
    #     items: dict[str, MetaChild] = {}
    #     async with self.get_session() as session:
    #         res = await session.execute(
    #             select(table).where(col(table.shortname).in_(shortnames))
    #         )
    #         rows = [r[0] for r in res.all()]
    #         for row in rows:
    #             model_obj = class_type.model_validate(row.model_dump())
    #             items[getattr(row, 'shortname')] = model_obj
    #     return items

    async def get_role_permissions(self, role: core.Role) -> list[core.Permission]:
        role_records = await self.load_or_none(
            settings.management_space, 'roles', role.shortname, core.Role
        )
        if role_records is None:
            return []
        role_permissions: list[core.Permission] = []
        for permission in role_records.permissions:
            permission_record = await self.load_or_none(
                settings.management_space, 'permissions', permission, core.Permission
            )
            if permission_record is None:
                continue
            role_permissions.append(permission_record)
        return role_permissions

    async def get_user_roles(self, user_shortname: str) -> dict[str, core.Role]:
        try:
            user = await self.load_or_none(
                settings.management_space, settings.users_subpath, user_shortname, core.User
            )
            if user is None:
                return {}
            euser_roles: dict[str, core.Role] = {}
            if user_shortname != "anonymous":
                role_record = await self.load_or_none(
                    settings.management_space, 'roles', 'logged_in', core.Role
                )
                if role_record is not None:
                    euser_roles['logged_in'] = role_record
            for role in user.roles:
                role_record = await self.load_or_none(
                    settings.management_space, 'roles', role, core.Role
                )
                if role_record is None:
                    continue
                euser_roles[role] = role_record
            return euser_roles
        except Exception as e2:
            print(f"Error: {e2}")
            return {}

    async def load_user_meta(self, user_shortname: str) -> Any:
        user = await self.load(
            space_name=settings.management_space,
            shortname=user_shortname,
            subpath="users",
            class_type=core.User,
            user_shortname=user_shortname,
        )

        return user

    async def generate_user_permissions(self, user_shortname: str) -> dict:
        user_permissions: dict = {}

        user_roles = await self.get_user_roles(user_shortname)

        for _, role in user_roles.items():
            role_permissions = await self.get_role_permissions(role)
            if user_shortname == "anonymous":
                permission_world_record = await self.load_or_none(settings.management_space, 'permissions', "world",
                                                                  core.Permission)
                if permission_world_record:
                    role_permissions.append(permission_world_record)

            for permission in role_permissions:
                for space_name, permission_subpaths in permission.subpaths.items():
                    for permission_subpath in permission_subpaths:
                        permission_subpath = trans_magic_words(permission_subpath, user_shortname)
                        for permission_resource_types in permission.resource_types:
                            actions = set(permission.actions)
                            conditions = set(permission.conditions)
                            if (
                                    f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                    in user_permissions
                            ):
                                old_perm = user_permissions[
                                    f"{space_name}:{permission_subpath}:{permission_resource_types}"
                                ]

                                if isinstance(actions, list):
                                    actions = set(actions)
                                actions |= set(old_perm["allowed_actions"])

                                if isinstance(conditions, list):
                                    conditions = set(conditions)
                                conditions |= set(old_perm["conditions"])

                            user_permissions[
                                f"{space_name}:{permission_subpath}:{permission_resource_types}"
                            ] = {
                                "allowed_actions": list(actions),
                                "conditions": list(conditions),
                                "restricted_fields": permission.restricted_fields,
                                "allowed_fields_values": permission.allowed_fields_values,
                                "filter_fields_values": permission.filter_fields_values
                            }
        return user_permissions

    async def get_user_permissions(self, user_shortname: str) -> dict:
        return await self.generate_user_permissions(user_shortname)

    async def get_user_by_criteria(self, key: str, value: str) -> str | None:
        _user = await self.get_entry_by_criteria(
            {key: value},
            Users
        )
        if _user is None:
            return None
        return str(_user.shortname)

    async def get_payload_from_event(self, event) -> dict:
        notification_request_meta = await self.load(
            event.space_name,
            event.subpath,
            event.shortname,
            getattr(sys_modules["models.core"], camel_case(event.resource_type)),
            event.user_shortname,
        )
        return notification_request_meta.payload.body  # type: ignore

    async def get_user_roles_from_groups(self, user_meta: core.User) -> list:
        return []

    async def drop_index(self, space_name):
        pass

    async def initialize_spaces(self) -> None:
        async with self.get_session() as session:
            try:
                (await session.execute(select(Spaces).limit(1))).one_or_none()
            except Exception as e:
                print(f"Error: {e}")
                try:
                    loop = asyncio.get_event_loop()
                    loop.stop()
                except RuntimeError as e:
                    print(f"Error: {e}")

    async def create_user_premission_index(self) -> None:
        pass

    async def store_modules_to_redis(self, roles, groups, permissions) -> None:
        pass

    async def delete_user_permissions_map_in_redis(self) -> None:
        pass

    async def internal_save_model(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            payload: dict | None = None
    ):
        await self.save(
            space_name=space_name,
            subpath=subpath,
            meta=meta,
        )

    async def internal_sys_update_model(
            self,
            space_name: str,
            subpath: str,
            meta: core.Meta,
            updates: dict,
            sync_redis: bool = True,
            payload_dict: dict[str, Any] = {},
    ):
        meta.updated_at = datetime.now()
        meta_updated = False
        payload_updated = False

        if not payload_dict:
            try:
                if meta.payload and isinstance(meta.payload.body, dict):
                    # Payload body is already loaded
                    payload_dict = meta.payload.body
                    
                elif meta.payload and isinstance(meta.payload.body, str):
                    # Payload body is the filename string
                    mydict = await self.load_resource_payload(
                        space_name, subpath, meta.payload.body, type(meta)
                    )
                    payload_dict = mydict if mydict else {}
            except Exception:
                pass

        restricted_fields = [
            "uuid",
            "shortname",
            "created_at",
            "updated_at",
            "owner_shortname",
            "payload",
        ]
        old_version_flattend = {**meta.model_dump()}
        for key, value in updates.items():
            if key in restricted_fields:
                continue

            if key in meta.model_fields.keys():
                meta_updated = True
                meta.__setattr__(key, value)
            elif payload_dict:
                payload_dict[key] = value
                payload_updated = True

        if meta_updated:
            await self.update(
                space_name,
                subpath,
                meta,
                old_version_flattend,
                {**meta.model_dump()},
                list(updates.keys()),
                meta.shortname
            )
        if payload_updated and meta.payload and meta.payload.schema_shortname:
            await self.validate_payload_with_schema(
                payload_dict, space_name, meta.payload.schema_shortname
            )
            await self.save_payload_from_json(
                space_name, subpath, meta, payload_dict
            )

    async def get_entry_by_var(
            self,
            key: str,
            val: str,
            logged_in_user,
            retrieve_json_payload: bool = False,
            retrieve_attachments: bool = False,
            retrieve_lock_status: bool = False,
    ) -> core.Record:
        _result = await self.get_entry_by_criteria({key: val})

        if _result is None:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="media", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"
                ),
            )

        from utils.access_control import access_control
        if not await access_control.check_access(
                user_shortname=logged_in_user,
                space_name=_result.attributes['space_name'],
                subpath=_result.subpath,
                resource_type=_result.resource_type,
                action_type=core.ActionType.view,
                resource_is_active=_result.attributes['is_active'],
                resource_owner_shortname=_result.attributes['owner_shortname'],
                resource_owner_group=_result.attributes['owner_group_shortname'],
                entry_shortname=_result.shortname
        ):
            raise api.Exception(
                status.HTTP_401_UNAUTHORIZED,
                api.Error(
                    type="request",
                    code=InternalErrorCode.NOT_ALLOWED,
                    message="You don't have permission to this action [42]",
                )
            )

        return _result

    async def delete_space(self, space_name, record, owner_shortname):
        resource_obj = core.Meta.from_record(
            record=record, owner_shortname=owner_shortname
        )
        await self.delete(space_name, record.subpath, resource_obj, owner_shortname)
        os.system(f"rm -r {settings.spaces_folder}/{space_name}")

    async def get_last_updated_entry(
            self,
            space_name: str,
            schema_names: list,
            retrieve_json_payload: bool,
            logged_in_user: str,
    ):
        pass

    async def get_group_users(self, group_name: str):
        async with self.get_session() as session:
            statement = select(Users.shortname).where(col(Users.groups).contains([group_name])) 
            result = await session.execute(statement)
            shortnames = result.scalars().all()
            return shortnames

    async def is_user_verified(self, user_shortname: str | None, identifier: str | None) -> bool:
        async with self.get_session() as session:
            statement = select(Users).where(Users.shortname == user_shortname)
            result = (await session.execute(statement)).one_or_none()

            if result is None:
                return False
            user = Users.model_validate(result[0])

            if identifier == "msisdn":
                return user.is_msisdn_verified
            if identifier == "email":
                return user.is_email_verified
            return False
