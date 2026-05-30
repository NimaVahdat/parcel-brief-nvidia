import { defineConfig } from "vitest/config";
import path from "node:path";

// Unit-test config for the pure report/selection logic. A node environment is
// sufficient because the tested modules (selection helpers, report assembler)
// have no DOM or React dependencies — the jsPDF rendering and the popup
// component are verified in the browser, not here.
export default defineConfig({
  test: {
    environment: "node",
    include: ["**/*.test.ts"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, ".") },
  },
});
