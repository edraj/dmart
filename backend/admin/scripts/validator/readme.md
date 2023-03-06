# Logs validator

Logs validator is a tool that validating JSON logs for `dmart-backend`.

### Before executing
You have to install these packages by ``pip``.
```
pip install jsonschema
pip install Rich
```

## Execute

```bash
python json_validator.py --schema [schema] --logs [logs...] 
python json_validator.py --schema logs_schema.json --logs logs1.json logs2.json
```
For more information:
```bash
python json_validator.py --help
```
### How it works ?

Simply, `SchemaValidator` class manages the validation.
the constructor takes the ``schema_path`` and verify it by ``jsonschema`` package, and the class has two main functions:
1. ```validate_file(file_path: str):``` the function takes ``file_path`` which is the file path and it validates the file by passing line by line into ``validate_row`` function to validate the line.

2. ```validate_row(self, json_row: dict)```: the function takes ``json_row` which is a row from json logs file and the function validates json by the schema.

Last thing we have ``print_report`` function which is printing the file validation report and ``exit_with_error`` it prints the error message like ``can't open  a file``.

