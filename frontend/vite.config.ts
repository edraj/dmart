// import { VitePWA } from "vite-plugin-pwa";
// <reference types="vitest" />
import { defineConfig } from "vite";
import { mdsvex } from "mdsvex";
import preprocess from "svelte-preprocess";
import routify from "@roxi/routify/vite-plugin";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import {viteStaticCopy} from "vite-plugin-static-copy";
import * as path from "path";
import plantuml from "@akebifiky/remark-simple-plantuml"

const production = process.env.NODE_ENV === "production";

export default defineConfig({
  clearScreen: false,
  resolve: {
    alias: {
      "@": process.cwd() + "/src",
      "~": process.cwd() + "/node_modules",
    },
  },
  plugins: [
    // VitePWA({
    //   strategies: "injectManifest",
    //   srcDir: "src",
    //   filename: "sw.ts",
    //   injectRegister: null,
    //   injectManifest: {
    //     globPatterns: ["**/*.{js,css,html,svg,png,woff2,ts,svelte}"],
    //   },
    //   registerType: "autoUpdate",
    //   manifest: {
    //     background_color: "#ffffff",
    //     theme_color: "#7E1F86",
    //     name: "Unixfy.net",
    //     short_name: "Unixfy.net",
    //     start_url: "/",
    //     display: "standalone",
    //     icons: [],
    //   },
    //   devOptions: {
    //     enabled: true,
    //     type: "module",
    //   },
    // }),
    /*svelteInspector({
            // toggleKeyCombo: 'meta-shift',
      showToggleButton: 'always',
      toggleButtonPos: 'bottom-right'
    }),*/
    viteStaticCopy({
      targets: [
        {
          src: path.resolve(__dirname, './assets') + '/[!.]*',
          dest: 'assets'
        },
        {
          src: path.resolve(__dirname, './node_modules/bootstrap-icons/font/fonts/bootstrap-icons.woff'),
          dest: 'assets/fonts'
        },
        {
          src: path.resolve(__dirname, './node_modules/bootstrap-icons/font/fonts/bootstrap-icons.woff2'),
          dest: 'assets/fonts'
        }
      ]
    }),
    routify({
      "render.ssr": { enable: false /*production*/ },
      // ssr: { enable: false /*production*/ },
    }),
    svelte({
      compilerOptions: {
        dev: !production,
        hydratable: true,
      },
      extensions: [".md", ".svelte"],
      preprocess: [preprocess(), mdsvex({
        extension: "md",
        remarkPlugins:  [plantuml,{ baseUrl: "https://www.plantuml.com/plantuml/svg" }]
      })],
      onwarn: (warning, defaultHandler) => {
        // Ignore a11y-click-events-have-key-events warning from sveltestrap
        if (
          warning.code?.startsWith("a11y") ||
          // warning.filename?.startsWith("/node_modules/svelte-jsoneditor")
          warning.filename?.startsWith("/node_modules")
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
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            return id.toString().split('node_modules/')[1].split('/')[0].toString();
          }
        },
      },
    }
  },
  server: { port: 1337 },
  // test: {
  //   environment: "jsdom",
  //   globals: true,
  // },
});
