#!/usr/bin/env python3
import json
import os
import sys

import jsonschema
import argparse
from rich.console import Console
from rich.progress import Progress

console = Console()


def exit_with_error(msg: str):
    console.print(f"ERROR!!", style="#FF0B0B")
    console.print(msg, style="#FF4040")
    sys.exit(1)


def print_report(success_count: int, failure_count: int, errors: dict, file_path: str):
    console.print(f"File: {file_path}")
    console.print(f"\tTotal rows: {failure_count + success_count}", style="#3D60FF")
    console.print(f"\tSuccess rows counter: {success_count}", style="#6EE853")
    console.print(f"\tFailure rows counter: {failure_count}", style="#FF4040")
    if errors:
        console.print("\tErrors found:", style="#CE2020")

    for idx, (key, val) in enumerate(errors.items()):
        json_data = json.dumps(val["json"])
        console.print(f"\t\tError number {idx + 1}:")
        console.print(f"\t\t\tLine number: {key}")
        console.print(f'\t\t\tMessage: {val["message"]}')
        console.print(f"\t\t\tJSON row: {json_data}\n")


class SchemaValidator:
    success_count = 0
    failure_count = 0
    errors = {}

    def __init__(self, schema_path: str):
        if not os.path.isfile(schema_path):
            exit_with_error(f"This file {schema_path} is not found.")
        with open(schema_path, "r") as f:
            self.schema = json.load(f)

    def validate_row(self, json_row: dict):
        try:
            jsonschema.validate(instance=json_row, schema=self.schema)
        except jsonschema.exceptions.ValidationError as error:  # type: ignore
            return error.message
        return None

    def validate_file(self, file_path: str):
        if not os.path.isfile(file_path):
            exit_with_error(f"This file {file_path} is not found.")
        with open(file_path) as f:
            lines = f.readlines()
            with Progress() as progress:
                task = progress.add_task("Processing...", total=len(lines))
                line_idx = 0
                for json_obj in lines:
                    line_idx += 1
                    row = json.loads(json_obj)
                    message = self.validate_row(row)
                    if not message:
                        self.success_count += 1
                    else:
                        self.failure_count += 1
                        self.errors[line_idx] = {"json": row, "message": message}
                    progress.update(task, advance=1)
        print_report(self.success_count, self.failure_count, self.errors, file_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True, help="Add JSON schema file.")
    parser.add_argument(
        "--logs",
        action="append",
        nargs="+",
        required=True,
        help="Add logs files pass seperated by space.",
    )
    args = parser.parse_args()
    sc = SchemaValidator(args.schema)

    for log_path in args.logs[0]:
        sc.validate_file(log_path)
