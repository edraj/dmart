<script lang="ts">
  import { params } from "@roxi/routify";
  import { retrieve_entry, ResourceType } from "@/dmart";
  import EntryRenderer from "@/components/management/renderers/EntryRenderer.svelte";

  let refresh = false;
</script>

{#key refresh}
{#if $params.space_name}
  {#await retrieve_entry(ResourceType.space, $params.space_name, "__root__", $params.space_name, false, false)}
  <p>Loading...</p>
  {:then entry}
    <EntryRenderer
      {entry}
      resource_type={ResourceType.space}
      space_name={$params.space_name}
      subpath={'/'}
      bind:refresh
    />
    <!--pre>{JSON.stringify(spaces.get($params.space_name), null, 2)}</pre-->
  {:catch error}
    <p style="color: red">{error.message}</p>
  {/await}
{:else}
  <h4>For some reason ... params doesn't have the needed info</h4>
  <pre>{JSON.stringify($params, null, 2)}</pre>
{/if}
{/key}
