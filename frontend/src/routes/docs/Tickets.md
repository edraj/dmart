### **Concept of Tickets in Dmart**

---

In Dmart, "Tickets" represent units of work or requests submitted to the system for performing specific actions, such as data operations, system modifications, or user requests. Tickets serve as a means of communication and coordination between users and the system, enabling efficient management of tasks and activities within a Space.

**Purpose of Tickets**

1.  **Task Management**: Tickets provide a structured way to manage tasks and activities within a Space. Users can create tickets to request data operations, system modifications, or other tasks, enabling organized task tracking and execution.

2.  **Issue Tracking**: Tickets are used to track and manage issues, bugs, or errors encountered within the system. Users can create tickets to report issues, track their resolution progress, and ensure timely resolution of problems.

3.  **Request Handling**: Tickets facilitate request handling by providing a centralized mechanism for users to submit requests for data access, system configurations, or other services. Tickets streamline request processing, ensuring that user requests are handled efficiently and effectively.

**Key Features of Tickets**

1.  **Ticket Creation**: Users can create tickets to request specific actions or tasks within a Space. Ticket creation typically involves providing relevant details, such as the nature of the request, priority level, and any additional information needed to address the request.

2.  **Ticket Assignment**: Tickets can be assigned to specific users or teams responsible for handling the requested tasks. Assigning tickets ensures accountability and facilitates task allocation, enabling efficient task management and resolution.

3.  **Ticket Tracking**: Dmart provides tools for tracking the status and progress of tickets throughout their lifecycle. Users can monitor ticket status, view updates, and track resolution progress, ensuring transparency and visibility into task management activities.

**Ticket Attributes**

- **state**: the state of the ticket

- **is_open**: boolean value indicates if the ticket is still open or closed

- **reporter**: object of type Reporter

- **workflow_shortname**: the lifecycle of the ticket, client defined, check the Workflow section for more details

- **collaborators**: a map of the ticket collaborators, the key is the action and the value is the collaborator name

- **resolution_reason**: the rejection reason if the ticket is rejected

**Create a Ticket**

First you need to define the workflow of the ticket, please check the Workflow section for the details

```

{
    "space_name": "damrt_data",
    "request_type": "create",
    "records": [
        {
            "resource_type": "ticket",
            "shortname": "auto",
            "branch_name": "master",
            "subpath": "tickets",
            "attributes": {
                "is_active": true,
                "tags": [
                    "me"
                ],
                "payload": {
                    "content_type": "json",
                    "schema_shortname": "schema",
                    // Ticket body goes here
                    "body": {}
                },
                "is_open": true,
                "reporter": {
                    "type": "admin_lite",
                    "name": "Foo Bar",
                    "channel": "HQTest",
                    "distributor": "Doo",
                    "governorate": "",
                    "msisdn": "1111111111",
                    "channel_address": {}
                },
                "workflow_shortname": "workflow_101"
            }
        }
    ]
}

```
