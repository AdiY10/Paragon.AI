/**
 * Compare selection: up to 4 ids, kept per viewer in localStorage (a convenience; the Compare page
 * itself works from `?ids=`). Storage failures fall back to memory for this tab.
 */
import { useCallback, useSyncExternalStore } from "react";
import { isUuid } from "../../app/router";

export const MAX_COMPARE = 4;
export const LIMIT_MESSAGE = "Up to 4. Remove one first.";
const KEY = "paragon.compare";

/** Valid, unique UUIDs, at most four, in order. */
export function cleanIds(values: unknown): string[] {
  if (!Array.isArray(values)) return [];
  const out: string[] = [];
  for (const value of values)
    if (typeof value === "string" && isUuid(value) && !out.includes(value.toLowerCase())) out.push(value.toLowerCase());
  return out.slice(0, MAX_COMPARE);
}
/** "a,b" from the URL → ids. */
export const parseIds = (param: string | null | undefined) => cleanIds((param ?? "").split(",").filter(Boolean));
export const compareHref = (ids: string[]) => "#/compare?ids=" + ids.join(",");

/** Add or remove `id`; a fifth id is refused (never silently drops another). */
export function toggleSelection(ids: string[], id: string): { ids: string[]; refused: boolean } {
  if (ids.includes(id)) return { ids: ids.filter((x) => x !== id), refused: false };
  if (ids.length >= MAX_COMPARE) return { ids, refused: true };
  return { ids: [...ids, id], refused: false };
}

let memory: string[] = [];
let cache: string[] | null = null;
const listeners = new Set<() => void>();

export function readSelection(): string[] {
  if (cache) return cache;
  try {
    cache = cleanIds(JSON.parse(localStorage.getItem(KEY) ?? "[]"));
  } catch {
    cache = memory;
  }
  return cache;
}
export function writeSelection(ids: string[]) {
  const next = cleanIds(ids);
  memory = next;
  cache = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable: the selection lasts for this tab only */
  }
  listeners.forEach((fn) => fn());
}
function subscribe(fn: () => void) {
  listeners.add(fn);
  const onStorage = (event: StorageEvent) => {
    if (event.key !== KEY) return;
    cache = null;
    fn();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(fn);
    window.removeEventListener("storage", onStorage);
  };
}
const EMPTY: string[] = [];

export function useCompareSelection() {
  const ids = useSyncExternalStore(subscribe, readSelection, () => EMPTY);
  /** Returns false when the id was refused (already four selected). */
  const toggle = useCallback((id: string) => {
    const result = toggleSelection(readSelection(), id);
    if (!result.refused) writeSelection(result.ids);
    return !result.refused;
  }, []);
  const remove = useCallback((id: string) => writeSelection(readSelection().filter((x) => x !== id)), []);
  const clear = useCallback(() => writeSelection([]), []);
  const set = useCallback((next: string[]) => writeSelection(next), []);
  return { ids, toggle, remove, clear, set, full: ids.length >= MAX_COMPARE };
}
