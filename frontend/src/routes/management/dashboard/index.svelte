<script>
  import { contents } from "./../../../stores/contents.js";
  import ListView from "../../../components/ListView.svelte";

  let cols = {};

  let query = {};

  contents.subscribe((value) => {
    if (Object.keys(value).length) {
      query = value;
      cols = {
        shortname: {
          path: "shortname",
          title: "shortname",
          type: "string",
          width: "10%",
        },
        owner_shortname: {
          path: "attributes.owner_shortname",
          title: "Owner shorname",
          type: "string",
          width: "15%",
        },
        resource_type: {
          path: "resource_type",
          title: "Resource type",
          type: "string",
          width: "15%",
        },
        owner_shortname: {
          path: "attributes.payload.schema_shortname",
          title: "Schema shortname",
          type: "string",
          width: "15%",
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
    }
  });
</script>

{#if Object.keys(query).length}
  {#key query}
    <ListView
      {query}
      {cols}
      details_split={0}
      clickable={true}
      filterable={true}
    />
  {/key}
{/if}
