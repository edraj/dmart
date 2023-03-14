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
