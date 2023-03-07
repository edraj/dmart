# Data Mart (D-MART)

A structure-oriented information management system (aka Data-as-a-Service DaaS).

DMART is a Content Registry/Repository that is able to assimilate various types of data (structured, unstructured and binary).

## Top highlights ...

- **Data-as-a-Service** : Backbone data store where the data assets get declared and used across multiple applications. The data assets are declared in the logical and business representation rather than classical RDBMS (physical). 
- **Standardized API** : Publicly accessible unified api layer to interact with the different types of data, simplifying the work of application developers.
- **Data longevity** : Time-proof data storage as data is stored in flat-files directly on the file system. This opens the door for easy access, inspection, validation, backup and change tracking. 
- **User management and access control** : "Batteries included" to elevate the burden from the application development. 

## Core concepts

- Each coherent information unit (data asset) is declared as **entry**. 
- An entry includes all related information (meta, structured, textual and binary) 
- Entries are organized within arbitrary category structure (folders) 
- Entries are indexed for fast search and retrieval.
- Entries can be optionally linked by "weak" links (aka relations).
- Changes on entries are recorded for audit and tracking.

## Architecture and technology stack

  - flat-file data persistence on standard file-system. Using folders, json, text and binary (media/documents) files. 
  - Python 3.11 with emphasis on asyncio and type hinting
  - FastAPI as the api micro-framework 
  - Redis as the operational data store. With RediSearch RedisJSON modules.
  - Intensive json-based logging for easier insights.  
