import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The FastAPI backend runs on 127.0.0.1:8000 (see README.md at the repo root).
// During `npm run dev`, every /api/* call is proxied there so the browser
// never needs to know the backend's real origin or deal with CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    outDir: "dist",
  },
});
