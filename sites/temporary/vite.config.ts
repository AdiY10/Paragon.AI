import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  base: "/static/ui/",
  build: {
    manifest: true,
    outDir: "build/client",
    emptyOutDir: true,
    rollupOptions: { input: "src/main.tsx" },
  },
  server: { host: "127.0.0.1", port: 5173 },
});
