# Relationships And Locators

In Dmart, "Relationships" define the connections or associations between different data entities. 
These relationships represent the links or dependencies between data entities, 
enabling users to establish connections, 
navigate between related data, and perform complex data queries and analyses.

## Relationship Attributes
1. **related_to**: an object of type Locator*
2. **attributes**: a free dictionary that can be used to associate any kind of data along with the relation

**Locator Attributes**:
- **uuid**: the UUID of the target
- **domain**: the dmart instance domain, if it's hosted on a different domain
- **type**: the resource type of the target
- **space_name**: the space name of the target
- **subpath**: the subpath of the target
- **shortname**: the shortname of the target
- **schema_shortname**: the schema shortname of the target, optional
- **displayname**: an object of type Translation*
- **description**: an object of type Translation
- **tags**: list of string tags

**Translation Attributes**:
- **en**: the english version of the data
- **ar**: the arabic version of the data
- **ku**: the kurdish version of the data


## Create Relationship
Lets say you have an entry under `space = dmart_data`, `subpath = content`, and `shortname = parent_entry`
and you want to add a link inside it to a child entry under `space = dmart_data`, `subpath = children`, and `shortname = child_entry`
so, you need to update the `parent` entry to add the relationship attachment to it, the request body would be as follows
```
{
    "space_name": "dmart_data",
    "request_type": "update",
    "records": [
        {
            "resource_type": "content",
            "shortname": "parent_entry",
            "subpath": "/content",
            "attributes": {
                "relationships": [
                    {
                        "related_to": {
                            "type": "content",
                            "space_name": "dmart_data",
                            "subpath": "children",
                            "shortname": "child_entry"
                        },
                        "attributes": {
                            "note": "An important link"
                        }
                    }
                ]
            }
        }
    ]
}
```