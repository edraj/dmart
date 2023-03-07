<script>
  import { contents } from "./../../../stores/contents.js";
  import ListView from "../../../components/ListView.svelte";

  let cols = {
    uuid: {
      path: "uuid",
      title: "uuid",
      type: "string",
      width: "15%",
    },
    shortname: {
      path: "shortname",
      title: "shortname",
      type: "string",
      width: "15%",
    },
    owner_shortname: {
      path: "attributes.owner_shortname",
      title: "Owner shorname",
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

  let query = {};

  contents.subscribe((value) => {
    query = value;
  });
</script>

{#key query}
  <ListView
    {query}
    {cols}
    details_split={0}
    clickable={true}
    filterable={true}
  />
{/key}
