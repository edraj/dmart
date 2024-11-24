<script module lang="ts">
  import { Router, createRouter } from "@roxi/routify";
  import routes from "../.routify/routes.default";
  import { SvelteToast } from "@zerodevx/svelte-toast";
  // import "bootstrap-icons/font/bootstrap-icons.min.css"
  // const rtlUrl = new URL('bootstrap/dist/css/bootstrap.rtl.min.css', import.meta.url).href;
  // const ltrUrl = new URL('bootstrap/dist/css/bootstrap.min.css', import.meta.url).href;
  // const rtlUrl = new URL('./../assets/morph/bootstrap.rtl.min.css', import.meta.url).href;
  // const ltrUrl = new URL('./../assets/morph/bootstrap.min.css', import.meta.url).href;

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

  function findRoute(routers, paths, lang) {
      if (paths.length === 0) {
          return routers;
      }

      const [currentPath, ...remainingPaths] = paths;

      const matchingChild = routers.children.find(
          (child) => child.name === `${currentPath}`
      );
      if (matchingChild) {
          return findRoute(matchingChild, remainingPaths, lang);
      } else {
          return null;
      }
  }
  async function prepareRouter() {
      return createRouter({
          routes: routes,
          urlRewrite: {
              toInternal: (url) => {
                  url = url === "" ? "/" : url;

                  if (url.startsWith("/management")){
                      return url;
                  }
                  const lang = $locale;
                  const paths = url.split("/");
                  paths.shift();
                  let fileName = paths[paths.length - 1];
                  if (fileName === "") {
                      fileName = "index";
                  }

                  if (![".en", ".ar", ".kd"].includes(fileName)) {
                      paths[paths.length - 1] = `${fileName}.${lang}`;
                      let result = findRoute(routes, paths, lang);
                      // if the REQUIRED+LANG file is NOT found
                      // then look for the REQUIRED file
                      if (result === null) {
                          paths[paths.length - 1] = fileName;
                          result = findRoute(routes, paths, lang);
                          // if the REQUIRED file is NOT found
                          // then look for the INDEX+LANG file
                          if (result === null) {
                              paths[paths.length - 1] = `index.${lang}`;
                              result = findRoute(routes, paths, lang);
                              // if the INDEX+LANG file is NOT found
                              // then look for the INDEX file
                              if (result === null) {
                                  paths[paths.length - 1] = `index`;
                                  result = findRoute(routes, paths, lang);
                                  if (result !== null) {
                                      // return INDEX
                                      return (
                                          url
                                              .split("/")
                                              .slice(0, url.split("/").length - 1)
                                              .join("/") + `/${paths[paths.length - 1]}`
                                      );
                                  }
                              } else {
                                  // return INDEX+LANG
                                  return (
                                      url
                                          .split("/")
                                          .slice(0, url.split("/").length - 1)
                                          .join("/") + `/${paths[paths.length - 1]}`
                                  );
                              }
                          } else {
                              // return REQUIRED
                              return (
                                  url
                                      .split("/")
                                      .slice(0, url.split("/").length - 1)
                                      .join("/") + `/${paths[paths.length - 1]}`
                              );
                          }
                      } else {
                          // return REQUIRED+LANG
                          return (
                              url
                                  .split("/")
                                  .slice(0, url.split("/").length - 1)
                                  .join("/") + `/${paths[paths.length - 1]}`
                          );
                      }
                  }

                  return url;
              },
              toExternal: (url) => url,
          },
      });
  }
  setupI18n();
  $effect(() => { document.dir = $dir; refresh_spaces.refresh(); });
</script>

<svelte:head>
  <link rel="stylesheet" media="screen" href="{new URL('bootstrap-icons/font/bootstrap-icons.min.css', import.meta.url).href}">
  <link rel="stylesheet" media="screen" href="{new URL('./app.css', import.meta.url).href}">
  {#key $themesStore}
    {#if $dir === "rtl"}
      <link rel="stylesheet" id="bootstrap" media="screen"
            href="{new URL($themesStore.rtlUrl, import.meta.url).href}"
      />
    {:else}
      <link rel="stylesheet" id="bootstrap" media="screen"
            href="{new URL($themesStore.ltrUrl, import.meta.url).href}"
      />
    {/if}
  {/key}
</svelte:head>

<div id="routify-app">
  <SvelteToast {options} />
  {#await prepareRouter() then router}
    <Router {router} />
  {/await}
</div>
