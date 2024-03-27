# Concept of Data Asset in Dmart

In Dmart, a "Data Asset" refers to a collection of data entities stored in a single file.
Which you can store and do an SQL queries on it later.
A data asset entry is type of Attachment.

## Supported Data Asset Types
- **CSV**
- **JSONL**
- **Sqlite**
- **Parquet**
- **DuckDB**


## Store Data Asset
use `/managed/resource_with_payload` API to store you data asset attachment entry.
Example
let's say you have an a departments subpath and you want to add data asset under a specific department called `HR`
Your request file would look like this:
```
{
    "resource_type": "csv", // or any other supported data asset type
    "subpath": "departments/hr", // the full path of the parent entry
    "shortname": "auto", // the shortname of the attachment entry
    "attributes": {
        "is_active": true,
        "payload": {
            "content_type": "csv",
            "schema_shortname": "users", // if a passed, the app will use it to validate all the records of the data asset file
            "body": {}
        }
    }
}
```

## Query Data Asset
After successfully storing a data asset file, you can do any kind of SQL queries on the file, whatever its type is, thanks to DuckDB
using the POST `/managed/data-asset` API
example request body to query the created attachment above
```
{
  "space_name": "dmart_data",
  "subpath": "departments", // the subpath of the parent entry
  "resource_type": "content", // the resource type of the parent entry
  "shortname": "hr", // the shortname of the parent entry
  "schema_shortname": "users", // if a passed, the app will use it to validate all the records of the data asset file
  "data_asset_type": "csv",
  "query_string": "SELECT * FROM '7d1f9b0b'" // Each data asset attachment file should be considered as a table, except for the Sqlite type because it's already a collection of tables
}

```
