import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const API_TARGET = process.env.VITE_API_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
  server: {
    port: 3000,
    proxy: {
      // Same contract as the old Next rewrites: /backend/* -> FastAPI (prefix stripped).
      "/backend": {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/backend/, ""),
      },
    },
  },
  preview: {
    port: 3000,
    proxy: {
      "/backend": {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/backend/, ""),
      },
    },
  },
});