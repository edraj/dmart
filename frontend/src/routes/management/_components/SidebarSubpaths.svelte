<script>
  import Folder from "./Folder.svelte";
  import { slide } from "svelte/transition";
  export let subpaths = [];
  export let space_name;
</script>

<div transition:slide={{ duration: 400 }}>
  {#each subpaths as subapth (subapth.shortname + subapth.uuid)}
    <Folder data={{ space_name, ...subapth }} />
  {/each}
</div>
