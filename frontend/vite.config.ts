import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to the backend. Inside docker-compose the
// target is http://backend:8000 (VITE_API_TARGET); on a bare host it falls
// back to localhost:8000.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
