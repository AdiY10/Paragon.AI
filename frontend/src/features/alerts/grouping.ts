/** Alerts page logic (pure): filter grouped alerts and arrange them by property, worst first. */
import type { SignalGroup } from "../../api/types";

export type Level = "High" | "Watch" | "FYI";
export const LEVELS: Level[] = ["High", "Watch", "FYI"];
export const DEFAULT_LEVELS: Level[] = ["High", "Watch"];
const RANK: Record<string, number> = { High: 0, Watch: 1, FYI: 2 };

/** "High,Watch" from the URL → levels; empty or invalid → the default High + Watch. */
export function parseLevels(param: string | null | undefined): Level[] {
  const levels = (param ?? "").split(",").filter((l): l is Level => (LEVELS as string[]).includes(l));
  return levels.length ? levels : DEFAULT_LEVELS;
}
export const levelsParam = (levels: Level[]) =>
  levels.length === DEFAULT_LEVELS.length && DEFAULT_LEVELS.every((l) => levels.includes(l)) ? "" : levels.join(",");

export function filterGroups(groups: SignalGroup[], { levels, category, property }: { levels: Level[]; category?: string; property?: string }) {
  return groups.filter(
    (g) =>
      levels.includes(g.severity) &&
      (!category || g.category === category) &&
      (!property || g.locations.some((l) => l.id === property)),
  );
}

export interface PropertyBucket {
  location: SignalGroup["locations"][number];
  groups: SignalGroup[];
}

/**
 * Shared alerts (one county figure or one nearby place for several properties) are listed once;
 * every other alert sits under its property. Properties are ordered worst first, then by name.
 */
export function arrange(groups: SignalGroup[]): { shared: SignalGroup[]; byProperty: PropertyBucket[] } {
  const sortGroups = (list: SignalGroup[]) => [...list].sort((a, b) => RANK[a.severity] - RANK[b.severity] || a.title.localeCompare(b.title));
  const shared = sortGroups(groups.filter((g) => g.locations.length > 1));
  const buckets = new Map<string, PropertyBucket>();
  for (const g of groups) {
    if (g.locations.length !== 1) continue;
    const loc = g.locations[0];
    const bucket = buckets.get(loc.id) ?? { location: loc, groups: [] };
    bucket.groups.push(g);
    buckets.set(loc.id, bucket);
  }
  const worst = (b: PropertyBucket) => Math.min(...b.groups.map((g) => RANK[g.severity]));
  const count = (b: PropertyBucket, level: Level) => b.groups.filter((g) => g.severity === level).length;
  const byProperty = [...buckets.values()]
    .map((b) => ({ ...b, groups: sortGroups(b.groups) }))
    .sort(
      (a, b) =>
        worst(a) - worst(b) ||
        count(b, "High") - count(a, "High") ||
        count(b, "Watch") - count(a, "Watch") ||
        a.location.name.localeCompare(b.location.name),
    );
  return { shared, byProperty };
}
