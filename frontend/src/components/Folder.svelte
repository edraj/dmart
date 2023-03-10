<script>
  import selectedSubpath from "./../stores/selected_subpath.js";
  import { contents } from "./../stores/contents.js";
  import { dmart_entries, dmart_folder, dmart_request } from "../dmart.js";
  import { entries } from "../stores/entries.js";
  import DynamicFormModal from "./DynamicFormModal.svelte";
  import { _ } from "../i18n";
  import { slide } from "svelte/transition";
  import Folder from "./Folder.svelte";
  import spaces, { getSpaces } from "../stores/spaces.js";
  import Fa from "sveltejs-fontawesome";
  import {
    faPlusSquare,
    faTrashCan,
    faEdit,
  } from "@fortawesome/free-regular-svg-icons";
  import { toastPushFail, toastPushSuccess } from "../utils.js";

  let expanded = false;

  export let data;

  let children_subpath;

  $: {
    children_subpath = data.subpath + "/" + data.shortname;
  }
  async function toggle() {
    selectedSubpath.set(data.subpath);
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

  let props = [];
  let entry_create_modal = false;
  let modalFlag = "create";
  async function handleModelSubmit(form) {
    if (modalFlag === "create") {
      const response = await dmart_folder(
        data.space_name,
        data.subpath,
        form[0].value,
        form[1].value
      );
      if (response.error) {
        alert(response.error.message);
      } else {
        toastPushSuccess();
        await getSpaces();
        entry_create_modal = false;
      }
    } else {
      const response = await dmart_request("managed/request", {
        space_name: data.space_name,
        request_type: "update",
        records: [
          {
            resource_type: "folder",
            shortname: form[0].value,
            subpath: data.subpath,
            attributes: {},
          },
        ],
      });
      if (response.status === "success") {
        toastPushSuccess();
        await getSpaces();
        entry_create_modal = false;
      } else {
        toastPushFail();
      }
    }
  }
  function handleSubpathCreate() {
    props = [
      { name: "schema_shortname", value: "" },
      { name: "shortname", value: "" },
    ];
    modalFlag = "create";
    entry_create_modal = true;
  }
  function handleSubpathUpdate() {
    props = [{ name: "shortname", value: data.shortname }];
    modalFlag = "update";
    entry_create_modal = true;
  }
  async function handleSubpathDelete() {
    console.log({ data });
    // const space_name = child.shortname;
    if (
      confirm(`Are you sure want to delete ${data.shortname} subpath`) === false
    ) {
      return;
    }
    const request = {
      space_name: data.space_name,
      request_type: "delete",
      records: [
        {
          resource_type: "folder",
          shortname: data.shortname,
          subpath: data.subpath,
          attributes: {},
        },
      ],
    };

    const response = await dmart_request("managed/request", request);
    if (response.status === "success") {
      toastPushSuccess();
      await getSpaces();
    } else {
      toastPushFail();
    }
  }

  let displayActionMenu = false;
</script>

{#key props}
  <DynamicFormModal
    {props}
    bind:open={entry_create_modal}
    {handleModelSubmit}
  />
{/key}

<div>
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-mouse-events-have-key-events -->
  <div
    transition:slide={{ duration: 400 }}
    class="d-flex row folder position-relative mt-1 ps-2 {$selectedSubpath ===
    data.subpath
      ? 'expanded'
      : ''}"
    on:mouseover={(e) => (displayActionMenu = true)}
    on:mouseleave={(e) => (displayActionMenu = false)}
  >
    <div class="col-7" on:click={toggle}>
      {data?.attributes?.displayname?.en ?? data.shortname}
    </div>

    <div
      class="col-1"
      hidden={!displayActionMenu}
      on:click={() => handleSubpathCreate()}
    >
      <Fa icon={faPlusSquare} size="sm" color="dimgrey" />
    </div>
    <div
      class="col-1"
      hidden={!displayActionMenu}
      on:click={() => handleSubpathUpdate()}
    >
      <Fa icon={faEdit} size="sm" color="dimgrey" />
    </div>
    <div
      class="col-1"
      hidden={!displayActionMenu}
      on:click={async () => await handleSubpathDelete()}
    >
      <Fa icon={faTrashCan} size="sm" color="dimgrey" />
    </div>

    <span class="toolbar top-0 end-0 position-absolute px-0" />
  </div>
</div>

{#if data.subpaths}
  {#each data.subpaths as subapth (subapth.shortname + subapth.uuid)}
    <div
      hidden={!expanded}
      style="padding-left: 5px;"
      transition:slide={{ duration: 400 }}
    >
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
