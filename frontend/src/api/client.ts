/** Same-origin JSON transport with CSRF; addresses only ever travel in POST bodies. */
import type { Location, Page } from "../types";
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** The server's own `detail`, when it sent JSON (a bare 404 means the route does not exist). */
    public detail: string | null = null,
    /** The parsed JSON error body (some endpoints return data with an error status, e.g. B5's 503). */
    public body: unknown = null,
  ) {
    super(message);
  }
}
export function csrfToken() {
  return (
    document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
      ?.content ?? ""
  );
}
export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
): Promise<T> {
  if (!path.startsWith("/api/")) throw new Error("Invalid API path");
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(data === undefined ? {} : { "Content-Type": "application/json" }),
      ...(method === "GET" ? {} : { "X-CSRFToken": csrfToken() }),
    },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  if (!response.ok) {
    let detail = "";
    let body: unknown = null;
    try {
      body = await response.clone().json();
      if (body && typeof (body as { detail?: unknown }).detail === "string") detail = (body as { detail: string }).detail;
    } catch {
      /* not JSON */
    }
    const message = detail && response.status !== 403 && response.status < 500 ? detail :
      response.status === 409
        ? "This record changed. Reload it before saving."
        : response.status === 403
          ? "Please sign in again to continue."
          : response.status === 400
            ? "Please check the entered values and try again."
            : response.status === 429
              ? "Too many requests in a short time. Please wait a minute and try again."
              : "This request could not be completed. Please try again.";
    throw new ApiError(response.status, message, detail || null, body);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
export async function allLocations(): Promise<Location[]> {
  let path: string | null = "/api/locations/?status=all";
  const records: Location[] = [];
  for (let page = 0; path && page < 200; page++) {
    const result: Page<Location> = await api<Page<Location>>(path);
    records.push(...result.results);
    if (result.next) {
      const next = new URL(result.next, window.location.origin);
      if (next.origin !== window.location.origin)
        throw new Error("Invalid pagination origin");
      path = next.pathname + next.search;
    } else path = null;
  }
  if (path) throw new Error("Portfolio pagination did not complete");
  return records;
}
