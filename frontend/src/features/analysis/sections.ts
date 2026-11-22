/** The fixed section menu (same order for every property and every new place). */
import { sectionRunState, type RunState } from "../../api/analysis";
import type { AnalysisBundle, SectionKey } from "../../api/types";

export type SectionId =
  | "overview"
  | "trade-area"
  | "daytime"
  | "retail"
  | "access"
  | "risk"
  | "market"
  | "tenants"
  | "ranking"
  | "sources";

export interface SectionDef {
  id: SectionId;
  label: string;
  /** Bundle sections whose run state drives the status dot. */
  needs: SectionKey[];
  propertyOnly?: boolean;
}

export const SECTIONS: SectionDef[] = [
  { id: "overview", label: "Overview", needs: [] },
  { id: "trade-area", label: "Trade area & demographics", needs: ["demographics"] },
  { id: "daytime", label: "Daytime population", needs: ["jobs", "demographics"] },
  { id: "retail", label: "Retail landscape", needs: ["businesses"] },
  { id: "access", label: "Access & traffic", needs: ["traffic"] },
  { id: "risk", label: "Risk", needs: ["hazards"] },
  { id: "market", label: "Market", needs: ["economy"] },
  { id: "tenants", label: "Tenants & SEC watch", needs: [], propertyOnly: true },
  { id: "ranking", label: "Ranking vs portfolio", needs: ["demographics", "jobs", "traffic"] },
  { id: "sources", label: "Sources & methods", needs: [] },
];

export const sectionsFor = (kind: "property" | "place") =>
  SECTIONS.filter((s) => kind === "property" || !s.propertyOnly);

export const isSectionId = (value: string): value is SectionId => SECTIONS.some((s) => s.id === value);

/** Status for the menu dot: loading if any input is still running, ready if any is ready. */
export function sectionStatus(def: SectionDef, bundle: AnalysisBundle | undefined): RunState | "none" {
  if (!def.needs.length) {
    if (def.id === "overview" && bundle) {
      const state = bundle.analysis.state;
      return state === "complete" ? "ready" : state === "failed" || state === "unplaced" ? "unavailable" : "loading";
    }
    return "none";
  }
  if (!bundle) return "loading";
  const states = def.needs.map((key) => sectionRunState(bundle.sections[key]));
  if (states.includes("loading")) return "loading";
  return states.includes("ready") ? "ready" : "unavailable";
}

export const STATUS_TEXT: Record<RunState | "none", string> = {
  ready: "ready",
  loading: "loading",
  unavailable: "unavailable",
  none: "",
};
