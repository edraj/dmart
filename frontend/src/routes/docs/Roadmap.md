### **Roadmap**

---

**Planned improvements**

1. Hashed history : like git, only one change can be applied at a time.

2. Add attributes to meta : general purpsoe key-value section

3. Export : export.json (export date/space/subpath/ notes ...) + meta + payload + history + attachments ...

4. Create/Edit/Update lock (file or redis)

5. Change ticket reporter to relation

6. Maqola : fix author, editor/owner, profiles/authors ...etc

**A : To create one large index for all entries across all spaces ...**

- key is uuid (or first 8 chars) : uuid:872343

- slug

- space_name

- subpath

- resource_type

- schema_shortname

- shortname

**B : To loop over all existing indexs and search by @uuid: 2343423-\_ ... @slug: xxxx**

- Get list of all spaces, and search in the meta index only for each space.

- After matching, use internal "entry api" and return the response

- One index for all entries

- All meta data

- Payload schema_shortname / type

- Payload_body : single text blob

- Attachments_payload? : (use multivalue fields)

- Uuid : should be unique across all entries

- Key : entries:space:subpath:shortname:type? (what about attachments? should they be included within?)

- Url_shortname / slug : unique entry short name across all system. we can use the uuid hash instead

- With proper/usual security support

- Extend shortname regex to include arabic alpha numerals + kasheeda

- Enable (again) sha1 on payload body

- Enable sha1 hash on history changes to guarantee change order

- Ability to export one or group of entries in a zip file (simply collecting all relevent files under the zip file)

- Create a schema definition for the combined meta data, to make it easy to validate meta.

---

**Future improvements**

- Consider providing GraphQL Api interface.

- There are several options for supporting GraphQL on FastApi

- Break the /xx/query api to multiple queries each for the respective type.

- Break the /xx/request api to multiple mutations

- Support file upload (already supported by one or more Fastapi compatible graphql libraries)

- Support websocket subscription (this can very well deprecate our websocket logic)

- Consider providing data-at-rest encryption that can only be accessed / viewed (decrypted) by the owner or a member of owner group.
