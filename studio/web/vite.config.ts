import { realpathSync } from "node:fs";
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// `build` -> dist/ (external assets; the Studio CSP allows script-src 'self' only).
// `build --mode artifact` -> dist-artifact/, then scripts/inline-artifact.mjs folds the
// one JS and one CSS file into index.html for the single-file artifact.
// The real path: a Windows 8.3 short name (C:\Users\ABCDEF~1\...) in the working directory
// would otherwise give React two module IDs and two copies in the bundle.
const root = realpathSync.native(import.meta.dirname);

export default defineConfig(({ mode }) => ({
  root,
  plugins: [react(), tailwindcss()],
  base: "./",
  resolve: { alias: { "@": path.resolve(root, "src") }, dedupe: ["react", "react-dom"] },
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
