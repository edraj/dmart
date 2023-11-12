<script>
  import { ResourceType } from "@/dmart";
  import { goto } from "@roxi/routify";
  import { onMount } from "svelte";
  import { ButtonGroup } from "sveltestrap";

  export let space_name;
  export let subpath;
  export let shortname;
  export let resource_type;
  export let schema_name;

  let items = [];
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
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      <span dir="ltr"
        class="text-success"
        style="cursor: pointer;"
        on:click={() => {
          $goto("/management/content/[space_name]", {
            space_name: space_name,
          });
        }}>{space_name}</span
      >
      <!-- svelte-ignore a11y-click-events-have-key-events -->
      <!-- svelte-ignore a11y-no-static-element-interactions -->
      {#each items as item (item.text)}
        <span dir="ltr"
          class="text-primary"
          style="cursor: pointer;"
          on:click={item.action}>{item.text}</span>
      {/each}
      {#if resource_type !== ResourceType.folder}: <strong>{shortname}</strong>
      {/if}
      ({resource_type}{#if schema_name}&nbsp;: {schema_name}{/if})
    </small>
  </span>
</ButtonGroup>
