### **Data Faker Tool / Data Generator**

---

The Data Faker Tool is a script designed to generate fake records based on a specified schema. It creates resources of type `Content` and stores the data in a flat-file database and Redis. This documentation provides an overview of the tool, its usage, and a detailed explanation of its components.

**Overview**

The script takes a JSON schema file and generates a specified number of records adhering to that schema. Each generated record includes a unique identifier (UUID), a short name, metadata, and payload content.

**Components**

**Imports**

- argparse: Parses command-line arguments.
- asyncio: Handles asynchronous operations.
- Path: Manages file system paths.
- uuid4: Generates unique identifiers.
- Content, Payload: Models from `models.core`.
- ContentType: Enum for content types from `models.enums`.
- JSF: JSON Schema Faker library for generating fake data.
- internal_save_model: Function to save the generated content into the database.

**Parameters**

- space: The space under which records are stored.
- subpath: The subpath under which records are stored.
- schema_path: Path to the JSON schema file.
- num: Number of records to generate.

**Arguments**

- -p, --space: The space where records will be stored.
- -s, --subpath: The subpath where records will be stored.
- -c, --schema-path: Path to the schema file used for generating records.
- -n, --num: Number of records to generate.

**Usage**

To use the Data Faker Tool, run the script with the required arguments. For example:

sh

`python data_faker.py -p my_space -s my_subpath -c path/to/schema.json -n 100`

This command will generate 100 records according to the schema specified in `path/to/schema.json`, and store them under `my_space` and `my_subpath`.
