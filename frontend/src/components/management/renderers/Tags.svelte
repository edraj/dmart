<!-- adapted from https://github.com/movingbrands/svelte-portable-text -->
<script lang="ts">
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
        <svelte:self children={child.children} />
      </svelte:component>
    {:else}
      <svelte:element this={child.name} {...child.attributes}>
        <svelte:self children={child.children} />
      </svelte:element>
    {/if}
  {/if}
{/each}