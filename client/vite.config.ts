import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The browser tests run their own backend on another port (see playwright.config.ts)
const API = process.env.VITE_API_PROXY || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: API,
        changeOrigin: true,
      },
      "/media": {
        target: API,
        changeOrigin: true,
      },
      "/uploads": {
        target: API,
        changeOrigin: true,
      },
    },
  },
});
