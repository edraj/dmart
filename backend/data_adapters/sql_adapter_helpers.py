import json
import re
import subprocess
from pathlib import Path

import models.api as api
import models.core as core
from models.enums import QueryType
from utils.database.create_tables import (
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
    sql_path += ' -> ' + ' -> '.join([f"'{part}'" for part in parts[1:-1]])
    sql_path += f" ->> '{parts[-1]}'"

    return sql_path


def validate_search_range(v_str):
    if isinstance(v_str, list):
        return False, v_str

    pattern = r"^\[\d+\s(\d+)*\]$"

    if re.match(pattern, v_str):
        v_list = list(map(int, v_str[1:-1].split()))
        return True, v_list
    else:
        return False, v_str


def parse_search_string(string, entity):
    list_criteria = string.split("@")
    list_criteria = [item.strip() for item in list_criteria if item.strip()]
    result = {}
    for s in list_criteria:
        if "[" in s and "]" in s:
            pattern = r"(\S+):(\S+ \S+)"
        else:
            pattern = r"(\S+):(\S+)"

        matches = re.findall(pattern, s)

        for key, value in matches:
            try:
                if "." in key:
                    if getattr(entity, key.split('.')[0]):
                        key = transform_keys_to_sql(key)
                        if "|" in value:
                            value = value.split("|")
                        result[key] = value
                elif getattr(entity, key):
                    if "|" in value:
                        value = value.split("|")
                    result[key] = value

            except Exception as e:
                print(f"Failed to parse search string: {s} cuz of {e}:{e.args}:{e.__dict__}")
                continue
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
