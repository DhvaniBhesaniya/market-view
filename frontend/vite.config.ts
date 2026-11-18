import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

// Dev: `npm run dev` serves the UI on :5173 and forwards /api to the Python API (`uv run mv ui --no-open`).
// Prod: `npm run build` -> dist/, which the Python API serves itself at http://127.0.0.1:8000.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
  build: {
    chunkSizeWarningLimit: 1200,
  },
  test: {
    include: ["src/**/*.test.ts"],
  },
})
