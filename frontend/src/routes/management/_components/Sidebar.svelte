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
</script>

{#key props}
  <DynamicFormModal
    {props}
    bind:open={popCreateSpaceModal}
    {handleModelSubmit}
  />
  <SchemaFormModal {props} bind:open={popCreateSchemaModal} />
{/key}

<div
  class="no-bullets scroller pe-0 w-100"
  style="height: calc(100% - {headHeight +
    footHeight}px); overflow: hidden auto;"
>
  <ListGroup flush class="w-100">
    {#each $spaces.children as child (child.uuid)}
      <div transition:slide={{ duration: 400 }}>
        <SidebarSpaces {child} />
      </div>
    {/each}
  </ListGroup>
</div>
<div class="w-100" bind:clientHeight={footHeight}>
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
