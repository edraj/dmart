import {defineConfig} from "vite";
import {mdsvex} from "mdsvex";
import routify from "@roxi/routify/vite-plugin";
import {svelte, vitePreprocess} from "@sveltejs/vite-plugin-svelte";
import {viteStaticCopy} from "vite-plugin-static-copy";
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
  base: "./",
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
      "render.ssr": {enable: false},
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
          'event_directive_deprecated',
          'css_unused_selector'
        ];
        if (
            warning.code?.startsWith("a11y") ||
            warning.filename?.startsWith("/node_modules") ||
            ignoredWarnings.includes(warning.code)
        )
          return;
        if (typeof defaultHandler !== "undefined") defaultHandler(warning);
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
            const pkg = id.toString().split('node_modules/')[1].split('/')[0].toString();
            // Skip packages that produce empty chunks after tree-shaking
            const skipChunks = [
              '@popperjs', 'date-fns', 'fast-deep-equal', 'fast-uri',
              'jmespath', 'json-schema-traverse', 'jsonpath-plus'
            ];
            if (skipChunks.includes(pkg)) return;
            return pkg;
          }
        },
      },
    }
  },
  server: {port: 1337},
});