### **Subpath**

---

In Dmart, a "Subpath" represents a hierarchical structure within a Space that helps organize and categorize data further. It serves as a way to create a nested hierarchy of folders or directories within a Space, allowing users to group related data together in a logical manner. Think of a Subpath as a subdirectory or subfolder within a Space, enabling finer-grained organization and management of data.

**Purpose of Subpaths**

1.  **Data Organization**: Subpaths provide a mechanism for organizing data into a hierarchical structure, making it easier to navigate and manage large volumes of data. Users can create nested levels of Subpaths to represent different levels of categorization or classification.

2.  **Granular Access Control**: Similar to Spaces, Subpaths can have their own access control settings, allowing users to define permissions at a more granular level. This enables finer control over who can access, modify, or delete specific subsets of data within a Space.

3.  **Data Contextualization**: By organizing data into Subpaths, users can provide context and meaning to the data, making it easier to understand its relevance and relationship to other data within the Space. This contextualization enhances data discoverability and usability.

**Key Features of Subpaths**

1.  **Nested Structure**: Subpaths support a nested structure, allowing users to create hierarchical relationships between different levels of Subpaths. This hierarchical organization facilitates the grouping and classification of data based on various criteria.

2.  **Customization**: Users can customize Subpaths by defining metadata, tags, or attributes to further describe and categorize the data within each Subpath. This customization helps in creating meaningful labels and annotations for data organization.

3.  **Data Management**: Within each Subpath, users can perform various data management tasks, such as creating, retrieving, deleting, and moving files or datasets. These capabilities enable users to manipulate data within the context of their respective Subpaths.

**Use Cases for Subpaths**

1.  **Project-based Data Organization**: Teams working on different projects can create Subpaths within a Space to organize project-related data, such as documents, datasets, and reports, into logical groupings.

2.  **Hierarchical Classification**: Organizations can use Subpaths to implement a hierarchical classification scheme for organizing data based on different attributes, such as department, location, or data type.

3.  **Version Control**: Subpaths can be utilized for version control purposes, allowing users to create separate Subpaths for different versions or revisions of data files. This enables users to track changes and maintain a history of data modifications over time.

4.  **Data Lifecycle Management**: Subpaths can be used to implement data lifecycle management policies, defining rules for data retention, archiving, and deletion based on the lifecycle stage of data within each Subpath.

**Subpath Configuration Attributes**

The Folder Rendering Configuration defines how folders within a space are displayed and interacted with. Below is a detailed explanation of each field within the folder rendering configuration:

**Fields Explanation**

- **stream**: A boolean flag indicating whether to stream the folder contents.

- **disable_filter**: A boolean flag indicating whether to disable filtering options for the folder.

- **expand_children**: A boolean flag indicating whether to automatically expand child folders.

- **append_subpath**: A string to append to the subpath of the folder.

- **csv_columns**: A list of dictionaries defining the columns to be included in CSV exports.

- **search_columns**: A list of dictionaries defining the columns to be included in search results.
- **enable_pdf_schema_shortnames**: A list of schema shortnames for which PDF generation is enabled.

- **workflow_shortnames**: A list of workflow shortnames associated with the folder.

- **query**: A dictionary defining the default query settings for the folder. Example:

```
{
"type": "search",
"search": "",
"filter_types": []
}
```

- **icon**: A URL or path to an icon representing the folder.

- **icon_opened**: A URL or path to an icon representing the folder when opened.

- **icon_closed**: A URL or path to an icon representing the folder when closed.

- **sort_by**: A field by which to sort the folder contents.

- **sort_type**: The type of sorting to apply (e.g., ascending or descending).

- **shortname_title**: The title to display for the folder's shortname.

- **content_schema_shortnames**: A list of schema shortnames for content associated with the folder.

- **content_resource_types**: A list of resource types associated with the folder's content.
- **filter**: A list of filters to apply to the folder's content.
- **index_attributes**: A list of dictionaries defining attributes to index for the folder.
- **unique_fields**: A list of unique fields for the folder's content.
- **allow_view**: A boolean flag indicating whether viewing the folder's content is allowed.
- **allow_create**: A boolean flag indicating whether creating new entries in the folder is allowed.
- **allow_create_category**: A boolean flag indicating whether creating new categories in the folder is allowed.
- **allow_update**: A boolean flag indicating whether updating entries in the folder is allowed.
- **allow_delete**: A boolean flag indicating whether deleting entries in the folder is allowed.
- **allow_csv**: A boolean flag indicating whether exporting the folder's content to CSV is allowed.
- **allow_upload_csv**: A boolean flag indicating whether uploading CSV files to the folder is allowed.
- **use_media**: A boolean flag indicating whether media files are used within the folder.
