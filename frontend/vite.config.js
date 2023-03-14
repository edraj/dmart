import { svelte } from "@sveltejs/vite-plugin-svelte";
import routify from "@roxi/routify/vite-plugin";
import { defineConfig } from "vite";
import { mdsvex } from "mdsvex";
import preprocess from "svelte-preprocess";
import pluginRewriteAll from "vite-plugin-rewrite-all";

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
      '^/docs.*': 'http://127.0.0.1:8282',
      '^/openapi.json': 'http://127.0.0.1:8282',
      '^/user/.*': 'http://127.0.0.1:8282',
      '^/info/.*': 'http://127.0.0.1:8282',
      '^/managed/.*': 'http://127.0.0.1:8282',
      '^/public/.*': 'http://127.0.0.1:8282',
      '^/ws': {
        target: 'ws://127.0.0.1:8484',
        ws: true,
      },
    }
  },
});
