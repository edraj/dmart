## Schema

In Dmart, a "Schema" defines the structure and organization of data within a Space. It serves as a blueprint or template for how data is stored, organized, and accessed within the system. Think of a Schema as a set of rules or guidelines that dictate the format, data types, and structure of the data stored in a Subpath.

### Purpose of Schemas

1.  **Data Organization**: Schemas provide a structured approach to organizing data within a Subpath, ensuring consistency and coherence across datasets. By defining the structure of data upfront, Schemas help maintain data integrity and facilitate efficient data management.

2.  **Data Validation**: Schemas enforce data validation rules, ensuring that data entered into the system conforms to predefined standards. This helps prevent errors, inconsistencies, and data quality issues, improving the reliability and accuracy of the data stored in the Subpath.

3.  **Data Querying and Analysis**: Schemas enable efficient querying and analysis of data by defining the attributes, relationships, and indexing strategies of the data. With a well-defined Schema, users can perform complex queries, aggregations, and transformations on the data stored in the Subpath.

### Key Features of Schemas

1.  **Attribute Definition**: Schemas define the attributes or fields that make up each dataset within a Subpath. Each attribute is associated with a specific data type and may have additional properties such as constraints, defaults, or validation rules.

2.  **Indexing and Optimization**: Schemas determine the indexing strategy used for data storage and retrieval, optimizing query performance and reducing latency. By defining indexes on frequently queried attributes, Schemas enhance the efficiency of data access operations.

### How to create a Schema

Follow the documentation of [JSON Schema](https://json-schema.org/) to write the Schema definition of your model.

Then, refer to the `Create Schema` request under `Managed -> Schema` section in the [Postman API Collection](https://www.postman.com/galactic-desert-723527/workspace/dmart/collection/5491055-c2a1ccd1-6554-4890-b6c8-59b522983e2f)

> Note: to be able to reference your schema later while data creation, it must be stored under the same space of your data or globally under the `management` space, and under the `schema` subpath
