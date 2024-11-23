<script>

  import CLI from "./assets/cli.png";
</script>

<style>
.center {
  display: block;
  margin-left: auto;
  margin-right: auto;
  width: 50%;
}
</style>

### **Command Line Interface Tool**

---

**Overview**

DMART comes with a command line tool that can run from anywhere. It communicates with DMART over the api.

**Key Features:**

- Interactive command prompt with auto-completion.
- Manage spaces and resources within spaces.
- Upload and manipulate schemas, folders, and files.
- Execute commands in REPL, CMD, or SCRIPT mode.

**Setup and Dependencies**

**Requirements:**

- Python 3.6+
- Dependencies listed in requirements.txt

**Install Dependencies:**

```bash
pip install -r requirements.txt

```

**Environment Configuration:**

Create a config.ini file or set the environment variable BACKEND_ENV to point to your configuration file.

**Command Reference**

**General Commands**

- _help_: Displays the help table.
- _pwd_: Prints the current subpath.
- _cd folder_: Changes the current directory.
- _ls folder_: Lists entries under the current subpath.
- _create folder folder_name_: Creates a new folder in the current space.
- _attach args_: Attaches a file to a resource.
- _upload csv args_: Uploads a CSV file to the current space.
- _upload schema args_: Uploads a schema to the current space.
- _request args_: Adds or manages a resource in the space.
- _move args_: Moves a resource to a new location.
- _rm shortname_: Deletes a resource or attachment.
- _progress args_: Progresses a ticket into a new state.
- _switch space_name_: Switches the current space.

**Usage Examples**

**Starting the CLI**

```bash
./dmart_cli.py
```

**Running a Command**

```bash
./dmart_cli.py c "create folder new_folder"

```

**Using the REPL**

```bash

./dmart_cli.py
❯ ls
❯ create folder new_folder

```

**Other Example Usage**

```bash
cd cli

# Create config.ini with proper access details (url, credentials ...etc)
cp config.ini.sample config.ini

# Install additional packages
pip install --user  -r requirements.txt

# Start the cli tool
./cli.py
```

<img class="center" src={CLI} width="450">

**Conclusion**

This tool is a powerful interface for managing resources on the server. With its interactive prompt, command auto-completion, and robust set of commands, it simplifies the management of spaces and resources.

```

```
