<script>
    import Logo from "./assets/data-mart.jpg";
</script>

<style>
.center {
  display: block;
  margin-left: auto;
  margin-right: auto;
  width: 50%;
}
</style>

**Why Choose DMART?**
<img class="center" src={Logo} width="500">

DMART serves as a data service layer, offering a streamlined approach for developing specific types of solutions with a moderate data footprint (less than 300 million primary entries). It is not tailored for systems handling large datasets or those necessitating complex data modeling or atomic operations (transactions).

Functioning as a versatile, structure-oriented information management system, DMART is commonly referred to as Data-as-a-Service (DaaS). It functions as a low-code information inventory platform, akin to a content registry, repository, or vault. DMART facilitates the ingestion of various data types (structured, unstructured, and binary), allowing users to treat their valuable data assets as commodities. This enables seamless authoring, sharing, and extension of data, ensuring that valuable assets remain as the mastered version and serve as the definitive source of truth.

**The Problem DMART attempts to solve**

Organizational and personal information is increasingly becoming unwieldy:

- Fragmented across numerous systems, necessitating multiple access points.
- Challenging to consolidate and link for consumption, analysis,
  reporting, and dashboard creation.
- Locked into vendor-specific or application-specific data formats.
- Chaotic and challenging to search through the accumulated data.
- Difficult to master, deduplicate, back up, archive, and restore.
- Prone to security vulnerabilities.

**Key Features of DMART**

**Data-as-a-Service (DaaS):** DMART acts as a backbone data store where data assets are declared and utilized across multiple applications and microservices, represented in logical and business terms rather than traditional RDBMS formats.

**Standardized API:** A publicly-accessible unified API layer simplifies interaction with various types of data, streamlining the work of application developers.

**Data Longevity:** Data is stored in flat-files directly on the file system, ensuring resilient and time-proof storage. This enables easy access, inspection, validation, backup, and change tracking, with the capability to recreate the Redis index from the flat-files at any point.

**User Management and Access Control:** DMART includes comprehensive user management and access control features to alleviate the burden from application development teams.

**Microservice Friendly:** Leveraging JWT shared secrets, additional microservices can seamlessly leverage user sessions with DMART. Additionally, a compatible FastAPI skeleton Git repository facilitates the development of additional microservices.

**Extensibility via Plugins:** Specialized logic (plugins) can be incorporated to respond to specific types of activities and content.

**Entry-Oriented Approach:** Unlike document-oriented NoSQL databases, DMART focuses on consolidating coherent information units alongside their associated assets (known as "attachments"), whether textual or binary, into a single entry.

**Activities and Workflows:** DMART offers configurable activity (ticket) and workflow management capabilities.

**Messaging and Notifications:** Users can trigger various types of notifications and store user messages within DMART.
