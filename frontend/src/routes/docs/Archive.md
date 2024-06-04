### **Archive**

---

This script is designed to archive records from a specific space, subpath, and schema within a data management system.

**Functionality**

- Moves payload files and related metadata folders from the active storage location to an archive folder.
- Deletes the corresponding payload and metadata documents from the Redis database.

**Arguments**

- `space` (str): The name of the space containing the records to archive.
- `subpath` (str): The subpath within the space to target.
- `schema` (str, optional): The schema name to archive. Defaults to "meta" if not provided. In this case, all schemas within the subpath will be archived.
- `olderthan` (int): The number of days older than which records will be archived, based on the `updated_at` timestamp.

**How to Use**

1.  Save the script as `archive.py`.
2.  Ensure the script has executable permissions: `chmod +x archive.py`
3.  Run the script with the desired arguments:

Bash

```
./archive.py <space> <subpath> [<schema>] <olderthan>

```

**Example**

To archive all records older than 30 days from the space "finance" in the subpath "reports", run:

Bash

```
./archive.py finance reports olderthan=30

```
