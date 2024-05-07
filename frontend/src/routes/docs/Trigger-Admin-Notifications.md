## Trigger Admin Notifications

### Purpose:

The script `trigger_admin_notifications` is designed to trigger admin notifications based on requests stored in Redis. It searches for admin notification requests within a specific time range and sends notifications to designated receivers.

### Usage:

The script is intended to be executed as a standalone Python script. It can be run directly from the command line.

### Dependencies:

- Python 3
- `asyncio`
- `datetime`
- `json`
- `models.core`
- `utils.db`
- `utils.helpers`
- `utils.notification.NotificationManager`
- `utils.redis_services.RedisServices`
- `utils.repository`

### Execution:

To execute the script, run it using Python 3 from the command line:

bash

`python3 <script_filename>.py`

### Description:

1.  **Imports**:

    - The script imports necessary modules and libraries required for its functionality, including modules from custom packages and standard Python libraries.

2.  **Function: trigger_admin_notifications**:

    - This function retrieves admin notification requests from Redis within a specified time range.
    - It prepares notification requests for sending based on the retrieved data.
    - It sends notifications to designated receivers and updates the notification status to "finished" in the database.
    - If any errors occur during the process, they are logged for debugging purposes.

3.  **Function: prepare_request**:

    - This function prepares notification requests for sending by formatting the notification data and retrieving any associated images.
    - It constructs a dictionary containing information about the notification, including the title, body, images URLs, and notification types.

4.  **Main Execution**:

    - The script entry point checks if the script is being run directly and then executes the `trigger_admin_notifications` function using asyncio's `run` method.

### Notes:

- The script relies on asynchronous programming using `asyncio` to handle I/O-bound operations efficiently.
- It interacts with Redis to retrieve notification data and store notification status updates.
- Error handling is implemented to log any exceptions that occur during the execution of the script.
