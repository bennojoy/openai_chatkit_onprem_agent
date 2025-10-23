import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Any call to /api/* from the frontend will be proxied to FastAPI
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});

