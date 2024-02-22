<script context="module" lang="ts">
  import { Router, createRouter } from "@roxi/routify";
  import routes from "../.routify/routes.default";
  import { SvelteToast } from "@zerodevx/svelte-toast";
  import "bootstrap-icons/font/bootstrap-icons.min.css";
  // const rtlUrl = new URL('bootstrap/dist/css/bootstrap.rtl.min.css', import.meta.url).href;
  // const ltrUrl = new URL('bootstrap/dist/css/bootstrap.min.css', import.meta.url).href;
  // const rtlUrl = new URL('./../assets/morph/bootstrap.rtl.min.css', import.meta.url).href;
  // const ltrUrl = new URL('./../assets/morph/bootstrap.min.css', import.meta.url).href;

  const router = createRouter({ routes });
  const options = {
    duration: 2500, // duration of progress bar tween to the `next` value
    initial: 1, // initial progress bar value
    next: 0, // next progress value
    pausable: false, // pause progress bar tween on mouse hover
    dismissable: true, // allow dismiss with close button
    reversed: false, // insert new toast to bottom of stack
    intro: { x: 256 }, // toast intro fly animation settings
    theme: {
      "--toastColor": "mintcream",
    }, // css var overrides
    classes: ["custom-toast"], // user-defined classes
  };
</script>

<script lang="ts">
  import { setupI18n, dir } from "./i18n";
  import refresh_spaces from "@/stores/management/refresh_spaces";
  import {themesStore} from "@/stores/themes_store";

  setupI18n();
  $: { document.dir = $dir; refresh_spaces.refresh(); }
</script>

<svelte:head>
  {#key $themesStore}
    {#if $dir === "rtl"}
      <link rel="stylesheet" id="bootstrap"
            href="{new URL($themesStore.rtlUrl, import.meta.url).href}"
      />
    {:else}
      <link rel="stylesheet" id="bootstrap"
            href="{new URL($themesStore.ltrUrl, import.meta.url).href}"
      />
    {/if}
  {/key}
</svelte:head>

<div id="routify-app">
  <SvelteToast {options} />
  <Router {router} />
</div>

<style>
  :global(.custom-toast.info) {
    --toastBackground: rgba(72, 187, 120, 0.9);
    --toastBarBackground: #2f855a;
  }
  :global(.custom-toast.warn) {
    --toastBackground: #bb4848e6;
    --toastBarBackground: #852f2f;
  }
</style>
