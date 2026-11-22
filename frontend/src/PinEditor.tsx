import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Check, MapPin, X } from "lucide-react";
import { api, ApiError } from "./api";
import type { Location } from "./types";
import { PreviewMap } from "./components/map/lazy";

export default function PinEditor({ location }: { location: Location }) {
  const [open, setOpen] = useState(false),
    [snapshot, setSnapshot] = useState(location);
  const [latitude, setLatitude] = useState(""),
    [longitude, setLongitude] = useState(""),
    [confirmed, setConfirmed] = useState(false);
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: (data: unknown) => api<Location>(`/api/locations/${location.id}/pin/`, "POST", data),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["location", location.id] });
      cache.invalidateQueries({ queryKey: ["locations"] });
      cache.invalidateQueries({ queryKey: ["history", location.id] });
      setOpen(false);
    },
  });
  function openChange(next: boolean) {
    if (next) {
      setSnapshot(location);
      setLatitude(location.current_revision.lat?.toFixed(6) ?? "");
      setLongitude(location.current_revision.lon?.toFixed(6) ?? "");
      setConfirmed(false);
      mutation.reset();
    }
    setOpen(next);
  }
  const lat = latitude.trim() ? Number(latitude) : NaN,
    lon = longitude.trim() ? Number(longitude) : NaN;
  const valid = Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180;
  const preview: Location = {
    ...snapshot,
    current_revision: {
      ...snapshot.current_revision,
      lat: valid ? lat : null,
      lon: valid ? lon : null,
      confirmed: false,
      method: "manual",
    },
  };
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (valid)
      mutation.mutate({
        expected_version: snapshot.version,
        lat,
        lon,
        confirmed,
      });
  }
  return (
    <Dialog.Root open={open} onOpenChange={openChange}>
      <Dialog.Trigger asChild>
        <button className="button secondary small-button">
          <MapPin size={15} />
          {location.current_revision.lat === null ? "Place pin" : "Correct / confirm pin"}
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="modal pin-editor">
          <div className="drawer-head">
            <Dialog.Title>Review the property pin</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label="Close pin editor">
              <X />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">
            Enter coordinates or drag the preview pin onto the building. Changes are saved only when you choose Save
            pin. Pin verification does not confirm ownership.
          </Dialog.Description>
          <div className="preview-label">UNSAVED PIN PREVIEW</div>
          {valid ? (
            <PreviewMap
              lat={lat}
              lon={lon}
              draggable
              label="Unsaved pin preview"
              onMove={(nextLat, nextLon) => {
                setLatitude(nextLat.toFixed(6));
                setLongitude(nextLon.toFixed(6));
                setConfirmed(false);
              }}
            />
          ) : (
            <p className="notice">
              Enter a valid latitude and longitude to preview a pin, or close this and use "Find from address" to look
              the address up.
            </p>
          )}
          <form onSubmit={submit}>
            <div className="coordinate-fields">
              <label>
                Latitude
                <input
                  name="latitude"
                  type="number"
                  min={-90}
                  max={90}
                  step="any"
                  required
                  value={latitude}
                  onChange={(e) => {
                    setLatitude(e.target.value);
                    setConfirmed(false);
                  }}
                />
              </label>
              <label>
                Longitude
                <input
                  name="longitude"
                  type="number"
                  min={-180}
                  max={180}
                  step="any"
                  required
                  value={longitude}
                  onChange={(e) => {
                    setLongitude(e.target.value);
                    setConfirmed(false);
                  }}
                />
              </label>
            </div>
            <label className="checkbox-label">
              <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />I checked
              that this pin is on the property building.
            </label>
            <p className="small muted">
              Saving creates a new manual pin revision and marks existing analysis for recalculation. Previous pin
              evidence remains in the history.
            </p>
            {mutation.error && (
              <p className="notice error" role="alert">
                {mutation.error.message}
              </p>
            )}
            {mutation.error instanceof ApiError && mutation.error.status === 409 && (
              <button
                type="button"
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
            <button className="button" disabled={!valid || mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save pin"}
              <Check size={16} />
            </button>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
