<script lang="ts">
  import { params } from "@roxi/routify";
  import { retrieve_entry, ResourceType } from "@/dmart";
  import SpaceRenderer from "@/components/management/renderers/SpaceRenderer.svelte";
  
</script>

{#if $params.space_name}
  {#await retrieve_entry(ResourceType.space, $params.space_name, "__root__", $params.space_name, false, false)}
    <!-- -->
  {:then entry}
    <SpaceRenderer bind:space_name={$params.space_name} current_space={entry} />
    <!--pre>{JSON.stringify(spaces.get($params.space_name), null, 2)}</pre-->
  {:catch error}
    <p style="color: red">{error.message}</p>
  {/await}
{:else}
  <h4>For some reason ... params doesn't have the needed info</h4>
  <pre>{JSON.stringify($params, null, 2)}</pre>
{/if}
