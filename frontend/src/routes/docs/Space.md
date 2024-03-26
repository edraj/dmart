# Space

In Dmart, a "Space" refers to a logical partition or container within the system where data is organized, stored, and managed. 
Think of a Space as a workspace, environment, or even a database, dedicated to a specific set of data. 
The concept of Spaces helps in organizing and isolating data based on different criteria, such as departments, projects, teams, or data types.

## Purpose of Spaces
**1. Data Organization**: Spaces allow users to organize data in a structured manner, making it easier to manage and access relevant information. Each Space can represent a distinct category or domain of data within the system.

**2. Isolation and Security**: Spaces provide a level of isolation, ensuring that data within each Space is segregated and accessible only to authorized users. This helps in maintaining data privacy, confidentiality, and security.

**3. Collaboration**: Spaces facilitate collaboration among users working on the same project or within the same department. By sharing a common Space, team members can collaborate on data-related tasks, share insights, and exchange information seamlessly.


## Use Cases for Spaces
**1. Departmental Data Management:** Organizations can create Spaces for different departments, such as sales, marketing, finance, and human resources, to manage department-specific data effectively.

**2. Project-based Collaboration:** Teams working on specific projects or initiatives can utilize Spaces to collaborate on data-related tasks, share project artifacts, and track project progress.

**3. Data Integration and Aggregation:** Spaces can be used to integrate and aggregate data from multiple sources, providing a unified view of data for analysis and reporting purposes.

**4. Multi-tenancy Support:** In multi-tenant environments, Spaces can be used to segregate data belonging to different tenants, ensuring data isolation and tenant-specific customization.


## Space Configuration Attributes

- **indexing_enabled**: a boolean value to enable or disable the automatic loading of the space data to Redis, which enable/disable Redis search and aggregation
- **capture_misses**: a boolean value, which if enabled will record any requests to a not found entries under that space
- **check_health**: a boolean value, enables or disables scanning this space at the `/health-check` API. You can disable it for large spaces when you run the API to check the health of other space, this will make the API execution time much faster
- **languages**: a list of accepted languages 
- **hide_space**: a boolean value used to hide/show the space in spaces list API
- **active_plugins**: list of the plugins that should be triggered upon this space events
- **hide_folders**: list of subpaths shortnames you want to hide from the list of folders under this space in the UI
- **icon**: the bootstrap icon to be displayed in the UI


***Regarding the List, Create, Update, and Delete space, please refer to `Managed -> Spaces` section at the [Postman API Collection](https://www.postman.com/galactic-desert-723527/workspace/dmart/collection/5491055-c2a1ccd1-6554-4890-b6c8-59b522983e2f)***