<script>
  import { ListGroupItem } from "sveltestrap";
  import Fa from "sveltejs-fontawesome";
  import {
    faPlusSquare,
    faTrashCan,
    faEdit,
  } from "@fortawesome/free-regular-svg-icons";
  import SidebarSubpaths from "./SidebarSubpaths.svelte";
  import { slide } from "svelte/transition";
  import spaces, { getSpaces } from "../stores/spaces.js";
  import { dmart_folder, dmart_spaces } from "../dmart.js";
  import DynamicFormModal from "./DynamicFormModal.svelte";
  import JsonEditorModal from "./JsonEditorModal.svelte";
  import { toastPushSuccess } from "../utils";

  export let child;
  export let displayActionMenu = false;
  let expanded = false;

  let content = {
    json: {},
    text: undefined,
  };

  async function handleSpaceDelete() {
    const space_name = child.shortname;
    if (confirm(`Are you sure want to delete ${space_name} space`) === false) {
      return;
    }
    const query = {
      space_name: space_name,
      request_type: "delete",
      records: [
        {
          resource_type: "space",
          subpath: "/",
          shortname: space_name,
          attributes: {},
        },
      ],
    };
    const response = await dmart_spaces(query);
    if (response.error) {
      alert(response.error.message);
    } else {
      await getSpaces();
    }
  }

  let modalFlag = "create";
  async function handleModelCreate(data) {
    const response = dmart_folder(
      child.shortname,
      "/",
      data[0].value,
      data[1].value
    );
    if (response.error) {
      alert(response.error.message);
    } else {
      toastPushSuccess();
      await getSpaces();
      entry_create_modal = false;
    }
    return;
  }

  async function handleModelUpdate(content) {
    const record = content.json ?? JSON.parse(content.text);
    delete record.type;
    const query = {
      space_name: child.shortname,
      request_type: modalFlag,
      records: [record],
    };
    const response = await dmart_spaces(query);
    if (response.error) {
      alert(response.error.message);
    } else {
      toastPushSuccess();
      await getSpaces();
      entry_create_modal = false;
    }
  }

  let props = [];
  let entry_create_modal = false;

  $: {
  }
</script>

{#key props}
  {#if modalFlag === "update"}
    <JsonEditorModal
      bind:open={entry_create_modal}
      handleModelSubmit={handleModelUpdate}
      bind:content
    />
  {/if}
  {#if modalFlag === "create"}
    <DynamicFormModal
      {props}
      bind:open={entry_create_modal}
      handleModelSubmit={handleModelCreate}
    />
  {/if}
{/key}
<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<div
  on:mouseover={(e) => (displayActionMenu = true)}
  on:mouseleave={(e) => (displayActionMenu = false)}
>
  <ListGroupItem class="px-0">
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div class="mb-2">
      <div class="d-flex row">
        <div class="col-7" on:click={() => (expanded = !expanded)}>
          <b style="cursor: pointer;"
            >{child?.attributes?.displayname?.en ?? child.shortname}</b
          >
        </div>

        <div
          class="col-1"
          hidden={!displayActionMenu}
          on:click={() => {
            props = [
              {
                label: "Schema Shortname",
                name: "schema_shortname",
                value: "",
              },
              { label: "Shortname", name: "shortname", value: "" },
            ];
            modalFlag = "create";
            entry_create_modal = true;
          }}
        >
          <Fa icon={faPlusSquare} size="sm" color="dimgrey" />
        </div>
        <div
          class="col-1"
          hidden={!displayActionMenu}
          on:click={() => {
            props = [
              {
                label: "Space Name",
                name: "space_name",
                value: child.shortname,
              },
            ];
            const space = $spaces.children.filter(
              (e) => e.shortname === child.shortname
            )[0];
            delete space.subpaths;

            content.json = space;
            entry_create_modal = true;
            modalFlag = "update";
          }}
        >
          <Fa icon={faEdit} size="sm" color="dimgrey" />
        </div>
        <div
          class="col-1"
          hidden={!displayActionMenu}
          on:click={async () => await handleSpaceDelete()}
        >
          <Fa icon={faTrashCan} size="sm" color="dimgrey" />
        </div>
      </div>
    </div>
    <div hidden={!expanded} transition:slide={{ duration: 400 }}>
      <SidebarSubpaths
        bind:space_name={child.shortname}
        bind:subpaths={child.subpaths}
      />
    </div>
  </ListGroupItem>
</div>
