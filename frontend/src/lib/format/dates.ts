/** Date labels (moved from api.ts in WI-2). */
/** "checked Nov 21, 2026" or "not checked yet" (never "checked Not checked"). */
export const checkedLabel = (value: string | null | undefined) =>
  value ? `checked ${dateLabel(value)}` : "not checked yet";
export const dateLabel = (value: string | null | undefined) =>
  value
    ? new Intl.DateTimeFormat("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "America/New_York",
      }).format(new Date(value.length === 10 ? value + "T12:00:00Z" : value))
    : "Not checked";

/** Readable data periods: "Overture 2026-11-18.0" → "Overture Nov 2026"; others unchanged. */
export function periodLabel(period: string | null | undefined): string | null {
  if (!period) return null;
  return period.replace(/\b(\d{4})-(\d{2})-\d{2}(?:\.\d+)?\b/, (_, y: string, m: string) =>
    new Date(Number(y), Number(m) - 1, 1).toLocaleString("en-US", { month: "short", year: "numeric" }),
  );
}
