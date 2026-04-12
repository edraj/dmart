#!/usr/bin/env -S BACKEND_ENV=config.env python3

import asyncio
import time
from typing import Any

from jsonschema.validators import Draft7Validator
from sqlmodel import col, select

from data_adapters.adapter import data_adapter as db
from data_adapters.sql.adapter import SQLAdapter
from data_adapters.sql.create_tables import Entries
from models import core
from models.enums import ContentType, ResourceType
from utils.settings import settings


async def main(space_param: str | None, schemas_param: list[str] | None) -> dict[str, Any]:
    """Run checks and return the full report as a dict (per space)."""
    space_param = space_param or "all"

    spaces = await db.get_spaces()

    if space_param != "all":
        if space_param not in spaces:
            print(f"Space '{space_param}' not found")
            return {}
        space_names = [space_param]
    else:
        space_names = list(spaces.keys())

    print(f"Checking {len(space_names)} space(s): {', '.join(space_names)}")
    print("=" * 60)

    tasks = [check_space(space, schemas_param) for space in space_names]
    results = await asyncio.gather(*tasks)

    full_report: dict[str, Any] = {}
    total_issues = 0
    for space_name, report in zip(space_names, results, strict=True):
        full_report[space_name] = report
        issue_count = sum(len(v.get("issues", [])) for v in report.values())
        total_issues += issue_count
        print_space_report(space_name, report)

    print("=" * 60)
    print(f"Total issues found: {total_issues}")

    return full_report


async def check_space(
    space_name: str, schemas_filter: list[str] | None
) -> dict[str, Any]:
    """Run all checks for a single space in parallel."""
    async with SQLAdapter().get_session() as session:
        # Load all entries for this space
        sql_stm = select(Entries).where(col(Entries.space_name) == space_name)
        if schemas_filter:
            sql_stm = sql_stm.where(col(Entries.resource_type).in_(
                [ResourceType.content, ResourceType.ticket]
            ))
        result = (await session.execute(sql_stm)).all()
        entries = [r[0] for r in result]

        # Load all schemas for this space (from both management and space itself)
        schema_stm = select(Entries).where(
            col(Entries.subpath) == "/schema",
            col(Entries.space_name).in_([space_name, settings.management_space]),
        )
        schema_result = (await session.execute(schema_stm)).all()
        schema_entries = [r[0] for r in schema_result]

        # Build schema cache: shortname -> schema body
        schema_cache: dict[str, dict] = {}
        for schema_entry in schema_entries:
            payload = _parse_payload(schema_entry.payload)
            if payload and isinstance(payload.body, dict):
                schema_cache[schema_entry.shortname] = payload.body

    # Run checks in parallel
    check_tasks = [
        _check_payload_structure(entries, schemas_filter),
        _check_payload_against_schema(entries, schema_cache, schemas_filter),
        _check_enum_values(entries, schemas_filter),
        _check_missing_schema_refs(entries, schema_cache, schemas_filter),
    ]
    results = await asyncio.gather(*check_tasks)

    # Merge results by subpath
    merged: dict[str, dict[str, Any]] = {}
    for check_result in results:
        for subpath, data in check_result.items():
            if subpath not in merged:
                merged[subpath] = {"total_entries": 0, "issues": []}
            merged[subpath]["total_entries"] = max(
                merged[subpath]["total_entries"], data.get("total_entries", 0)
            )
            merged[subpath]["issues"].extend(data.get("issues", []))

    return merged


async def _check_payload_structure(
    entries: list[Entries], schemas_filter: list[str] | None
) -> dict[str, Any]:
    """Check that payload fields are valid Payload models."""
    report: dict[str, Any] = {}

    for entry in entries:
        subpath = entry.subpath.lstrip("/") or "/"
        if subpath not in report:
            report[subpath] = {"total_entries": 0, "issues": []}
        report[subpath]["total_entries"] += 1

        if not entry.payload:
            continue

        payload = _parse_payload(entry.payload)
        if payload is None and isinstance(entry.payload, dict) and _should_check(entry, schemas_filter):
            report[subpath]["issues"].append({
                "check": "payload_structure",
                "shortname": entry.shortname,
                "uuid": str(entry.uuid),
                "resource_type": entry.resource_type,
                "message": "Payload dict does not conform to Payload model",
            })

    return report


async def _check_payload_against_schema(
    entries: list[Entries],
    schema_cache: dict[str, dict],
    schemas_filter: list[str] | None,
) -> dict[str, Any]:
    """Validate each entry's payload body against its declared schema."""
    report: dict[str, Any] = {}

    for entry in entries:
        subpath = entry.subpath.lstrip("/") or "/"
        if subpath not in report:
            report[subpath] = {"total_entries": 0, "issues": []}

        if not _should_check(entry, schemas_filter):
            continue

        payload = _parse_payload(entry.payload)
        if not payload or not payload.schema_shortname or not payload.body:
            continue
        if not isinstance(payload.body, dict):
            continue

        schema_body = schema_cache.get(payload.schema_shortname)
        if not schema_body:
            continue  # handled by _check_missing_schema_refs

        try:
            validator = Draft7Validator(schema_body)
            errors = list(validator.iter_errors(payload.body))
            for error in errors:
                path = " -> ".join(str(p) for p in error.absolute_path) or "(root)"
                report[subpath]["issues"].append({
                    "check": "schema_validation",
                    "shortname": entry.shortname,
                    "uuid": str(entry.uuid),
                    "resource_type": entry.resource_type,
                    "schema": payload.schema_shortname,
                    "field_path": path,
                    "message": error.message,
                })
        except Exception as e:
            report[subpath]["issues"].append({
                "check": "schema_validation",
                "shortname": entry.shortname,
                "uuid": str(entry.uuid),
                "resource_type": entry.resource_type,
                "schema": payload.schema_shortname,
                "message": f"Schema validation error: {e}",
            })

    return report


async def _check_enum_values(
    entries: list[Entries], schemas_filter: list[str] | None
) -> dict[str, Any]:
    """Check that enum fields contain valid values."""
    report: dict[str, Any] = {}

    valid_resource_types = set(ResourceType.__members__.values())

    for entry in entries:
        subpath = entry.subpath.lstrip("/") or "/"
        if subpath not in report:
            report[subpath] = {"total_entries": 0, "issues": []}

        # Check resource_type for every entry (not gated by schema filter)
        if entry.resource_type and entry.resource_type not in valid_resource_types:
            report[subpath]["issues"].append({
                "check": "enum_validation",
                "shortname": entry.shortname,
                "uuid": str(entry.uuid),
                "resource_type": entry.resource_type,
                "message": f"Invalid resource_type: '{entry.resource_type}'",
            })

        if not _should_check(entry, schemas_filter):
            continue

        # Check content_type in payload
        payload = _parse_payload(entry.payload)
        if payload and payload.content_type:
            try:
                ContentType(payload.content_type)
            except ValueError:
                report[subpath]["issues"].append({
                    "check": "enum_validation",
                    "shortname": entry.shortname,
                    "uuid": str(entry.uuid),
                    "resource_type": entry.resource_type,
                    "message": f"Invalid content_type in payload: '{payload.content_type}'",
                })

    return report


async def _check_missing_schema_refs(
    entries: list[Entries],
    schema_cache: dict[str, dict],
    schemas_filter: list[str] | None,
) -> dict[str, Any]:
    """Check for entries referencing schemas that don't exist."""
    report: dict[str, Any] = {}

    for entry in entries:
        subpath = entry.subpath.lstrip("/") or "/"
        if subpath not in report:
            report[subpath] = {"total_entries": 0, "issues": []}

        if not _should_check(entry, schemas_filter):
            continue

        payload = _parse_payload(entry.payload)
        if not payload or not payload.schema_shortname:
            continue

        if payload.schema_shortname not in schema_cache:
            report[subpath]["issues"].append({
                "check": "missing_schema",
                "shortname": entry.shortname,
                "uuid": str(entry.uuid),
                "resource_type": entry.resource_type,
                "message": f"References non-existent schema: '{payload.schema_shortname}'",
            })

    return report


def _parse_payload(payload_data) -> core.Payload | None:
    """Safely parse payload data into a Payload model."""
    if not payload_data:
        return None
    if isinstance(payload_data, core.Payload):
        return payload_data
    if isinstance(payload_data, dict):
        try:
            return core.Payload.model_validate(payload_data)
        except Exception:
            return None
    return None


def _should_check(entry: Entries, schemas_filter: list[str] | None) -> bool:
    """Check if this entry matches the optional schema filter."""
    if not schemas_filter:
        return True
    payload = _parse_payload(entry.payload)
    if not payload or not payload.schema_shortname:
        return False
    return payload.schema_shortname in schemas_filter


def print_space_report(space_name: str, report: dict[str, Any]):
    """Print a formatted report for a single space."""
    total_issues = sum(len(v.get("issues", [])) for v in report.values())
    total_entries = sum(v.get("total_entries", 0) for v in report.values())

    print(f"\nSpace: {space_name}")
    print(f"  Entries checked: {total_entries}")
    print(f"  Issues found: {total_issues}")

    if total_issues == 0:
        return

    # Group issues by check type
    by_check: dict[str, list[dict]] = {}
    for subpath, data in sorted(report.items()):
        for issue in data.get("issues", []):
            check = issue["check"]
            if check not in by_check:
                by_check[check] = []
            by_check[check].append({**issue, "subpath": subpath})

    check_labels = {
        "payload_structure": "Payload Structure",
        "schema_validation": "Schema Validation",
        "enum_validation": "Enum Values",
        "missing_schema": "Missing Schema References",
    }

    for check, issues in by_check.items():
        label = check_labels.get(check, check)
        print(f"\n  [{label}] ({len(issues)} issue(s))")
        for issue in issues:
            print(f"    - {issue['subpath']}/{issue['shortname']} ({issue['uuid'][:8]})")
            print(f"      {issue['message']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Check data integrity in dmart database",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-s", "--space", help="Target space (default: all)")
    parser.add_argument("-m", "--schemas", nargs="*", help="Filter by schema shortnames")

    args = parser.parse_args()
    before_time = time.time()
    asyncio.run(main(args.space, args.schemas))
    print(f"\nTotal time: {time.time() - before_time:.2f} sec")
