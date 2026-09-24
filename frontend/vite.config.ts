import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    coverage: {
      provider: "v8",
      reportsDirectory: "./coverage",
      thresholds: {
        statements: 23,
        branches: 14,
        functions: 27,
        lines: 23,
      },
    },
  },
});
