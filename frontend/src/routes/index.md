<script lang="ts">
  import { Col, Container, Row } from "sveltestrap";
  import Icon from "@/components/Icon.svelte";

</script>
<!--Container fluid={true} class="pt-4 ps-4 pe-4"-->
<Row><Col>

> #### What is DMART?
> DMART is an open-source general-purpose low-code data platform that is capable of assimilating and servcing a wide variety of data.
> DMART offers a number of unique features that simplify the setup of your backend.

----

##### <Icon name="stars" class="text-success m-2 fs-2" /> Features

- Unified API (Data-as-a-Service) that can readily and directly service Web and mobile frontends. OpenAPI-compatible [JSON API](https://api.dmart.cc/docs)
- Built-in user management
- Built-in security management (Permissions and Roles)
- Web-based admin management UI
- Extensible by plugins or micro-services (leveraging JWT)
- Licensed as free / open source software (AGPL3+). 

----

##### <Icon name="bank" class="text-danger m-2 fs-2" /> Design principals

- Entry-based, business-oriented data definitions (no need for relational modeling and physical RDBMS table structure).
- Entries are extensible by meta-data and arbitrary attachments
- Entries and attachments can involve structured, unstructured and binary data
- Entry changes are tracked for auditing and review : Who, when and what
- Entries are represented using file-based Json that is optionally schema-enabled
- Operational store that can be reconstructed from the file-based data.

</Col><Col>


##### <Icon name="briefcase" class="text-warning m-2 fs-2" /> Usecases

One initial category of usecases targets organizations and individuals to establish their online presence: Provision a website that is indexed by search engines, manage users, be able to recieve/send messages/emails and allow users to ineract with published content. 

[Universal online presnce](/presence_usecases)

----

##### <Icon name="airplane-engines" class="text-primary m-2 fs-2" /> Technology stack

###### Backend

- Programming language : Python 3.11 (latest revision)
- Microframework : FastAPI (microframework for python) with full leverage of async programming paradigm
- API validation : Pydantic v2 (rust-based)
- Live-update : Web socket
- Operational store : Redis 7.2.x with RediSearch 2.8.x and ReJson 2.6.x modules (based on C/C++ and rust)
- Viewing logs and building dashboards (optional): Grafana/Loki/Promtail (based on golang)
- Container : Podman (or Docker) for fast setup using light-wieght Alpine linux and OpenRC.
- System/User level OS service management : Systemd.
- Reverse-proxy : Caddy (with automatic SSL/Let's encrypt integration)

###### Frontend

- Single-Page-Application : Svelte with Typescript (compiled as static files)
- CSS/UI framework : Bootstrap 5.3 with full RTL support

###### High-quality code

- Heavy leverage of type hinting
- Automated tests via pytest and curl (curl.sh) tests
- Full compliance with pyright, ruff and mypi (pylint.sh)
- Load testing with locust vegeta ab appache

</Col></Row><!--/Container-->
