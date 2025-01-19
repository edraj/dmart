from copy import deepcopy
import csv
from datetime import datetime
import json
from pathlib import Path
from re import sub as re_sub
import aiofiles
from jsonschema.validators import _RefResolver as RefResolver  # type: ignore

# TBD from referencing import Registry, Resource
# TBD import referencing.jsonschema
from collections.abc import MutableMapping
from models.enums import Language
from typing import Any
from languages.loader import languages


def flatten_all(d: MutableMapping, parent_key: str = "", sep: str = ".") -> dict:
    items: list = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten_all(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            items.extend(flatten_all(flatten_list(v), new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def flatten_dict(d, parent_key='', sep='.'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def flatten_list(ll: list, key: str | None = None):
    flattened = {}
    for idx, item in enumerate(ll):
        flattened[f"{key}.{idx}" if key else f"{idx}"] = item
    return flattened


def arr_remove_common(arr1: list, arr2: list):
    for i1 in arr1[:]:
        if i1 in arr2:
            arr1.remove(i1)
            arr2.remove(i1)

    return arr1, arr2


def get_removed_items(arr1: list, arr2: list):
    removed_items = []

    for i1 in arr1:
        if i1 not in arr2:
            removed_items.append(i1)

    return removed_items


def flatten_list_of_dicts_in_dict(d: dict) -> dict:
    """
    example:
    d = {
        "key": [
            {
                'imsi': '12345',
                'name': 'Saad Adel'
            },
            {
                'imsi': '556566',
                'name': 'Saad Adel'
            }
        ],
        "another": "s",
        "another2": 222,
    }
    return {
        "key.imsi": ['12345', '556566'],
        "key.name": ['Saad Adel', 'Saad Adel'],
        "another": "s",
        "another2": 222,
    }
    """
    flattened_d = deepcopy(d)
    for parent_key, list_of_dict in d.items():
        if (
            isinstance(list_of_dict, list)
            and len(list_of_dict) > 0
            and isinstance(list_of_dict[0], dict)
        ):
            flattened: dict = {}
            for dict_item in list_of_dict:
                for key, value in dict_item.items():
                    flattened.setdefault(f"{parent_key}.{key}", [])
                    flattened[f"{parent_key}.{key}"].append(value)
            flattened_d.pop(parent_key)
            flattened_d.update(flattened)

    return flattened_d


def resolve_schema_references(schema: dict, refs: dict = {}) -> dict:
    """Resolves and replaces json-schema $refs with the appropriate dict.

    Recursively walks the given schema dict, converting every instance
    of $ref in a 'properties' structure with a resolved dict.

    This modifies the input schema and also returns it.

    Arguments:
        schema:
            the schema dict
        refs:
            a dict of <string, dict> which forms a store of referenced schemata

    Returns:
        schema
    """
    refs = refs or {}
    resolved_schema = _resolve_schema_references(
        schema, RefResolver("", schema, store=refs)
    )
    if "definitions" in resolved_schema:
        resolved_schema.pop("definitions")
    return resolved_schema


def _resolve_schema_references(schema: dict, resolver) -> dict:
    if "$ref" in schema:
        reference_path = schema.pop("$ref", None)
        resolved = resolver.resolve(reference_path)[1]
        schema.update(resolved)
        return _resolve_schema_references(schema, resolver)

    if "properties" in schema:
        for k, val in schema["properties"].items():
            schema["properties"][k] = _resolve_schema_references(val, resolver)

    if "patternProperties" in schema:
        for k, val in schema["patternProperties"].items():
            schema["patternProperties"][k] = _resolve_schema_references(val, resolver)

    if "items" in schema:
        schema["items"] = _resolve_schema_references(schema["items"], resolver)

    if "anyOf" in schema:
        for i, element in enumerate(schema["anyOf"]):
            schema["anyOf"][i] = _resolve_schema_references(element, resolver)

    if "oneOf" in schema:
        for i, element in enumerate(schema["oneOf"]):
            schema["oneOf"][i] = _resolve_schema_references(element, resolver)

    return schema


def camel_case(snake_str):
    words = snake_str.split("_")
    return "".join(word.title() for word in words)


def snake_case(camel_str):
    return re_sub(r"(?<!^)(?=[A-Z])", "_", camel_str).lower()


def divide_chunks(lll, n):
    """
    Yield successive n-sized chunks from lll.
    """

    # looping till length l
    for i in range(0, len(lll), n):
        yield lll[i : i + n]


def remove_none_dict(target: dict[str, Any] ) -> dict[str, Any]:
    new_d: dict = {}
    for key, val in target.items():
        if val is None:
            continue

        if isinstance(val, dict) : 
            new_d[key] = remove_none_dict(val)
        elif isinstance(val, list):
            new_d[key] = remove_none_list(val)
        else:
            new_d[key] = val

    return new_d

def remove_none_list(target: list):
    new_l: list = []
    for val in target:
        if val is None:
            continue

        if isinstance(val, dict) : 
            new_l.append(remove_none_dict(val))
        elif isinstance(val, list):
            new_l.append(remove_none_list(val))
        else:
            new_l.append(val)

    return new_l


def alter_dict_keys(
    target: dict,
    include: list | None = None,
    exclude: list | None = None,
    parents: str = "",
):
    result: dict = {}
    for k in list(target):
        search_for = f"{parents}.{k}" if parents else f"{k}"
        if isinstance(target[k], dict):
            if include and search_for in include:
                result[k] = target[k]
                continue
            if exclude and search_for in exclude:
                continue
            result[k] = alter_dict_keys(
                target[k], include, exclude, search_for if parents else f"{k}"
            )

        elif (include and search_for not in include) or (
            exclude and search_for in exclude
        ):
            continue

        else:
            result[k] = target[k]

    return result


def json_flater(data: dict[str, Any]) -> dict[str, Any]:
    flatened_data = {}
    for k, v in data.items():
        if isinstance(v, dict):
            __flatened_data = json_flater(v)
            _flatened_data = {
                key: val for key, val in __flatened_data.items()
            }  # deep copy to resolve the runtime error
            _keys = list(_flatened_data.keys())
            for key in _keys:
                flatened_data[f"{k}.{key}"] = _flatened_data[key]
                if k in flatened_data and key in flatened_data[k]:
                    del flatened_data[k][key]
        else:
            flatened_data = {**flatened_data, k: v}
    return flatened_data


def lang_code(lang: Language):
    match lang:
        case Language.ar:
            return "ar"
        case Language.en:
            return "en"
        case Language.ku:
            return "ku"
        case Language.fr:
            return "fr"
        case Language.tr:
            return "tr"


def replace_message_vars(message: str, dest_data: dict, locale: str):
    dest_data_dict = flatten_dict(dest_data)
    for field, value in dest_data_dict.items():
        if isinstance(value, dict) and locale in value:
            value = value[locale]
        if field in ["created_at", "updated_at"]:
            message = message.replace(
                f"{{{field}}}",
                datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S.%f").strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            )
        else:
            message = message.replace(
                f"{{{field}}}", languages[Language[locale]].get(str(value), str(value))
            )

    return re_sub(r"\{\w*.*\}", "", message)


def str_to_datetime(str: str, format: str = "%Y-%m-%dT%H:%M:%S.%f"):
    return datetime.strptime(str, format)


def pp(*args, **kwargs):
    """
    Pretty Print
    """
    print_str = "\n\n================== DUMP DATA ==================\n"
    if args:
        for arg in args:
            print_str += f"\n\narg: {arg}"

    if kwargs:
        for k, v in kwargs.items():
            print_str += f"\n\n{k}: {v}"

    print_str += "\n\n_____________________END________________________\n\n"
    print(print_str)


async def csv_file_to_json(csv_file_path: Path) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = []

    async with aiofiles.open(
        csv_file_path, mode="r", encoding="utf-8", newline=""
    ) as csvf:
        contents = await csvf.readlines()
        csvReader = csv.DictReader(contents)

        for row in csvReader:
            data.append(row)

    return data

def read_jsonl_file(file_path):
    data = []
    with open(file_path, 'r') as file:
        for line in file:
            data.append(json.loads(line))
    return data
