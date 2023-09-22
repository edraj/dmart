<script lang="ts">
  import { params } from "@roxi/routify";
  import { retrieve_entry, ResourceType } from "@/dmart";
  import TicketEntryRenderer from "@/components/management/renderers/TicketEntryRenderer.svelte";

  let refresh = {};
</script>

{#if $params.space_name && $params.subpath && $params.shortname}
  {#await retrieve_entry(ResourceType.ticket, $params.space_name, $params.subpath.replaceAll("-", "/"), $params.shortname, true, true, $params.validate_schema === "false" ? false : true)}
    <h6>Loading ... @{$params.space_name}/{$params.subpath}</h6>
  {:then entry}
    <TicketEntryRenderer
      bind:refresh
      {entry}
      resource_type={ResourceType.ticket}
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
