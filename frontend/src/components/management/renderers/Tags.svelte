<!-- adapted from https://github.com/movingbrands/svelte-portable-text -->
<script lang="ts">

    import Tags from "./Tags.svelte";

    let {
      children = [],
      components = new Map
    } : {
      children: any[],
      components: Map<string, any>
    } = $props();
</script>

{#each children as child}
  {#if typeof child === "string"}{child}{/if}
  {#if child.children}
    {#if components.has(child.name)}
      <svelte:component this={components.get(child.name)} {...child.attributes}>
        <Tags children={child.children} components={new Map} />
      </svelte:component>
    {:else}
      <svelte:element this={child.name} {...child.attributes}>
        <Tags children={child.children} components={new Map} />
      </svelte:element>
    {/if}
  {/if}
{/each}
