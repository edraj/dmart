<script>
  import { contents } from "./../stores/contents.js";
  import { dmart_entries, dmart_folder, dmart_query } from "../dmart.js";
  import { entries } from "../stores/entries.js";
  import Icon from "./Icon.svelte";
  import { getNotificationsContext } from "svelte-notifications";
  import { _ } from "../i18n";
  import { slide } from "svelte/transition";
  import Folder from "./Folder.svelte";
  import spaces from "../stores/spaces.js";
  import Fa from "sveltejs-fontawesome";
  import {
    faPlusSquare,
    faTrashCan,
    faEdit,
  } from "@fortawesome/free-regular-svg-icons";

  let expanded = false;

  export let data;

  let children_subpath;

  $: {
    children_subpath = data.subpath + "/" + data.shortname;
  }
  async function toggle() {
    expanded = !expanded;
    if (!$entries[children_subpath]) {
      const _entries = await dmart_entries(
        data.space_name,
        data.subpath,
        [data.resource_type],
        [],
        "subpath"
      );
      if (_entries.length === 0) {
        contents.set({
          type: "subpath",
          space_name: data.space_name,
          subpath: data.subpath,
        });
        return;
      }
      _entries.forEach((entry) => {
        entry.subpath = `${entry.subpath}/${entry.shortname}`;
      });

      const idxSpace = $spaces.children.findIndex(
        (child) => child.shortname === data.space_name
      );
      const idxSubpath = $spaces.children[idxSpace].subpaths.findIndex(
        (child) => child.shortname === data.shortname
      );
      data["subpaths"] = _entries;
      $spaces.children[idxSpace].subpaths[idxSubpath]["subpaths"] = _entries;
      $spaces.children[idxSpace].subpaths[idxSubpath][
        "subpath"
      ] += `/${data.shortname}`;

      spaces.set({
        ...$spaces,
        children: $spaces.children,
      });
    }
  }
</script>

<div>
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <div
    transition:slide={{ duration: 400 }}
    class:expanded
    class="d-flex row folder position-relative mt-1 ps-2"
    on:click={toggle}
  >
    <div class="col-7">
      {data.shortname}
    </div>

    <div class="col-1">
      <Fa icon={faPlusSquare} size="lg" color="green" />
    </div>
    <div class="col-1">
      <Fa icon={faEdit} size="lg" color="yellow" />
    </div>
    <div class="col-1">
      <Fa icon={faTrashCan} size="lg" color="red" />
    </div>

    <span class="toolbar top-0 end-0 position-absolute px-0" />
  </div>
</div>

{#if data.subpaths}
  {#each data.subpaths as subapth (subapth.shortname + subapth.uuid)}
    <div hidden={!expanded} style="padding-left: 5px;">
      <Folder data={{ space_name: data.space_name, ...subapth }} />
    </div>
  {/each}
{/if}

<!-- {#if expanded && $entries[children_subpath]}
  <ul class="py-1 ps-1 ms-2 border-start">
    {#each $entries[children_subpath] as child (children_subpath + child.data.shortname)}
      <li>
        {#if child.data.resource_type === "folder"}
          <svelte:self data={child.data} />
        {:else}
          <File data={child.data} />
        {/if}
      </li>
    {/each}
  </ul>
{/if} -->
<style>
  .folder {
    /*font-weight: bold;*/
    cursor: pointer;
    display: list-item;
    list-style: none;
    border-top: thin dotted grey;
  }

  .folder:hover {
    z-index: 2;
    color: #495057;
    text-decoration: none;
    background-color: #e8e9ea;
  }

  .expanded {
    background-color: #e8e9ea;
    border-bottom: thin dotted green;
  }

  ul {
    list-style: none;
  }

  li {
    padding: 0;
  }

  .toolbar {
    display: none;
    color: brown;
  }

  .toolbar span:hover {
    color: green;
  }

  .folder:hover .toolbar {
    display: flex;
  }
</style>
