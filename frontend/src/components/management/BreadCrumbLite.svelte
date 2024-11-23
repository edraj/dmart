<script lang="ts">
  import { ResourceType } from "@/dmart";
  import { goto } from "@roxi/routify";
  $goto // this should initiate the helper at component initialization
  import { onMount } from "svelte";
  import { ButtonGroup } from "sveltestrap";

  let {
      space_name,
      subpath,
      shortname,
      resource_type,
      schema_name
  } : {
      space_name: string,
      subpath: string,
      shortname?: string,
      resource_type: ResourceType,
      schema_name?: string
  } = $props();


  let items = $state([]);
  onMount(() => {
    const parts = subpath.split("/");
    items = parts.filter((item) => item !== "").map((part, index) => ({
      text: `/${part}`.replaceAll("//", "/"),
      action: () =>
        $goto("/management/content/[space_name]/[subpath]", {
          space_name: space_name,
          subpath: parts
            .slice(0, index + 1)
            .join("/")
            .replaceAll("/", "-"),
        }),
    }));
  });
</script>

<ButtonGroup size="sm" class="align-items-center">
  <span dir="ltr" class="font-monospace">
    <small>
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <span dir="ltr"
        class="text-success"
        style="cursor: pointer;"
        onclick={() => {
          $goto("/management/content/[space_name]", {
            space_name: space_name,
          });
        }}>{space_name}</span
      >
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      {#each items as item (item.text)}
        <span dir="ltr"
          class="text-primary"
          style="cursor: pointer;"
          onclick={item.action}>{item.text}</span>
      {/each}
      {#if resource_type !== ResourceType.folder}: <strong>{shortname}</strong>
      {/if}
      ({resource_type}{#if schema_name}&nbsp;: {schema_name}{/if})
    </small>
  </span>
</ButtonGroup>
