## Content Types

Content Types within Dmart dictate the structure and format of data stored within an entry. It acts as blueprints that specify the kind of information your data will contain. These definitions determine the fields, their data types (text, numbers, images, etc.), and how they are arranged. By establishing content types, you ensure consistency and organization within your dmart application.

Supported Content Types include:

- Text
- Markdown
- HTML
- JSON
- Image
- Python
- PDF
- Audio
- Video
- CSV
- Parquet
- JSONL
- DuckDB
- SQLite

To set the content type in the request body, navigate to `record.attributes.payload.content_type`.

## Data Assets

Data assets represent the actual content you store in dmart. This is the information that populates the various content types you create. It can encompass text, images, videos, or any other digital element that resides within your dmart system. Data assets are the building blocks of your content, and they adhere to the structure defined by the corresponding content types.

**CSV (Comma-Separated Values)**

CSV is a common file format for storing tabular data. It utilizes commas to separate values within each row of data, making it a simple and widely-used method for exchanging information between different applications. Dmart allows you to import or export your data assets in CSV format, providing a way to migrate data from other sources or for backup purposes.

**JSONL (JSON Lines)**

JSONL (JavaScript Object Notation Lines) is a format where each line represents a valid JSON object. JSON is a popular data interchange format that uses key-value pairs to structure information. JSONL provides a convenient way to store and exchange data assets, especially when dealing with collections of similar objects. Dmart might support importing or exporting data assets in JSONL format for similar reasons as CSV.

**DuckDB**

DuckDB is an embedded relational database that dmart can leverage for data storage. Unlike traditional database systems, embedded databases reside within the application itself. This simplifies deployment and management as there's no need for a separate database server. Dmart potentially uses DuckDB to store and manage your data assets, allowing you to structure and query your content using familiar SQL commands.
