/** Data hooks against the PART C contract (docs/REDESIGN_PLAN.md F3). */
import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Location, Session, Source } from "../types";
import { isBusy, newlyReady, POLL_GIVE_UP_MS, pollDelay, readyMessage } from "./analysis";
import { allLocations, api, ApiError } from "./client";
import { keys } from "./keys";
import { fetchLegacyBundle } from "./legacyAnalysis";
import type {
  AnalysisBundle,
  AnalysisListItem,
  CreateAnalysisBody,
  CreateAnalysisResponse,
  SignalsResponse,
} from "./types";

/** A bare 404 (no JSON detail) means the route is not deployed yet, not that the record is missing. */
export const isMissingRoute = (error: unknown) => error instanceof ApiError && error.status === 404 && !error.detail;

let bundleRoute: boolean | null = null;
/** For tests: forget whether the bundle endpoint exists. */
export function resetRouteDetection() {
  bundleRoute = null;
  analysesRoute = null;
}

/** GET the PART C bundle; falls back to the legacy adapter until B3b is deployed. */
export async function fetchAnalysis(id: string): Promise<AnalysisBundle> {
  if (bundleRoute !== false) {
    try {
      const bundle = await api<AnalysisBundle>(`/api/locations/${id}/analysis/`);
      bundleRoute = true;
      return { ...bundle, kpis: bundle.kpis ?? [], takeaways: bundle.takeaways ?? [], signals: bundle.signals ?? [], risk_badges: bundle.risk_badges ?? [] };
    } catch (error) {
      if (!isMissingRoute(error)) throw error;
      bundleRoute = false;
    }
  }
  return fetchLegacyBundle(id);
}

export function useSession() {
  return useQuery({ queryKey: keys.session, queryFn: () => api<Session>("/api/session/"), retry: false });
}
export function useLocations(enabled = true) {
  return useQuery({ queryKey: keys.locations, queryFn: allLocations, enabled });
}
export function useSources(enabled = true) {
  return useQuery({ queryKey: keys.sources, queryFn: () => api<Source[]>("/api/sources/"), enabled });
}

/**
 * The analysis bundle, polled only while it is queued/running/partial (poll_after_ms clamped to
 * 1.5–30 s). After 15 minutes of polling it stops; `gaveUp` lets the page show "Still processing ·
 * Check again", and `checkAgain` refetches and restarts the clock.
 */
export function useAnalysis(id: string) {
  const busySince = useRef<number | null>(null);
  const [gaveUp, setGaveUp] = useState(false);
  const query = useQuery({
    queryKey: keys.analysis(id),
    queryFn: () => fetchAnalysis(id),
    refetchIntervalInBackground: false,
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 1,
    refetchInterval: (q) => {
      const analysis = q.state.data?.analysis;
      if (!isBusy(analysis?.state)) {
        busySince.current = null;
        return false;
      }
      busySince.current ??= Date.now();
      const delay = pollDelay(analysis, Date.now() - busySince.current);
      if (delay === false) setTimeout(() => setGaveUp(true), 0);
      return delay;
    },
  });
  const checkAgain = useCallback(() => {
    busySince.current = Date.now();
    setGaveUp(false);
    void query.refetch();
  }, [query]);
  return { ...query, gaveUp: gaveUp && isBusy(query.data?.analysis.state), checkAgain };
}

/**
 * Announces sections as they become ready ("Retail landscape is ready") and, once the analysis
 * completes, refreshes the property list and alerts that depend on it.
 */
export function useAnalysisTransitions(bundle: AnalysisBundle | undefined) {
  const cache = useQueryClient();
  const previous = useRef<AnalysisBundle | undefined>(undefined);
  const [message, setMessage] = useState("");
  useEffect(() => {
    const before = previous.current;
    previous.current = bundle;
    if (!before || !bundle || before.location.id !== bundle.location.id) return;
    const ready = newlyReady(before, bundle);
    const completed = isBusy(before.analysis.state) && bundle.analysis.state === "complete";
    if (ready.length || completed) setMessage(readyMessage(ready, completed));
    if (completed) {
      void cache.invalidateQueries({ queryKey: keys.locations });
      void cache.invalidateQueries({ queryKey: ["signals"] });
    }
  }, [bundle, cache]);
  return message;
}

// ---- New places (B5). Until /api/analyses/ is deployed, the screens API stands in. ----
let analysesRoute: boolean | null = null;
interface LegacyScreen extends Location {
  screening?: boolean;
}
function fromScreen(l: LegacyScreen): AnalysisListItem {
  return {
    id: l.id,
    name: l.name,
    display_label: null,
    address: l.address,
    lat: l.current_revision.lat,
    lon: l.current_revision.lon,
    created_at: l.created_at,
    kept: false,
    expires_at: null,
    // The screens API has no run state; key numbers appear once the analysis has finished.
    state: l.current_revision.lat === null ? "unplaced" : l.key_numbers && Object.keys(l.key_numbers).length ? "complete" : "running",
    key_numbers: l.key_numbers,
  };
}
export async function fetchAnalyses(): Promise<AnalysisListItem[]> {
  if (analysesRoute !== false) {
    try {
      const rows = await api<AnalysisListItem[] | { results: AnalysisListItem[] }>("/api/analyses/");
      analysesRoute = true;
      return Array.isArray(rows) ? rows : rows.results;
    } catch (error) {
      if (!isMissingRoute(error)) throw error;
      analysesRoute = false;
    }
  }
  const screens = await api<{ results: LegacyScreen[] }>("/api/screens/");
  return screens.results.map(fromScreen);
}
export function useAnalyses() {
  return useQuery({ queryKey: keys.analyses, queryFn: fetchAnalyses });
}

export async function createAnalysis(body: CreateAnalysisBody): Promise<CreateAnalysisResponse> {
  if (analysesRoute !== false) {
    try {
      const result = await api<CreateAnalysisResponse>("/api/analyses/", "POST", body);
      analysesRoute = true;
      return result;
    } catch (error) {
      if (!isMissingRoute(error)) throw error;
      analysesRoute = false;
    }
  }
  if (!("address" in body))
    throw new ApiError(400, "Analyzing a map point needs the latest server update. Type an address instead.");
  const legacy = await api<{ location: Location; geocode_status: string }>("/api/screens/", "POST", body);
  const status = legacy.geocode_status === "matched" ? "matched" : legacy.geocode_status === "ambiguous" ? "ambiguous" : "no_match";
  return { location: legacy.location, geocode: { status }, ...(status === "matched" ? {} : { next: "place_pin" as const }) };
}
export function useCreateAnalysis() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: createAnalysis,
    onSuccess: () => void cache.invalidateQueries({ queryKey: keys.analyses }),
  });
}

/** Star / unstar a new place (optimistic; rolled back on failure). */
export function useKeepAnalysis() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: ({ id, kept }: { id: string; kept: boolean }) =>
      api<{ kept: boolean; expires_at: string | null }>(`/api/analyses/${id}/keep/`, "POST", { kept }),
    onMutate: async ({ id, kept }) => {
      await cache.cancelQueries({ queryKey: keys.analyses });
      const before = cache.getQueryData<AnalysisListItem[]>(keys.analyses);
      cache.setQueryData<AnalysisListItem[]>(keys.analyses, (rows) => rows?.map((r) => (r.id === id ? { ...r, kept } : r)));
      cache.setQueryData<AnalysisBundle>(keys.analysis(id), (b) => (b ? { ...b, location: { ...b.location, kept } } : b));
      return { before };
    },
    onError: (_error, { id }, context) => {
      if (context?.before) cache.setQueryData(keys.analyses, context.before);
      void cache.invalidateQueries({ queryKey: keys.analysis(id) });
    },
    onSettled: (_data, _error, { id }) => {
      void cache.invalidateQueries({ queryKey: keys.analyses });
      void cache.invalidateQueries({ queryKey: keys.analysis(id) });
    },
  });
}

export function useSignals(status = "active") {
  return useQuery({
    queryKey: keys.signals(status),
    queryFn: () => api<SignalsResponse>(`/api/signals/?status=${encodeURIComponent(status)}`),
  });
}

export function useCompare<T>(ids: string[]) {
  return useQuery({
    queryKey: keys.compare(ids),
    enabled: ids.length >= 2,
    queryFn: () => api<T>(`/api/compare/?ids=${ids.join(",")}`),
  });
}

export { POLL_GIVE_UP_MS };
