# Simple Example


## Important terms
**Each term has a dedicated section with a detailed explanation**
- **Space**: Top-level business category that facilitates grouping of relevant content.
- **Subpath**: aka folder, The path within space that leads to an entry
- **Meta**: Meta information associated with the entry such as owner, shortname, unique uuid, creation/update timestamp, tags ..etc
- **Schema**: The JSON schema definition of the entry
- **Payload**: The actual content associated with the entry
<img src="./docs/tree.png" width="500">

*In this example we will use those attributes*
`space = dmart_data`
`subpath = content`
`schema = product`

## 1. Define your Schema (Model)
Let's say we need to define a Product model with the following fields:
- title
- description
- price
- category
- image

Using [JSON schema definition](https://json-schema.org/) our schema would be:
```
{
  "title": "Product",
  "additionalProperties": false,
  "type": "object",
  "properties": {
    "title": {
      "type": "string"
    },
    "description": {
      "type": "string"
    },
    "price": {
      "type": "number"
    },
    "category": {
      "type": "string"
    },
    "image": {
      "type": "string"
    }
  }
}
```

*Please note all schemas must be created under the `schema` subpath*

## 2. Create an entry
Specify the location, the Meta data, and the Payload (actual product data) data
```
{
    "space_name": "dmart_data",
    "request_type": "create", // Explained at Concepts -> Request Types
    "records": [ // accepts a list of records to be created
        {
            "resource_type": "content", // Explained at Concepts -> Resource Types
            "subpath": "products",
            "shortname": "auto", // auto is a magic word that asks the system to generate a unique shortname
            "attributes": {
                "is_active": true, // Meta data
                "tags": ["red", "awesome"], // Meta data

                "payload": {
                    "content_type": "json", // Explained at Concepts -> Content Types
                    "schema_shortname": "product", // The shortname of the created schema
                    // The attributes values of the product entry
                    "body": {
                        "title": "Iphone 14",
                        "description": "Red, 128GB",
                        "price": 799.99,
                        "category": "Mobile Phones",
                        "image": "https://dmart.com/media/iphone-14-red"
                    }
                }
            }
        }
    ]
}
```

Now the system retrieves the schema you provided in `attributes.payload.schema_shortname` form the same space and the `schema` subpath, and validates the `attributes.payload.body` against it,
if it's valid, the system stores the entry under `dmart_data/products`.

## 3. Search
Now you can do a full text search or an attribute based search for that field.
for example, lets say we want to retrieve product under **Mobile Phones** category

we call the `/query` API with the following request body

```
{
    "type": "search",
    "space_name": "dmart_data",
    "subpath": "products",
    "filter_schema_names": ["product"],
    "search": "@category:Mobile Phones"
}
```


