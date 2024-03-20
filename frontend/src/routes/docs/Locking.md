# Locking

In Dmart, "Locking" refers to a mechanism that restricts access to a data entity or resource within a Space to prevent simultaneous modifications by multiple users. Locking ensures data integrity and consistency by allowing only one user to modify the data entity at a time, thereby preventing conflicts and data inconsistencies.

## Purpose of Locking

1. **Data Integrity**: Locking ensures data integrity by preventing concurrent modifications to a data entity by multiple users. By restricting access to the data entity, locking helps maintain consistency and coherence in the data stored within a Space.

2. **Concurrency Control**: Locking facilitates concurrency control by managing access to shared resources within a Space. By acquiring locks on data entities, users can control access and prevent concurrent modifications that may lead to data corruption or inconsistency.

3. **Collaborative Editing**: Locking supports collaborative editing scenarios where multiple users may need to access and modify the same data entity. By acquiring locks on the data entity, users can coordinate their editing activities and prevent conflicts or data overwrite situations.

## Key Features of Locking

1. **Exclusive Locks**: Dmart supports exclusive locks, which allow only one user to acquire a lock on a data entity at a time. Exclusive locks prevent other users from accessing or modifying the data entity until the lock is released by the user holding the lock.

2. **Lock Management**: Dmart provides tools for lock management, allowing users to acquire, release, and manage locks on data entities within a Space. Users can acquire locks when accessing data for modification and release locks after completing their modifications to allow other users to access the data.

3. **Timeout Mechanism**: Dmart includes a timeout mechanism for locks to prevent indefinite blocking of access to data entities. If a user fails to release a lock within a specified timeout period, the lock is automatically released to allow other users to access the data entity.

## Use Cases for Locking

1. **Data Modification**: Locking is used when users need to modify data entities within a Space to prevent concurrent modifications that may lead to data inconsistency. Users acquire locks on data entities before making modifications and release locks after completing their modifications to ensure data integrity.

2. **Collaborative Editing**: Locking supports collaborative editing scenarios where multiple users may need to edit the same document or data entity simultaneously. By acquiring locks on the data entity, users can coordinate their editing activities and prevent conflicts or data overwrite situations.

3. **Batch Processing**: Locking is used in batch processing scenarios where multiple users or processes may access and modify data entities within a Space. By acquiring locks on data entities before processing, users can ensure that data modifications are performed sequentially to prevent conflicts and ensure data consistency.

4. **Critical Operations**: Locking is employed for critical operations or transactions that require exclusive access to data entities within a Space. By acquiring locks on data entities, users can ensure that critical operations are executed atomically and reliably, without interference from concurrent operations.


## Acquire a lock
You can lock an entry using the API
PUT `/managed/lock/{resource_type}/{space_name}/{subpath:path}/{shortname}`.

The lock will be released automatically after your first update action.

You can explicitly release the lock using the API
DELETE `/managed/lock/{resource_type}/{space_name}/{subpath:path}/{shortname}`

