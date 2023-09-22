<script lang="ts">
  import SidebarItem from "./SidebarItem.svelte";
  import Icon from "./Icon.svelte";
  import { _ } from "@/i18n";
  import { Section } from "./types";

  export let section: Section;
  // export let path : Array<string>;
  // export let expanded : boolean;
  // export let id : string;
  // export let children; //  : Array<Section>;
  // export let type : string;
  // export let icon : string;
  $: displayname = $_(section.id);

  if (!section.path) {
    section.path = [];
  }
  section.path.push(section.id);
  async function toggle() {
    section.expanded = !section.expanded;
  }

  // type = type; // silence the warning
</script>

<div class="mb-3">
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <span class:expanded={section.expanded} on:click={toggle} class="py-1 ps-1">
    <Icon name={section.icon} class="me-1" />
    <b>{displayname}</b>
  </span>
  {#if section.expanded}
    <ul class="border-start pt-1 px-1 ms-1">
      {#each section.children as child}
        <li class="px-1 py-1">
          {#if child.type === "item"}
            <SidebarItem item={child} />
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  span {
    /*padding: 0 0 0 0.5em;*/
    cursor: pointer;
    display: list-item;
    border-top: thin solid green;
  }

  .expanded {
    background-color: #e8e9ea;
  }

  ul {
    /*padding: 0.2em 0 0 0.5em;
    margin: 0 0 0 0.5em;*/
    list-style: none;
    /*border-left: 1px solid #eee;*/
  }

  li:hover {
    z-index: 2;
    color: #495057;
    text-decoration: none;
    background-color: #e8e9ea;
  }

  /*li {
    padding: 0.2em 0;
    margin-top: 0.2em;
    }*/
</style>
