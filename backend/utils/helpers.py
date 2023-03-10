from copy import deepcopy
from re import sub as re_sub
from jsonschema import RefResolver
from collections.abc import MutableMapping
from models.enums import Language
from utils.settings import settings
from typing import Any


def flatten_dict(d: MutableMapping, parent_key: str = "", sep: str = ".") -> dict:
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, MutableMapping):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


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
        if type(list_of_dict) == list and len(list_of_dict) > 0 and type(list_of_dict[0]) == dict:
            flattened = {}
            for dict_item in list_of_dict:
                for key, value in dict_item.items():
                    flattened.setdefault(f"{parent_key}.{key}", [])
                    flattened[f"{parent_key}.{key}"].append(value)
            flattened_d.pop(parent_key)
            flattened_d.update(flattened)

    return flattened_d
    


def resolve_schema_references(schema: dict, refs: dict = {}):
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


def _resolve_schema_references(schema, resolver):
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


def divide_chunks(l, n):
    """
    Yield successive n-sized chunks from l.
    """

    # looping till length l
    for i in range(0, len(l), n):
        yield l[i : i + n]


def remove_none(target: dict | list):
    if isinstance(target, dict):
        new_d: dict = {}
        for key, val in target.items():
            if val == None:
                continue

            if isinstance(val, dict) or isinstance(val, list):
                new_d[key] = remove_none(val)
            else:
                new_d[key] = val

        return new_d
    else:
        new_l: list = []
        for val in target:
            if val == None:
                continue

            if isinstance(val, dict) or isinstance(val, list):
                new_l.append(remove_none(val))
            else:
                new_l.append(val)

        return new_l
            
        

def branch_path(branch_name: str | None = settings.default_branch):
    return (
        (f"branches/{branch_name}") if branch_name != settings.default_branch else "./"
    )


def json_flater(data: dict[str, Any]) -> dict[str, Any]:
    flatened_data = {}
    for k, v in data.items():
        if type(v) is dict:
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
        case Language.kd:
            return "kd"
        case Language.fr:
            return "fr"
        case Language.tr:
            return "tr"
