import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/check-company": "http://127.0.0.1:8000",
      "/recheck-company": "http://127.0.0.1:8000",
      "/extract-entities": "http://127.0.0.1:8000",
      "/extract-job-info": "http://127.0.0.1:8000",
      "/upload": "http://127.0.0.1:8000",
      "/upload-offer-letter": "http://127.0.0.1:8000",
      "/analyze-screenshot": "http://127.0.0.1:8000",
      "/api": "http://127.0.0.1:8000",
      "/create-share-report": "http://127.0.0.1:8000",
      "/report": "http://127.0.0.1:8000",
      "/extension": "http://127.0.0.1:8000",
    },
  },
});
