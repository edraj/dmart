<script>
  import {QueryType} from "@/dmart";
  import ListView from "@/components/management/ListView.svelte";
  import Tree from "./assets/tree.png"
</script>

### **Examples**

---

_In this example we will use those attributes_
`space = dmart_data`
`subpath = content`
`schema = product`

**1. Define your Schema (Model)**

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

_Please note all schemas must be created under the `schema` subpath_

**2. Create an entry**

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

            }
        }
    ]
}
```

Now the system retrieves the schema you provided in `attributes.payload.schema_shortname` form the same space and the `schema` subpath, and validates the `attributes.payload.body` against it,
if it's valid, the system stores the entry under `dmart_data/products`.

**3. Search**

Now you can do a full text search or an attribute based search for that field.
for example, lets say we want to retrieve all sub-folders under **mysapce** space

we call the `/query` API with the following request body

```json
{
  "filter_shortnames": [],
  "type": "subpath",
  "search": "",
  "subpath": "/",
  "exact_subpath": true,
  "limit": 15,
  "offset": 0,
  "retrieve_json_payload": true,
  "sort_type": "ascending",
  "sort_by": "created_at"
}
```

And the results would be:

<ListView
type={QueryType.subpath}
is_clickable={false}
/>
