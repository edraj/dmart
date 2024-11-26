<script lang="ts">
  import { params } from "@roxi/routify";
  import { retrieve_entry, ResourceType } from "@/dmart";
  import EntryRenderer from "@/components/management/renderers/EntryRenderer.svelte";

</script>

{#if $params.space_name && $params.subpath && $params.shortname}
  {#await retrieve_entry(ResourceType.user, $params.space_name, $params.subpath.replaceAll("-", "/"), $params.shortname, true, true)}
    <h6>Loading ... @{$params.space_name}/{$params.subpath}</h6>
  {:then entry}
    <EntryRenderer
      {entry}
      resource_type={ResourceType.user}
      space_name={$params.space_name}
      subpath={$params.subpath?.replaceAll("-", "/")}
      schema_name={$params.schema_name}
    />
  {:catch error}
    <div class="alert alert-danger text-center m-5">
      <h4 class="alert-heading text-capitalize">{error}</h4>
    </div>
  {/await}
{:else}
  <h4>We shouldn't be here ...</h4>
  <pre>{JSON.stringify($params)}</pre>
{/if}
