<script>
  import ListView from "../_components/ListView.svelte";
  import { triggerSidebarSelection } from "../_stores/triggers";

  let cols = {};

  let query = {};

  triggerSidebarSelection.subscribe((value) => {
    if (value) {
      query = {
        type: "events",
        space_name: value,
        subpath: "/",
      };
    } else {
      query = {};
    }
    cols = {
      subpath: {
        path: "subpath",
        title: "Subpath",
        type: "string",
        width: "25%",
      },
      shortname: {
        path: "shortname",
        title: "Shortname",
        type: "string",
        width: "25%",
      },
      request: {
        path: "attributes.request",
        title: "Resource type",
        type: "string",
        width: "15%",
      },
      timestamp: {
        path: "attributes.timestamp",
        title: "Timestamp",
        type: "string",
        width: "25%",
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
      clickable={true}
      filterable={false}
    />
  {/key}
{/if}
