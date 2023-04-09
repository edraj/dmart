<script>
  import Folder from "./Folder.svelte";
  import { slide } from "svelte/transition";
  export let parent;
  $: console.log({ parent });
</script>

<div transition:slide={{ duration: 400 }}>
  {#each parent.subpaths as subapth (subapth.shortname + subapth.uuid)}
    <Folder
      data={{ space_name: parent.shortname, ...subapth }}
      parent_data={parent}
    />
  {/each}
</div>
