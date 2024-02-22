<script lang="ts">
  import EntryRenderer from "@/components/management/renderers/EntryRenderer.svelte";
  import { ResourceType, retrieve_entry } from "@/dmart";
  import { params } from "@roxi/routify";
  const resource_type: ResourceType = ResourceType[$params.resource_type];
</script>

{#await retrieve_entry(resource_type, $params.space_name, $params.subpath.replaceAll("-", "/"), $params.shortname, true, true)}
  <h6>Loading ... @{$params.space_name}/{$params.subpath}</h6>
{:then entry}
  <EntryRenderer
    {entry}
    {resource_type}
    space_name={$params.space_name}
    subpath={$params.subpath?.replaceAll("-", "/")}
    schema_name={$params.schema_name}
  />
{:catch error}
  <p style="color: red">{error.message}</p>
{/await}
