<script>
  import {QueryType} from "@/dmart";
  import ListView from "@/components/management/ListView.svelte";
  import Tree from "./assets/tree.png"
</script>
<style>
.center {
  display: block;
  margin-left: auto;
  margin-right: auto;
  width: 50%;
}
</style>

## Data Organization in Dmart

## Important terms

**Each term has a dedicated section with a detailed explanation**

- **Space**: Top-level business category that facilitates grouping of relevant content.
- **Subpath**: aka folder, The path within space that leads to an entry
- **Meta**: Meta information associated with the entry such as owner, shortname, unique uuid, creation/update timestamp, tags ..etc
- **Schema**: The JSON schema definition of the entry
- **Payload**: The actual content associated with the entry

<img class="center" src={Tree} width="500">

In DMart nodes, data is organized in a hierarchical structure to facilitate efficient management and access. This documentation outlines the data organization scheme within DMart nodes, focusing on [spaces](Space), [subpaths](Subpath) & folders, [entries](Entries), and [attachments](Attachments).

### Hierarchical Structure

At the top level of the data organization hierarchy are **spaces**. Spaces represent broad categories or business breakdowns of information groups. Each space serves as a container for organizing related data and resources.

### Components of Data Organization

#### Spaces

- **Definition:** Spaces are top-level containers that categorize and organize related information groups.
- **Purpose:** Spaces provide a high-level organizational structure for grouping similar data.
- **Characteristics:** Each instance of DMart, being self-hosted, consists of multiple spaces. Spaces serve as independent containers for organizing data within a DMart node.

#### Folders

- **Definition:** Folders are hierarchical structures within spaces used for further categorization and organization of data.
- **Purpose:** Folders help in organizing data into subcategories, providing a logical structure for data management.
- **Characteristics:** Folders exist within spaces and can contain other folders or entries.

#### Entries

- **Definition:** Entries are individual units of business-relevant information stored within folders.
- **Purpose:** Entries represent specific data points or pieces of information relevant to the business context.
- **Characteristics:** Entries can include various attributes and metadata associated with the stored information.

#### Attachments

- **Definition:** Attachments are extensible pieces of information and blobs associated with entries.
- **Purpose:** Attachments complement entries by providing additional context or supporting data.
- **Characteristics:** Attachments are linked to entries and can include various file types such as documents, images, or multimedia files.
