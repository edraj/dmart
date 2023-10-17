<script context="module" lang="ts">
  import { Router, createRouter } from "@roxi/routify";
  import routes from "../.routify/routes.default";
  import { SvelteToast } from "@zerodevx/svelte-toast";

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
  import { Level, showToast } from "./utils/toast";

  setupI18n();
  $: {
     try {
       document.dir = $dir;
       const rtl = (<HTMLLinkElement>document.querySelector('link#rtl'));
       const ltr = (<HTMLLinkElement>document.querySelector('link#ltr'));
       if ($dir == "rtl") {
         // document.head.children["rtl"].disabled = false;
         // document.head.children["ltr"].disabled = true;
         rtl.disabled = false;
         ltr.disabled = true;
       } else {
         // document.head.children["ltr"].disabled = false;
         // document.head.children["rtl"].disabled = true;
         ltr.disabled = false;
         rtl.disabled = true;
       }
     } catch (error) {
       showToast(Level.warn, "Error in App: "+error)
    }
  }
</script>

<div id="routify-app">
  <SvelteToast {options} />
  <Router {router} />
</div>

<style>
  @import "~/bootstrap-icons/font/bootstrap-icons.min.css";
  @import "~/bootstrap/dist/css/bootstrap.min.css";

  :global(.custom-toast.info) {
    --toastBackground: rgba(72, 187, 120, 0.9);
    --toastBarBackground: #2f855a;
  }
  :global(.custom-toast.warn) {
    --toastBackground: #bb4848e6;
    --toastBarBackground: #852f2f;
  }
</style>
