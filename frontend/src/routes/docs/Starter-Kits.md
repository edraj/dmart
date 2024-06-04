### **Starter Kits**

---

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
