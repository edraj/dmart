### **Data Exporter Tool for DMART**

---

**Description:**

This tool is designed to extract data from DMART instances based on provided configurations. It retrieves data from specified spaces, subpaths, and resource types, and prepares the extracted data for further processing or analysis.

**Features:**

- Extracts data from DMART instances based on user-defined configurations.
- Supports filtering data based on creation or modification timestamps.
- Generates output files containing extracted data in a structured format.
- Supports schema validation to ensure data integrity.
- Provides options for specifying included meta fields and excluded payload fields for customization.

**Dependencies:**

- Python 3.6+
- aiofiles
- jsonschema
- pydantic

**Configuration:**

The tool requires a JSON configuration file (`--config`) specifying the extraction settings for each extraction task. The configuration file should include the following parameters for each task:

- `space`: The name of the space from which data will be extracted.
- `subpath`: The subpath within the space from which data will be extracted.
- `resource_type`: The type of resource from which data will be extracted.
- `schema_shortname`: The shortname of the schema used for validation.
- `included_meta_fields`: A list of meta fields to be included in the output.
- `excluded_payload_fields`: A list of payload fields to be excluded from the output.

**Example Configuration:**

```json
[
  {
    "space": "example_space",
    "subpath": "example_subpath",
    "resource_type": "example_type",
    "schema_shortname": "example_schema",
    "included_meta_fields": [
      {
        "field_name": "example_field",
        "rename_to": "renamed_field",
        "schema_entry": {
          "type": "string"
        }
      }
    ],
    "excluded_payload_fields": [
      {
        "field_name": "example_field"
      }
    ]
  }
]
```

**Output:**

The tool generates output files in a structured format, including:

- A schema file (`schema.json`) containing the schema for the extracted data.
- A data file (`data.ljson`) containing the extracted data.
- A hashed data file (`hashed_data.json`) containing hashed values of sensitive fields.

**Example Usage:**

```
`python data_extraction_tool.py --config config.json --spaces /path/to/spaces --output /path/to/output --since 1622560000`
```

**Note:**

- Ensure that the specified spaces directory (`--spaces`) contains the required DMART space data.
- Provide the configuration file (`--config`) specifying the extraction settings.
- Optionally, specify the output directory (`--output`) for storing the extracted data.
- Optionally, specify the timestamp (`--since`) to filter data based on creation or modification time.
