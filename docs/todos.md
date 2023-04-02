## Planned improvements

- One index for all entries
  - all meta data
  - payload schema_shortname / type
  - payload_body : single text blob
  - attachments_payload? : (use multivalue fields)
  - uuid : should be unique across all entries
  - key : entries:space:subpath:shortname:type? (what about attachments? should they be included within?)
  - url_shortname : unique entry short name across all system. we can use the uuid hash instead
  - With proper/usual security support

- Extend shortname regex to include arabic alpha numerals + kasheeda



### Future improvements

- Consider providing GraphQL Api interface.
  - There are several options for supporting GraphQL on FastApi
  - Break the /xx/query api to multiple queries each for the respective type.
  - Break the /xx/request api to multiple mutations
  - Support file upload (already supported by one or more Fastapi compatible graphql libraries)
  - Support websocket subscription (this can very well deprecate our websocket logic)

- Consider providing data-at-rest encryption that can only be accessed / viewed (decrypted) by the owner or a member of owner group.
