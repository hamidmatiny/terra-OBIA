import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "happy-dom",
    setupFiles: "./src/test/setup.ts",
    globals: true,
    // Explicit fixed bounds — never derive min/max from runner CPU count.
    // (CI previously failed with Tinypool RangeError when --maxWorkers=1 left
    // minWorkers at the auto CPU-derived value, so min > max.)
    pool: "forks",
    minWorkers: 1,
    maxWorkers: 2,
    poolOptions: {
      forks: {
        minForks: 1,
        maxForks: 2,
      },
    },
  },
});
