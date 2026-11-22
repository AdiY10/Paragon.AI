import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Check, MapPin, X } from "lucide-react";
import { api, ApiError } from "../../../api/client";
import type { Location } from "../../../types";
import { PreviewMap } from "../../../components/map/lazy";

export default function PinEditor({
  location,
  open: openProp,
  onOpenChange,
  returnFocus,
}: {
  location: Location;
  /** Controlled from the "Property actions" menu (no own trigger button). */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Where focus goes when the dialog closes (the menu button). */
  returnFocus?: () => void;
}) {
  const controlled = openProp !== undefined;
  const [openState, setOpen] = useState(false),
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
      cache.invalidateQueries({ queryKey: ["analysis", location.id] });
      openChange(false);
    },
  });
  const open = controlled ? openProp : openState;
  function init() {
    setSnapshot(location);
    setLatitude(location.current_revision.lat?.toFixed(6) ?? "");
    setLongitude(location.current_revision.lon?.toFixed(6) ?? "");
    setConfirmed(false);
    mutation.reset();
  }
  function openChange(next: boolean) {
    if (next) init();
    if (controlled) onOpenChange?.(next);
    else setOpen(next);
  }
  useEffect(() => {
    if (controlled && openProp) init();
    // Initialise once each time the menu opens the dialog.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [controlled, openProp]);
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
      {!controlled && (
        <Dialog.Trigger asChild>
          <button className="btn btn-secondary btn-sm">
            <MapPin size={15} />
            {location.current_revision.lat === null ? "Place pin" : "Correct / confirm pin"}
          </button>
        </Dialog.Trigger>
      )}
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content
          className="modal pin-editor"
          onCloseAutoFocus={
            returnFocus
              ? (event) => {
                  event.preventDefault();
                  returnFocus();
                }
              : undefined
          }
        >
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
                className="btn btn-secondary btn-md"
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
            <button className="btn btn-primary btn-md" disabled={!valid || mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save pin"}
              <Check size={16} />
            </button>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
