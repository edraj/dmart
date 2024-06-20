### **Operational Database**

---

**1) Redis [Optional Operation DB]**

While dmart likely has a primary data storage mechanism, Redis can be optionally integrated as a secondary operational database. Redis is a high-performance in-memory data store that excels in caching, real-time data processing, and leaderboards. Integrating Redis can potentially enhance performance for specific use cases within your dmart application.

- **Enable/Disable:**

This module offers functionalities for managing the activation state of various features or functionalities within dmart. You can selectively enable or disable modules based on your application's requirements.

- **Search:**

The search module empowers users to efficiently locate specific data assets within your dmart application. It allows for full-text search capabilities, potentially including filtering and sorting options to refine search results.

- **Aggregation:**

The aggregation module enables you to perform calculations and summaries on your dmart data. This allows you to extract insights by grouping and processing data sets. For example, you could calculate total sales figures across different product categories.

**2) Manticore Search Database Module**

**Module Overview**

The `dmart` module leverages Manticore Search, a high-performance search engine, to manage data. Manticore Search excels at full-text search, real-time data processing, and aggregations, making it an ideal choice for dmart that require efficient data retrieval and analysis.

**Key Functionalities**

The `dmart` module offers a rich set of features:

- **Optional Integration:** While dmart likely has a primary data storage mechanism, Redis can be optionally integrated as a secondary operational database for caching and specific use cases.
- **Enable/Disable Modules:** This functionality allows you to selectively activate or deactivate specific features within dmart to suit your application's needs.
- **Full-Text Search:** The search module empowers users to locate data efficiently using full-text search capabilities. It might also include filtering and sorting options to refine results.
- **Data Aggregation:** The aggregation module enables you to perform calculations and summaries on your data, allowing you to extract insights by grouping and processing data sets.

**Data Operations**

The `dmart` module provides functions for various data operations:

- **Creation:** These functions handle creating and storing data within Manticore Search. This includes preparing data documents, assigning keys, and saving them to the database.
- **Retrieval:** Functions for querying and retrieving data are implemented, allowing you to search, filter, and find specific data based on various criteria.
- **Locking, Altering, and Deletion:** These functions manage data modification and deletion. They enable features like locking data for exclusive access, updating existing data, and removing data from the database.
- **Schema and Indexing:** Functions for creating tables (collections) and indexes within Manticore Search are provided. This optimizes data access and search performance.
