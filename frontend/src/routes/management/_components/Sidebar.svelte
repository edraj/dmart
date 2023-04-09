<script>
  import spaces, { getSpaces } from "../_stores/spaces.js";
  import { active_entry } from "../_stores/active_entry.js";
  import { _ } from "../../../i18n/index.js";
  import { status_line } from "../_stores/status_line.js";
  import { ListGroup } from "sveltestrap";
  import { slide } from "svelte/transition";
  import { dmartSpaces } from "../../../dmart.js";
  import { toastPushSuccess } from "../../../utils.js";
  import DynamicFormModal from "./DynamicFormModal.svelte";
  import SchemaFormModal from "./SchemaFormModal.svelte";
  import SidebarSpaces from "./SidebarSpaces.svelte";
  import { Collapse, Navbar, NavbarToggler } from "sveltestrap";

  let headHeight;
  let footHeight;
  let props = [];
  let popCreateSpaceModal = false;
  let popCreateSchemaModal = false;

  async function handleModelSubmit(data) {
    const space_name = data[0].value;
    const query = {
      space_name: space_name,
      request_type: "create",
      records: [
        {
          resource_type: "space",
          subpath: "/",
          shortname: space_name,
          attributes: {},
        },
      ],
    };
    const response = await dmartSpaces(query);
    if (response.error) {
      alert(response.error.message);
    } else {
      toastPushSuccess();
      await getSpaces();
      popCreateSpaceModal = false;
    }
  }

  let isOpen = false;
  function handleUpdate(event) {
    isOpen = event.detail.isOpen;
  }
  let subpaths = $spaces.children ? [...$spaces.children] : [];
  $: {
    async function refreshSidebar() {
      await getSpaces();
      subpaths = $spaces.children ? [...$spaces.children] : [];
    }

    if ($spaces.children === undefined) {
      refreshSidebar();
    }
  }
</script>

{#key props}
  <DynamicFormModal
    {props}
    bind:open={popCreateSpaceModal}
    {handleModelSubmit}
  />
  <SchemaFormModal {props} bind:open={popCreateSchemaModal} />
{/key}

<Navbar
  container="fuild"
  color="light"
  light
  expand="md"
  class="w-100 rounded-3"
  style="overflow-y: auto;overflow-x: hidden;"
>
  <NavbarToggler on:click={() => (isOpen = !isOpen)} />
  <Collapse
    class="px-0 py-0"
    {isOpen}
    navbar
    expand="md"
    on:update={handleUpdate}
  >
    <ul class="px-0 w-100 px-1">
      {#each subpaths as child (child.uuid + Math.round(Math.random() * 10000).toString())}
        <li transition:slide={{ duration: 400 }}>
          <SidebarSpaces {child} />
        </li>
        <hr />
      {/each}
    </ul>
  </Collapse>
</Navbar>
<div class="w-100">
  {#if $status_line}
    <hr class="my-1" />
    {@html $status_line}
  {/if}
</div>

<style>
  ul {
    list-style: none;
  }

  li:hover {
    z-index: 1;
    color: #495057;
    text-decoration: none;
    background-color: #f8f9fa;
  }
</style>
