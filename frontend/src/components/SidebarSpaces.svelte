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
  import { getSpaces } from "../stores/spaces.js";
  import { dmart_spaces } from "../dmart.js";
  import DynamicFormModal from "./DynamicFormModal.svelte";

  export let child;
  export let displayActionMenu = false;
  let expanded = false;

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

  async function handleModelSubmit(data) {
    const space_name = data[0].value;
    const query = {
      space_name: child.shortname,
      request_type: "update",
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

  let props = [{ name: "space_name", value: child.shortname }];
  let entry_create_modal = false;
</script>

<DynamicFormModal {props} bind:open={entry_create_modal} {handleModelSubmit} />

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
          <b>{child.shortname}</b>
        </div>

        <div class="col-1" hidden={!displayActionMenu}>
          <Fa icon={faPlusSquare} size="lg" color="green" />
        </div>
        <div
          class="col-1"
          hidden={!displayActionMenu}
          on:click={() => {
            entry_create_modal = true;
          }}
        >
          <Fa icon={faEdit} size="lg" color="yellow" />
        </div>
        <div
          class="col-1"
          hidden={!displayActionMenu}
          on:click={async () => await handleSpaceDelete()}
        >
          <Fa icon={faTrashCan} size="lg" color="red" />
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
