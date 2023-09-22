<script lang="ts">
  import { params } from "@roxi/routify";
  import { retrieve_entry, ResourceType } from "@/dmart";
  import EntryRenderer from "@/components/management/renderers/EntryRenderer.svelte";
  // import { fade } from 'svelte/transition';

  let parent_subpath: string;
  let shortname: string;
  let refresh = false;

  $: {
    if (typeof $params.subpath == "string" && $params.subpath) {
      const arr = $params.subpath.split("-");
      parent_subpath = arr.slice(0, arr.length - 1).join("/");
      if (!parent_subpath) parent_subpath = "__root__";
      shortname = arr[arr.length - 1];
    }
  }
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
      <p style="color: red">{error.message}</p>
    {/await}
  {:else}
    <h4>For some reason ... params doesn't have the needed info</h4>
    <pre>{JSON.stringify($params, null, 2)}</pre>
    <pre>Parent subpath {parent_subpath} ... Entry shortname {shortname}</pre>
  {/if}
{/key}
