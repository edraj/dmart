<script>
  import ListView from "../_components/ListView.svelte";
  import { triggerSidebarSelection } from "../_stores/triggers";

  let cols = {};

  let query = {};

  triggerSidebarSelection.subscribe((value) => {
    if (value) {
      query = value;
    } else {
      query = {};
    }
    cols = {
      shortname: {
        path: "shortname",
        title: "Shortname",
        type: "string",
        width: "25%",
      },
      resource_type: {
        path: "resource_type",
        title: "Resource type",
        type: "string",
        width: "25%",
      },
      created_at: {
        path: "attributes.created_at",
        title: "Created At",
        type: "string",
        width: "15%",
      },
      updated_at: {
        path: "attributes.updated_at",
        title: "Updated At",
        type: "string",
        width: "15%",
      },
    };
  });
</script>

{#if Object.keys(query).length}
  {#key query}
    <ListView
      {query}
      {cols}
      details_split={0}
      clickable={false}
      filterable={false}
    />
  {/key}
{/if}
