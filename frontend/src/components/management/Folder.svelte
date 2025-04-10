<script module lang="ts">
  import { writable } from "svelte/store";
  const active_path = writable("notassigned");
</script>

<script lang="ts">
  import Icon from "../Icon.svelte";
  import { _ } from "@/i18n";
  import { goto } from "@roxi/routify";
  $goto
  import { type ApiResponseRecord, get_children, ResourceType } from "@/dmart";
  import { fly } from "svelte/transition";
  import Folder from "./Folder.svelte";

  let {
      space_name,
      folder
  } : {
      space_name: string,
      folder: ApiResponseRecord
  } = $props();

  let expanded = $state(false);
  let fullpath = `${space_name}/${
    folder.subpath == "/" ? "" : folder.subpath + "/"
  }${folder.shortname}`;

  let children = $state([]);

  function displayname(): string {
    let lang = JSON.parse(typeof localStorage !== 'undefined' && localStorage.getItem("preferred_locale") || "ar");
    if (folder?.attributes?.displayname && lang in folder?.attributes?.displayname) {
      return folder?.attributes?.displayname[lang] ?? folder.shortname;
    } else {
      return folder.shortname;
    }
  }

  $effect(() => {
    if (expanded && !$active_path.startsWith(fullpath)) {
      expanded = false;
    }
  });

  async function toggle() {
    // expanded = !expanded;
    if (!expanded) {
      $active_path = fullpath;
      expanded = true;
    } else {
      expanded = false;
      if (folder.subpath != "/") {
        $active_path = `${space_name}/${folder.subpath}`;
      }
    }
    if (expanded) {
      const data = await get_children(
        space_name,
        `${folder.subpath}/${folder.shortname}`,
        10,
        0,
        [ResourceType.folder]
      );

      children = data.records;

      let subpath = `${folder.subpath}/${folder.shortname}`.replace(
        /\/+/g,
        "/"
      );

      // Trim leading or traling '/'
      if (subpath.length > 0 && subpath[0] === "/") {
          subpath = subpath.substring(1);
      }
      if (subpath.length > 0 && subpath[subpath.length - 1] === "/") {
          subpath = subpath.slice(0, -1);
      }

      // If empty, use __root__ magic word
      if (subpath.length === 0) {
          subpath = "__root__";
      }

      $goto("/management/content/[space_name]/[subpath]", {
        space_name: space_name,
        subpath: subpath.replaceAll("/", "-"),
      });
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<span
  class:expanded
  class="folder position-relative mt-1 ps-2"
  onclick={toggle}
  transition:fly={{ y: -10, duration: 200 }}
>
  <span style="overflow: hidden;">
    <Icon class="text-start" name="folder{expanded ? '2-open' : ''}" />
    {displayname()}
  </span>
</span>

{#if expanded}
  <ul class="py-1 ps-1 ms-2 border-start">
    {#if children.length > 0}
      {#each children as child}
        <li>
          <Folder folder={child} {space_name} />
        </li>
      {/each}
    {/if}
  </ul>
{/if}

<style>
  .folder {
    /*font-weight: bold;*/
    cursor: pointer;
    display: list-item;
    list-style: none;
    /*border-top: thin dotted grey;*/
  }

  .folder:hover {
    z-index: 2;
    background-color: #b7b7b7;
    text-decoration: none;
    /*background-color: #e8e9ea;*/
  }

  .expanded {
    background-color: #e8e9ea;
    /*border-bottom: thin dotted green;*/
  }

  ul {
    list-style: none;
  }

  li {
    padding: 0;
  }
</style>
