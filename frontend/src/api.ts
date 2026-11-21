import type { Location, Page } from "./types";
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
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
    try {
      const body = await response.clone().json();
      if (body && typeof body.detail === "string") detail = body.detail;
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
    throw new ApiError(response.status, message);
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
export const dateLabel = (value: string | null | undefined) =>
  value
    ? new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "America/New_York",
      }).format(new Date(value.length === 10 ? value + "T12:00:00Z" : value))
    : "Not checked";
