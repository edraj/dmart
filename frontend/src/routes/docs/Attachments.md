# Attachments

In Dmart, an "Attachment" refers to any additional file or document associated with a data entity within a Space. 
Attachments allow users to supplement data with relevant files, 
such as images, documents, spreadsheets, or multimedia files, enhancing the context and usability of the data.

## Supported Attachment Types
- **reaction**: Add a reaction to a post
- **share**: Share a post
- **json**: JSON document attachment
- **reply**: Reply to a comment
- **comment**: Comment on a post
- **lock**: Used by the system to Lock/Unlock the entry
- **media**: Image attachments
- **data_asset**: Supports JSONL, CSV, Parquet, and DuckDB files
- **relationship**: A link to another entry
- **alteration**: Alteration request added by some user for the admin to review and approve

## Create Attachment
For attachments that are not files,
which are: reaction, share, reply, comment, json, relationship, and alteration
you can use the `/managed/request` API, as follows:
```
{
    "space_name": "dmart_data",
    "request_type": "create",
    "records": [
        {
            "resource_type": "comment", // Must be one of the attachment types that is not file
            "shortname": "my_comment",
            "subpath": "{parent_entry_subpath}/{parent_entry_shortname}"
            "attributes": {
                "is_active": true, // Attachments have meta fields also
                "tags": ["one", "two"],
                "body": "Very Intersting entry", // The comment
            }
        }
    ]
}
```

And for the file attachments,
which are media and data_asset
you can use the `/managed/resource_with_payload` API.
it accepts three inputs
1. request_record file, consists of the record data, example
```
{
    "resource_type": "csv",
    "subpath": "asset_csv/test_csv",
    "shortname": "auto",
    "attributes": {
        "is_active": true,
        "payload": {
            "content_type": "csv",
            "schema_shortname": "users",
            "body": {}
        }
    }
}
```
2. the attachment file itself
3. the space name

> For more API examples refer to the `Managed -> Content -> Attachment` section in the [Postman API collection](https://www.postman.com/galactic-desert-723527/workspace/dmart/collection/5491055-c2a1ccd1-6554-4890-b6c8-59b522983e2f)
