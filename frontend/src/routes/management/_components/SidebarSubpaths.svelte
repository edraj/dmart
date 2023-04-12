<script>
  import Folder from "./Folder.svelte";
  import { slide } from "svelte/transition";
  export let parent;
</script>

{#each parent.subpaths as subapth (subapth.shortname + subapth.uuid)}
  <Folder
    data={{ space_name: parent.shortname, ...subapth }}
    parent_data={parent}
  />
{/each}
