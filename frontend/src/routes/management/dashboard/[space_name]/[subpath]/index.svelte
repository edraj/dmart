<script>
  import { params } from "@roxi/routify";
  import ListView from "../../../_components/ListView.svelte";

  let query = {};
  console.log({ $params });
  $: $params &&
    $params.space_name &&
    $params.subpath &&
    (query = {
      type: "search",
      search: "",
      retrieve_attachments: true,
      space_name: $params.space_name,
      subpath: $params.subpath.replaceAll("-", "/"),
    });
  let cols = {
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
