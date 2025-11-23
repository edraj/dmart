<script lang="ts">
    import {ResourceType} from "@edraj/tsdmart";
    import {marked} from "marked";
    import Prism from "@/components/Prism.svelte";

    export let attributes: any = {};
  export let resource_type: ResourceType;
  export let url: string;
  export let displayname: string = undefined;
  let content_type: string = attributes?.payload?.content_type || "";
  let body: any = attributes?.payload?.body;
</script>

{#if resource_type === ResourceType.comment}
  <div class="h-full w-full">
    <p style="margin: 0px"><b>State:</b> {attributes?.payload?.body?.state}</p>
    <br />
    <p style="margin: 0px"><b>Body:</b> {attributes?.payload?.body?.body}</p>
  </div>
{:else if resource_type === ResourceType.json || resource_type === ResourceType.reaction}
  <div>
    <div class="h-full w-full">
      <Prism language="json" code={body} />
    </div>
    {#if resource_type === ResourceType.reaction}
      <p style="margin: 0px"><b>Type: </b> {attributes.type ?? "N/A"}</p>
    {/if}
  </div>
{:else if content_type.includes("image")}
  {#if url.endsWith('svg')}
    <object data={url} type="image/svg+xml" title="{displayname}">
      <img src={url} alt={displayname} class="mw-100 border" />
    </object>
  {:else}
    <img src={url} alt={displayname} class="mw-100 border" />
  {/if}
{:else if content_type.includes("audio")}
  <audio controls src={url}>
    <track kind="captions" />
  </audio>
{:else if content_type.includes("video")}
  <video controls src={url}>
    <track kind="captions" />
  </video>
{:else if content_type.includes("pdf")}
  <object
          title={displayname}
          class="pdf-viewer"
          type="application/pdf"
          data={url}
  >
    <p>For some reason PDF is not rendered here properly.</p>
  </object>
{:else if ["markdown", "html", "text"].includes(content_type)}
  <div class="w-full h-full">
    <article class="prose">
      {@html marked(body)}
    </article>
  </div>
{:else}
  <a href={url} title={displayname}
     target="_blank" rel="noopener noreferrer" download>link {displayname}</a>
{/if}

<style>
  .pdf-viewer {
    width: 100%;
    height: 90vh;
    min-height: 500px;
  }
</style>