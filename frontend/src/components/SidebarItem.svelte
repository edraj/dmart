<script lang="ts">
  import { goto } from "@roxi/routify";
  $goto
  import { _ } from "@/i18n";
  // import { active_subsection } from "../_stores/active_subsection";
  import Icon from "./Icon.svelte";
  import { type Item } from "./types";

  let { item } : { item: Item; } = $props();

  // export let item: Item;
  // export let path : Array<string>;
  // export let id : string;
  // export let type;
  // export let icon;
  // export let description = undefined;
  // export let link;

  let displayname = $derived($_(item.id));
  async function show_item() {
    //console.log("Requested to show item: ", path.join("|"), id, displayname);
    // $active_subsection = { path: null, id: item.id, displayname: displayname };
    if (!item.link.startsWith("http") && !item.link.startsWith("/")) {
      item.link = "/" + item.link;
    }

    if (item.link.startsWith("http")) window.location.href = item.link;
    else $goto(item.link);

    //window.location.href = `/${link}`;
  }
  // type = type; // Silence the warning
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<span onclick={show_item} class=" " title={item.description}>
  <Icon name={item.icon} class="" />
  {displayname}
</span>

<style>
  span {
    cursor: pointer;
    display: list-item;
  }
</style>
