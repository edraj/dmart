<script lang="ts">
  import { get_spaces } from "@/dmart";
  import { ListGroupItem } from "sveltestrap";
  import Icon from "../../Icon.svelte";
  import { _ } from "@/i18n";
  import { goto } from "@roxi/routify";
  $goto // this should initiate the helper at component initialization
  // import { fade } from 'svelte/transition';
  export let name;

  // let expanded: string;

  let selectedSpace;
  function handleClick(e, space) {
    e.preventDefault();    
    selectedSpace = space.shortname; 
    $goto(`/management/tools/${name}/[space_name]`, {
      space_name: space.shortname,
    });
  }
</script>

{#await get_spaces()}
  <!--h3 transition:fade >Loading spaces list</h3-->
{:then spaces_data}
  {#each spaces_data.records as space}
    <ListGroupItem class="ps-2 pe-0 py-0" style={selectedSpace === space.shortname?"background-color: #49505757;":""}>
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <div
        class="hover mb-2 mt-2"
        style="cursor: pointer;"
        onclick={(e) => {
          handleClick(e, space);
        }}
      >
        <Icon name="diagram-3" class="me-1" /> <b>{space.shortname}</b>
      </div>
    </ListGroupItem>
  {/each}
{:catch error}
  <p style="color: red">{error.message}</p>
{/await}

<style>
    div.hover:hover {
    background-color: #b7b7b7;
  } 
</style>