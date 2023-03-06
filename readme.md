# Data Mart (D-MART)

A structure-oriented information management system (aka Data-as-a-Service DaaS).

DMART is a Content Registry/Repository that is able to assimilate various types of data (structured, unstructured and binary).

## Top highlights ...

- Ability to serve an arbitrary number of applications. Unlike classical data layers, that are totally managed and eclipsed by the application running on top of it. DMART is designed to serve multiple applications at the same time (hence "Data as a Service")..

- One set of standardized API to interact with the different types of data in a unified way. Making it easier for the application developers to interact with. 

- Designed for maximum data longevity (time-proof) as all data is stored as flat-files directly on the file system. 

- Provides user-management and access control; elevating the burden from the application development. 

## Core concepts

- Each core informational unit is created as an entry. An entry is a Data asset that is made of meta data, optional schema-enabled data and attachments (binary and/or otherwise).

- Entries are organized in arbitrary category structure (folders) 

- Entries are indexed for fast search and retrival

- Entries can be optionally linked by "weak" links called relations.

## Architecture and technology stack

  - Flat-file design that leverages the file-system to establish the data organization/hierarchy through regular folders and actual data (entry-oriented and meta) through json files and binary files (media / documents).
  - Python 3.11 with emphasis on asyncio and type hinting
  - FastAPI as the api micro-framework 
  - Redis as the operational data store. With RediSearch RedisJSON modules.
  - Intensive json-based logging for insights.  
