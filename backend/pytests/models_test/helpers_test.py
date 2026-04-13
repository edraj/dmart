"""Tests for utils/helpers.py — covers pure functions with zero external dependencies."""

import json
from datetime import datetime
from uuid import UUID

import pytest

from models.enums import Language
from utils.helpers import (
    alter_dict_keys,
    arr_remove_common,
    csv_file_to_json,
    divide_chunks,
    flatten_all,
    flatten_list,
    flatten_list_of_dicts_in_dict,
    jq_dict_parser,
    json_flater,
    lang_code,
    pp,
    process_jsonl_file,
    read_jsonl_file,
    remove_none_dict,
    remove_none_list,
    resolve_schema_references,
    str_to_datetime,
)


def test_flatten_all_nested_dict():
    result = flatten_all({"a": {"b": 1}, "c": 2})
    assert result == {"a.b": 1, "c": 2}


def test_flatten_all_with_list():
    result = flatten_all({"a": [10, 20]})
    assert result == {"a.0": 10, "a.1": 20}


def test_flatten_all_deeply_nested():
    result = flatten_all({"a": {"b": {"c": 3}}})
    assert result == {"a.b.c": 3}


def test_flatten_all_mixed():
    result = flatten_all({"x": {"y": [1, 2]}, "z": "val"})
    assert result == {"x.y.0": 1, "x.y.1": 2, "z": "val"}


def test_flatten_list_basic():
    result = flatten_list([10, 20, 30])
    assert result == {"0": 10, "1": 20, "2": 30}


def test_flatten_list_with_key():
    result = flatten_list([10, 20], key="items")
    assert result == {"items.0": 10, "items.1": 20}


def test_arr_remove_common():
    a, b = arr_remove_common([1, 2, 3], [2, 3, 4])
    assert a == [1]
    assert b == [4]


def test_arr_remove_common_no_overlap():
    a, b = arr_remove_common([1], [2])
    assert a == [1]
    assert b == [2]


def test_flatten_list_of_dicts_in_dict():
    d = {
        "key": [
            {"imsi": "12345", "name": "Alice"},
            {"imsi": "556", "name": "Bob"},
        ],
        "another": "s",
        "another2": 222,
    }
    result = flatten_list_of_dicts_in_dict(d)
    assert result == {
        "key.imsi": ["12345", "556"],
        "key.name": ["Alice", "Bob"],
        "another": "s",
        "another2": 222,
    }


def test_flatten_list_of_dicts_in_dict_no_list():
    d = {"a": "val", "b": 123}
    result = flatten_list_of_dicts_in_dict(d)
    assert result == d


def test_resolve_schema_references_with_ref():
    schema = {
        "definitions": {
            "Address": {"type": "object", "properties": {"street": {"type": "string"}}},
        },
        "type": "object",
        "properties": {
            "home": {"$ref": "#/definitions/Address"},
        },
    }
    result = resolve_schema_references(schema)
    assert "definitions" not in result
    assert result["properties"]["home"]["type"] == "object"
    assert "street" in result["properties"]["home"]["properties"]


def test_resolve_schema_references_with_items():
    schema = {
        "definitions": {
            "Item": {"type": "string"},
        },
        "type": "object",
        "properties": {
            "list": {
                "type": "array",
                "items": {"$ref": "#/definitions/Item"},
            },
        },
    }
    result = resolve_schema_references(schema)
    assert result["properties"]["list"]["items"]["type"] == "string"


def test_resolve_schema_references_with_anyof():
    schema = {
        "definitions": {"A": {"type": "string"}},
        "anyOf": [{"$ref": "#/definitions/A"}, {"type": "integer"}],
    }
    result = resolve_schema_references(schema)
    assert result["anyOf"][0]["type"] == "string"
    assert result["anyOf"][1]["type"] == "integer"


def test_resolve_schema_references_with_oneof():
    schema = {
        "definitions": {"B": {"type": "number"}},
        "oneOf": [{"$ref": "#/definitions/B"}],
    }
    result = resolve_schema_references(schema)
    assert result["oneOf"][0]["type"] == "number"


def test_resolve_schema_references_with_pattern_properties():
    schema = {
        "definitions": {"Val": {"type": "boolean"}},
        "patternProperties": {"^x-": {"$ref": "#/definitions/Val"}},
    }
    result = resolve_schema_references(schema)
    assert result["patternProperties"]["^x-"]["type"] == "boolean"


def test_divide_chunks():
    result = list(divide_chunks([1, 2, 3, 4, 5], 2))
    assert result == [[1, 2], [3, 4], [5]]


def test_divide_chunks_exact():
    result = list(divide_chunks([1, 2, 3, 4], 2))
    assert result == [[1, 2], [3, 4]]


def test_remove_none_dict():
    result = remove_none_dict({"a": None, "b": 1, "c": {"d": None, "e": 2}})
    assert result == {"b": 1, "c": {"e": 2}}


def test_remove_none_dict_with_list():
    result = remove_none_dict({"a": [None, 1, {"b": None, "c": 3}]})
    assert result == {"a": [1, {"c": 3}]}


def test_remove_none_list():
    result = remove_none_list([None, 1, {"a": None, "b": 2}, [None, 3]])
    assert result == [1, {"b": 2}, [3]]


def test_alter_dict_keys_include():
    target = {"a": 1, "b": 2, "c": 3}
    result = alter_dict_keys(target, include=["a", "c"])
    assert result == {"a": 1, "c": 3}


def test_alter_dict_keys_exclude():
    target = {"a": 1, "b": 2, "c": 3}
    result = alter_dict_keys(target, exclude=["b"])
    assert result == {"a": 1, "c": 3}


def test_alter_dict_keys_nested_include():
    target = {"a": {"x": 1, "y": 2}, "b": 3}
    result = alter_dict_keys(target, include=["a.x", "b"])
    assert result == {"a": {"x": 1}, "b": 3}


def test_alter_dict_keys_nested_exclude():
    target = {"a": {"x": 1, "y": 2}, "b": 3}
    result = alter_dict_keys(target, exclude=["a.y"])
    assert result == {"a": {"x": 1}, "b": 3}


def test_alter_dict_keys_include_whole_nested():
    target = {"a": {"x": 1, "y": 2}, "b": 3}
    result = alter_dict_keys(target, include=["a"])
    assert result == {"a": {"x": 1, "y": 2}}


def test_json_flater():
    result = json_flater({"a": {"b": {"c": 1}}, "d": 2})
    assert result == {"a.b.c": 1, "d": 2}


def test_json_flater_flat():
    result = json_flater({"x": 1, "y": 2})
    assert result == {"x": 1, "y": 2}


def test_lang_code():
    assert lang_code(Language.ar) == "ar"
    assert lang_code(Language.en) == "en"
    assert lang_code(Language.ku) == "ku"
    assert lang_code(Language.fr) == "fr"
    assert lang_code(Language.tr) == "tr"


def test_str_to_datetime():
    result = str_to_datetime("2024-01-15T10:30:00.123456")
    assert isinstance(result, datetime)
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15


def test_str_to_datetime_custom_format():
    result = str_to_datetime("2024-01-15", fmt="%Y-%m-%d")
    assert result.year == 2024


def test_pp(capsys):
    pp("hello", key="value")
    captured = capsys.readouterr()
    assert "hello" in captured.out
    assert "key: value" in captured.out
    assert "DUMP DATA" in captured.out


def test_pp_no_args(capsys):
    pp()
    captured = capsys.readouterr()
    assert "DUMP DATA" in captured.out


def test_jq_dict_parser_uuid():
    uid = UUID("12345678-1234-5678-1234-567812345678")
    result = jq_dict_parser({"id": uid, "name": "test"})
    assert result == {"id": "12345678-1234-5678-1234-567812345678", "name": "test"}


def test_jq_dict_parser_datetime():
    dt = datetime(2024, 1, 15, 10, 30)
    result = jq_dict_parser({"ts": dt})
    assert isinstance(result, dict)
    assert isinstance(result["ts"], str)
    assert "2024" in result["ts"]


def test_jq_dict_parser_nested():
    uid = UUID("12345678-1234-5678-1234-567812345678")
    raw = jq_dict_parser({"data": {"id": uid}, "items": [uid]})
    assert isinstance(raw, dict)
    assert isinstance(raw["data"], dict)
    assert isinstance(raw["items"], list)
    assert raw["data"]["id"] == str(uid)  # type: ignore[index]
    assert raw["items"][0] == str(uid)  # type: ignore[index]


def test_jq_dict_parser_primitives():
    assert jq_dict_parser(42) == 42
    assert jq_dict_parser("hello") == "hello"
    assert jq_dict_parser(None) is None


@pytest.mark.anyio
async def test_csv_file_to_json(tmp_path):
    csv_content = "name,age\nAlice,30\nBob,25\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)
    result = await csv_file_to_json(csv_file)
    assert len(result) == 2
    assert result[0]["name"] == "Alice"
    assert result[0]["age"] == "30"
    assert result[1]["name"] == "Bob"


@pytest.mark.anyio
async def test_read_jsonl_file(tmp_path):
    lines = [json.dumps({"a": 1}), json.dumps({"b": 2})]
    jsonl_file = tmp_path / "test.jsonl"
    jsonl_file.write_text("\n".join(lines) + "\n")
    result = await read_jsonl_file(jsonl_file)
    assert len(result) == 2
    assert result[0] == {"a": 1}
    assert result[1] == {"b": 2}


@pytest.mark.anyio
async def test_process_jsonl_file(tmp_path):
    lines = [json.dumps({"i": i}) for i in range(10)]
    jsonl_file = tmp_path / "test.jsonl"
    jsonl_file.write_text("\n".join(lines) + "\n")

    total, result = await process_jsonl_file(jsonl_file, limit=3, offset=0)
    assert total == 10
    assert len(result) == 3


@pytest.mark.anyio
async def test_process_jsonl_file_with_search(tmp_path):
    lines = [json.dumps({"name": "alice"}), json.dumps({"name": "bob"}), json.dumps({"name": "alice2"})]
    jsonl_file = tmp_path / "test.jsonl"
    jsonl_file.write_text("\n".join(lines) + "\n")

    total, result = await process_jsonl_file(jsonl_file, search="alice")
    assert total == 2
    assert len(result) == 2


@pytest.mark.anyio
async def test_process_jsonl_file_reverse(tmp_path):
    lines = [json.dumps({"i": i}) for i in range(5)]
    jsonl_file = tmp_path / "test.jsonl"
    jsonl_file.write_text("\n".join(lines) + "\n")

    total, result = await process_jsonl_file(jsonl_file, reverse=True, limit=2)
    assert total == 5
    first = json.loads(result[0])
    assert first["i"] == 4  # reversed, so last element first


@pytest.mark.anyio
async def test_process_jsonl_file_not_exists(tmp_path):
    total, result = await process_jsonl_file(tmp_path / "nonexistent.jsonl")
    assert total == 0
    assert result == []


@pytest.mark.anyio
async def test_process_jsonl_file_offset(tmp_path):
    lines = [json.dumps({"i": i}) for i in range(10)]
    jsonl_file = tmp_path / "test.jsonl"
    jsonl_file.write_text("\n".join(lines) + "\n")

    total, result = await process_jsonl_file(jsonl_file, offset=5, limit=3)
    assert total == 10
    assert len(result) == 3
    first = json.loads(result[0])
    assert first["i"] == 5
