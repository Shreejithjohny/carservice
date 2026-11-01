import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import basicSsl from "@vitejs/plugin-basic-ssl";

// The browser tests run their own backend on another port (see playwright.config.ts)
const API = process.env.VITE_API_PROXY || "http://127.0.0.1:8000";

export default defineConfig(({ mode }) => {
  // `npm run dev:phone`: serve over https:// on the Wi-Fi network, because phone browsers only
  // allow GPS on https:// (or localhost). The certificate is self-signed, so the phone shows a
  // warning once; accept it to continue. Development only.
  const phone = mode === "phone";
  return {
    plugins: [react(), tailwindcss(), ...(phone ? [basicSsl({ name: "doorstep-dev" })] : [])],
    server: {
      port: 5173,
      strictPort: true,
      host: phone ? true : undefined,
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
  };
});
