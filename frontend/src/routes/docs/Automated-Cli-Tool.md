# CLI Tool

## Overview

The Dmart CLI tool provides an interactive command-line interface to manage and interact with a the server. It supports various commands to create, update, delete, and query resources on the server.

### Key Features:

- Interactive command prompt with auto-completion.
- Manage spaces and resources within spaces.
- Upload and manipulate schemas, folders, and files.
- Execute commands in REPL, CMD, or SCRIPT mode.

## Setup and Dependencies

### Requirements:

- Python 3.6+
- Dependencies listed in requirements.txt

### Install Dependencies:

bash

```
pip install -r requirements.txt
```

### Environment Configuration:

Create a config.ini file or set the environment variable BACKEND_ENV to point to your configuration file.

## Code Structure

### Main Components:

1. _Settings Configuration_: Manages application settings from environment variables.
2. _CLI Modes_: Different modes of running the CLI (REPL, CMD, SCRIPT).
3. _DMart Class_: Core functionalities for interacting with the DMart server.
4. _CustomCompleter_: Provides auto-completion for commands.
5. _Action Dispatcher_: Handles execution of various commands.
6. _Prompt Session_: Manages the interactive REPL session.

## Code Explanation

### Settings Class

Manages configuration settings for the DMart CLI.
python
class Settings(BaseSettings):
url: str = "http://localhost:8282"
shortname: str = "dmart"
password: str = "password"
query_limit: int = 100
retrieve_json_payload: bool = True
default_space: str = "management"
pagination: int = 5

    model_config = SettingsConfigDict(env_file=os.getenv("BACKEND_ENV", "config.ini"), env_file_encoding="utf-8")

### DMart Class

Provides methods to interact with the DMart server, including CRUD operations and authentication.
python

```
@dataclass
class DMart:
session = requests.Session()
headers = {"Content-Type": "application/json"}
dmart_spaces = []
space_names = []
current_space: str = settings.default_space
current_subpath: str = "/"
current_subpath_entries = []

    # Core API interaction methods
    def __dmart_api(self, endpoint, json=None):
        # Implementation...

    def create_content(self, endpoint, json):
        # Implementation...

    def delete(self, spacename, subpath, shortname, resource_type):
        # Implementation...

    def register(self, invitation):
        # Implementation...

    def login(self):
        # Implementation...

    def profile(self):
        # Implementation...

    def spaces(self):
        # Implementation...

    def query(self, json):
        # Implementation...

    def meta(self, resource_type, space_name, subpath, shortname):
        # Implementation...

    def payload(self, resource_type, space_name, subpath, shortname):
        # Implementation...

    def print_spaces(self):
        # Implementation...

    def list(self, folder_shortname):
        # Implementation...

    def get_mime_type(self, ext):
        # Implementation...

    def create_folder(self, shortname):
        # Implementation...

    def manage_space(self, spacename, mode: SpaceManagmentType):
        # Implementation...

    def create_entry(self, shortname, resource_type):
        # Implementation...

    def create_attachments(self, request_record: dict, payload_file):
        # Implementation...

    def upload_csv(self, subpath, schema_shortname, payload_file):
        # Implementation...

    def upload_schema(self, shortname, payload_file_path):
        # Implementation...

    def upload_folder(self, folder_schema_path):
        # Implementation...

    def move(self, resource_type, source_path, source_shortname, destination_path, destination_shortname):
        # Implementation...
```

### CustomCompleter

Provides auto-completion for commands and arguments.
python
class CustomCompleter(Completer):
def get*completions(self, document, *): # Implementation...

### Action Dispatcher

Executes commands based on user input.
python
def action(text: str): # Command parsing and execution logic

### Interactive Session

Manages the REPL session with prompt-toolkit.
python

```
if **name** == "**main**":
session = PromptSession(style=style, completer=CustomCompleter(), history=FileHistory(".cli_history"))

    if len(sys.argv) >= 2:
        # Handle CMD or SCRIPT mode
    else:
        while True:
            try:
                text = session.prompt([("class:prompt", "❯ ")], cursor=CursorShape.BLINKING_UNDERLINE, bottom_toolbar=bottom_toolbar, complete_in_thread=True, complete_while_typing=True)
                action(text)
            except (KeyboardInterrupt, EOFError):
                break
```

## Command Reference

### General Commands

- _help_: Displays the help table.
- _pwd_: Prints the current subpath.
- _cd <folder>_: Changes the current directory.
- _ls <folder>_: Lists entries under the current subpath.
- _create folder <folder_name>_: Creates a new folder in the current space.
- _attach <args>_: Attaches a file to a resource.
- _upload csv <args>_: Uploads a CSV file to the current space.
- _upload schema <args>_: Uploads a schema to the current space.
- _request <args>_: Adds or manages a resource in the space.
- _move <args>_: Moves a resource to a new location.
- _rm <shortname>_: Deletes a resource or attachment.
- _progress <args>_: Progresses a ticket into a new state.
- _switch <space_name>_: Switches the current space.

## Usage Examples

### Starting the CLI

bash

```
./dmart_cli.py
```

### Running a Command

bash

```
./dmart_cli.py c "create folder new_folder"

```

### Using the REPL

bash

```

./dmart_cli.py
❯ ls
❯ create folder new_folder

```

## Conclusion

The DMart CLI tool is a powerful interface for managing resources on a DMart server. With its interactive prompt, command auto-completion, and robust set of commands, it simplifies the management of spaces and resources.

```

```
