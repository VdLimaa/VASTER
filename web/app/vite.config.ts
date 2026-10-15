import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// No desenvolvimento o Vite serve a tela e repassa /api para o FastAPI, que
// continua sendo o backend. No build, o FastAPI serve o dist/ direto, então
// só sobe um processo.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VASTER_API ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
