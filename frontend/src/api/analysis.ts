/** Polling and run-state rules for an analysis bundle (pure; tested in tests/analysis.test.ts). */
import type { AnalysisBundle, AnalysisInfo, AnalysisState, SectionKey, SectionResult } from "./types";

export const POLL_MIN_MS = 1500;
export const POLL_MAX_MS = 30_000;
export const POLL_DEFAULT_MS = 3000;
/** After this long without finishing, stop polling and offer "Check again". */
export const POLL_GIVE_UP_MS = 15 * 60_000;

export const isBusy = (state: AnalysisState | undefined) => state === "queued" || state === "running" || state === "partial";

/**
 * Next refetch delay, or false to stop: only while queued/running/partial, `poll_after_ms`
 * clamped to 1.5–30 s (3 s when absent), and never after 15 minutes of polling.
 */
export function pollDelay(analysis: Pick<AnalysisInfo, "state" | "poll_after_ms"> | undefined, pollingForMs = 0): number | false {
  if (!analysis || !isBusy(analysis.state)) return false;
  if (pollingForMs >= POLL_GIVE_UP_MS) return false;
  const wanted = analysis.poll_after_ms ?? POLL_DEFAULT_MS;
  return Math.min(POLL_MAX_MS, Math.max(POLL_MIN_MS, wanted));
}

export const SECTION_LABELS: Record<SectionKey, string> = {
  demographics: "Trade area & demographics",
  economy: "Market",
  traffic: "Access & traffic",
  hazards: "Risk",
  businesses: "Retail landscape",
  jobs: "Daytime population",
};

export type RunState = "ready" | "loading" | "unavailable";
/** What a section shell shows: skeleton while running/pending, the reason when unavailable. */
export function sectionRunState(section: SectionResult | undefined): RunState {
  if (!section) return "loading";
  if (section.status === "ready") return section.data ? "ready" : "unavailable";
  if (section.status === "unavailable") return "unavailable";
  return "loading";
}

/** Sections that turned ready between two bundles, for the polite "… is ready" announcement. */
export function newlyReady(before: AnalysisBundle | undefined, after: AnalysisBundle | undefined): SectionKey[] {
  if (!before || !after) return [];
  return (Object.keys(after.sections) as SectionKey[]).filter(
    (key) => after.sections[key]?.status === "ready" && before.sections[key]?.status !== "ready",
  );
}

/** Overall state from section states (used by the legacy adapter). */
export function deriveState(placed: boolean, sections: SectionResult[]): AnalysisState {
  if (!placed) return "unplaced";
  const busy = sections.filter((s) => s.status === "running" || s.status === "pending").length;
  const ready = sections.filter((s) => s.status === "ready").length;
  if (!busy) return ready || sections.length === 0 ? "complete" : "failed";
  return ready ? "partial" : "running";
}

/** "Retail landscape is ready" / "Analysis complete". */
export function readyMessage(keys: SectionKey[], complete: boolean): string {
  if (complete) return "Analysis complete.";
  if (!keys.length) return "";
  const names = keys.map((k) => SECTION_LABELS[k]);
  return names.length === 1 ? `${names[0]} is ready.` : `${names.slice(0, -1).join(", ")} and ${names.at(-1)} are ready.`;
}
