import { lazy, Suspense, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Compass, X } from "lucide-react";
import { api, ApiError, dateLabel } from "./api";
import type { Location } from "./types";
const LocationMap = lazy(() => import("./LocationMap"));
export interface GeocodePreview {
  id: string;
  expected_version: number;
  status: "matched" | "ambiguous" | "no_match";
  candidates: {
    lat: number;
    lon: number;
    method: string;
    matched_address: string;
    match_quality: string;
    geographies: Record<
      string,
      { geoid: string; name: string; geography_vintage: string }
    >;
  }[];
  benchmark: { id: string; name: string };
  vintage: { id: string; name: string };
  retrieved_at: string;
  last_checked_at: string;
  expires_at: string;
  source: {
    id: string;
    name: string;
    url: string;
    snapshot_id: string;
    sha256: string;
  };
  notice: string;
}
export default function GeocodeDialog({ location }: { location: Location }) {
  const [open, setOpen] = useState(false),
    [snapshot, setSnapshot] = useState(location),
    [choice, setChoice] = useState<number | null>(null);
  const cache = useQueryClient();
  const lookup = useMutation({
    mutationFn: () =>
      api<GeocodePreview>(`/api/locations/${location.id}/geocode/`, "POST", {
        expected_version: snapshot.version,
      }),
    onSuccess: (data) => setChoice(data.candidates.length === 1 ? 0 : null),
  });
  const accept = useMutation({
    mutationFn: () =>
      api<Location>(
        `/api/locations/${location.id}/geocode/${lookup.data!.id}/accept/`,
        "POST",
        { expected_version: snapshot.version, candidate_index: choice },
      ),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["locations"] });
      cache.invalidateQueries({ queryKey: ["location", location.id] });
      cache.invalidateQueries({ queryKey: ["history", location.id] });
      setOpen(false);
    },
  });
  function onOpenChange(next: boolean) {
    if (next) {
      setSnapshot(location);
      setChoice(null);
      lookup.reset();
      accept.reset();
    }
    setOpen(next);
  }
  const data = lookup.data,
    candidate = choice === null ? null : data?.candidates[choice];
  const error = accept.error ?? lookup.error;
  const preview: Location | undefined = candidate
    ? {
        ...snapshot,
        name: candidate.matched_address,
        current_revision: {
          ...snapshot.current_revision,
          lat: candidate.lat,
          lon: candidate.lon,
          confirmed: false,
          method: "census_interpolated",
          matched_address: candidate.matched_address,
        },
      }
    : undefined;
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Trigger asChild>
        <button className="button secondary small-button">
          <Compass size={15} />
          Find address pin
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="modal geocode-dialog">
          <div className="drawer-head">
            <Dialog.Title>Find a Census address pin</Dialog.Title>
            <Dialog.Close
              className="icon-button"
              aria-label="Close address lookup"
            >
              <X />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">
            Census will receive the saved address below. Its points are
            interpolated along the street, not verified on the building. Your
            saved pin changes only after you choose a suggestion and accept it.
          </Dialog.Description>
          <p className="lookup-address">{snapshot.address}</p>
          {!data && (
            <button
              className="button"
              disabled={lookup.isPending}
              onClick={() => lookup.mutate()}
            >
              {lookup.isPending ? "Finding suggestions…" : "Find suggestions"}
              <ArrowRight size={15} />
            </button>
          )}
          {lookup.isPending && (
            <p className="small muted" role="status">
              Looking up this address. Your saved record has not changed.
            </p>
          )}
          {error && (
            <p className="notice error" role="alert">
              {error instanceof ApiError && error.status === 503
                ? "Census could not complete this lookup. Try again later or place a pin manually."
                : error.message}
            </p>
          )}
          {error instanceof ApiError && error.status === 409 && (
            <button
              className="button secondary"
              onClick={() => {
                cache.invalidateQueries({
                  queryKey: ["location", location.id],
                });
                setOpen(false);
              }}
            >
              Reload record
            </button>
          )}
          {data && (
            <>
              <p className="notice" role="status">
                {data.status === "no_match"
                  ? "No Census match. Your saved pin is unchanged. You can place or correct it manually."
                  : data.status === "ambiguous"
                    ? "More than one address matched. Review the alternatives and choose one; none is selected automatically."
                    : "One address matched. Review its position before accepting this suggestion."}
              </p>
              {data.candidates.length > 0 && (
                <fieldset className="census-choices">
                  <legend>Choose a recorded suggestion</legend>
                  {data.candidates.map((item, index) => (
                    <label className="census-choice" key={index}>
                      <input
                        type="radio"
                        name="census-choice"
                        value={index}
                        checked={choice === index}
                        onChange={() => setChoice(index)}
                      />
                      <span>
                        <strong>{item.matched_address}</strong>
                        <small>
                          {item.lat.toFixed(6)}, {item.lon.toFixed(6)} ·
                          Street-interpolated
                        </small>
                      </span>
                    </label>
                  ))}
                </fieldset>
              )}
              {preview && (
                <>
                  <span className="preview-label">
                    CENSUS SUGGESTION · NOT YET SAVED
                  </span>
                  <Suspense fallback={<p>Loading suggestion map…</p>}>
                    <LocationMap locations={[preview]} previewOnly />
                  </Suspense>
                </>
              )}
              <p className="small muted">
                Source: U.S. Census Bureau · Checked{" "}
                {dateLabel(data.last_checked_at)} · Original capture{" "}
                {dateLabel(data.retrieved_at)}
              </p>
              <details className="geocode-evidence">
                <summary>Source and geography evidence</summary>
                <dl className="facts">
                  <dt>Address benchmark</dt>
                  <dd>{data.benchmark.name}</dd>
                  <dt>Geography vintage</dt>
                  <dd>{data.vintage.name}</dd>
                  <dt>Exactness</dt>
                  <dd>Not reported by this Census endpoint</dd>
                  <dt>Response hash</dt>
                  <dd>{data.source.sha256}</dd>
                  {candidate &&
                    Object.entries(candidate.geographies).map(
                      ([kind, geography]) => (
                        <div className="geography-evidence" key={kind}>
                          <dt>{kind.replaceAll("_", " ")}</dt>
                          <dd>
                            {geography.name} · {geography.geoid} ·{" "}
                            {geography.geography_vintage}
                          </dd>
                        </div>
                      ),
                    )}
                </dl>
                <a
                  className="text-button"
                  href={data.source.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open provider page
                </a>
              </details>
              {data.candidates.length > 0 && (
                <button
                  className="button"
                  disabled={choice === null || accept.isPending}
                  onClick={() => accept.mutate()}
                >
                  {accept.isPending ? "Saving…" : "Use selected Census pin"}
                  <ArrowRight size={15} />
                </button>
              )}
            </>
          )}
          <p className="small muted">
            Accepting a suggestion does not confirm ownership or verify the
            building position. Manual pin placement remains available from the
            property record.
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
