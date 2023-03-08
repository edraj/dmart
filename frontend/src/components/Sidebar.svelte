<script>
  import spaces, { getSpaces } from "../stores/spaces.js";
  import { active_entry } from "../stores/active_entry.js";
  import { _ } from "../i18n";
  import { status_line } from "../stores/status_line.js";
  import { ListGroup, ListGroupItem } from "sveltestrap";
  import { slide } from "svelte/transition";
  import SidebarSpaces from "./SidebarSpaces.svelte";
  import Fa from "sveltejs-fontawesome";
  import { faPlusSquare } from "@fortawesome/free-regular-svg-icons";
  import DynamicFormModal from "./DynamicFormModal.svelte";
  import { dmart_spaces } from "../dmart.js";
  import SchemaFormModal from "./SchemaFormModal.svelte";

  let head_height;
  let foot_height;
  let props = [];
  let pop_create_space_modal = false;
  let pop_create_schema_modal = false;

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
    const response = await dmart_spaces(query);
    if (response.error) {
      alert(response.error.message);
    } else {
      await getSpaces();
    }
  }
</script>

{#key props}
  <DynamicFormModal
    {props}
    bind:open={pop_create_space_modal}
    {handleModelSubmit}
  />
  <SchemaFormModal {props} bind:open={pop_create_schema_modal} />
{/key}
<div bind:clientHeight={head_height}>
  <div class="row">
    <h5 class="my-0 col-9">Schema</h5>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div
      class="my-0 col-2 d-flex justify-content-end"
      on:click={() => {
        props = [
          { name: "space_name", value: "" },
          { name: "shortname", value: "" },
        ];
        pop_create_schema_modal = true;
      }}
    >
      <Fa icon={faPlusSquare} size="x" color="green" />
    </div>
  </div>
  <hr class="w-100 mt-1 mb-0" />
  <div class="row">
    <h5 class="my-0 col-9">Spaces</h5>
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <div
      class="my-0 col-2 d-flex justify-content-end"
      on:click={() => {
        props = [{ name: "space_name", value: "" }];
        pop_create_space_modal = true;
      }}
    >
      <Fa icon={faPlusSquare} size="x" color="green" />
    </div>
  </div>
  <hr class="w-100 mt-1 mb-0" />
</div>
<div
  class="no-bullets scroller pe-0 w-100"
  style="height: calc(100% - {head_height +
    foot_height}px); overflow: hidden auto;"
>
  <ListGroup flush class="w-100">
    {#each $spaces.children as child (child.uuid)}
      <div transition:slide={{ duration: 400 }}>
        <SidebarSpaces {child} />
      </div>
    {/each}
  </ListGroup>
</div>
<div class="w-100" bind:clientHeight={foot_height}>
  {#if $active_entry.data}
    <hr class="my-0" />
    <p class="lh-1 my-0">
      <small>
        <span class="text-muted">{$_("path")}:</span>
        {$active_entry.data.subpath}/{$active_entry.data.shortname} <br />
        <span class="text-muted">{$_("displayname")}:</span>
        {$active_entry.data.displayname} <br />
        <span class="text-muted">{$_("content_type")}:</span>
        {$active_entry?.data?.attributes?.payload?.content_type?.split(
          ";"
        )[0] || "uknown"}<br />
        <span class="text-muted">{$_("schema_shortname")}:</span>
        {$active_entry?.data?.attributes?.payload?.schema_shortname || "uknown"}
      </small>
    </p>
  {/if}
  {#if $status_line}
    <hr class="my-1" />
    {@html $status_line}
  {/if}
</div>
