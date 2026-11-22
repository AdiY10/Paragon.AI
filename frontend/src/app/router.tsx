/**
 * Hash router (no library). Routes live after "#", query parameters after "?" inside the hash,
 * e.g. "#/?state=CT". Addresses never go into the URL.
 */
import { useCallback, useSyncExternalStore, type AnchorHTMLAttributes, type ReactNode } from "react";

export type Route =
  | { name: "properties" }
  | { name: "property"; id: string }
  | { name: "analyze" }
  | { name: "place"; id: string }
  | { name: "alerts" }
  | { name: "compare" }
  | { name: "sources" }
  | { name: "admin" }
  | { name: "notFound"; path: string };

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const isUuid = (value: string) => UUID.test(value);

const STATIC: Record<string, Route> = {
  "/": { name: "properties" },
  "/analyze": { name: "analyze" },
  "/alerts": { name: "alerts" },
  "/compare": { name: "compare" },
  "/sources": { name: "sources" },
  "/admin": { name: "admin" },
};

/** Splits "#/p/1?section=risk" (or "/p/1?section=risk") into a path and its query. */
export function parseHash(hash: string): { path: string; query: URLSearchParams } {
  const raw = hash.startsWith("#") ? hash.slice(1) : hash;
  const [pathPart, ...rest] = raw.split("?");
  let path = pathPart || "/";
  if (!path.startsWith("/")) path = "/" + path;
  if (path.length > 1 && path.endsWith("/")) path = path.slice(0, -1);
  return { path, query: new URLSearchParams(rest.join("?")) };
}

export function matchRoute(path: string): Route {
  const fixed = STATIC[path];
  if (fixed) return fixed;
  const parts = path.split("/").filter(Boolean);
  if (parts.length === 2 && isUuid(parts[1])) {
    if (parts[0] === "p") return { name: "property", id: parts[1].toLowerCase() };
    if (parts[0] === "analyze") return { name: "place", id: parts[1].toLowerCase() };
  }
  return { name: "notFound", path };
}

/** The new hash for an old route ("#/portfolio" → "#/"), or null when the hash is current. */
export function legacyRedirect(hash: string): string | null {
  const { path, query } = parseHash(hash);
  const q = query.toString();
  const withQuery = (to: string) => "#" + to + (q ? "?" + q : "");
  if (path === "/portfolio") return withQuery("/");
  if (path === "/setup") return "#/";
  if (path === "/screen") return "#/analyze";
  const old = /^\/locations\/([^/]+)$/.exec(path);
  if (old) return withQuery("/p/" + old[1]);
  return null;
}

const NAVIGATE_EVENT = "paragon:navigate";
const listeners = new Set<() => void>();
function notify() {
  listeners.forEach((fn) => fn());
}
function applyLegacyRedirect() {
  const next = legacyRedirect(window.location.hash);
  if (next) window.history.replaceState(window.history.state, "", next);
}
function subscribe(fn: () => void) {
  listeners.add(fn);
  const onHash = () => {
    applyLegacyRedirect();
    fn();
  };
  window.addEventListener("hashchange", onHash);
  window.addEventListener(NAVIGATE_EVENT, fn);
  return () => {
    listeners.delete(fn);
    window.removeEventListener("hashchange", onHash);
    window.removeEventListener(NAVIGATE_EVENT, fn);
  };
}
const snapshot = () => window.location.hash || "#/";

/** Call once before the first render so old bookmarks land on the new route. */
export function installRouter() {
  applyLegacyRedirect();
}

/** Go to a route ("/p/…" or "#/p/…"). `replace` swaps the history entry instead of adding one. */
export function navigate(to: string, { replace = false } = {}) {
  const hash = to.startsWith("#") ? to : "#" + to;
  if (replace) {
    window.history.replaceState(window.history.state, "", hash);
    window.dispatchEvent(new Event(NAVIGATE_EVENT));
    notify();
  } else window.location.hash = hash;
}

export function useHash() {
  return useSyncExternalStore(subscribe, snapshot, () => "#/");
}

export function useRoute(): { path: string; route: Route; query: URLSearchParams } {
  const hash = useHash();
  const { path, query } = parseHash(hash);
  return { path, route: matchRoute(path), query };
}

/**
 * One query parameter as state. Updates replace the history entry and never move focus,
 * because the path does not change.
 */
export function useQueryState(key: string, fallback = ""): [string, (value: string) => void] {
  const hash = useHash();
  const value = parseHash(hash).query.get(key) ?? fallback;
  const set = useCallback(
    (next: string) => {
      const { path, query } = parseHash(window.location.hash);
      if (next === fallback || next === "") query.delete(key);
      else query.set(key, next);
      const q = query.toString();
      navigate(path + (q ? "?" + q : ""), { replace: true });
    },
    [key, fallback],
  );
  return [value, set];
}

/** Is `path` inside the section a top-nav item points at? Properties owns "/p/…". */
export function isActive(item: string, path: string) {
  if (item === "/") return path === "/" || path.startsWith("/p/");
  return path === item || path.startsWith(item + "/");
}

export function Link({
  to,
  children,
  ...rest
}: { to: string; children: ReactNode } & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href">) {
  return (
    <a href={"#" + (to.startsWith("#") ? to.slice(1) : to)} {...rest}>
      {children}
    </a>
  );
}
