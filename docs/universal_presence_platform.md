## Universal online presence platform

The objective of this platform is to help customers establish their organisational or personal online presence. I.e. Ability to have a website, use messaging, digital assets and collaboration.

In otherwords, this is a simple platform that combines a number of features to cover the intial and generic needs of becoming available online.

### Design principles

1. Manage complexity through generalisation. We tend to write reasonabily gneric code base that allows the user to deal with a larger variety of needs.
2. Flat-file, json-based schema enabled meta-data enriched extensible data store with unified api with discovery. This is essentially accomplished by the DMART engine.
3. Borrow concepts or protocols from similar systems where applicable.
4. Federated node/instance/domain setup. This is similar to Email (smtp) concept, but applied additionally to content managment and interactions. Where each individual setup (aka node, instance, domain) of this system can interact with another setup. E.g. Messaging, Content interaction (comment, react, share), Follow, ...etc. Each setup manages their own user base. I.e. a user must always belong to a valid setup for them to interact and use the system (apart from public read-only view of course).


### Core features

1. Content Management System to organize and publish content such as Posts (including rich media like Videos, Audio, Images ...) and pages (within any desired hirarchy) such as About, Contact, ...etc.  
2. Messages : internal and external messages via email (postfix) with tread-support. This combines chat with email in a simplified messaging presentation. 
3. Personal Profile : User's own data + Bio/public contact.
4. Personal Posts : within their personal space under protected or public as they desire.
5. Personal Timeline (aka news feed) : with ability to follow specific dmart_instance_domain:space:subpath (default `__all_spaces__` and `__all_subpaths__`). The feeds/updates coming from various sources are then merged into one feed that is displayed in the timeline. This is similar to RSS feed aggregator.
6. User interaction with all entries. A user can interact with content (per allowed permissions) to do Comments / Reactions / Share ...etc
7. Digital assets / Knowledgebase : This is the actual entries in Dmart … The entries could be any thing: HR/Employee, CRM/Customer, Tasks, Activities, Reminders, Invoices, Contacts, Orders, Topics, Posts, Books ... etc. The assets are accessible directly from the CMS pages and are dsiplayable in list and expanded formats.
8. Collaboration sections: Forums, Polls, Planned activities, Contact us …
9. Notifications : View, tune (streaming / websockets), Mark as read, delete. 
10. Root/Directory services (dmart sphere) : Announce and index public information about dmart instances (aka nodes), spaces and public content in them. The directory service is a dmart instance itself but specialises at holding public information about other instances. Each new node should be registered with a unique name (shortname), description and tags. Then the public spaces within that node are automatically indexed / crawled. 

