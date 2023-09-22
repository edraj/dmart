<script lang="ts">
  import { active_section } from "@/stores/management/active_section";
  import Icon from "../Icon.svelte";
  import { _ } from "@/i18n";
  import { status_line } from "@/stores/management/status_line";
  import Spaces from "./sidebar/Spaces.svelte";
  import Profile from "./sidebar/Profile.svelte";
  import Folder from "./Folder.svelte";
  import { isActive } from "@roxi/routify";
  import { ResourceType } from "@/dmart";
  import SimpleSpaces from "./sidebar/SimpleSpaces.svelte";
  import {
    // Form,
    // FormGroup,
    // Button,
    // Modal,
    // ModalBody,
    // ModalFooter,
    // ModalHeader,
    // Label,
    // Input,
    ListGroupItem,
    ListGroup,
  } from "sveltestrap";

  const components = {
    spaces: Spaces,
    profile: Profile,
  };

  let head_height: number;
  let foot_height: number;
  const withSpaces = ["events", "qatool"];
</script>

<div bind:clientHeight={head_height} class="p-2">
  <h5 class="mt-0 mb-2">
    {#if $active_section.icon}<Icon
        name={$active_section.icon}
        class="pe-1"
      />{/if}
    {#if $active_section.name}{$_($active_section.name)}{/if}
  </h5>
  <hr class="w-100 mt-1 mb-0 py-1" />
</div>
<div
  class="no-bullets scroller pe-0 w-100"
  style="height: calc(100% - {head_height +
    foot_height}px); overflow: hidden auto;"
>
  <ListGroup flush class="w-100">
    {#each $active_section.children as child ($active_section.name + child.name)}
      {#if child.type == "component" && child.name in components}
        <svelte:component this={components[child.name]} />
      {:else if child.type == "link"}
        <!--p class="my-0 font-monospace"><small>{JSON.stringify(child, undefined,1)}</small></p-->
        <ListGroupItem
          color="light"
          action
          href={`/management/${$active_section.name}/${child.name}`}
          active={$isActive(
            `/management/${$active_section.name}/${child.name}`
          )}
        >
          {#if child.icon}<Icon name={child.icon} class="pe-1" />{/if}
          {$_(child.name)}
          
        </ListGroupItem>
        {#if withSpaces.includes(child.name) && $active_section.name === "tools"}
            <SimpleSpaces name={child.name} />
          {/if}
      {:else if child.type == "folder"}
        <ListGroupItem class="px-0">
          {#if child.icon}<Icon name={child.icon} class="pe-1" />{/if}
          {$_(child.name)}
          <Folder
            space_name={child.space_name}
            folder={{
              shortname: child.name,
              subpath: child.subpath,
              resource_type: ResourceType.folder,
              attributes: {},
            }}
          />
        </ListGroupItem>
      {/if}
    {/each}
  </ListGroup>
  <hr class="w-100 mt-1 mb-0 py-1" />
</div>
<div class="w-100" bind:clientHeight={foot_height}>
  {#if $status_line}
    <hr class="my-1" />
    {@html $status_line}
  {/if}
</div>
