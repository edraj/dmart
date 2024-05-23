**Attachments**

Attachments within Dmart encompass any additional file or document linked to a data entity within a Space. These attachments enrich the associated data by providing relevant files such as images, documents, spreadsheets, or multimedia, thereby enhancing the comprehensiveness and utility of the data.

**Supported Attachment Types in Dmart include:**

- **Reaction**: Allows users to add reactions to a post.
- **Share**: Facilitates the sharing of a post.
- **JSON**: Supports attachment of JSON documents.
- **Reply**: Enables users to reply to a comment.
- **Comment**: Allows users to comment on a post.
- **Lock**: Used by the system for locking/unlocking entries.
- **Media**: Supports attachment of image files.
- **Data Asset**: Supports attachment of JSONL, CSV, Parquet, and DuckDB files.
- **Relationship**: Establishes a link to another entry.
- **Alteration**: Enables users to submit alteration requests for review and approval by administrators.

Create Attachment

For attachments that are not files, which are: reaction, share, reply, comment, json, relationship, and alteration you can use the /managed/request API, as follows:

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

And for the file attachments, which are media and data_asset you can use the /managed/resource_with_payload API. it accepts three inputs

request_record file, consists of the record data, example

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

the attachment file itself
the space name

> For more API examples refer to the `Managed -> Content -> Attachment` section in the [Postman API collection](https://www.postman.com/galactic-desert-723527/workspace/dmart/collection/5491055-c2a1ccd1-6554-4890-b6c8-59b522983e2f)
