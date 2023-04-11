<script>
  import ListView from "../_components/ListView.svelte";
  import { contents } from "../_stores/contents";

  let cols = {};

  let query = {};

  contents.subscribe((value) => {
    if (Object.keys(value).length) {
      console.log({ value });
      query = value;
      cols = {
        shortname: {
          path: "shortname",
          title: "shortname",
          type: "string",
          width: "25%",
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
