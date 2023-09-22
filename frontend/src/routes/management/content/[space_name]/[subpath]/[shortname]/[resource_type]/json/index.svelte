<script lang="ts">
  import { params } from "@roxi/routify";
  import { retrieve_entry, ResourceType } from "@/dmart";
  import EntryRenderer from "@/components/management/renderers/EntryRenderer.svelte";

  const resource_type: ResourceType = ResourceType[$params.resource_type];
</script>

{#if $params.space_name && $params.subpath && $params.shortname}
  {#await retrieve_entry(resource_type, $params.space_name, $params.subpath.replaceAll("-", "/"), $params.shortname, true, true)}
    <!--h6 transition:fade >Loading ... @{$params.space_name}/{$params.subpath}</h6-->
  {:then entry}
    <EntryRenderer
      {entry}
      {resource_type}
      space_name={$params.space_name}
      subpath={$params.subpath?.replaceAll("-", "/")}
    />
  {:catch error}
    <p style="color: red">{error.message}</p>
  {/await}
{:else}
  <h4>We shouldn't be here ...</h4>
  <pre>{JSON.stringify($params)}</pre>
{/if}
