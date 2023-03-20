<script>
  import Icon from "./Icon.svelte";
  import ContentModal from "./ContentModal.svelte";
  import { entries } from "../_stores/entries.js";
  import { active_entry } from "../_stores/active_entry.js"
  import { dmartDeleteContent } from "../../../dmart.js";
  import { getNotificationsContext } from "svelte-notifications";
  import { _ } from "../../../i18n/index.js";

  const { addNotification } = getNotificationsContext();

  export let data;

  const type_icon_map = { post: "file-text" };

  let icon = "file-text";
  let displayname;
  $: {
    if (data.resource_type in type_icon_map)
      icon = type_icon_map[data.resource_type];
    displayname =
      data.displayname.length < 15
        ? data.displayname
        : data.displayname.substring(0, 14) + " ...";
  }

  function showEntry() {
    $active_entry = { data: data };
    //console.log("switching active_entry to " + data.subpath + "/" + data.shortname);
  }

  async function deleteEntry() {
    if (
      confirm(
        `Are you sure you want to delete "${data.displayname}" under ${data.subpath}?`
      )
    ) {
      let result = await dmartDeleteContent(
        data.resource_type,
        data.subpath,
        data.shortname
      );
      addNotification({
        text: `Deleted "${data.shortname}" under ${data.subpath}`,
        position: "bottom-center",
        type: result.status == "success" ? "success" : "warning",
        removeAfter: 5000,
      });
      if (result.status == "success") {
        entries.del(data.subpath, data.shortname);
      }
    }
  }

  let details_modal;

  async function toggleActive() {
    if (
      confirm(
        `Entry "${data.displayname}" is currently ${
          data.attributes.is_active ? "active" : "inactive"
        } are you sure you want to set it to ${
          data.attributes.is_acitve ? "inactive" : "active"
        }?`
      )
    ) {
      data.attributes.is_active = !data.attributes.is_active;
    }
  }
</script>

<ContentModal
  bind:open={details_modal}
  fix_resource_type={data.resource_type}
  {data}
/>
<span on:click={showEntry} class="file position-relative  ps-2">
  <Icon name={icon} />
  {displayname}
  <span class="toolbar top-0 end-0 position-absolute px-0">
    <span
      title={$_("toggle_active_state")}
      class="px-0"
      on:click|stopPropagation={toggleActive}
    >
      <Icon name={data.attributes.is_active ? "eye" : "eye-slash"} />
    </span>
    <span
      title={$_("edit")}
      class="px-0"
      on:click|stopPropagation={() => (details_modal = true)}
    >
      <Icon name="pencil" />
    </span>
    <span
      title={$_("delete")}
      class="px=0"
      on:click|stopPropagation={deleteEntry}
    >
      <Icon name="trash" />
    </span>
  </span>
</span>

<style>
  .file {
    cursor: pointer;
    display: list-item;
    list-style: none;
  }

  .file:hover {
    z-index: 2;
    color: #495057;
    text-decoration: none;
    background-color: #e8e9ea;
  }

  .toolbar {
    display: none;
    color: brown;
  }

  .toolbar span:hover {
    color: green;
  }

  .file:hover .toolbar {
    display: flex;
  }
</style>
