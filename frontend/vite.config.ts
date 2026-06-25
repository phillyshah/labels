import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API/processor/health calls to the FastAPI backend.
// In production the build is served as static files by the backend, so all
// API paths used in the app are RELATIVE (e.g. "/api/login") — never hardcoded.
const BACKEND = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
      "/process": { target: BACKEND, changeOrigin: true },
      "/healthz": { target: BACKEND, changeOrigin: true },
    },
  },
});
