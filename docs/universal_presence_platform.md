## Universal Online Presence Platform

The objective of this platform is to enable users (aka providers) establish their organizational or personal online presence: The ability to publish a website, use messaging, maintain digital assets and collaborate with consumers ( regular users who are onboarded on the setup itself or coming from other installments of the platform - i.e. federated).

This is a simple platform that combines a number of features to cover the initial and generic needs of becoming available online.

### Target provider types

1. Individuals like content creators, influences, self-run service providers like doctors
2. Small businesses like restaurants, shops, healthcare, educational providers 
3. (Non-Government-Organizations) NGOs and (Special-Interest-Groups) SIGs like sports clubs, political parties, communities, non-profit.

### Design principles

1. **Low-code**: Manage complexity through generalization. We tend to write reasonably generic code base that allows the user to deal with a larger variety of needs.This gives more empowerment to the end user delivering a low-code productivity platform.
2. **Data as a Service**: Flat-file, json-based schema enabled meta-data enriched extensible data store with unified api with discovery. This is essentially accomplished by the DMART engine.
3. **Learn from the best**: Borrow concepts or protocols from similar systems where applicable.
4. **Federated inter-operation**. This is similar to Email (smtp) concept, but applied additionally to content management and interactions. Where each individual setup (aka node, instance, domain) of this system can interact with another setup. E.g. Messaging, Content interaction (comment, react, share), Follow, ...etc. Each setup manages their own user base. I.e. a user must always belong to a valid setup for them to interact and use the system (apart from public read-only view of course).


### Core features

1. **Content Management System**: to organize and publish content such as Posts (including rich media like Videos, Audio, Images ...) and pages (within any desired hierarchy) such as About, Contact, ...etc.
2. **Messages** : internal and external messages via email (postfix) with tread-support. This combines chat with email in a simplified messaging presentation. 
3. **Personal Profile** : User's own data + Bio/public contact.
4. **Personal Posts** : within their personal space under protected or public as they desire.
5. **Personal Timeline** (aka news feed) : with ability to follow specific dmart_instance_domain:space:subpath (default `__all_spaces__` and `__all_subpaths__`). The feeds/updates coming from various sources are then merged into one feed that is displayed in the timeline. This is similar to RSS feed aggregator.
6. **User interaction**: A user can interact with content (per allowed permissions) to do Comments / Reactions / Share ...etc
7. **Digital assets / Knowledge-base** : This is the actual entries in Dmart … The entries could be any thing: HR/Employee, CRM/Customer, Tasks, Activities, Reminders, Invoices, Contacts, Orders, Topics, Posts, Books ... etc. The assets are accessible directly from the CMS pages and are displayable in list and expanded formats.
8. **Collaboration sections**: Forums, Polls, Planned activities, Contact us …
9. **Notifications** : View, tune (streaming / websockets), Mark as read, delete. 
10. **Root/Directory services** (dmart sphere) : Announce and index public information about dmart instances (aka nodes), spaces and public content in them. The directory service is a dmart instance itself but specializes at holding public information about other instances. Each new node should be registered with a unique name (shortname), description and tags. Then the public spaces within that node are automatically indexed / crawled. 

### Starter kits

Based on the type of the provider and the answers collected during the on-boarding process, a parameterized template is used to construct the setup.

A starter kit (template) defines ...

1. Folder Hierarchy
2. Entry definitions (Schema)
3. Pages (Svelte/MDSvex)
4. Custom plugins
5. Initial content (sample / seed)
6. Theme packs (look and feel)

When the environment setup is completed, the provider can create and organize entries such as products, services, activities, and content. Consumers can consume and interact with the entries. An entry can optionally have a geo-context, so it is matched with the user's geo context (Country-level, City-level, Area-level, Global). Consumers can also initiate requests (like orders, requests, tickets ...etc).

