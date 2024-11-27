<script lang="ts">
  import { params } from "@roxi/routify";
  import { retrieve_entry, ResourceType } from "@/dmart";
  import EntryRenderer from "@/components/management/renderers/EntryRenderer.svelte";

  let _parent_subpath = $derived($params.subpath.split("-"))
  let parent_subpath: string = $derived(
      _parent_subpath.slice(0, _parent_subpath.length - 1).join("/") || "__root__"
  );
  let shortname: string =  $derived(_parent_subpath[_parent_subpath.length - 1]);
  let refresh: boolean = $state(false);

</script>

{#key refresh}
  {#if $params.space_name && parent_subpath && shortname}
    {#await retrieve_entry(ResourceType.folder, $params.space_name, parent_subpath, shortname, true, true)}
      <!--h6 transition:fade >Loading ... @{$params.space_name}/{$params.subpath}</h6-->
    {:then entry}
      <!--Prism code={entry} /-->
      <EntryRenderer
        {entry}
        resource_type={ResourceType.folder}
        space_name={$params.space_name}
        subpath={$params.subpath.replaceAll("-", "/")}
        bind:refresh
      />
    {:catch error}
      <div class="alert alert-danger text-center m-5">
        <h4 class="alert-heading text-capitalize">{error}</h4>
      </div>
    {/await}
  {:else}
    <h4>For some reason ... params doesn't have the needed info</h4>
    <pre>{JSON.stringify($params, null, 2)}</pre>
    <pre>Parent subpath {parent_subpath} ... Entry shortname {shortname}</pre>
  {/if}
{/key}
