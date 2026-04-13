"""Tests for data_adapters/sql/adapter_helpers.py — covers pure functions."""

import pytest

from data_adapters.sql.adapter_helpers import (
    _sanitize_sql_part,
    build_query_filter_for_allowed_field_values,
    get_next_date_value,
    is_date_time_value,
    parse_search_array,
    parse_search_expression,
    parse_search_string,
    set_table_for_query,
    subpath_checker,
    transform_keys_to_sql,
    validate_search_range,
)
from data_adapters.sql.create_tables import Entries, Histories, Permissions, Roles, Spaces, Users
from models.enums import QueryType


# --- subpath_checker ---


def test_subpath_checker_trailing_slash():
    assert subpath_checker("/test/") == "/test"


def test_subpath_checker_missing_leading_slash():
    assert subpath_checker("test") == "/test"


def test_subpath_checker_normal():
    assert subpath_checker("/test") == "/test"


# --- _sanitize_sql_part ---


def test_sanitize_sql_part_valid():
    assert _sanitize_sql_part("valid_name") == "valid_name"
    assert _sanitize_sql_part("field123") == "field123"


def test_sanitize_sql_part_wildcard():
    assert _sanitize_sql_part("*") == "*"


def test_sanitize_sql_part_injection():
    with pytest.raises(ValueError, match="Invalid field name part"):
        _sanitize_sql_part("DROP TABLE;")

    with pytest.raises(ValueError, match="Invalid field name part"):
        _sanitize_sql_part("field' OR '1'='1")


# --- transform_keys_to_sql ---


def test_transform_keys_simple_two_parts():
    result = transform_keys_to_sql("payload.name")
    assert result == "payload ->> 'name'"


def test_transform_keys_three_parts():
    result = transform_keys_to_sql("payload.body.name")
    assert result == "payload -> 'body' ->> 'name'"


def test_transform_keys_single_part():
    result = transform_keys_to_sql("shortname")
    # single part: just the name with ->> to itself
    assert "->>  'shortname'" in result or result == "shortname ->> 'shortname'"


def test_transform_keys_wildcard_at_start():
    result = transform_keys_to_sql("*.field")
    assert result == "payload::text"


def test_transform_keys_wildcard_in_middle():
    result = transform_keys_to_sql("payload.body.*.field")
    assert "payload -> 'body'" in result
    assert "::text" in result


def test_transform_keys_wildcard_after_root():
    result = transform_keys_to_sql("payload.*")
    assert result == "(payload)::text"


# --- validate_search_range ---


def test_validate_search_range_list_input():
    is_range, val = validate_search_range(["a", "b"])
    assert is_range is False
    assert val == ["a", "b"]


def test_validate_search_range_date_year():
    is_range, val = validate_search_range("[2024 2025]")
    assert is_range is True
    assert val == ["2024", "2025"]


def test_validate_search_range_date_full():
    is_range, val = validate_search_range("[2024-01-01 2024-12-31]")
    assert is_range is True
    assert val == ["2024-01-01", "2024-12-31"]


def test_validate_search_range_date_comma():
    is_range, val = validate_search_range("[2024,2025]")
    assert is_range is True
    assert val == ["2024", "2025"]


def test_validate_search_range_numeric():
    is_range, val = validate_search_range("[10 20]")
    assert is_range is True
    assert val == ["10", "20"]


def test_validate_search_range_numeric_negative():
    is_range, val = validate_search_range("[-5 10]")
    assert is_range is True
    assert val == ["-5", "10"]


def test_validate_search_range_float():
    is_range, val = validate_search_range("[1.5 2.5]")
    assert is_range is True
    assert val == ["1.5", "2.5"]


def test_validate_search_range_not_range():
    is_range, val = validate_search_range("hello")
    assert is_range is False
    assert val == "hello"


def test_validate_search_range_year_month():
    is_range, val = validate_search_range("[2025-04 2025-01]")
    assert is_range is True
    assert val == ["2025-04", "2025-01"]


def test_validate_search_range_datetime_with_hours():
    is_range, val = validate_search_range("[2025-04-28T12 2025-01-15T09]")
    assert is_range is True
    assert val == ["2025-04-28T12", "2025-01-15T09"]


def test_validate_search_range_datetime_with_minutes():
    is_range, val = validate_search_range("[2025-04-28T12:30 2025-01-15T09:45]")
    assert is_range is True


def test_validate_search_range_datetime_with_seconds():
    is_range, val = validate_search_range("[2025-04-28T12:30:45 2025-01-15T09:45:30]")
    assert is_range is True


def test_validate_search_range_datetime_with_microseconds():
    is_range, val = validate_search_range("[2025-04-28T12:30:45.123456 2025-01-15T09:45:30.654321]")
    assert is_range is True


# --- parse_search_array ---


def test_parse_search_array():
    input_string = "payload -> 'body' -> 'items' ->> 'name'"
    result = parse_search_array(input_string, "items", "testval")
    assert "@>" in result
    assert "items" in result
    assert "testval" in result


# --- get_next_date_value ---


def test_get_next_date_value_year():
    assert get_next_date_value("2025", "YYYY") == "2026"


def test_get_next_date_value_year_month():
    assert get_next_date_value("2025-04", "YYYY-MM") == "2025-05"


def test_get_next_date_value_year_month_december():
    assert get_next_date_value("2025-12", "YYYY-MM") == "2026-01"


def test_get_next_date_value_date():
    assert get_next_date_value("2025-04-28", "YYYY-MM-DD") == "2025-04-29"


def test_get_next_date_value_hour():
    assert get_next_date_value("2025-04-28T12", 'YYYY-MM-DD"T"HH24') == "2025-04-28T13"


def test_get_next_date_value_minute():
    assert get_next_date_value("2025-04-28T12:30", 'YYYY-MM-DD"T"HH24:MI') == "2025-04-28T12:31"


def test_get_next_date_value_second():
    assert get_next_date_value("2025-04-28T12:30:45", 'YYYY-MM-DD"T"HH24:MI:SS') == "2025-04-28T12:30:46"


def test_get_next_date_value_microsecond():
    result = get_next_date_value("2025-04-28T12:30:45.000001", 'YYYY-MM-DD"T"HH24:MI:SS.US')
    assert result == "2025-04-28T12:30:45.000002"


def test_get_next_date_value_unknown_format():
    assert get_next_date_value("whatever", "UNKNOWN") == "whatever"


# --- is_date_time_value ---


def test_is_date_time_value_full_iso():
    is_dt, fmt = is_date_time_value("2025-04-28T12:28:00.660475")
    assert is_dt is True
    assert fmt == 'YYYY-MM-DD"T"HH24:MI:SS.US'


def test_is_date_time_value_no_microseconds():
    is_dt, fmt = is_date_time_value("2025-04-28T12:28:00")
    assert is_dt is True
    assert fmt == 'YYYY-MM-DD"T"HH24:MI:SS'


def test_is_date_time_value_minutes():
    is_dt, fmt = is_date_time_value("2025-04-28T12:28")
    assert is_dt is True
    assert fmt == 'YYYY-MM-DD"T"HH24:MI'


def test_is_date_time_value_hours():
    is_dt, fmt = is_date_time_value("2025-04-28T12")
    assert is_dt is True
    assert fmt == 'YYYY-MM-DD"T"HH24'


def test_is_date_time_value_date_only():
    is_dt, fmt = is_date_time_value("2025-04-28")
    assert is_dt is True
    assert fmt == "YYYY-MM-DD"


def test_is_date_time_value_not_date():
    is_dt, fmt = is_date_time_value("hello")
    assert is_dt is False
    assert fmt is None


# --- parse_search_string ---


def test_parse_search_string_simple():
    result = parse_search_string("@field:value")
    assert "field" in result
    assert result["field"]["values"] == ["value"]
    assert result["field"]["operation"] == "AND"
    assert result["field"]["negative"] is False


def test_parse_search_string_or():
    result = parse_search_string("@status:active|pending")
    assert result["status"]["values"] == ["active", "pending"]
    assert result["status"]["operation"] == "OR"


def test_parse_search_string_negative():
    result = parse_search_string("-@field:value")
    assert result["field"]["negative"] is True


def test_parse_search_string_comparison():
    result = parse_search_string("@age:>25")
    assert result["age"]["comparison_operator"] == ">"
    assert result["age"]["values"] == ["25"]


def test_parse_search_string_comparison_gte():
    result = parse_search_string("@price:>=100")
    assert result["price"]["comparison_operator"] == ">="
    assert result["price"]["values"] == ["100"]


def test_parse_search_string_negation_operator():
    result = parse_search_string("@status:!active")
    assert result["status"]["comparison_operator"] == "!"
    assert result["status"]["values"] == ["active"]


def test_parse_search_string_range():
    # Ranges must use comma separator since the parser splits on spaces first
    result = parse_search_string("@score:[10,20]")
    assert result["score"]["is_range"] is True
    assert result["score"]["range_values"] == ["10", "20"]
    assert result["score"]["value_type"] == "numeric"


def test_parse_search_string_datetime_range():
    result = parse_search_string("@created_at:[2024-01-01,2024-12-31]")
    assert result["created_at"]["is_range"] is True
    assert result["created_at"]["value_type"] == "datetime"
    assert "format_strings" in result["created_at"]


def test_parse_search_string_multiple():
    result = parse_search_string("@name:john @age:>25")
    assert "name" in result
    assert "age" in result


def test_parse_search_string_skip_non_at():
    result = parse_search_string("plain text @field:value")
    assert "field" in result
    assert len(result) == 1


def test_parse_search_string_boolean_type():
    result = parse_search_string("@active:true")
    assert result["active"]["value_type"] == "boolean"


def test_parse_search_string_numeric_type():
    result = parse_search_string("@count:42")
    assert result["count"]["value_type"] == "numeric"


def test_parse_search_string_datetime_value():
    result = parse_search_string("@created_at:2025-04-28T12:30:00")
    assert result["created_at"]["value_type"] == "datetime"
    assert "format_strings" in result["created_at"]


def test_parse_search_string_duplicate_field_same_sign():
    result = parse_search_string("@tag:a @tag:b")
    assert result["tag"]["values"] == ["a", "b"]


def test_parse_search_string_duplicate_field_diff_sign():
    result = parse_search_string("@tag:a -@tag:b")
    # Second overwrites since different sign
    assert result["tag"]["negative"] is True
    assert result["tag"]["values"] == ["b"]


def test_parse_search_string_no_colon():
    result = parse_search_string("@invalidterm")
    assert len(result) == 0


# --- set_table_for_query ---


class _FakeQuery:
    def __init__(self, qtype, space_name="data", subpath="/"):
        self.type = qtype
        self.space_name = space_name
        self.subpath = subpath


def test_set_table_for_query_spaces():
    assert set_table_for_query(_FakeQuery(QueryType.spaces)) is Spaces


def test_set_table_for_query_history():
    assert set_table_for_query(_FakeQuery(QueryType.history)) is Histories


def test_set_table_for_query_management_users():
    assert set_table_for_query(_FakeQuery(QueryType.search, "management", "/users")) is Users


def test_set_table_for_query_management_roles():
    assert set_table_for_query(_FakeQuery(QueryType.search, "management", "/roles")) is Roles


def test_set_table_for_query_management_permissions():
    assert set_table_for_query(_FakeQuery(QueryType.search, "management", "/permissions")) is Permissions


def test_set_table_for_query_management_other():
    assert set_table_for_query(_FakeQuery(QueryType.search, "management", "/other")) is Entries


def test_set_table_for_query_regular():
    assert set_table_for_query(_FakeQuery(QueryType.search, "data", "/content")) is Entries


# --- build_query_filter_for_allowed_field_values ---


def test_build_filter_string_value():
    result = build_query_filter_for_allowed_field_values({"role": "admin"})
    assert result == "@role:admin"


def test_build_filter_list_value():
    result = build_query_filter_for_allowed_field_values({"role": ["admin", "user"]})
    assert result == "@role:admin|user"


def test_build_filter_nested_list():
    result = build_query_filter_for_allowed_field_values({"role": [["admin", "user"], "guest"]})
    assert result == "@role:admin|user|guest"


def test_build_filter_multiple_fields():
    result = build_query_filter_for_allowed_field_values({"role": "admin", "dept": ["eng", "qa"]})
    assert "@role:admin" in result
    assert "@dept:eng|qa" in result


def test_build_filter_empty_list():
    result = build_query_filter_for_allowed_field_values({"role": []})
    assert result == ""


def test_build_filter_dedup():
    result = build_query_filter_for_allowed_field_values({"role": ["admin", "admin", "user"]})
    assert result == "@role:admin|user"


def test_build_filter_empty_strings_skipped():
    result = build_query_filter_for_allowed_field_values({"role": ["admin", "", "user"]})
    assert result == "@role:admin|user"


# --- parse_search_expression ---


def test_parse_search_expression_simple_backward_compat():
    """No operators — single group, same as parse_search_string."""
    result = parse_search_expression("@field:value")
    assert len(result) == 1
    assert "field" in result[0]["fields"]
    assert result[0]["fields"]["field"]["values"] == ["value"]
    assert result[0]["text_terms"] == []


def test_parse_search_expression_multiple_fields_backward_compat():
    """Space-separated fields without operators — single AND group."""
    result = parse_search_expression("@name:john @age:>25")
    assert len(result) == 1
    assert "name" in result[0]["fields"]
    assert "age" in result[0]["fields"]


def test_parse_search_expression_and_keyword():
    """Explicit 'and' between terms — still one group (AND)."""
    result = parse_search_expression("@payload.body.x:1 and @is_active:true")
    assert len(result) == 1
    assert "payload.body.x" in result[0]["fields"]
    assert "is_active" in result[0]["fields"]


def test_parse_search_expression_and_with_text_term():
    """'and' chain with a plain text term."""
    result = parse_search_expression("@payload.body.x:1 and @is_active:true and dummy")
    assert len(result) == 1
    assert "payload.body.x" in result[0]["fields"]
    assert "is_active" in result[0]["fields"]
    assert result[0]["text_terms"] == ["dummy"]


def test_parse_search_expression_and_case_insensitive():
    """'AND' keyword is case-insensitive."""
    result = parse_search_expression("@a:1 AND @b:2")
    assert len(result) == 1
    assert "a" in result[0]["fields"]
    assert "b" in result[0]["fields"]


def test_parse_search_expression_paren_grouping_or():
    """Parenthesized group + standalone term → two groups (OR)."""
    result = parse_search_expression("(@payload.body.x:1 and @is_active:true) @roles:admin")
    assert len(result) == 2
    # Group 0: payload.body.x AND is_active
    assert "payload.body.x" in result[0]["fields"]
    assert "is_active" in result[0]["fields"]
    # Group 1: roles
    assert "roles" in result[1]["fields"]
    assert result[1]["fields"]["roles"]["values"] == ["admin"]


def test_parse_search_expression_two_paren_groups():
    """Two parenthesized groups → OR."""
    result = parse_search_expression("(@a:1) (@b:2)")
    assert len(result) == 2
    assert "a" in result[0]["fields"]
    assert "b" in result[1]["fields"]


def test_parse_search_expression_leading_terms_then_group():
    """Non-grouped terms followed by a group → two groups (OR)."""
    result = parse_search_expression("@a:1 @b:2 (@c:3 and @d:4)")
    assert len(result) == 2
    # Group 0: a AND b
    assert "a" in result[0]["fields"]
    assert "b" in result[0]["fields"]
    # Group 1: c AND d
    assert "c" in result[1]["fields"]
    assert "d" in result[1]["fields"]


def test_parse_search_expression_single_paren_group():
    """Single parenthesized group — still one group."""
    result = parse_search_expression("(@a:1 and @b:2)")
    assert len(result) == 1
    assert "a" in result[0]["fields"]
    assert "b" in result[0]["fields"]


def test_parse_search_expression_negative_field():
    """Negative field inside groups."""
    result = parse_search_expression("(-@status:deleted) @type:content")
    assert len(result) == 2
    assert result[0]["fields"]["status"]["negative"] is True
    assert "type" in result[1]["fields"]


def test_parse_search_expression_text_term_in_group():
    """Text term inside a parenthesized group."""
    result = parse_search_expression("(@a:1 and search_text) @b:2")
    assert len(result) == 2
    assert "a" in result[0]["fields"]
    assert result[0]["text_terms"] == ["search_text"]
    assert "b" in result[1]["fields"]


def test_parse_search_expression_empty_parens():
    """Empty parentheses are ignored — only non-empty groups are kept."""
    result = parse_search_expression("() @a:1")
    assert len(result) == 1
    assert "a" in result[0]["fields"]


def test_parse_search_expression_preserves_pipe_or():
    """Pipe OR syntax within field values is preserved."""
    result = parse_search_expression("(@status:active|pending) @role:admin")
    assert len(result) == 2
    assert result[0]["fields"]["status"]["values"] == ["active", "pending"]
    assert result[0]["fields"]["status"]["operation"] == "OR"
