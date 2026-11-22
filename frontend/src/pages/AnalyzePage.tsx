import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";
import { useCreateAnalysis, useLocations } from "../api/hooks";
import { keys } from "../api/keys";
import type { CreateAnalysisResponse } from "../api/types";
import { navigate } from "../app/router";
import { PickMap, type PickPoint } from "../components/map/lazy";
import { Button } from "../components/ui/Button";
import { AddressSearch } from "../features/analyze/AddressSearch";
import { CandidateList, type Candidate } from "../features/analyze/CandidateList";
import { RecentAnalyses } from "../features/analyze/RecentAnalyses";
import type { Location } from "../types";

type Step =
  | { kind: "idle" }
  | { kind: "ambiguous"; location: Location; lookupId: string; version: number; candidates: Candidate[] }
  | { kind: "place-pin"; location: Location; message: string };

/** 400 (outside the US) and 429 (busy) become field-level messages; everything else stays general. */
function messageFor(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 429) {
      const retry = (error.body as { retry_after?: number } | null)?.retry_after;
      return `Several analyses are running. Try again${retry ? ` in ${retry} seconds` : " in a minute"}.`;
    }
    if (error.status === 400) return error.detail || "Enter a US street address or choose a point in the United States.";
    return error.message;
  }
  return error instanceof Error ? error.message : "The analysis could not start.";
}

/**
 * `#/analyze`: type an address or click the map; the new place's analysis page opens at once and
 * fills in as each part arrives. Ambiguous addresses ask which match; unmatched ones are placed by
 * clicking the map for the same record.
 */
export function AnalyzePage() {
  const cache = useQueryClient();
  const create = useCreateAnalysis();
  const locations = useLocations();
  const [step, setStep] = useState<Step>({ kind: "idle" });
  const [draft, setDraft] = useState<PickPoint | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mapError, setMapError] = useState<string | null>(null);

  const bounds = useMemo(() => {
    const pins = (locations.data ?? []).filter((l) => l.status === "owned" && l.current_revision.lat !== null);
    if (!pins.length) return null;
    const lons = pins.map((l) => l.current_revision.lon!),
      lats = pins.map((l) => l.current_revision.lat!);
    return [
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)],
    ] as [[number, number], [number, number]];
  }, [locations.data]);

  const open = (id: string) => {
    void cache.invalidateQueries({ queryKey: keys.analyses });
    navigate("/analyze/" + id);
  };
  function handle(result: CreateAnalysisResponse) {
    const status = result.geocode?.status;
    if (status === "matched" || status === "map_point" || (!status && result.location.current_revision.lat !== null))
      return open(result.location.id);
    if (status === "ambiguous" && result.geocode?.lookup_id && result.geocode.candidates?.length) {
      setStep({
        kind: "ambiguous",
        location: result.location,
        lookupId: result.geocode.lookup_id,
        version: result.geocode.expected_version ?? result.location.version,
        candidates: result.geocode.candidates,
      });
      return;
    }
    setDraft(null);
    setStep({
      kind: "place-pin",
      location: result.location,
      message:
        status === "unavailable"
          ? "The Census geocoder is not responding. Click the map to place this address."
          : "We couldn't find that address. Click the map to place it.",
    });
  }

  const accept = useMutation({
    mutationFn: ({ location, lookupId, version, index }: { location: Location; lookupId: string; version: number; index: number }) =>
      api<Location>(`/api/locations/${location.id}/geocode/${lookupId}/accept/`, "POST", {
        expected_version: version,
        candidate_index: index,
      }),
    onSuccess: (location) => open(location.id),
    onError: (e) => setError(messageFor(e)),
  });
  const placePin = useMutation({
    mutationFn: ({ location, point }: { location: Location; point: PickPoint }) =>
      api<Location>(`/api/locations/${location.id}/pin/`, "POST", {
        expected_version: location.version,
        lat: Number(point.lat.toFixed(6)),
        lon: Number(point.lon.toFixed(6)),
        confirmed: false,
      }),
    onSuccess: (location) => open(location.id),
    onError: (e) => setMapError(messageFor(e)),
  });

  const busy = create.isPending || accept.isPending || placePin.isPending;
  const placing = step.kind === "place-pin";
  return (
    <div className="analyze-page">
      <div className="analyze-panel">
        <h1>Analyze a place</h1>
        <p className="analyze-intro">
          A full analysis of any US location from public data: residents, jobs, retail, traffic, risk and the local
          market, ranked against your properties.
        </p>
        {step.kind === "ambiguous" ? (
          <CandidateList
            candidates={step.candidates}
            busy={accept.isPending}
            onChoose={(index) => accept.mutate({ location: step.location, lookupId: step.lookupId, version: step.version, index })}
            onCancel={() => setStep({ kind: "idle" })}
          />
        ) : (
          <AddressSearch
            busy={create.isPending}
            error={error}
            onSubmit={(address) => {
              setError(null);
              setStep({ kind: "idle" });
              create.mutate({ address }, { onSuccess: handle, onError: (e) => setError(messageFor(e)) });
            }}
          />
        )}
        {placing && (
          <div className="place-pin-note" role="status">
            <p>{step.message}</p>
            <Button variant="ghost" size="sm" onClick={() => setStep({ kind: "idle" })}>
              Cancel
            </Button>
          </div>
        )}
        {!placing && <p className="analyze-or">or click anywhere on the map</p>}
        <RecentAnalyses />
      </div>
      <div className="analyze-map">
        <PickMap
          initialBounds={bounds}
          draft={draft}
          busy={busy}
          confirmLabel={placing ? "Place the pin here" : "Analyze this point"}
          label={placing ? "Map: click where the address is" : "Map: click a point to analyze it"}
          onPick={(point) => {
            setMapError(null);
            setDraft(point);
          }}
          onConfirm={(point) => {
            setMapError(null);
            if (step.kind === "place-pin") placePin.mutate({ location: step.location, point });
            else create.mutate({ lat: point.lat, lon: point.lon }, { onSuccess: handle, onError: (e) => setMapError(messageFor(e)) });
          }}
        />
        {mapError && (
          <p className="field-error" role="alert">
            {mapError}
          </p>
        )}
      </div>
    </div>
  );
}
