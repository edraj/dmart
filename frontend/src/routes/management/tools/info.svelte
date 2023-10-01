<script>
  import Prism from "@/components/Prism.svelte";
  import { get_manifest, get_settings } from "@/dmart";

</script>

<p class="my-3">Manifest:</p>
{#await get_manifest()}
    <p>Loading...</p>
{:then response} 
    <Prism code={response} />
{/await}

<p class="my-3">Settings:</p>
{#await get_settings()}
    <p>Loading...</p>
{:then response} 
    <Prism code={response} />
{/await}

