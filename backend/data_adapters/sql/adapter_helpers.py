import json
import re
import subprocess
from pathlib import Path

import models.api as api
import models.core as core
from models.enums import QueryType
from data_adapters.sql.create_tables import (
    Entries,
    Histories,
    Permissions,
    Roles,
    Users,
    Spaces,
    Aggregated
)
from utils.helpers import (
    str_to_datetime,
)
from utils.settings import settings

postgres_aggregate_functions = [
    "avg",
    "count",
    "max",
    "min",
    "sum",
    "array_agg",
    "string_agg",
    "bool_and",
    "bool_or",
    "bit_and",
    "bit_or",
    "every",
    "json_agg",
    "jsonb_agg",
    "json_object_agg",
    "jsonb_object_agg",
    "mode",
    "regr_avgx",
    "regr_avgy",
    "regr_count",
    "regr_intercept",
    "regr_r2",
    "regr_slope",
    "regr_sxx",
    "regr_sxy",
    "regr_syy",
    "corr",
    "covar_pop",
    "covar_samp",
    "stddev",
    "stddev_pop",
    "stddev_samp",
    "variance",
    "var_pop",
    "var_samp",
]

mysql_aggregate_functions = [
    "avg",
    "count",
    "max",
    "min",
    "sum",
    "group_concat",
    "json_arrayagg",
    "json_objectagg",
    "std",
    "stddev",
    "stddev_pop",
    "stddev_samp",
    "variance",
    "var_pop",
    "var_samp",
]

sqlite_aggregate_functions = [
    "avg",
    "count",
    "group_concat",
    "max",
    "min",
    "sum",
    "total",
]


def subpath_checker(subpath: str):
    if subpath.endswith("/"):
        subpath = subpath[:-1]
    if not subpath.startswith("/"):
        subpath = '/' + subpath
    return subpath


def transform_keys_to_sql(path):
    parts = path.split('.')
    sql_path = parts[0]
    if len(parts[1:-1]) != 0:
        sql_path += ' -> ' + ' -> '.join([f"'{part}'" for part in parts[1:-1]])
    sql_path += f" ->> '{parts[-1]}'"
    sql_path.replace("->  ->>", "->>")
    return sql_path


def validate_search_range(v_str):
    if isinstance(v_str, list):
        return False, v_str

    date_patterns = [
        # Year only: [2025 2024] or [2025,2024]
        r"^\[\d{4}[\s,]\d{4}\]$",
        # Year-month: [2025-04 2025-01] or [2025-04,2025-01]
        r"^\[\d{4}-\d{2}[\s,]\d{4}-\d{2}\]$",
        # Full date: [2025-04-28 2025-01-15] or [2025-04-28,2025-01-15]
        r"^\[\d{4}-\d{2}-\d{2}[\s,]\d{4}-\d{2}-\d{2}\]$",
        # Date with hours: [2025-04-28T12 2025-01-15T09] or [2025-04-28T12,2025-01-15T09]
        r"^\[\d{4}-\d{2}-\d{2}T\d{2}[\s,]\d{4}-\d{2}-\d{2}T\d{2}\]$",
        # Date with hours and minutes: [2025-04-28T12:30 2025-01-15T09:45] or [2025-04-28T12:30,2025-01-15T09:45]
        r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}[\s,]\d{4}-\d{2}-\d{2}T\d{2}:\d{2}\]$",
        # Date with hours, minutes, and seconds: [2025-04-28T12:30:45 2025-01-15T09:45:30] or [2025-04-28T12:30:45,2025-01-15T09:45:30]
        r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[\s,]\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\]$",
        # Full ISO format with microseconds: [2025-04-28T12:30:45.123456 2025-01-15T09:45:30.654321] or [2025-04-28T12:30:45.123456,2025-01-15T09:45:30.654321]
        r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+[\s,]\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+\]$",
    ]

    for pattern in date_patterns:
        if re.match(pattern, v_str):
            # Split on either space or comma
            if ',' in v_str[1:-1]:
                range_values = v_str[1:-1].split(',')
            else:
                range_values = v_str[1:-1].split()
            return True, range_values

    if re.match(r"^\[-?\d+(?:\.\d+)?[\s,]-?\d+(?:\.\d+)?\]$", v_str):
        if ',' in v_str[1:-1]:
            v_list = v_str[1:-1].split(',')
        else:
            v_list = v_str[1:-1].split()
        return True, v_list

    return False, v_str


def parse_search_array(input_string: str, key: str, value: str) -> str:
    parts = input_string.split("->")
    dict_key = parts[3].strip().replace("'", "").replace(">", "")
    if dict_key.startswith(' '):
        dict_key = dict_key[1:]
    output_sql = (
        f"payload::jsonb -> 'body' -> '{key}' "
        f"@> '[{{\"{dict_key}\": \"{value}\"}}]'"
    )
    return output_sql


def get_next_date_value(value, format_string):
    from datetime import datetime, timedelta
    if format_string == 'YYYY':
        year = int(value)
        return str(year + 1)
    elif format_string == 'YYYY-MM':
        year, month = map(int, value.split('-'))
        if month == 12:
            return f"{year + 1}-01"
        else:
            return f"{year}-{month + 1:02d}"
    elif format_string == 'YYYY-MM-DD':

        dt = datetime.strptime(value, '%Y-%m-%d')
        next_dt = dt + timedelta(days=1)
        return next_dt.strftime('%Y-%m-%d')
    elif format_string == 'YYYY-MM-DD"T"HH24':
        from datetime import datetime, timedelta
        dt = datetime.strptime(value, '%Y-%m-%dT%H')
        next_dt = dt + timedelta(hours=1)
        return next_dt.strftime('%Y-%m-%dT%H')
    elif format_string == 'YYYY-MM-DD"T"HH24:MI':
        from datetime import datetime, timedelta
        dt = datetime.strptime(value, '%Y-%m-%dT%H:%M')
        next_dt = dt + timedelta(minutes=1)
        return next_dt.strftime('%Y-%m-%dT%H:%M')
    elif format_string == 'YYYY-MM-DD"T"HH24:MI:SS':
        from datetime import datetime, timedelta
        dt = datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
        next_dt = dt + timedelta(seconds=1)
        return next_dt.strftime('%Y-%m-%dT%H:%M:%S')
    elif format_string == 'YYYY-MM-DD"T"HH24:MI:SS.US':
        from datetime import datetime, timedelta
        dt = datetime.strptime(value.split('.')[0], '%Y-%m-%dT%H:%M:%S')
        microseconds = int(value.split('.')[1])
        dt = dt.replace(microsecond=microseconds)
        next_dt = dt + timedelta(microseconds=1)
        return next_dt.strftime('%Y-%m-%dT%H:%M:%S.%f')

    return value



def is_date_time_value(value):
    patterns = [
        # Full ISO format with microseconds: 2025-04-28T12:28:00.660475
        (r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+$', 'YYYY-MM-DD"T"HH24:MI:SS.US'),
        # ISO format without microseconds: 2025-04-28T12:28:00
        (r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', 'YYYY-MM-DD"T"HH24:MI:SS'),
        # ISO format with minutes precision: 2025-04-28T12:28
        (r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$', 'YYYY-MM-DD"T"HH24:MI'),
        # ISO format with hours precision: 2025-04-28T12
        (r'^\d{4}-\d{2}-\d{2}T\d{2}$', 'YYYY-MM-DD"T"HH24'),
        # Date only: 2025-04-28
        (r'^\d{4}-\d{2}-\d{2}$', 'YYYY-MM-DD')
    ]

    for pattern, format_string in patterns:
        if re.match(pattern, value):
            return True, format_string

    return False, None


def parse_search_string(string):
    result = {}
    terms = string.split()

    for term in terms:
        negative = term.startswith('-@')

        if not (term.startswith('@') or term.startswith('-@')):
            continue

        parts = term.split(':', 1)
        if len(parts) != 2:
            continue

        field, value = parts
        field = field[2:] if negative else field[1:]

        is_range, range_values = validate_search_range(value)

        if is_range:
            value_type = 'string'
            format_strings = {}

            all_numeric = True
            for val in range_values:
                is_datetime, format_string = is_date_time_value(val)
                if is_datetime:
                    value_type = 'datetime'
                    format_strings[val] = format_string
                if not re.match(r'^-?\d+(?:\.\d+)?$', val):
                    all_numeric = False

            if value_type != 'datetime' and all_numeric:
                value_type = 'numeric'

            field_data = {
                'values': range_values,
                'operation': 'RANGE',
                'negative': negative,
                'is_range': True,
                'range_values': range_values,
                'value_type': value_type
            }

            if value_type == 'datetime':
                field_data['format_strings'] = format_strings

            result[field] = field_data
            continue

        values = value.split('|')
        operation = 'OR' if len(values) > 1 else 'AND'

        value_type = 'string'  # Default type 
        format_strings = {}
        all_boolean = True
        
        for i, val in enumerate(values):
            is_datetime, format_string = is_date_time_value(val)
            if is_datetime:
                value_type = 'datetime'
                format_strings[val] = format_string
                all_boolean = False
            elif val.lower() not in ['true', 'false']:
                all_boolean = False

        if all_boolean and value_type == 'string':
            value_type = 'boolean'

        if field not in result:
            field_data = {
                'values': values,
                'operation': operation,
                'negative': negative,
                'value_type': value_type,
            }

            if value_type == 'datetime':
                field_data['format_strings'] = format_strings

            result[field] = field_data
        else:
            if result[field]['negative'] != negative:
                field_data = {
                    'values': values,
                    'operation': operation,
                    'negative': negative
                }

                if value_type == 'datetime':
                    field_data['value_type'] = value_type
                    field_data['format_strings'] = format_strings

                result[field] = field_data
            else:
                result[field]['values'].extend(values)
                if operation == 'OR':
                    result[field]['operation'] = 'OR'

                if value_type == 'datetime':
                    result[field]['value_type'] = value_type
                    if 'format_strings' not in result[field]:
                        result[field]['format_strings'] = {}
                    result[field]['format_strings'].update(format_strings)
    return result


async def events_query(
        query: api.Query, user_shortname: str | None = None
) -> tuple[int, list[core.Record]]:
    from utils.access_control import access_control

    records: list[core.Record] = []
    total: int = 0

    path = Path(f"{settings.spaces_folder}/{query.space_name}/.dm/events.jsonl")
    if not path.is_file():
        return total, records

    result = []
    if query.search:
        p = subprocess.Popen(
            ["grep", f'"{query.search}"', path], stdout=subprocess.PIPE
        )
        p = subprocess.Popen(
            ["tail", "-n", f"{query.limit + query.offset}"],
            stdin=p.stdout,
            stdout=subprocess.PIPE,
        )
        p = subprocess.Popen(["tac"], stdin=p.stdout, stdout=subprocess.PIPE)
        if query.offset > 0:
            p = subprocess.Popen(
                ["sed", f"1,{query.offset}d"],
                stdin=p.stdout,
                stdout=subprocess.PIPE,
            )
        r, _ = p.communicate()
        result = list(filter(None, r.decode("utf-8").split("\n")))
    else:
        cmd = f"(tail -n {query.limit + query.offset} {path}; echo) | tac"
        if query.offset > 0:
            cmd += f" | sed '1,{query.offset}d'"
        result = list(
            filter(
                None,
                subprocess.run(
                    [cmd], capture_output=True, text=True, shell=True
                ).stdout.split("\n"),
            )
        )

    if query.search:
        p1 = subprocess.Popen(
            ["grep", f'"{query.search}"', path], stdout=subprocess.PIPE
        )
        p2 = subprocess.Popen(["wc", "-l"], stdin=p1.stdout, stdout=subprocess.PIPE)
        r, _ = p2.communicate()
        total = int(
            r.decode(),
            10,
        )
    else:
        total = int(
            subprocess.run(
                [f"wc -l < {path}"],
                capture_output=True,
                text=True,
                shell=True,
            ).stdout,
            10,
        )
    for line in result:
        action_obj = json.loads(line)
        if (
            query.from_date
            and str_to_datetime(action_obj["timestamp"]) < query.from_date
        ):
            continue

        if query.to_date and str_to_datetime(action_obj["timestamp"]) > query.to_date:
            break

        if not await access_control.check_access(
                user_shortname=str(user_shortname),
                space_name=query.space_name,
                subpath=action_obj.get(
                    "resource", {}).get("subpath", "/"),
                resource_type=action_obj["resource"]["type"],
                action_type=core.ActionType(action_obj["request"]),
        ):
            continue

        records.append(
            core.Record(
                resource_type=action_obj["resource"]["type"],
                shortname=action_obj["resource"]["shortname"],
                subpath=action_obj["resource"]["subpath"],
                attributes=action_obj,
            ),
        )

    return total, records


def set_results_from_aggregation(query, item, results, idx):
    extra = {}
    for key, value in item._mapping.items():
        if not hasattr(Aggregated, key):
            extra[key] = value

    results[idx] = Aggregated.model_validate(item).to_record(
        query.subpath,
        (
            str(getattr(item, "shortname"))
            if hasattr(item, "shortname") and isinstance(item.shortname, str)
            else "/"
        ),
        extra=extra,
    )

    return results


def set_table_for_query(query):
    if query.type is QueryType.spaces:
        return Spaces
    elif query.type is QueryType.history:
        return Histories
    elif query.space_name == "management":
        match query.subpath:
            case "/users":
                return Users
            case "/roles":
                return Roles
            case "/permissions":
                return Permissions
            case _:
                return Entries
    else:
        return Entries


def build_query_filter_for_allowed_field_values(perm_value) -> str:
    filters = []

    for k, v in perm_value.items():
        if isinstance(v, str):
            filters.append(f"@{k}:{v}")
        elif isinstance(v, list) and v:
            flat_values = []
            for item in v:
                if isinstance(item, list):
                    for sub in item:
                        if isinstance(sub, str) and sub:
                            flat_values.append(sub)
                elif isinstance(item, str) and item:
                    flat_values.append(item)
            if flat_values:
                seen_vals = set()
                uniq_flat_values = []
                for val in flat_values:
                    if val not in seen_vals:
                        seen_vals.add(val)
                        uniq_flat_values.append(val)
                values = "|".join(uniq_flat_values)
                filters.append(f"@{k}:{values}")

    return " ".join(filters)
