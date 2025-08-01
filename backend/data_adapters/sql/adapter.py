import asyncio
import json
import os
import sys
import time
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
    get_next_date_value, is_date_time_value
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

    statement = select(
        *[
            getattr(table, ll.replace("@", ""))
            for ll in query.aggregation_data.load
        ]
    )

    if bool(query.aggregation_data.group_by):
        statement = statement.group_by(
            *[
                table.__dict__[column]
                for column in [
                    group_by.replace("@", "")
                    for group_by in query.aggregation_data.group_by
                ]
            ]
        )

    if bool(query.aggregation_data.reducers):
        for reducer in query.aggregation_data.reducers:
            if reducer.reducer_name in aggregate_functions:
                if len(reducer.args) == 0:
                    field = "*"
                else:
                    if not hasattr(table, reducer.args[0]):
                        continue

                    field = getattr(table, reducer.args[0])

                    if field is None:
                        continue

                    if isinstance(field.type, Integer) \
                            or isinstance(field.type, Boolean):
                        field = f"{field}::int"
                    elif isinstance(field.type, Float):
                        field = f"{field}::float"
                    else:
                        field = f"{field}::text"

                statement = select(
                    getattr(func, reducer.reducer_name)(text(field)).label(reducer.alias),
                    text(f"'{reducer.alias}' AS key")
                )

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


async def set_sql_statement_from_query(table, statement, query, is_for_count):
    try:
        if query.type == QueryType.attachments_aggregation and not is_for_count:
            return query_attachment_aggregation(query.subpath)

        if query.type == QueryType.aggregation and not is_for_count:
            statement = query_aggregation(table, query)

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
            statement = statement.where(
                or_(
                    table.subpath == query.subpath,
                    text(f"subpath ILIKE '{query.subpath}/%'".replace('//', '/'))
                )
            )
    if query.search:
        if not query.search.startswith("@") and not query.search.startswith("-"):
            statement = statement.where(text(
                f"(shortname || ' ' || tags || ' ' || displayname || ' ' || description || ' ' || payload) ILIKE '%' || '{query.search}' || '%'"
            ))
        else:
            search_tokens = parse_search_string(query.search, table)
            for field, field_data in search_tokens.items():
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
                    conditions = []
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
                                                dt1 = datetime.strptime(val1, fmt1.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d').replace('"T"HH24', 'T%H').replace('MI', '%M').replace('SS', '%S').replace('US', '%f'))
                                                dt2 = datetime.strptime(val2, fmt2.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d').replace('"T"HH24', 'T%H').replace('MI', '%M').replace('SS', '%S').replace('US', '%f'))
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
                                        string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND TO_TIMESTAMP(payload::jsonb->'body'->>{payload_path}, '{start_format}') NOT BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}') AND TO_TIMESTAMP('{end_value}', '{end_format}'))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND (payload::jsonb->'body'->>{payload_path})::text NOT BETWEEN '{start_value}' AND '{end_value}')"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                                    else:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND TO_TIMESTAMP(payload::jsonb->'body'->>{payload_path}, '{start_format}') BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}') AND TO_TIMESTAMP('{end_value}', '{end_format}'))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND (payload::jsonb->'body'->>{payload_path})::text BETWEEN '{start_value}' AND '{end_value}')"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                            else:
                                format_string = format_strings.get(value)
                                if format_string:
                                    next_value = get_next_date_value(value, format_string)

                                    if negative:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND (TO_TIMESTAMP(payload::jsonb->'body'->>{payload_path}, '{format_string}') < TO_TIMESTAMP('{value}', '{format_string}') OR TO_TIMESTAMP(payload::jsonb->'body'->>{payload_path}, '{format_string}') >= TO_TIMESTAMP('{next_value}', '{format_string}')))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND ((payload::jsonb->'body'->>{payload_path})::text < '{value}' OR (payload::jsonb->'body'->>{payload_path})::text >= '{next_value}'))"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                                    else:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND TO_TIMESTAMP(payload::jsonb->'body'->>{payload_path}, '{format_string}') >= TO_TIMESTAMP('{value}', '{format_string}') AND TO_TIMESTAMP(payload::jsonb->'body'->>{payload_path}, '{format_string}') < TO_TIMESTAMP('{next_value}', '{format_string}'))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND (payload::jsonb->'body'->>{payload_path})::text >= '{value}' AND (payload::jsonb->'body'->>{payload_path})::text < '{next_value}')"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                        elif value_type == 'numeric':
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
                                    number_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'number' AND (payload::jsonb->'body'->>{payload_path})::float NOT BETWEEN {val1} AND {val2})"
                                    string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND ((payload::jsonb->'body'->>{payload_path})::float NOT BETWEEN {val1} AND {val2}))"
                                    conditions.append(f"({number_condition} OR {string_condition})")
                                else:
                                    number_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'number' AND (payload::jsonb->'body'->>{payload_path})::float BETWEEN {val1} AND {val2})"
                                    string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND ((payload::jsonb->'body'->>{payload_path})::float BETWEEN {val1} AND {val2}))"
                                    conditions.append(f"({number_condition} OR {string_condition})")
                        elif value_type == 'boolean':
                            for value in values:
                                bool_value = value.lower()
                                if negative:
                                    bool_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'boolean' AND (payload::jsonb->'body'->>{payload_path})::boolean != {bool_value})"
                                    string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND (payload::jsonb->'body'->>{payload_path})::boolean != {bool_value})"
                                    conditions.append(f"({bool_condition} OR {string_condition})")
                                else:
                                    bool_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'boolean' AND (payload::jsonb->'body'->>{payload_path})::boolean = {bool_value})"
                                    string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND (payload::jsonb->'body'->>{payload_path})::boolean = {bool_value})"
                                    conditions.append(f"({bool_condition} OR {string_condition})")
                        else:
                            is_numeric = False
                            if value.isnumeric():
                                is_numeric = True

                            if negative:
                                array_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'array' AND NOT (payload::jsonb->'body'->{payload_path} @> '[\"{value}\"]'::jsonb))"
                                string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND payload::jsonb->'body'->>{payload_path} != '{value}')"
                                direct_condition = f"(payload::jsonb->'body'->{payload_path} != '\"{value}\"'::jsonb)"

                                if is_numeric:
                                    number_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'number' AND (payload::jsonb->'body'->>{payload_path})::float != {value})"
                                    conditions.append(f"({array_condition} OR {string_condition} OR {direct_condition} OR {number_condition})")
                                else:
                                    conditions.append(f"({array_condition} OR {string_condition} OR {direct_condition})")
                            else:
                                array_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'array' AND payload::jsonb->'body'->{payload_path} @> '[\"{value}\"]'::jsonb)"
                                payload_path_splited = payload_path.split('->')
                                if len(payload_path_splited) > 1:
                                    string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND payload::jsonb->'body'->>{'->'.join(payload_path_splited[:-1]) + '->>' + payload_path_splited[-1]} = '\"{value}\"')"
                                else:
                                    string_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'string' AND payload::jsonb->'body'->>{payload_path} = '{value}')"
                                direct_condition = f"(payload::jsonb->'body'->{payload_path} = '\"{value}\"'::jsonb)"

                                if is_numeric:
                                    number_condition = f"(jsonb_typeof(payload::jsonb->'body'->{payload_path}) = 'number' AND (payload::jsonb->'body'->>{payload_path})::float = {value})"
                                    conditions.append(f"({array_condition} OR {string_condition} OR {direct_condition} OR {number_condition})")
                                else:
                                    conditions.append(f"({array_condition} OR {string_condition} OR {direct_condition})")

                    if conditions:
                        if negative:
                            join_operator = " OR " if operation == 'AND' else " AND "
                        else:
                            join_operator = " AND " if operation == 'AND' else " OR "
                        statement = statement.where(text("(" + join_operator.join(conditions) + ")"))
                elif field.startswith('payload.'):
                    payload_field = field.replace('payload.', '')
                    payload_path = '->'.join([f"'{part}'" for part in payload_field.split('.')])

                    conditions = []
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
                                                dt1 = datetime.strptime(val1, fmt1.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d').replace('"T"HH24', 'T%H').replace('MI', '%M').replace('SS', '%S').replace('US', '%f'))
                                                dt2 = datetime.strptime(val2, fmt2.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d').replace('"T"HH24', 'T%H').replace('MI', '%M').replace('SS', '%S').replace('US', '%f'))
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
                                        string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND TO_TIMESTAMP(payload::jsonb->>{payload_path}, '{start_format}') NOT BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}') AND TO_TIMESTAMP('{end_value}', '{end_format}'))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND (payload::jsonb->>{payload_path})::text NOT BETWEEN '{start_value}' AND '{end_value}')"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                                    else:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND TO_TIMESTAMP(payload::jsonb->>{payload_path}, '{start_format}') BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}') AND TO_TIMESTAMP('{end_value}', '{end_format}'))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND (payload::jsonb->>{payload_path})::text BETWEEN '{start_value}' AND '{end_value}')"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                            else:
                                format_string = format_strings.get(value)
                                if format_string:
                                    next_value = get_next_date_value(value, format_string)

                                    if negative:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND (TO_TIMESTAMP(payload::jsonb->>{payload_path}, '{format_string}') < TO_TIMESTAMP('{value}', '{format_string}') OR TO_TIMESTAMP(payload::jsonb->>{payload_path}, '{format_string}') >= TO_TIMESTAMP('{next_value}', '{format_string}')))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND ((payload::jsonb->>{payload_path})::text < '{value}' OR (payload::jsonb->>{payload_path})::text >= '{next_value}'))"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                                    else:
                                        string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND TO_TIMESTAMP(payload::jsonb->>{payload_path}, '{format_string}') >= TO_TIMESTAMP('{value}', '{format_string}') AND TO_TIMESTAMP(payload::jsonb->>{payload_path}, '{format_string}') < TO_TIMESTAMP('{next_value}', '{format_string}'))"
                                        fallback_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND (payload::jsonb->>{payload_path})::text >= '{value}' AND (payload::jsonb->>{payload_path})::text < '{next_value}')"
                                        conditions.append(f"({string_condition} OR {fallback_condition})")
                        elif value_type == 'numeric':
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
                                    number_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'number' AND (payload::jsonb->>{payload_path})::float NOT BETWEEN {val1} AND {val2})"
                                    string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND ((payload::jsonb->>{payload_path})::float NOT BETWEEN {val1} AND {val2}))"
                                    conditions.append(f"({number_condition} OR {string_condition})")
                                else:
                                    number_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'number' AND (payload::jsonb->>{payload_path})::float BETWEEN {val1} AND {val2})"
                                    string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND ((payload::jsonb->>{payload_path})::float BETWEEN {val1} AND {val2}))"
                                    conditions.append(f"({number_condition} OR {string_condition})")
                        else:
                            is_numeric = False
                            try:
                                is_numeric = True
                            except ValueError:
                                pass

                            if negative:
                                array_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'array' AND NOT (payload::jsonb->{payload_path} @> '[\"{value}\"]'::jsonb))"
                                string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND payload::jsonb->>{payload_path} != '{value}')"
                                direct_condition = f"(payload::jsonb->{payload_path} != '\"{value}\"'::jsonb)"

                                if is_numeric:
                                    number_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'number' AND (payload::jsonb->>{payload_path})::float != {value})"
                                    conditions.append(f"({array_condition} OR {string_condition} OR {direct_condition} OR {number_condition})")
                                else:
                                    conditions.append(f"({array_condition} OR {string_condition} OR {direct_condition})")
                            else:
                                array_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'array' AND payload::jsonb->{payload_path} @> '[\"{value}\"]'::jsonb)"
                                string_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'string' AND payload::jsonb->>{payload_path} = '{value}')"
                                direct_condition = f"(payload::jsonb->{payload_path} = '\"{value}\"'::jsonb)"

                                if is_numeric:
                                    number_condition = f"(jsonb_typeof(payload::jsonb->{payload_path}) = 'number' AND (payload::jsonb->>{payload_path})::float = {value})"
                                    conditions.append(f"({array_condition} OR {string_condition} OR {direct_condition} OR {number_condition})")
                                else:
                                    conditions.append(f"({array_condition} OR {string_condition} OR {direct_condition})")

                    if conditions:
                        if negative:
                            join_operator = " OR " if operation == 'AND' else " AND "
                        else:
                            join_operator = " AND " if operation == 'AND' else " OR "
                        statement = statement.where(text("(" + join_operator.join(conditions) + ")"))
                elif field == 'roles':
                    conditions = []
                    for value in values:
                        if negative:
                            conditions.append(f"NOT (roles @> '[\"{value}\"]'::jsonb)")
                        else:
                            conditions.append(f"roles @> '[\"{value}\"]'::jsonb")

                    if conditions:
                        if negative:
                            join_operator = " OR " if operation == 'AND' else " AND "
                        else:
                            join_operator = " AND " if operation == 'AND' else " OR "
                        statement = statement.where(text("(" + join_operator.join(conditions) + ")"))
                elif field == 'owner_shortname':
                    if negative:
                        if operation == 'AND' and len(values) > 1:
                            conditions = []
                            for value in values:
                                conditions.append(f"owner_shortname != '{value}'")
                            statement = statement.where(text(" OR ".join(conditions)))
                        else:
                            if len(values) == 1:
                                statement = statement.where(table.owner_shortname != values[0])
                            else:
                                statement = statement.where(~col(table.owner_shortname).in_(values))
                    else:
                        if operation == 'AND' and len(values) > 1:
                            for value in values:
                                statement = statement.where(table.owner_shortname == value)
                        else:
                            if len(values) == 1:
                                statement = statement.where(table.owner_shortname == values[0])
                            else:
                                statement = statement.where(col(table.owner_shortname).in_(values))
                else:
                    try:
                        if hasattr(table, field):
                            if value_type == 'datetime':
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
                                                    dt1 = datetime.strptime(val1, fmt1.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d').replace('"T"HH24', 'T%H').replace('MI', '%M').replace('SS', '%S').replace('US', '%f'))
                                                    dt2 = datetime.strptime(val2, fmt2.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d').replace('"T"HH24', 'T%H').replace('MI', '%M').replace('SS', '%S').replace('US', '%f'))
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
                                            conditions.append(f"({field}::timestamp NOT BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}')::timestamp AND TO_TIMESTAMP('{end_value}', '{end_format}')::timestamp)")
                                        else:
                                            conditions.append(f"({field}::timestamp BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}')::timestamp AND TO_TIMESTAMP('{end_value}', '{end_format}')::timestamp)")
                                else:
                                    for value in values:
                                        format_string = format_strings.get(value)
                                        if format_string:
                                            next_value = get_next_date_value(value, format_string)

                                            if negative:
                                                conditions.append(f"({field}::timestamp < TO_TIMESTAMP('{value}', '{format_string}')::timestamp OR {field}::timestamp >= TO_TIMESTAMP('{next_value}', '{format_string}')::timestamp)")
                                            else:
                                                conditions.append(f"({field}::timestamp >= TO_TIMESTAMP('{value}', '{format_string}')::timestamp AND {field}::timestamp < TO_TIMESTAMP('{next_value}', '{format_string}')::timestamp)")

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

                                if conditions:
                                    if negative:
                                        join_operator = " OR " if operation == 'AND' else " AND "
                                    else:
                                        join_operator = " AND " if operation == 'AND' else " OR "

                                    statement = statement.where(text("(" + join_operator.join(conditions) + ")"))

                                    statement = statement.where(text(join_operator.join(conditions)))
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
                                is_timestamp = hasattr(field_obj, 'type') and str(field_obj.type).lower().startswith('timestamp')

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
                                    if negative:
                                        if operation == 'AND' and len(values) > 1:
                                            conditions = []
                                            for value in values:
                                                conditions.append(f"{field} != '{value}'")
                                            statement = statement.where(text(f'( {" OR ".join(conditions)} )'))
                                        else:
                                            if len(values) == 1:
                                                statement = statement.where(getattr(table, field) != values[0])
                                            else:
                                                statement = statement.where(~col(getattr(table, field)).in_(values))
                                    else:
                                        if operation == 'AND' and len(values) > 1:
                                            for value in values:
                                                statement = statement.where(getattr(table, field) == value)
                                        else:
                                            if len(values) == 1:
                                                statement = statement.where(getattr(table, field) == values[0])
                                            else:
                                                statement = statement.where(col(getattr(table, field)).in_(values))
                        else:
                            conditions = []
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
                                                        dt1 = datetime.strptime(val1, fmt1.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d').replace('"T"HH24', 'T%H').replace('MI', '%M').replace('SS', '%S').replace('US', '%f'))
                                                        dt2 = datetime.strptime(val2, fmt2.replace('YYYY', '%Y').replace('MM', '%m').replace('DD', '%d').replace('"T"HH24', 'T%H').replace('MI', '%M').replace('SS', '%S').replace('US', '%f'))
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
                                                conditions.append(f"(payload::jsonb->'{field}'::timestamp NOT BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}')::timestamp AND TO_TIMESTAMP('{end_value}', '{end_format}')::timestamp)")
                                            else:
                                                conditions.append(f"(payload::jsonb->'{field}'::timestamp BETWEEN TO_TIMESTAMP('{start_value}', '{start_format}')::timestamp AND TO_TIMESTAMP('{end_value}', '{end_format}')::timestamp)")
                                    else:
                                        format_string = format_strings.get(value)
                                        if format_string:
                                            next_value = get_next_date_value(value, format_string)

                                            if negative:
                                                conditions.append(f"(payload::jsonb->'{field}'::timestamp < TO_TIMESTAMP('{value}', '{format_string}')::timestamp OR payload::jsonb->'{field}'::timestamp >= TO_TIMESTAMP('{next_value}', '{format_string}')::timestamp)")
                                            else:
                                                conditions.append(f"(payload::jsonb->'{field}'::timestamp >= TO_TIMESTAMP('{value}', '{format_string}')::timestamp AND payload::jsonb->'{field}'::timestamp < TO_TIMESTAMP('{next_value}', '{format_string}')::timestamp)")
                                elif value_type == 'numeric':
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
                                            conditions.append(f"(jsonb_typeof(payload::jsonb->'{field}') = 'number' AND (payload::jsonb->'{field}')::float NOT BETWEEN {val1} AND {val2})")
                                        else:
                                            conditions.append(f"(jsonb_typeof(payload::jsonb->'{field}') = 'number' AND (payload::jsonb->'{field}')::float BETWEEN {val1} AND {val2})")
                                elif value_type == 'boolean':
                                    bool_value = value.lower()
                                    if negative:
                                        conditions.append(f"(jsonb_typeof(payload::jsonb->'{field}') = 'boolean' AND (payload::jsonb->'{field}')::boolean != {bool_value})")
                                    else:
                                        conditions.append(f"(jsonb_typeof(payload::jsonb->'{field}') = 'boolean' AND (payload::jsonb->'{field}')::boolean = {bool_value})")
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
                    sort_expression = transform_keys_to_sql(query.sort_by)
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

    return statement

class SQLAdapter(BaseDataAdapter):
    session: Session
    async_session: sessionmaker
    engine: Any

    def locators_query(self, query: api.Query) -> tuple[int, list[core.Locator]]:
        locators: list[core.Locator] = []
        total: int = 0
        match query.type:
            case api.QueryType.subpath:
                pass
                #!TODO finsih...
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
        async with self.get_session() as session:
            try:
                otp_entry = OTP(
                    key=key,
                    value={"otp": otp},
                    timestamp=datetime.now()
                )
                session.add(otp_entry)
                await session.commit()
            except Exception as e:
                if "UniqueViolationError" in str(e) or "unique constraint" in str(e).lower():
                    await session.rollback()
                    statement = delete(OTP).where(col(OTP.key) == key)
                    await session.execute(statement)
                    await session.commit()

                    otp_entry = OTP(
                        key=key,
                        value={"otp": otp},
                        timestamp=datetime.now()
                    )
                    session.add(otp_entry)
                    await session.commit()
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
                    await session.commit()
                    return None
                return otp_entry.value.get("otp")
            return None

    def metapath(self,
                 space_name: str,
                 subpath: str,
                 shortname: str,
                 class_type: Type[MetaChild],
                 schema_shortname: str | None = None,
                 ) -> tuple[Path, str]:
        return (Path(), "")


    def __init__(self):
        self.engine = create_async_engine(
            URL.create(
                drivername=settings.database_driver,
                host=settings.database_host,
                port=settings.database_port,
                username=settings.database_username,
                password=settings.database_password,
                database=settings.database_name,
            ),
            echo=False,
            max_overflow=settings.database_max_overflow,
            pool_size=settings.database_pool_size,
            pool_pre_ping=True,
        )
        try:
            self.async_session = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            ) # type: ignore
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
        finally:
            await async_session.close() # type: ignore


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

    def get_base_model(self, class_type : Type[MetaChild], data, update=None) -> Roles | Permissions | Users | Spaces | Locks | Attachments | Entries:
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
                    "subpath": "/".join(attachment_json["subpath"].split("/")[:-1])#join(),
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

        async with self.get_session() as session:
            table = self.get_table(class_type)

            statement = select(table).where(table.space_name == space_name)
            statement = statement.where(table.shortname == shortname)

            if table in [Entries, Attachments]:
                statement = statement.where(table.subpath == subpath)

            _result = (await session.execute(statement)).one_or_none()
            if _result is None:
                return None
            result : Attachments | Entries | Locks | Permissions | Roles | Spaces | Users | None = _result[0]
            try:
                return result
            except Exception as e:
                print("[!load_or_none]", e)
                logger.error(f"Failed parsing an entry. Error: {e}")
                return None

    async def get_entry_by_criteria(self, criteria: dict, table: Any = None) -> list[core.Record] | None:
        async with self.get_session() as session:
            results: list[core.Record] = []
            if table is None:
                tables = [Entries, Users, Roles, Permissions, Spaces, Attachments]
                for _table in tables:
                    statement = select(_table)
                    for k, v in criteria.items():
                        if isinstance(v, str):
                            statement = statement.where(
                                text(f"{k}::text LIKE :{k}")
                            ).params({k: f"{v}%"})
                        else:
                            statement = statement.where(text(f"{k}=:{k}")).params({k: v})
                        _results = (await session.execute(statement)).all()
                        _results = [result[0] for result in _results]
                        if len(_results) > 0:
                            for result in _results:
                                core_model_class : core.Meta = getattr(sys.modules["models.core"], camel_case(result.resource_type))
                                results.append(
                                    core_model_class.model_validate(
                                        result.model_dump()
                                    ).to_record(result.subpath, result.shortname)
                               )

                            return results
                return None
            else:
                statement = select(table)
                for k, v in criteria.items():
                    if isinstance(v, str):
                        statement = statement.where(
                            text(f"{k}::text=:{k}")
                        ).params({k: f"{v}"})
                    else:
                        statement = statement.where(text(f"{k}=:{k}")).params({k: v})

                    _results = (await session.execute(statement)).all()
                    _results = [result[0] for result in _results]
                    if len(_results) > 0:
                        for result in _results:
                            _core_model_class: core.Meta = getattr(sys.modules["models.core"],
                                                                   camel_case(result.resource_type))
                            results.append(
                                _core_model_class.model_validate(
                                    result.model_dump()
                                ).to_record(result.subpath, result.shortname)
                            )
                        return results
                return None

    async def query(
        self, query: api.Query, user_shortname: str | None = None
    ) -> Tuple[int, list[core.Record]]:
        total : int
        results : list
        async with self.get_session() as session:
            user_shortname = user_shortname if user_shortname else "anonymous"
            user_query_policies = await get_user_query_policies(
                self, user_shortname, query.space_name, query.subpath
            )
            if not query.exact_subpath:
                r = await get_user_query_policies(
                    self, user_shortname, query.space_name, f'{query.subpath}/%'
                )
                user_query_policies.extend(r)
            if not query.subpath.startswith("/"):
                query.subpath = f"/{query.subpath}"

            if query.type in [QueryType.attachments, QueryType.attachments_aggregation]:
                table = Attachments
                statement = select(table).options(defer(table.media)) # type: ignore
            else:
                table = set_table_for_query(query)
                statement = select(table)

            statement_total = select(func.count(col(table.uuid)))

            if table not in [Attachments, Histories] and user_query_policies and hasattr(table, 'query_policies'):
                statement = statement.where(
                    text("EXISTS (SELECT 1 FROM unnest(query_policies) AS qp WHERE qp ILIKE ANY (:query_policies))")
                ).params(
                    query_policies=[user_query_policy.replace('*', '%') for user_query_policy in user_query_policies]
                )

                statement_total = statement_total.where(
                    text("EXISTS (SELECT 1 FROM unnest(query_policies) AS qp WHERE qp ILIKE ANY (:query_policies))")
                ).params(
                    query_policies=[user_query_policy.replace('*', '%') for user_query_policy in user_query_policies]
                )

            if query and query.type == QueryType.events:
                try:
                    return await events_query(query, user_shortname)
                except Exception as e:
                    print(e)
                    return 0, []
            is_fetching_spaces = False
            if (query.space_name
                    and query.type == QueryType.spaces
                    and query.space_name == "management"
                    and query.subpath == "/"):
                is_fetching_spaces = True
                statement = select(Spaces) # type: ignore
                statement_total = select(func.count(col(Spaces.uuid)))
            else:
                statement = await set_sql_statement_from_query(table, statement, query, False)
                statement_total = await set_sql_statement_from_query(table, statement_total, query, True)

                # if query_allowed_fields_values:
                #     for query_allowed_fields_value in query_allowed_fields_values:
                #         statement = statement.where(text(query_allowed_fields_value))
                #         statement_total = statement_total.where(text(query_allowed_fields_value))

            try:
                if query.type == QueryType.aggregation and query.aggregation_data and bool(query.aggregation_data.group_by):
                    statement_total = select(
                        func.sum(statement_total.c["count"]).label('total_count')
                    )


                _total = (await session.execute(statement_total)).one()

                total = int(_total[0])
                if query.type == QueryType.counters:
                    return total, []

                # TODO EFFECIVENESS
                # if not query.retrieve_json_payload:
                #     cols = list(table.model_fields.keys())
                #     cols = [getattr(table, xcol) for xcol in cols if xcol not in ["payload", "media"]]
                #     statement = statement.options(load_only(*cols))

                results = list((await session.execute(statement)).all())
                if query.type == QueryType.attachments_aggregation:
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
                if query.type != QueryType.aggregation:
                    results = [result[0] for result in results]
                if is_fetching_spaces:
                    from utils.access_control import access_control
                    results = [result for result in results if await access_control.check_space_access(
                        user_shortname if user_shortname else "anonymous", result.shortname
                    )]
                if len(results) == 0:
                    return 0, []

                results = await self._set_query_final_results(query, results)

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

    async def load_or_none(
            self,
            space_name: str,
            subpath: str,
            shortname: str,
            class_type: Type[MetaChild],
            user_shortname: str | None = None,
            schema_shortname: str | None = None,
    ) -> MetaChild | None:

        result = await self.db_load_or_none(space_name, subpath, shortname, class_type, user_shortname,schema_shortname)
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
        meta: MetaChild | None = await self.load_or_none(space_name, subpath, shortname, class_type, user_shortname, schema_shortname)
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
            var : dict = result.model_dump().get("payload", {}).get("body", {})
            return var

    async def save(
            self, space_name: str, subpath: str, meta: core.Meta
    ) -> Any:
        """Save"""
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
        async with self.get_session() as session:
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
                result.sqlmodel_update(meta.model_dump())

                session.add(result)
                await session.commit()
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
        async with self.get_session() as session:
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

                session.add(result)
                await session.commit()
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
        async with self.get_session() as session:
            try:
                diff_keys = list(old_version_flattend.keys())
                diff_keys.extend(list(new_version_flattend.keys()))
                history_diff = {}
                for key in set(diff_keys):
                    if key in ["updated_at"]:
                        continue
                    # if key in updated_attributes_flattend:
                    old = copy(old_version_flattend.get(key, "null"))
                    new = copy(new_version_flattend.get(key, "null"))

                    if old != new:
                        if isinstance(old, list) and isinstance(new, list):
                            old, new = arr_remove_common(old, new)

                        removed = get_removed_items(list(old_version_flattend.keys()), list(new_version_flattend.keys()))

                        history_diff[key] = {
                            "old": old,
                            "new": new,
                        }
                        for r in removed:
                            history_diff[r] = {
                                "old": old_version_flattend[r],
                                "new": None,
                            }
                if not history_diff:
                    return {}

                history_obj = Histories(
                    space_name=space_name,
                    uuid=uuid4(),
                    shortname=shortname,
                    owner_shortname=owner_shortname or "__system__",
                    timestamp=datetime.now(),
                    request_headers=get_request_data().get("request_headers", {}),
                    diff=history_diff,
                    subpath=subpath,
                )

                session.add(Histories.model_validate(history_obj))
                await session.commit()

                return history_diff
            except Exception as e:
                print("[!store_entry_diff]", e)
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
        if isinstance(origin,  Locks):
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
                    resource_type=origin.resource_type if hasattr(origin, 'resource_type') else origin.__class__.__name__.lower()[:-1],
                    is_active=origin.is_active if hasattr(origin, 'is_active') else True,
                    owner_shortname=origin.owner_shortname,
                    owner_group_shortname=None,
                )

                session.add(origin)
                await session.commit()
                try:
                    if table is Spaces:
                        session.add(
                            update(Spaces)
                            .where(col(Spaces.space_name) == dest_space_name)
                            .values(space_name=dest_shortname))
                        session.add(
                            update(Entries)
                            .where(col(Entries.space_name) == dest_space_name)
                            .values(space_name=dest_shortname))
                        session.add(
                            update(Attachments)
                            .where(col(Attachments.space_name) == dest_space_name)
                            .values(space_name=dest_shortname))
                        await session.commit()
                except Exception as e:
                    origin.shortname = old_shortname
                    if hasattr(origin, 'subpath'):
                        origin.subpath = old_subpath

                    session.add(origin)
                    await session.commit()

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
        async with self.get_session() as session:
            try:
                if not subpath.startswith("/"):
                    subpath = f"/{subpath}"

                result = await self.db_load_or_none(space_name, subpath, meta.shortname, meta.__class__)
                await session.delete(result)
                if meta.__class__ == core.Space:
                    statement2 = delete(Attachments).where(col(Attachments.space_name) == space_name)
                    await session.execute(statement2)
                    statement = delete(Entries).where(col(Entries.space_name) == space_name)
                    await session.execute(statement)
                await session.commit()
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

    async def lock_handler(self, space_name: str, subpath: str, shortname: str, user_shortname: str, action: LockAction) -> dict | None:
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
            print("[!fetch_space]", e)
            return None

    async def set_user_session(self, user_shortname: str, token: str) -> bool:
        async with (self.get_session() as session):
            try:
                total, last_session = await self.get_user_session(user_shortname, token)

                if (settings.max_sessions_per_user == 1 and last_session is not None) \
                    or (settings.max_sessions_per_user != 0 and total >= settings.max_sessions_per_user):
                    await self.remove_user_session(user_shortname)

                timestamp = datetime.now()
                session.add(
                    Sessions(
                        uuid=uuid4(),
                        shortname=user_shortname,
                        token=hash_password(token),
                        timestamp=timestamp,
                    )
                )
                await session.commit()

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
                else:
                    await session.execute(delete(Sessions).where(col(Sessions.uuid) == r.uuid))
        return len(results), None


    async def remove_user_session(self, user_shortname: str) -> bool:
        async with self.get_session() as session:
            try:
                statement = select(Sessions).where(col(Sessions.shortname) == user_shortname).order_by(
                    col(Sessions.timestamp).desc()
                ).offset(settings.max_sessions_per_user-1)
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
                await session.commit()
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
                await session.commit()
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
                await session.commit()
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
                await session.commit()
                return True
            except Exception as e:
                print("[!remove_sql_user_session]", e)
                return False

    async def delete_url_shortner_by_token(self, invitation_token: str) -> bool:
        async with self.get_session() as session:
            try:
                statement = delete(URLShorts).where(col(URLShorts.url).ilike(f"%{invitation_token}%"))
                await session.execute(statement)
                await session.commit()
                return True
            except Exception as e:
                print("[!delete_url_shortner_by_token]", e)
                return False

    async def _set_query_final_results(self, query, results):
        is_aggregation = query.type == QueryType.aggregation
        not_history_event = query.type not in [QueryType.history, QueryType.events]

        if query.type == QueryType.attachments:
            for idx, item in enumerate(results):
                results[idx] = item.to_record(
                    results[idx].subpath, item.shortname
                )
        else:
            for idx, item in enumerate(results):
                if is_aggregation:
                    results = set_results_from_aggregation(
                        query, item, results, idx
                    )
                else:
                    results[idx] = item.to_record(
                        item.subpath, item.shortname
                    )

                if not_history_event:
                    if not query.retrieve_json_payload:
                        attrb = results[idx].attributes
                        if (
                            attrb
                            and attrb.get("payload", {})
                            and attrb.get("payload", {}).get("body", False)
                        ):
                            attrb["payload"]["body"] = None

                    if query.retrieve_attachments:
                        results[idx].attachments = await self.get_entry_attachments(
                            results[idx].subpath,
                            Path(f"{query.space_name}/{results[idx].shortname}"),
                            retrieve_json_payload=True,
                        )

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
                await session.commit()
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
                await session.commit()
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
                if current_user is not None and hasattr(current_user,composite_unique_key) \
                        and getattr(current_user,composite_unique_key) == value:
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

            user_roles: dict[str, core.Role] = {}
            for role in user.roles:
                role_record = await self.load_or_none(
                    settings.management_space, 'roles', role, core.Role
                )
                if role_record is None:
                    continue

                user_roles[role] = role_record
            return user_roles
        except Exception as e:
            print(f"Error: {e}")
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
                                "allowed_fields_values": permission.allowed_fields_values
                            }
        return user_permissions

    async def get_user_permissions(self, user_shortname: str) -> dict:
        return await self.generate_user_permissions(user_shortname)

    async def get_user_by_criteria(self, key: str, value: str) -> str | None:
        _user = await self.get_entry_by_criteria(
            {key: value},
            Users
        )
        if _user is None or len(_user) == 0:
            return None
        return str(_user[0].shortname)

    async def get_payload_from_event(self, event) -> dict:
        notification_request_meta = await self.load(
            event.space_name,
            event.subpath,
            event.shortname,
            getattr(sys_modules["models.core"], camel_case(event.resource_type)),
            event.user_shortname,
        )
        return notification_request_meta.payload.body # type: ignore

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
                body = str(meta.payload.body) if meta and meta.payload else ""
                mydict = await self.load_resource_payload(
                    space_name, subpath, body, core.Content
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

        if _result is None or len(_result) == 0:
            raise api.Exception(
                status.HTTP_400_BAD_REQUEST,
                error=api.Error(
                    type="media", code=InternalErrorCode.OBJECT_NOT_FOUND, message="Request object is not available"
                ),
            )

        return _result[0]

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
        return []

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
