<script>

  import BACKEND from "./assets/backend.png";
</script>

<style>
.center {
  display: block;
  margin-left: auto;
  margin-right: auto;
  width: 50%;
}

.bg-img {
background-image: url('./assets/features1.jpg');
	background-size: cover;
	width: 100%;
	height: 529px;

}

.bg-img h2 {	margin-left: 2em;
	margin-top: 0em;
	padding-top: 172px;
	font-size: 51px;
	font-weight: 800;
	letter-spacing: 1.5px;

}
.bg-img2 {
background-image: url('./assets/design.jpg');
	background-size: cover;
	width: 100%;
	height: 529px;
margin-bottom: 2em;
}
.bg-img2 h2 {	margin-left: 2em;
	margin-top: 0em;
	padding-top: 172px;
	font-size: 51px;
	font-weight: 800;
	letter-spacing: 1.5px;

}

.bg-img3 {
background-image: url('./assets/tech_stack.png');
	background-size: cover;
	width: 100%;
	height: 529px;
margin-bottom: 2em;
}

.bg-img3 h2 {	
	margin-left: 1.3em;

	padding-top: 113px;
	font-size: 50px;
	font-weight: 800;
	letter-spacing: 1.5px;


}
</style>

<div class=bg-img>
<h2> Features of DMART</h2>

</div>

<!-- <div style="float:right; width:12%; padding-left:10px; border-left:1px solid gray;">
    <h3>Table of Contents</h3>
    <ul>
        <li><a href="#features-of-dmart">Features of DMART</a></li>
        <li><a href="#design-principles">Design Principles</a></li>
        <li><a href="#technology-stack">Technology Stack</a></li>
    </ul>
</div> -->

---

**Unified API (Data-as-a-Service)**

- **Description:** DMART provides a unified API that can directly service web and mobile frontends. The API is OpenAPI-compatible and uses JSON, facilitating easy integration and data exchange.

- **Benefits:** Simplifies the development process by providing a single API for all data interactions, ensuring consistency and ease of use.

**Built-in User Management**

- **Description:** DMART includes comprehensive user management features, allowing for easy user registration, authentication, and role management.

- **Benefits:** Reduces the need for additional user management systems, streamlining development and improving security.

**Built-in Security Management (Permissions and Roles)**

- **Description:** Security management in DMART includes permission and role-based access control, ensuring that users have appropriate access to data and functionality.

- **Benefits:** Enhances security by providing granular control over user access and actions within the system.

**Extensibility by Plugins or Micro-Services**

- **Description:** DMART is extensible through plugins or micro-services, leveraging JWT (JSON Web Tokens) for secure communication.

- **Benefits:** Allows for customization and extension of DMART's capabilities to meet specific business needs.

---

<div class=bg-img2>
<h2> Design Principles</h2>

</div>

**Entry-Based Business-Oriented Data Definitions**

- **Description:** DMART uses entry-based data definitions, eliminating the need for complex relational modeling and physical RDBMS table structures. Entries are extensible by metadata and can include structured, unstructured, and binary data.

- **Benefits:** Simplifies data management and enhances flexibility, allowing for easy adaptation to various business requirements.

**Operational Store and Reconstruction**

- **Description:** Data in DMART is stored in a file-based JSON format, enabling the operational store to be reconstructed from the file-based data. Changes to entries are tracked for auditing and review.

- **Benefits:** Ensures data integrity and provides a robust mechanism for auditing and data recovery.

**Federation and Inter-Operation**

- **Description:** DMART supports federated inter-operation, similar to the email (SMTP) concept, allowing different DMART instances to interact with each other. This includes messaging, content interaction (comments, reactions, shares), and user management.

- **Benefits:** Facilitates collaboration and data sharing across different DMART instances, enhancing the platform's versatility and reach.

---

<div class=bg-img3>
<h2> Technology  <br/> Stack</h2>

</div>

<img class="center" src={BACKEND} width="300">

**Backend Technologies**

- **Programming Language:** Python 3.11 (latest revision)

- **Benefits:** Utilizes the latest features and improvements in Python, ensuring modern and efficient code.

- **Microframework:** FastAPI

- **Description:** FastAPI is a modern, fast (high-performance), web framework for building APIs with Python 3.6+ based on standard Python type hints.

- **Benefits:** Full leverage of the async programming paradigm, providing high performance and concurrency.

- **API Validation:** Pydantic v2 (Rust-based)

- **Benefits:** Ensures data validation and parsing using a high-performance data validation library.

- **Live-Update:** WebSocket

- **Benefits:** Enables real-time communication between the server and clients, facilitating instant updates and interactions.

- **Operational Store:** Redis 7.2.x with RediSearch 2.8.x and ReJSON 2.6.x modules

- **Description:** Redis is an in-memory data structure store used as a database, cache, and message broker.

- **Benefits:** Provides fast data access and complex query capabilities with RediSearch and ReJSON modules.

- **Logging and Dashboards (Optional):** Grafana, Loki, and Promtail (based on GoLang)

- **Benefits:** Offers powerful tools for visualizing logs and building real-time dashboards.

- **Containerization:** Podman (or Docker) using lightweight Alpine Linux and OpenRC

- **Benefits:** Facilitates fast setup and deployment of the DMART environment in isolated containers.

- **System/User Level OS Service Management:** Systemd

- **Benefits:** Provides efficient and powerful service management for maintaining the DMART backend.

- **Reverse-Proxy:** Caddy (with automatic SSL/Let’s Encrypt integration)

- **Benefits:** Simplifies reverse proxy setup with automatic HTTPS and SSL certificate management.

**Frontend Technologies**

- **Single-Page Application Framework:** Svelte with TypeScript

- **Benefits:** Svelte is a modern framework that compiles to highly optimized JavaScript, ensuring fast and responsive user interfaces.

- **CSS/UI Framework:** Bootstrap 5.3 with full RTL support

- **Benefits:** Provides a comprehensive set of styles and components for building responsive and accessible user interfaces, including right-to-left language support.
