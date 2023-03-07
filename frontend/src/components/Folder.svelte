<script>
  import { contents } from "./../stores/contents.js";
  import { dmart_entries, dmart_folder, dmart_query } from "../dmart.js";
  import { entries } from "../stores/entries.js";
  import Icon from "./Icon.svelte";
  import { getNotificationsContext } from "svelte-notifications";
  import ContentModal from "./ContentModal.svelte";
  import { _ } from "../i18n";
  import { slide } from "svelte/transition";
  import Folder from "./Folder.svelte";
  import spaces from "../stores/spaces.js";

  const { addNotification } = getNotificationsContext();

  let expanded = false;
  //let children_loaded = false;
  export let data;

  let children_subpath;
  let displayname;
  let folder;

  $: {
    children_subpath = data.subpath + "/" + data.shortname;
    // data.displayname = data.displayname || data.shortname;
    // displayname =
    //   data.displayname.length < 20
    //     ? data.displayname
    //     : data.displayname.substring(0, 20) + " ...";
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
        // const queryResult = await dmart_query({
        //   type: "subpath",
        //   space_name: data.space_name,
        //   subpath: data.subpath,
        //   retrieve_json_payload: true,
        //   search: "",
        //   limit: 100,
        //   offset: 0,
        // });
        // console.log({ queryResult });
        // contents.set(queryResult.records);

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
      // $entries[children_subpath] = [];
      // _entries.forEach((_entry) => {
      //   $entries[children_subpath].push({ data: _entry });
      // });
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

  let entry_create_modal;
  async function handleEntryCreated(event) {}

  let folder_details_modal;

  async function deleteFolder() {
    if (
      confirm(
        `Are you sure you want to delete the folder "${data.shortname}|${data.displayname}" under ${data.subpath}?`
      )
    ) {
      let result = await dmart_folder("delete", data.subpath, data.shortname);
      addNotification({
        text: `Deleted folder "${data.shortname}|${data.displayname}" under ${data.subpath}`,
        position: "bottom-center",
        type: result.status == "success" ? "success" : "warning",
        removeAfter: 5000,
      });
      if (result.status == "success") {
        entries.del(data.subpath, data.shortname);
      }
    }
  }
</script>

<div>
  <ContentModal
    subpath={children_subpath}
    bind:open={entry_create_modal}
    on:created={handleEntryCreated}
  />
  <ContentModal
    bind:open={folder_details_modal}
    fix_resource_type="folder"
    {data}
  />

  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <span
    transition:slide={{ duration: 400 }}
    class:expanded
    class="folder position-relative mt-1 ps-2"
    on:click={toggle}
  >
    <span style="overflow: hidden;">
      <Icon class="text-start" name="folder{expanded ? '2-open' : ''}" />
      {data.shortname}
    </span>
    <span class="toolbar top-0 end-0 position-absolute px-0">
      <span
        class="px-0"
        title={$_("create_subentry")}
        on:click|stopPropagation={() => (entry_create_modal = true)}
      >
        <Icon name="file-plus" />
      </span>
      <span
        class="px-0"
        title={$_("edit")}
        on:click|stopPropagation={() => (folder_details_modal = true)}
      >
        <Icon name="pencil" />
      </span>
      <span
        class="px-0"
        title={$_("delete")}
        on:click|stopPropagation={deleteFolder}
      >
        <Icon name="trash" />
      </span>
    </span>
  </span>
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
