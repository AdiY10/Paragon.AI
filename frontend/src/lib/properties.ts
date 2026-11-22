/** Filtering and sorting for the Properties page (pure, URL-driven). */
import type { Location } from "../types";

export type Attention = "High" | "Watch" | "Clear";
export const ATTENTION_LEVELS: Attention[] = ["High", "Watch", "Clear"];

export function attentionRank(level: Attention | null | undefined): number {
  return level === "High" ? 0 : level === "Watch" ? 1 : 2;
}

export interface PropertyFilters {
  q?: string;
  state?: string;
  attention?: string;
}

const normalise = (text: string) =>
  text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();

/** Owned properties matching the search text (name, address, city, state), state and attention. */
export function filterProperties(locations: Location[], { q = "", state = "", attention = "" }: PropertyFilters) {
  const words = normalise(q).split(/\s+/).filter(Boolean);
  return locations.filter((l) => {
    if (l.status !== "owned") return false;
    if (state && l.state !== state) return false;
    if (attention && (l.attention ?? "Clear") !== attention) return false;
    if (!words.length) return true;
    const haystack = normalise([l.name, l.address, l.city, l.state].filter(Boolean).join(" "));
    return words.every((word) => haystack.includes(word));
  });
}

export type SortKey =
  | "name"
  | "state"
  | "attention"
  | "population"
  | "income"
  | "aadt"
  | "flood"
  | "supermarket"
  | "alerts";
export type SortDir = "asc" | "desc";
export const SORT_KEYS: SortKey[] = [
  "name",
  "state",
  "attention",
  "population",
  "income",
  "aadt",
  "flood",
  "supermarket",
  "alerts",
];
/** Direction a column sorts in when first chosen: numbers biggest first, risk worst first. */
export const DEFAULT_DIR: Record<SortKey, SortDir> = {
  name: "asc",
  state: "asc",
  attention: "asc",
  population: "desc",
  income: "desc",
  aadt: "desc",
  flood: "asc",
  supermarket: "asc",
  alerts: "desc",
};
export const isSortKey = (value: string): value is SortKey => (SORT_KEYS as string[]).includes(value);

const FLOOD_ORDER = { inside: 0, near: 1, none: 2 } as const;

/** The comparable value for a column; null = missing (always sorted last). */
export function sortValue(l: Location, key: SortKey): number | string | null {
  const k = l.key_numbers ?? {};
  switch (key) {
    case "name":
      return l.name.toLowerCase();
    case "state":
      return l.state || null;
    case "attention":
      return attentionRank(l.attention);
    case "population":
      return k.population ?? null;
    case "income":
      return k.median_household_income ?? null;
    case "aadt":
      return k.aadt ?? null;
    case "flood":
      return k.flood ? FLOOD_ORDER[k.flood] : null;
    case "supermarket":
      return k.nearest_supermarket?.distance_mi ?? null;
    case "alerts":
      return k.active_alerts ?? null;
  }
}

/** Stable sort; missing values last in either direction; ties by attention, then name. */
export function sortProperties(locations: Location[], key: SortKey = "attention", dir: SortDir = "asc") {
  const sign = dir === "asc" ? 1 : -1;
  return [...locations].sort((a, b) => {
    const va = sortValue(a, key),
      vb = sortValue(b, key);
    if (va === null && vb !== null) return 1;
    if (vb === null && va !== null) return -1;
    if (va !== null && vb !== null && va !== vb) return (va < vb ? -1 : 1) * sign;
    return attentionRank(a.attention) - attentionRank(b.attention) || a.name.localeCompare(b.name);
  });
}

export function attentionCounts(locations: Location[]) {
  const counts: Record<Attention, number> = { High: 0, Watch: 0, Clear: 0 };
  for (const l of locations) if (l.status === "owned") counts[(l.attention ?? "Clear") as Attention] += 1;
  return counts;
}
