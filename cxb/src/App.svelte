<script module lang="ts">
    import {createRouter, Router} from "@roxi/routify";
    import routes from "../.routify/routes.default";
    import {SvelteToast, type SvelteToastOptions} from "@zerodevx/svelte-toast";
    import './app.css'

    const prefix='cxb'; // ""

  const options: SvelteToastOptions = {
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
  var appRouter = null;
  async function prepareRouter() {
    if (appRouter) return appRouter;
    appRouter = createRouter({
      routes: routes,
      urlRewrite: {
        toInternal: (url) => {
          if(url.startsWith(`/${prefix}`)){
              url = url.replace(`/${prefix}`, "");
          }
          url = url === "" ? "/" : url;
          if (url.startsWith("/management")){
            return url;
          }
          // eslint-disable-next-line svelte/valid-compile
          const lang = $locale;
          const paths = url.split("/");
          paths.shift();
          let fileName = paths[paths.length - 1];
          if (fileName === "") {
            fileName = "index";
          }

          if (![".en", ".ar", ".ku"].includes(fileName)) {
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
        //  toExternal: (url) => url,
        toExternal: (url) => `/${prefix}${url}`,
      },
    });
    return appRouter;
  }
  setupI18n();
  $effect(() => { document.dir = $dir; refresh_spaces.refresh(); });
</script>

<div id="routify-app">
  <SvelteToast {options} />
  {#await prepareRouter() then router}
    <Router {router} />
  {/await}
</div>

<style lang="postcss">
  :global(.custom-toast.info) {
    --toastBackground: rgba(72, 187, 120, 0.9);
    --toastBarBackground: #2f855a;
    z-index: 999;
  }
  :global(.custom-toast.warn) {
    --toastBackground: #bb4848e6;
    --toastBarBackground: #852f2f;
    --toastContainerZIndex: 99999999999999;
  }
</style>
