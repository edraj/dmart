<script>
    import Permission from "./assets/create_permission.png";
     import Role from "./assets/create_role.png";
      import Schema from "./assets/create_schema.png";
       import User from "./assets/create_user.png";
         import AdminUI1 from "./assets/admin_ui_1.png";
  import AdminUI2 from "./assets/admin_ui_2.png";
        import Entry from "./assets/create_entry.png";
</script>

<style>
.center {
  display: block;
  margin-left: auto;
  margin-right: auto;
  width: 50%;
}
</style>

### **System Admin Tool (GUI)**

---

**Introduction**

The System Admin Tool (GUI) is a powerful administrative interface designed to facilitate the management of entries within a system. It provides system administrators with the ability to view, update, and delete entries based on their role and associated permissions. This tool serves as a centralized platform for accessing and manipulating data, similar to interacting with a database.DMART has a comprehensive Admin UI that interacts with the backend entirely via the formal API. It is built with Svelte, Routify3 and SvelteStrap.\

```bash
cd dmart/frontend
yarn install

# Configure the dmart server backend url in src/config.ts

# To run in Development mode
yarn dev

# To build and run in production / static file serving mode (i.e. w/o nodejs) using Caddy
yarn build
caddy run
```

**Building tauri binary (Linux AppImage)**

This allows packaging the admin tool as a desktop application.

```
# Regular build without inspection
yarn tauri build --bundles appimage

# To add inspection (right mouse click -> inspect)
yarn tauri build --bundles appimage --debug

```

<img class="center" src={AdminUI1}>
<img class="center" src={AdminUI2}>

**Key Features**

1.  **Entry Management**: System administrators can create, view, update, and delete entries within the system. This includes the ability to manage various types of entries such as content, tickets, and attachments.

2.  **Schema Definition**: The tool allows users to define schemas, which serve as templates for organizing and structuring data. Administrators can create custom schemas to suit the specific requirements of their organization.
3.  **Workflow Configuration**: Administrators can define workflows within the system, specifying the steps and processes required to complete tasks or resolve issues. Users can then create tickets associated with these workflows.

4.  **Role and Permission Management**: The tool provides functionality for defining new roles and permissions within the system. Administrators can assign roles to users, control their access levels, and manage permissions based on organizational requirements.
5.  **User Management**: Using the management space, administrators can create, activate, deactivate, update, and delete user accounts. This includes managing user information, roles, and permissions.
6.  **Application Configuration**: Administrators can manage various application settings and configurations within the system. This includes updating logs, translations, configurations, announcements, and other system-related parameters.

**Usage**

**Entry Management**
<img class="center" src={Entry} width="500">

1.  **View Entries**: Navigate to the appropriate space and folder to view existing entries within the system.
2.  **Create Entry**: Select the desired space and folder, then create a new entry by providing relevant details and attachments.
3.  **Update Entry**: Edit existing entries by selecting the entry to be updated and modifying its content or attachments as needed.
4.  **Delete Entry**: Remove entries from the system by selecting the entry and confirming the deletion action.

**Schema and Workflow Configuration**
<img class="center" src={Schema} width="500">

1.  **Define Schema**: Access the schema management interface to define new schemas tailored to specific data structures and requirements.
2.  **Configure Workflow**: Define workflows by specifying the sequence of steps and actions required to complete tasks or resolve issues.

**Role and Permission Management**
<img class="center" src={Permission} width="500">
<img class="center" src={Role} width="500">

1.  **Create Role**: Define new roles within the system by specifying their name, description, and associated permissions.
2.  **Assign Role**: Assign roles to users by selecting the user and assigning the desired role(s) from the available options.
3.  **Manage Permissions**: Control user access levels and permissions by modifying role assignments and permissions settings.

**User Management**
<img class="center" src={User} width="500">

1.  **Create User**: Add new users to the system by providing their details, including username, password, email, and role assignments.
2.  **Activate/Deactivate User**: Enable or disable user accounts based on organizational requirements.
3.  **Update User Information**: Modify user details, including contact information, roles, and permissions.
4.  **Delete User**: Remove user accounts from the system, optionally transferring or archiving their data as necessary.

**Application Configuration**

1.  **Update Logs**: Manage system logs to track and monitor system activity, errors, and performance metrics.
2.  **Manage Translations**: Update language translations for user interfaces and system messages.
3.  **Configure Settings**: Modify system configurations and parameters to customize the behavior and appearance of the application.
4.  **Publish Announcements**: Create and publish announcements to communicate important information or updates to system users.

**Conclusion**

The System Admin Tool (GUI) provides system administrators with a comprehensive set of tools for managing entries, schemas, workflows, roles, permissions, users, and application configurations within a system. By leveraging this intuitive interface, administrators can efficiently organize, control, and maintain system data and settings to meet the needs of their organization.
