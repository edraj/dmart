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
  import {locale} from "svelte-i18n";

  function findRoute(routesChildren, paths) {
      if (paths.length === 0) {
          return routesChildren;
      }

      const [currentPath, ...remainingPaths] = paths;
      const matchingChild = routesChildren.find(child => child.name === currentPath);

      if (matchingChild) {
          return findRoute(matchingChild.children, remainingPaths);
      } else {
          return null;
      }
  }
  async function prepareRouter(lang: string) {
      // console.log($activeRoute.fragments.pop().node);
      return createRouter({
          routes: routes,
          urlRewrite: {
              toInternal: (url) => {
                  const paths = url.split("/");
                  paths.shift();
                  const fileName = paths[paths.length-1]
                  if (![".en", ".ar", ".kd"].includes(fileName)) {
                      paths[paths.length-1] = `${fileName}.${lang}`;
                      if (findRoute(routes.children, paths) !== null){
                          return url.split('/').slice(0, url.split('/').length-1).join("/") + `/${fileName}.${lang}`;
                      }
                  }
                  return url;
              },
              toExternal: url => {
                  return url;
              }
          }
      });
  }

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
  {#await prepareRouter($locale) then router}
    <Router {router} />
  {/await}
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
