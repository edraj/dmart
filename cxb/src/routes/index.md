<script lang="ts">
import {StarSolid,FolderSolid,BriefcaseSolid,LayersSolid,CubeSolid} from 'flowbite-svelte-icons';
</script>
<div class="prose">
<div class="flex flex-row" style="width: 98vw">
<div class="flex-col p-6">

# What is DMART?
> DMART is an open-source general-purpose low-code data platform that is capable of assimilating and servcing a wide variety of data.
> DMART offers a number of unique features that simplify the setup of your backend.

----

# <span class="flex"><StarSolid class="mx-2" size="xl"/>Features</span>

- Unified API (Data-as-a-Service) that can readily and directly service Web and mobile frontends. OpenAPI-compatible [JSON API](https://api.dmart.cc/docs)
- Built-in user management
- Built-in security management (Permissions and Roles)
- Web-based admin management UI
- Extensible by plugins or micro-services (leveraging JWT)
- Licensed as free / open source software (AGPL3+).

----

# <span class="flex"><FolderSolid class="mx-2" size="xl"/> Design principals</span>

- Entry-based, business-oriented data definitions (no need for relational modeling and physical RDBMS table structure).
- Entries are extensible by meta-data and arbitrary attachments
- Entries and attachments can involve structured, unstructured and binary data
- Entry changes are tracked for auditing and review : Who, when and what
- Entries are represented using file-based Json that is optionally schema-enabled
- Operational store that can be reconstructed from the file-based data.

----

# <span class="flex"><CubeSolid class="mx-2" size="xl"/> Drivers</span>

- Python: [pydmart](https://pypi.org/project/pydmart/)
- Flutter/Dart: [dmart](https://pub.dev/packages/dmart)
- Typescript: [@edraj/tsdmart](https://www.npmjs.com/package/@edraj/tsdmart)

</div>
<div class="flex-col p-6">


# <span class="flex"><BriefcaseSolid class="mx-2" size="xl"/> Usecases</span>

One initial category of usecases targets organizations and individuals to establish their online presence: Provision a website that is indexed by search engines, manage users, be able to recieve/send messages/emails and allow users to ineract with published content.

[Universal online presnce](/presence_usecases)

----

# <span class="flex"><LayersSolid class="mx-2" size="xl"/> Technology stack</span>

## Backend

- Programming language : Python 3.13 (latest revision)
- Microframework : FastAPI (microframework for python) with full leverage of async programming paradigm
- API validation : Pydantic v2 (rust-based)
- Live-update : Web socket
- Operational store : PostgreSQL 16
- Viewing logs and building dashboards (optional): Grafana/Loki/Alloy (based on golang)
- Container : Podman (or Docker) for fast setup using light-wieght Alpine linux and OpenRC.
- System/User level OS service management : Systemd.
- Reverse-proxy : Caddy (with automatic SSL/Let's encrypt integration)

----

## Frontend

- Single-Page-Application : Svelte with Typescript (compiled as static files)
- CSS/UI framework : Flowbite with Tailwind and full RTL support

----

## High-quality code

- Heavy leverage of type hinting
- Automated tests via pytest and curl (curl.sh) tests
- Full compliance with pyright, ruff and mypi (pylint.sh)
- Load testing with locust vegeta ab appache

</div>
</div>
</div>
