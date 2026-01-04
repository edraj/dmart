// import { VitePWA } from "vite-plugin-pwa";
// <reference types="vitest" />
import {defineConfig} from "vite";
import {mdsvex} from "mdsvex";
// import preprocess from "svelte-preprocess";
import routify from "@roxi/routify/vite-plugin";
import {svelte, vitePreprocess} from "@sveltejs/vite-plugin-svelte";
import {viteStaticCopy} from "vite-plugin-static-copy";
import * as path from "path";
import plantuml from "@akebifiky/remark-simple-plantuml";
import svelteMd from "vite-plugin-svelte-md";
import tailwindcss from "@tailwindcss/vite"
import {execSync} from "node:child_process";

const production = process.env.NODE_ENV === "production";
const gitHash = (() => {
  try {
    return execSync("git rev-parse --short HEAD").toString().trim();
  } catch {
    return "unknown";
  }
})();

export default defineConfig({
  base: "/cxb",  // "/"
  clearScreen: false,
  define: {
    'import.meta.env.VITE_GIT_HASH': JSON.stringify(gitHash),
  },
  resolve: {
    alias: {
      "@": process.cwd() + "/src",
      "~": process.cwd() + "/node_modules",
    },
  },
  plugins: [
    tailwindcss(),
    svelteMd(),
    viteStaticCopy({
      targets: [
        {
          src: 'public/config.json',
          dest: ''
        }
      ]
    }),
    routify({
      "render.ssr": {enable: false /*production*/},
      // ssr: { enable: false /*production*/ },
    }),
    svelte({
      compilerOptions: {
        dev: !production,
      },
      extensions: [".md", ".svelte"],
      preprocess: [
        vitePreprocess(),
        mdsvex({
          extension: "md",
          remarkPlugins: [
            plantuml, {
              baseUrl: "https://www.plantuml.com/plantuml/svg"
            }
          ],
        }) as any
      ],
      onwarn: (warning, defaultHandler) => {
        const ignoredWarnings = [
                    'non_reactive_update',
                    'state_referenced_locally',
                    'element_invalid_self_closing_tag',
                    'event_directive_deprecated'
                ];
        // Ignore a11y_click_events_have_key_events warning from sveltestrap
        if (
            warning.code?.startsWith("a11y") ||
            // warning.filename?.startsWith("/node_modules/svelte-jsoneditor")
            warning.filename?.startsWith("/node_modules") ||
            ignoredWarnings.includes(warning.code)
        )
          return;
        if (typeof defaultHandler != "undefined") defaultHandler(warning);
      },
    }),
  ],
  build: {
    chunkSizeWarningLimit: 512,
    cssMinify: 'lightningcss',
    rollupOptions: {
      external: ['$app/environment', '$app/stores', '$app/navigation'],
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            return id.toString().split('node_modules/')[1].split('/')[0].toString();
          }
        },
      },
    }
  },
  server: {port: 1337},
});
