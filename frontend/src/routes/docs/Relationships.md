## Relationships And Locators

In Dmart, "Relationships" define the connections or associations between different data entities.

These relationships represent the links or dependencies between data entities, enabling users to establish connections, navigate between related data, and perform complex data queries and analyses.

**Relationship Attributes**

1.  **related_to**: An object of type Locator

2.  **attributes**: A flexible dictionary allowing users to associate additional data with the relationship.

**Locator Attributes**:

- **uuid**: The UUID of the target entity.

- **domain**: The dmart instance domain, if it's hosted on a different domain

- **type**: The resource type of the target entity.

- **space_name**: The space name of the target entity.

- **subpath**: The subpath of the target entity.

- **shortname**: The shortname of the target entity.

- **schema_shortname**: Optional schema shortname of the target entity.

- **displayname**: An object of type Translation, representing the display name.

- **description**: An object of type Translation,representing the description.

- **tags**: A list of string tags

**Translation Attributes:**

- **en**: English version of the data.

- **ar**: Arabic version of the data.

- **ku**: Kurdish version of the data.

### Create Relationship

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
}}]}}]
}

```
