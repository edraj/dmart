<script lang="ts">
  import { Col, Container, Row } from "sveltestrap";

</script>
<Container fluid={true} class="p-2">
<Row><Col>

> #### What is DMART?
> DMART is open-source general-purpose low-code data platform.
> 

----

##### Features

- Unified Api (Data-as-a-Service) that can readily and directly service Web and mobile frontends. (OpenApi-compatible JSON Api)
- Built-in user management
- Built-in security management (Permissions and Roles)
- Web-based admin management UI 
- Micro-service friendly (leveraging JWT)
- Extensible by plugins 

----

##### Design principals 

- Entry-based, only requiring business-level descriptions (definitions)
- Entries are extensible by meta-data and arbitrary attachments
- Entries and attachments can be structured, unstructured and binary data
- Entry changes are tracked for auditing and review : Who, when and what
- Entries are represented using file-based Json that is optionally schema-enabled
- Operational store can always reconstruct its index from the file-based data. 

</Col><Col>


#### Technology stack
----

##### Backend 

- Programming language : Python 3.11 (latest revision)
- Microframework : FastApi (microframework for python) with full leverage of async programming paradigm 
- Api validation : Pydantic v2 (rust-based)
- Live-update : Web socket 
- Operational store : Redis 7.2.x with RediSearch 2.8.x and ReJson 2.6.x modules (based on C/C++ and rust)
- Grafana/Loki/Promtail for viewing logs and building dashboards (based on golang)
- Container : Podman or Docker based option for fast setup using light-wieght Alpine linux
- Systemd : System/User level service management 
- Web proxy server : Caddy (with automatic SSL/Let's encrypt integration)

----

##### Frontend

- Sing-page-application : Svelte with Typescript (compiled as static files)
- CSS/UI framework : Bootstrap 5.3 with full RTL support

----

##### High quality code

- Heavy leverage of type hinting
- Automated tests via pytest and curl (curl.sh) tests
- Full compliance with pyright, ruff and mypi (pylint.sh)
- Load testing with vegeta


----

</Col></Row></Container>
