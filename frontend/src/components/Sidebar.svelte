<script lang="ts">
  import { Collapse, Navbar, NavbarToggler } from "sveltestrap";
  // import { sections } from "../_stores/sections";

  import SidebarSection from "./SidebarSection.svelte";
  // import SidebarItem from "./SidebarItem.svelte";
  import {type Section} from "./types";

  import sections_untyped from  "@/stores/sections.json";
  let sections : Array<Section> =  sections_untyped;

  let isOpen = false;

  function handleUpdate(event : CustomEvent) {
    isOpen = event.detail.isOpen;
  }
</script>

<!-- TODO add search to the top -->
<Navbar color="light" light expand="md" class="px-1 me-0 mt-1 rounded-3" container={false}>
  <NavbarToggler onclick="{() => (isOpen = !isOpen)}" />
  <Collapse isOpen="{isOpen}" navbar expand="md" on:update="{handleUpdate}" class="mx-0">
    <ul class="w-100 px-0 mx-0">
      {#each sections as section}
        <li>
          {#if section.type === "section"}
            <SidebarSection {section} />
          {/if}
        </li>
      {/each}
    </ul>
  </Collapse>
</Navbar>

<!-- TODO add search to the top -->
<style>
  ul {
    /*padding: 0.2em 0.2em 0 0; 0.2em 0.5em 0 0;*/
    /*margin: 0 0.5em 0 0;*/
    /*border-right: 1px solid #eee;*/
    list-style: none;
  }

  /*li {
    padding: 0.2em 0;
    }*/

  li:hover {
    z-index: 1;
    color: #495057;
    text-decoration: none;
    background-color: #f8f9fa;
  }
</style>
