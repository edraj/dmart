<script lang="ts">
  
import {website} from "@/config";
import {Button, Input} from "sveltestrap";
import MarkdownEditor from "@/components/management/editors/MarkdownEditor.svelte";
import HtmlEditor from "@/components/management/editors/HtmlEditor.svelte";


export let space_name;
export let subpath;
export let content_type;
export let body;
export let jseContent;
export let handleSave;
</script>

{#if content_type === "image"}
  {#if body.endsWith(".wsq")}
    <a
      target="_blank"
      download={body}
      href={`${website.backend}/managed/payload/media/${space_name}/${subpath}/${body}`}
    >{body}</a
    >
  {:else}
    <img
      src={`${website.backend}/managed/payload/media/${space_name}/${subpath}/${body}`}
      alt=""
      class="mw-100 border"
    />
  {/if}
{/if}
{#if content_type === "audio"}
  <audio
    controls
    src={`${website.backend}/managed/payload/content/${space_name}/${subpath}/${body}`}
  >
    <track kind="captions" />
  </audio>
{/if}
{#if content_type === "video"}
  <video
    controls
    src={`${website.backend}/managed/payload/content/${space_name}/${subpath}/${body}`}
  >
    <track kind="captions" />
  </video>
{/if}
{#if content_type === "pdf"}
  <object
    title=""
    class="h-100 w-100 embed-responsive-item"
    type="application/pdf"
    style="height: 100vh;"
    data={`${website.backend}/managed/payload/content/${space_name}/${subpath}/${body}`}
  >
    <p>For some reason PDF is not rendered here properly.</p>
  </object>
{/if}
{#if content_type === "markdown"}
  {#if typeof(jseContent) === "string"}
    <MarkdownEditor bind:content={jseContent} {handleSave} />
  {/if}
{/if}
{#if content_type === "html"}
  <div class="d-flex justify-content-end">
    <Button on:click={handleSave}>Save</Button>
  </div>
  <HtmlEditor bind:content={jseContent} />
{/if}
{#if content_type === "text"}
  <div class="d-flex justify-content-end">
    <Button on:click={handleSave}>Save</Button>
  </div>
  <Input class="mt-3" type="textarea" bind:value={jseContent} />
{/if}
