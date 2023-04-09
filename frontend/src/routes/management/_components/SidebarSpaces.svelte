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
  import spaces, { getSpaces } from "../_stores/spaces.js";
  import { dmartCreateFolder, dmartSpaces } from "../../../dmart.js";
  import DynamicFormModal from "./DynamicFormModal.svelte";
  import JsonEditorModal from "./JsonEditorModal.svelte";
  import { toastPushSuccess } from "../../../utils.js";

  export let child;
  export let displayActionMenu = false;
  let expanded = false;

  let content = {
    json: {},
    text: undefined,
  };

  async function handleSpaceDelete() {
    console.log("handleSpaceDelete");
    const spacename = child.shortname;
    if (confirm(`Are you sure want to delete ${spacename} space`) === false) {
      return;
    }
    const query = {
      space_name: spacename,
      request_type: "delete",
      records: [
        {
          resource_type: "space",
          subpath: "/",
          shortname: spacename,
          attributes: {},
        },
      ],
    };
    const response = await dmartSpaces(query);
    if (response.error) {
      alert(response.error.message);
    } else {
      await getSpaces();
    }
  }

  let modalFlag = "create";
  async function handleModelCreate(data) {
    console.log("handleModelCreate");
    const response = dmartCreateFolder(
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
      entryCreateModal = false;
    }
    return;
  }

  async function handleModelUpdate(content) {
    const record = content.json ?? JSON.parse(content.text);
    const query = {
      space_name: child.shortname,
      request_type: modalFlag,
      records: [{ ...record, subpath: "/" }],
    };
    const response = await dmartSpaces(query);
    if (response.error) {
      alert(response.error.message);
    } else {
      toastPushSuccess();
      entryCreateModal = false;
      const space = [...$spaces.children].filter(
        (e) => e.shortname === child.shortname
      )[0];
      console.log({ child }, { space });
      child = { ...child, ...record };
    }
  }

  let props = [];
  let entryCreateModal = false;
</script>

{#key props}
  {#if modalFlag === "update"}
    <JsonEditorModal
      bind:open={entryCreateModal}
      handleModelSubmit={handleModelUpdate}
      bind:content
    />
  {/if}
  {#if modalFlag === "create"}
    <DynamicFormModal
      {props}
      bind:open={entryCreateModal}
      handleModelSubmit={handleModelCreate}
    />
  {/if}
{/key}
<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<div class="mb-3" style="padding-left: 8px;">
  <ListGroupItem class="px-0">
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div
      on:mouseover={(e) => (displayActionMenu = true)}
      on:mouseleave={(e) => (displayActionMenu = false)}
      on:click={() => (expanded = !expanded)}
    >
      <div class="d-flex row justify-content-between folder position-relative">
        <div class="col-12" style="overflow-wrap: anywhere;">
          <b style="cursor: pointer;"
            >{child?.attributes?.displayname?.en ?? child.shortname}</b
          >
        </div>

        <div
          class="d-flex col justify-content-end"
          style="position: absolute;z-index: 1;"
        >
          <div
            style="cursor: pointer;background-color: #e8e9ea;"
            hidden={!displayActionMenu}
            on:click={(e) => {
              e.stopPropagation();
              props = [
                {
                  label: "Schema Shortname",
                  name: "schema_shortname",
                  value: "",
                },
                { label: "Shortname", name: "shortname", value: "" },
              ];
              modalFlag = "create";
              entryCreateModal = true;
            }}
          >
            <Fa icon={faPlusSquare} size="sm" color="dimgrey" />
          </div>
          <div
            class="px-1"
            style="cursor: pointer;background-color: #e8e9ea;"
            hidden={!displayActionMenu}
            on:click={() => {
              props = [
                {
                  label: "Space Name",
                  name: "space_name",
                  value: child.shortname,
                },
              ];
              const space = {
                ...$spaces.children.filter(
                  (e) => e.shortname === child.shortname
                )[0],
              };
              delete space?.subpaths;
              delete space?.subpath;
              delete space?.type;
              delete space?.attachments;
              delete space?.attributes?.created_at;
              delete space?.attributes?.updated_at;
              delete space?.attributes?.owner_shortname;

              content.json = space;
              entryCreateModal = true;
              modalFlag = "update";
            }}
          >
            <Fa icon={faEdit} size="sm" color="dimgrey" />
          </div>
          <div
            style="cursor: pointer;background-color: #e8e9ea;"
            hidden={!displayActionMenu}
            on:click={async () => await handleSpaceDelete()}
          >
            <Fa icon={faTrashCan} size="sm" color="dimgrey" />
          </div>
        </div>
      </div>
    </div>
    <div hidden={!expanded} transition:slide={{ duration: 400 }}>
      <SidebarSubpaths bind:parent={child} />
    </div>
  </ListGroupItem>
</div>
