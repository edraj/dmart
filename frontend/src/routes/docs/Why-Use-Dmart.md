# Why Use Dmart?

<img src="./docs/data-mart.jpg" width="500">


DMART is a data service layer that offers a streamlined / simplified way to develop certain class of solutions with small to medium data footprint (less than 300 million primary entries). It is not suited for systems that have large data nor systems that require heavily/complex related data modeling or requiring atomic operations (transactions).

DMART serves as general-purpose, structure-oriented information management system (aka Data-as-a-Service DaaS).

It represents a low-code information inventory platform (aka content registry/repository/vault) that is able to assimilate various types of data (structured, unstructured and binary). It allows you to treat your valuable data assets as commodity; where you can cleanly author, share and extend. Thus, valuable data assets can be maintained as the mastered version and act as the single source of truth. 

## The problem DMART attempts to solve

Valuable information (organizational and personal) is getting out of control!

- Dispersed over too many systems, requiring multiple access contexts.
- Difficult to consolidate and link for consumption, insights, reporting and dashboards
- Locked to vendors or application-specific data-formats
- Chaotic and hard to discover / search the data piling up over the years
- Difficult to master, dedup, backup, archive and restore.
- Difficult to protect and secure

## Top highlights

### Data-as-a-Service 
Backbone data store where the data assets get declared and used across multiple applications and microservices. The data assets are declared in the logical and business representation rather than classical RDBMS (physical).

### Standardized API
Publicly-accessible unified api layer allowing interaction with the different types of data; and simplifying the work of application developers.

### Data longevity
Resilient and time-proof data storage, as data is stored in flat-files directly on the file system. This opens the door for easy access, inspection, validation, backup and change tracking. At any point in time, the redis index can be recreated from the flat-files.

### User management and access control
"Batteries included" to elevate the burden from application development. 

### Microservice friendly
Leveraging JWT shared secret, additional microservices can automatically leverage the user's session with dmart. There is also a compatible FastApi skeleton git repository to facilitate the development of additional microservices.

### Extensible via plugins 
Specialized logic (plugins) can be added to react to certain types of activities and content.

### Entry-oriented 
As opposed to document-oriented NoSQL, entry-orientation revolves around consolidating the coherent information unit alongside its belongings (known as "attachments" that can involve textual and/or binary) as one entry. 

### Activities and workflows 
Configurable activity (ticket) and workflow management. 

### Messaging and notifications 
Ability to trigger different types of notifications and ability to store user messages.
