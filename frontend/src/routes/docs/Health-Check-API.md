* Health Check API:**

**Overview:** Health Check API is a Python script designed for conducting health checks on a system. The script is intended to evaluate the health and integrity of data stored . It supports two modes of operation: soft and hard health checks.

**Usage:** The script can be executed from the command line with various parameters to specify the type of health check, target space, target schemas, and branch.

**Command Line Arguments:**

-   `-t, --type`: Specifies the type of health check to perform. Valid options are "soft" or "hard".
-   `-s, --space`: Specifies the target space for the health check. "all" can be specified to perform a health check on all spaces.
-   `-b, --branch`: Specifies the target branch for the health check.
-   `-m, --schemas`: Specifies the target schemas within the space for the health check.

**Dependencies:**

-   `asyncio`: For asynchronous programming.
-   `argparse`: For parsing command line arguments.
-   `json`: For handling JSON data.
-   `os`, `shutil`, `sys`, `time`: For file and system operations.
-   `datetime`, `pathlib`: For handling date/time and file paths.
-   `jsonschema`: For validating JSON data against schemas.
-   External dependencies: `redis`, `api`, `models`, `utils`.

**Functionality:**

1.  **Soft Health Check (`soft_health_check`):**
    
    -   Performs a soft health check on the specified space and schema.
    -   Iterates through the documents in the specified space and validates them against the schema.
    -   Identifies valid and invalid entries, and collects relevant information.
    -   Reports the health check results including valid and invalid entries.
2.  **Hard Health Check (`hard_health_check`):**
    
    -   Performs a hard health check on the specified space.
    -   Validates the data structure and integrity of documents within the space.
    -   Reports any invalid folders or documents found during the check.
3.  **Main Function (`main`):**
    
    -   Coordinates the execution of soft or hard health checks based on user input.
    -   Handles command line arguments and executes the appropriate health check function.
    -   Prints the health check results including valid and invalid entries.
4.  **Utility Functions:**
    
    -   `print_header`: Prints the header for displaying health check results.
    -   `print_health_check`: Prints the detailed health check report including valid and invalid entries.
    -   `load_spaces_schemas`: Loads schemas for the specified space or all spaces.
    -   `save_health_check_entry`: Saves the health check results to a JSON file for the specified space.
    -   `cleanup_spaces`: Cleans up the health check entries and meta data.

