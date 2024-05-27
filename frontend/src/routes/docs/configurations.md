### Space Meta Configuration

The Space Meta Configuration is a critical component to allow managing various attributes and settings for a given space. Below is a detailed explanation of each field within the space meta configuration:

**Fields Explanation**

- **uuid**: A unique identifier for the space, represented as a UUID (Universally Unique Identifier). Example: `"2c4ed293-7d69-418f-8fad-9a72596cd037"`.
- **shortname**: A short, human-readable name for the space. Example: `"my_space"`.
- **is_active**: A boolean flag indicating whether the space is active. Example: `true`.
- **displayname**: A dictionary containing the display names of the space in different languages. Example:

  json

- `{
  "en": "Space",
  "ar": "ar"
}`
- **tags**: A list of tags associated with the space for categorization and search purposes. Example: `[]`.
- **created_at**: The timestamp indicating when the space was created. Example: `"2024-03-17T11:32:08.972410"`.
- **updated_at**: The timestamp indicating the last update to the space. Example: `"2024-04-01T14:09:54.146205"`.
- **owner_shortname**: The shortname of the owner or administrator of the space. Example: `"dmart"`.
- **relationships**: A list of relationships associated with the space, often used for linking to other spaces or entities. Example: `[]`.
- **root_registration_signature**: A signature used for verifying the registration of the root space. Example: `""`.
- **primary_website**: The primary website URL associated with the space. Example: `""`.
- **indexing_enabled**: A boolean flag indicating whether indexing is enabled for the space, which affects search functionality. Example: `true`.
- **capture_misses**: A boolean flag indicating whether to capture missed searches or requests within the space. Example: `false`.
- **check_health**: A boolean flag indicating whether to perform health checks on the space. Example: `false`.
- **languages**: A list of languages supported by the space. Example: `["english"]`.
- **icon**: A URL or path to an icon representing the space. Example: `""`.
- **mirrors**: A list of mirror URLs or paths for the space, used for redundancy and backup. Example: `[]`.
- **hide_folders**: A list of folders to be hidden from the default view within the space. Example: `[]`.
- **active_plugins**: A list of active plugins enabled for the space. Example:

  json

- `[
  "action_log",
  "redis_db_update",
  "resource_folders_creation"
]`
- **branches**: A list of branches or sub-spaces associated with the space. Example: `[]`.

**Folder Rendering Configuration**

The Folder Rendering Configuration defines how folders within a space are displayed and interacted with. Below is a detailed explanation of each field within the folder rendering configuration:

**Fields Explanation**

- **stream**: A boolean flag indicating whether to stream the folder contents. Example: `true`.
- **disable_filter**: A boolean flag indicating whether to disable filtering options for the folder. Example: `true`.
- **expand_children**: A boolean flag indicating whether to automatically expand child folders. Example: `true`.
- **append_subpath**: A string to append to the subpath of the folder. Example: `""`.
- **csv_columns**: A list of dictionaries defining the columns to be included in CSV exports. Example:

  json

- `[
  {
    "key": "",
    "name": ""
  },
  {
    "key": "displayname.en",
    "name": "Title (en)"
  }
]`
- **search_columns**: A list of dictionaries defining the columns to be included in search results. Example:

  json

- `[
  {
    "key": "",
    "name": ""
  }
]`
- **enable_pdf_schema_shortnames**: A list of schema shortnames for which PDF generation is enabled. Example: `[]`.
- **workflow_shortnames**: A list of workflow shortnames associated with the folder. Example: `[]`.
- **query**: A dictionary defining the default query settings for the folder. Example:

  json

- `{
  "type": "search",
  "search": "",
  "filter_types": []
}`
- **icon**: A URL or path to an icon representing the folder. Example: `""`.
- **icon_opened**: A URL or path to an icon representing the folder when opened. Example: `""`.
- **icon_closed**: A URL or path to an icon representing the folder when closed. Example: `""`.
- **sort_by**: A field by which to sort the folder contents. Example: `""`.
- **sort_type**: The type of sorting to apply (e.g., ascending or descending). Example: `"ascending"`.
- **shortname_title**: The title to display for the folder's shortname. Example: `"Shortname"`.
- **content_schema_shortnames**: A list of schema shortnames for content associated with the folder. Example:

  json

- `[
  "category"
]`
- **content_resource_types**: A list of resource types associated with the folder's content. Example:

  json

- `[
  "content"
]`
- **filter**: A list of filters to apply to the folder's content. Example: `[{}]`.
- **index_attributes**: A list of dictionaries defining attributes to index for the folder. Example:

  json

- `[
  {
    "key": "",
    "name": ""
  }
]`
- **unique_fields**: A list of unique fields for the folder's content. Example: `[]`.
- **allow_view**: A boolean flag indicating whether viewing the folder's content is allowed. Example: `true`.
- **allow_create**: A boolean flag indicating whether creating new entries in the folder is allowed. Example: `true`.
- **allow_create_category**: A boolean flag indicating whether creating new categories in the folder is allowed. Example: `true`.
- **allow_update**: A boolean flag indicating whether updating entries in the folder is allowed. Example: `true`.
- **allow_delete**: A boolean flag indicating whether deleting entries in the folder is allowed. Example: `true`.
- **allow_csv**: A boolean flag indicating whether exporting the folder's content to CSV is allowed. Example: `true`.
- **allow_upload_csv**: A boolean flag indicating whether uploading CSV files to the folder is allowed. Example: `true`.
- **use_media**: A boolean flag indicating whether media files are used within the folder. Example: `true`.

**Conclusion**

The System Admin Tool provides a robust interface for managing spaces and folders, allowing administrators to define, organize, and control various aspects of their data and workflows. By understanding and utilizing the space meta configuration and folder rendering fields, administrators can effectively tailor the system to meet their specific needs and requirements.
