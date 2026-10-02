// Vite and TanStack Start configuration for CityCare Clinic web client.
// Bundles React 19, TanStack Start/Router, and TailwindCSS for production.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
  },
});
