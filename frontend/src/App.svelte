<script context="module">
  import { Router, createRouter } from "@roxi/routify";
  import routes from "../.routify/routes.default.js";

  const router = createRouter({ routes });
</script>

<script>
  import { setupI18n, dir } from "./i18n";

  setupI18n();
  $: {
    try {
      document.dir = $dir;
      if ($dir == "rtl") {
        document.head.children["bootstrap"].href =
          "/assets/bootstrap.rtl.min.css";
      } else {
        document.head.children["bootstrap"].href = "/assets/bootstrap.min.css";
      }
    } catch (error) {
      console.log("Error in App:", error);
    }
  }
</script>

<div id="routify-app">
  <Router {router} />
</div>
