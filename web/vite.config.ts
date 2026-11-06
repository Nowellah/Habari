import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the app runs on :3000 (an origin the API allows) and every server path goes to Django on :8000.
const api = process.env.HABARI_API ?? "http://127.0.0.1:8000";
const proxied = ["/api", "/hooks", "/sim", "/manifest.webmanifest", "/sw.js", "/admin", "/officer", "/login", "/logout", "/static",
  "/kb", "/status", "/metrics", "/about", "/share", "/r", "/mock", "/voice"];

// Screens of the app that share a prefix with a server path. The app itself serves them; /status/<code> still goes to Django.
const appScreens = new Set(["/status"]);
const proxy = Object.fromEntries(proxied.map((path) => [path, {
  target: api,
  bypass: (req: { url?: string }) => (appScreens.has((req.url ?? "").split("?")[0]) ? "/index.html" : undefined),
}]));

export default defineConfig({
  plugins: [react()],
  server: { port: 3000, proxy },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
