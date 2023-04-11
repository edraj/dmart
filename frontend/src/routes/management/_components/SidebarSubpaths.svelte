<script>
  import Folder from "./Folder.svelte";
  export let parent;
</script>

<div>
  {#each parent.subpaths as subapth (subapth.shortname + subapth.uuid)}
    <Folder
      data={{ space_name: parent.shortname, ...subapth }}
      parent_data={parent}
    />
  {/each}
</div>
