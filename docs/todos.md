
## Tasks


## Planned improvements


hashed history : like git, only one change can be applied at a time.
add relations to meta : array of relations to other locators
add attributes to meta : general purpsoe key-value section
export : export.json (export date/space/subpath/ notes ...) + meta + payload + history + attachments ...
create/edit/update lock (file or redis)
- Change ticket reporter to relation
- maqola : fix author, editor/owner, profiles/authors ...etc



uuid : each entry (folder/space/content ... ) has unique uuid

new api end point : like /managed/entry api : /{managemed,public}/byuuid/{uuid} 
                                              /{managemed,public}/byslug/{slug}

# A : To create one large index for all entries across all spaces ...
  key is uuid (or first 8 chars) : uuid:872343
  slug
  space_name
  subpath
  resource_type
  schema_shortname
  shortname

# B : To loop over all existing indexs and search by @uuid: 2343423-* ... @slug: xxxx
    Get list of all spaces, and search in the meta index only for each space.
    After matching, use internal "entry api" and return the response

























- One index for all entries
  - all meta data
  - payload schema_shortname / type
  - payload_body : single text blob
  - attachments_payload? : (use multivalue fields)
  - uuid : should be unique across all entries
  - key : entries:space:subpath:shortname:type? (what about attachments? should they be included within?)
  - url_shortname / slug : unique entry short name across all system. we can use the uuid hash instead
  - With proper/usual security support

- Extend shortname regex to include arabic alpha numerals + kasheeda

- Enable (again) sha1 on payload body
- Enable sha1 hash on history changes to guarantee change order
- Ability to export one or group of entries in a zip file (simply collecting all relevent files under the zip file)

- Create a schema definition for the combined meta data, to make it easy to validate meta.

- Why space_name,subpath,resource_type,schema_shortname...etc is not indexed in meta? Saad

### Future improvements

- Consider providing GraphQL Api interface.
  - There are several options for supporting GraphQL on FastApi
  - Break the /xx/query api to multiple queries each for the respective type.
  - Break the /xx/request api to multiple mutations
  - Support file upload (already supported by one or more Fastapi compatible graphql libraries)
  - Support websocket subscription (this can very well deprecate our websocket logic)

- Consider providing data-at-rest encryption that can only be accessed / viewed (decrypted) by the owner or a member of owner group.
