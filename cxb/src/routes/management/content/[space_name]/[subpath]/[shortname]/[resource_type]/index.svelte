<script lang="ts">
    import {params} from "@roxi/routify";
    import {Dmart, ResourceType} from "@edraj/tsdmart";
    import EntryRenderer from "@/components/management/renderers/EntryRenderer.svelte";
    import {TextPlaceholder} from "flowbite-svelte";
</script>

{#if $params.space_name && $params.subpath && $params.shortname}
  {#await Dmart.retrieveEntry({
     resource_type: ResourceType[$params.resource_type],
      space_name: $params.space_name,
     subpath: $params.subpath.replaceAll("-", "/"),
     shortname: $params.shortname,
     retrieve_json_payload: true,
     retrieve_attachments: true,
     validate_schema: $params.validate_schema !== "false"
  })}
    <div class="flex flex-col w-full">
      {#each Array(5) as _, i}
        <TextPlaceholder class="m-5" size="lg" style="width: 100vw"/>
      {/each}
    </div>
  {:then entry}
    <EntryRenderer
      {entry}
      resource_type={ResourceType[$params.resource_type]}
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
