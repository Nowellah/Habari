import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the app runs on :3000 (an origin the API allows) and every server path goes to Django on :8000.
const api = process.env.HABARI_API ?? "http://127.0.0.1:8000";
const proxied = ["/api", "/hooks", "/sim", "/manifest.webmanifest", "/sw.js", "/admin", "/officer", "/login", "/logout", "/static",
  "/kb", "/status", "/metrics", "/about", "/share", "/r", "/mock", "/voice"];

export default defineConfig({
  plugins: [react()],
  server: { port: 3000, proxy: Object.fromEntries(proxied.map((path) => [path, api])) },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
