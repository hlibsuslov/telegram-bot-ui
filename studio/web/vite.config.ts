import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `build` -> dist/ (external assets; the Studio CSP allows script-src 'self' only).
// `build --mode artifact` -> dist-artifact/, then scripts/inline-artifact.mjs folds the
// one JS and one CSS file into index.html for the single-file artifact.
export default defineConfig(({ mode }) => ({
  plugins: [react(), tailwindcss()],
  base: "./",
  resolve: { alias: { "@": path.resolve(import.meta.dirname, "src") } },
  build: {
    outDir: mode === "artifact" ? "dist-artifact" : "dist",
    emptyOutDir: true,
    modulePreload: false,
    assetsInlineLimit: 0,
    cssCodeSplit: false,
    chunkSizeWarningLimit: 1500,
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
}));
