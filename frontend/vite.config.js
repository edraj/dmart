import { defineConfig } from "vite";
import { mdsvex } from "mdsvex";
import pluginRewriteAll from "vite-plugin-rewrite-all";
import preprocess from "svelte-preprocess";
import routify from "@roxi/routify/vite-plugin";
import { svelte } from "@sveltejs/vite-plugin-svelte";

const production = process.env.NODE_ENV === "production";

export default defineConfig({
  clearScreen: false,
  base: "/",
  plugins: [
    routify({
      ssr: { enable: false },
    }),
    svelte({
      compilerOptions: {
        dev: !production,
        hydratable: !!process.env.ROUTIFY_SSR_ENABLE,
      },
      extensions: [".md", ".svelte"],
      preprocess: [preprocess(), mdsvex({ extension: "md" })],
      onwarn: (warning, defaultHandler) => {
        // Ignore a11y-click-events-have-key-events warning from sveltestrap
        // This ignore can be removed after this issue is closed https://github.com/bestguy/sveltestrap/issues/509.
        if (
          warning.code === "a11y-click-events-have-key-events" &&
          warning.filename?.startsWith("/node_modules/sveltestrap")
        )
          return;

        // ignore a11y warnings from sveltetab
        if (
          warning.code ===
            "a11y-no-noninteractive-element-to-interactive-role" ||
          warning.code === "a11y-click-events-have-key-events"
        )
          return;
        console.log(warning);
        defaultHandler(warning);
      },
    }),
    pluginRewriteAll(),
  ],
  build: {
    chunkSizeWarningLimit: 1000,
    outDir: "./dist/",
  },
  server: {
    strictPort: true,
    port: 5000,
    proxy: {
      "^/docs.*": "http://127.0.0.1:8282",
      "^/openapi.json": "http://127.0.0.1:8282",
      "^/user/.*": "http://127.0.0.1:8282",
      "^/info/.*": "http://127.0.0.1:8282",
      "^/managed/.*": "http://127.0.0.1:8282",
      "^/public/.*": "http://127.0.0.1:8282",
      "^/ws": {
        target: "ws://127.0.0.1:8484",
        ws: true,
      },
    },
  },
});
