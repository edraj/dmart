### Target Providers

DMART caters to a variety of users and organizations looking to establish their online presence or manage their data efficiently. The platform is designed to be flexible and adaptable to the needs of different providers, including:

**Individuals**

- **Content Creators and Influencers:** Individuals who produce content such as blogs, videos, and social media posts.
- **Self-Run Service Providers:** Professionals like tutors, doctors, and consultants who offer their services independently.

**Small Businesses**

- **Restaurants and Shops:** Local businesses looking to manage their inventory, take orders, and engage with customers online.
- **Healthcare Providers:** Clinics and individual practitioners who need to manage patient records and appointments.
- **Educational Providers:** Schools, tutors, and educational institutions that need to manage courses, students, and educational content.

**NGOs and SIGs**

- **Non-Governmental Organizations (NGOs):** Organizations focused on social, environmental, or humanitarian efforts.
- **Special-Interest Groups (SIGs):** Groups formed around shared interests, such as sports clubs, political parties, and community organizations.
- **Non-Profits:** Organizations that operate on a non-profit basis to achieve specific goals or support causes.

**Core Features for Target Providers:**

- **Content Management System (CMS):** Organize and publish content, including posts and pages.
- **Messaging:** Internal and external messaging via email with thread support.
- **Personal Profile and Posts:** Manage personal information and publish posts within a protected or public space.
- **User Interaction:** Engage with content through comments, reactions, and shares.
- **Digital Assets and Knowledge-Base:** Manage and access various data assets like HR records, customer data, tasks, and more.
- **Collaboration Sections:** Forums, polls, planned activities, and contact forms.
- **Notifications:** Real-time notifications via streaming (WebSockets) with options to mark as read or delete.
- **Root/Directory Services:** Announce and index public information about DMART instances, spaces, and public content.

### Starter Kits

A Starter Kit in DMART is a set of definitions and custom code that resides as a layer above DMART, preparing the system to serve a particular use case. The starter kit simplifies the onboarding process and helps users quickly set up their DMART environment tailored to their specific needs.

**Purpose of a Starter Kit:**

- **Customization:** Provides a tailored environment setup based on the user's specific requirements.
- **Efficiency:** Streamlines the setup process, reducing the time and effort required to configure the system.
- **Scalability:** Allows for easy modifications and updates as the user's needs evolve.

**Components of a Starter Kit:**

- **Folder Hierarchy:** Defines the structure and organization of folders within the DMART space.
- **Entry Definitions (Schema):** Specifies the data models and schemas to be used for different types of entries.
- **Pages:** Includes Svelte/MDSvex pages for the frontend interface.
- **Custom Plugins:** Adds functionality specific to the user's requirements.
- **Initial Content:** Provides sample or seed data to populate the system.
- **Theme Packs:** Defines the look and feel of the user interface.

**On-Boarding Process:**

1.  **Collect Answers from the Provider:** Gather information about the provider's needs and preferences.
2.  **Generate the Layer:** Create a customized layer above DMART based on the collected information.
3.  **Change Management:** Maintain the generated layer under a change management system like Git.

**Example Use Case for a Starter Kit:**

- **E-commerce Platform:**
  - **Folder Hierarchy:** Set up folders for products, orders, and customer information.
  - **Entry Definitions:** Define schemas for product listings, order details, and customer profiles.
  - **Pages:** Create pages for product browsing, order placement, and customer account management.
  - **Custom Plugins:** Add plugins for payment processing, inventory management, and order tracking.
  - **Initial Content:** Populate the system with sample product listings and customer data.
  - **Theme Packs:** Apply a theme pack that aligns with the brand's aesthetics.
