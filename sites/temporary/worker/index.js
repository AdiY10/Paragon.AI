import assets from "../build/assets.json";
import manifest from "../build/client/.vite/manifest.json";
import { handleAPI, HttpError } from "./api.js";
const headers = {
  "Cache-Control": "private, no-store",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "SAMEORIGIN",
  "Referrer-Policy": "strict-origin-when-cross-origin",
};
const json = (body, status = 200, extra = {}) =>
  Response.json(body, { status, headers: { ...headers, ...extra } });
export default {
  async fetch(request, env) {
    const url = new URL(request.url),
      path = url.pathname;
    if (path === "/health/") return json({ status: "ok" });
    const identity = {
      id: request.headers.get("oai-authenticated-user-id"),
      email: request.headers.get("oai-authenticated-user-email"),
    };
    if (!identity.id || !identity.email) {
      if (path.startsWith("/api/"))
        return json({ detail: "Sign in to continue" }, 401);
      return Response.redirect(
        url.origin + "/signin-with-chatgpt?return_to=%2F",
        302,
      );
    }
    if (path.startsWith("/api/")) {
      if (!["GET", "HEAD"].includes(request.method)) {
        if (
          request.headers.get("Origin") !== url.origin ||
          request.headers.get("Sec-Fetch-Site") === "cross-site"
        )
          return json({ detail: "Cross-origin changes are denied" }, 403);
        if (
          !(request.headers.get("Content-Type") ?? "").startsWith(
            "application/json",
          )
        )
          return json({ detail: "JSON required" }, 415);
        const body = await request.text();
        if (body.length > 100000)
          return json({ detail: "Request too large" }, 413);
        request = new Request(request, { body });
      }
      try {
        const data = await handleAPI(request, env, identity);
        return json(
          data,
          path === "/api/locations/" && request.method === "POST" ? 201 : 200,
          path === "/api/export/"
            ? {
                "Content-Disposition":
                  'attachment; filename="paragon-radar-workspace.json"',
              }
            : {},
        );
      } catch (error) {
        return json(
          {
            detail:
              error instanceof HttpError
                ? error.message
                : error instanceof SyntaxError
                  ? "Invalid JSON"
                  : "Request could not be completed",
          },
          error instanceof HttpError
            ? error.status
            : error instanceof SyntaxError
              ? 400
              : 500,
        );
      }
    }
    if (request.method !== "GET" && request.method !== "HEAD")
      return new Response("Method not allowed", { status: 405, headers });
    if (assets[path])
      return new Response(
        request.method === "HEAD" ? null : assets[path].body,
        { headers: { ...headers, "Content-Type": assets[path].type } },
      );
    if (path !== "/")
      return new Response("Not found", { status: 404, headers });
    const entry = manifest["src/main.tsx"];
    const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="csrf-token" content=""><meta name="theme-color" content="#153d32"><title>Paragon Radar · Private workspace</title>${(entry.css ?? []).map((file) => `<link rel="stylesheet" href="/static/ui/${file}">`).join("")}<script type="module" src="/static/ui/${entry.file}"></script></head><body><div id="root"></div><noscript>Enable JavaScript to open your private workspace.</noscript></body></html>`;
    return new Response(html, {
      headers: { ...headers, "Content-Type": "text/html; charset=utf-8" },
    });
  },
};
