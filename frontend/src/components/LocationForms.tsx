import { useEffect, useState, type FormEvent } from "react";
import { useQueryClient, useMutation } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { ArrowRight, Check, Plus, Settings2, X } from "lucide-react";
import { ApiError, api } from "../api";
import { type Location } from "../types";
import { ErrorNotice } from "./ui";

export function AddLocation() {
  const [open, setOpen] = useState(false);
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: (data: unknown) =>
      api<Location>("/api/locations/", "POST", data),
    onSuccess: (data) => {
      cache.invalidateQueries({ queryKey: ["locations"] });
      setOpen(false);
      window.location.hash = "/p/" + data.id;
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    mutation.mutate({
      name: data.get("name"),
      address: data.get("address"),
      status: data.get("status"),
    });
  }
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button className="button">
          <Plus size={17} /> Add location
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="modal">
          <div className="drawer-head">
            <Dialog.Title>Add a location</Dialog.Title>
            <Dialog.Close
              className="icon-button"
              aria-label="Close add location"
            >
              <X />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">
            Save a property record for your team. A new address starts without a
            verified pin or area metrics.
          </Dialog.Description>
          <form onSubmit={submit}>
            <label>
              Property name
              <input name="name" required maxLength={200} />
            </label>
            <label>
              US address
              <input name="address" required maxLength={500} />
            </label>
            <label>
              Status
              <select name="status" defaultValue="candidate">
                <option value="candidate">Candidate</option>
                <option value="owned">Owned</option>
              </select>
            </label>
            {mutation.error && <ErrorNotice error={mutation.error} />}
            <button className="button" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save record"}
              <ArrowRight size={16} />
            </button>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function EditLocation({
  location,
  open: openProp,
  onOpenChange: onOpenChangeProp,
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
  const [openState, setOpen] = useState(false);
  const open = controlled ? openProp : openState;
  const [snapshot, setSnapshot] = useState(location);
  useEffect(() => {
    if (controlled && openProp) setSnapshot(location);
    // Initialise once each time the menu opens the dialog.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [controlled, openProp]);
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: (data: unknown) =>
      api<Location>(`/api/locations/${location.id}/`, "PATCH", data),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["locations"] });
      cache.invalidateQueries({ queryKey: ["location", location.id] });
      cache.invalidateQueries({ queryKey: ["history", location.id] });
      cache.invalidateQueries({ queryKey: ["analysis", location.id] });
      if (controlled) onOpenChangeProp?.(false);
      else setOpen(false);
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (
      data.get("status") === "archived" &&
      snapshot.status !== "archived" &&
      !window.confirm("Archive this property? It leaves the portfolio and the weekly brief. You can restore it later by setting the status back.")
    )
      return;
    mutation.mutate({
      expected_version: snapshot.version,
      name: data.get("name"),
      status: data.get("status"),
      ring_preset: data.get("ring_preset"),
      notes: data.get("notes"),
    });
  }
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (next) {
          setSnapshot(location);
          mutation.reset();
        }
        if (controlled) onOpenChangeProp?.(next);
        else setOpen(next);
      }}
    >
      {!controlled && (
        <Dialog.Trigger asChild>
          <button className="button secondary">
            Edit record <Settings2 size={16} />
          </button>
        </Dialog.Trigger>
      )}
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content
          className="modal"
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
            <Dialog.Title>Edit property record</Dialog.Title>
            <Dialog.Close
              className="icon-button"
              aria-label="Close edit record"
            >
              <X />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">
            Changes are attributed to your account and kept in the record
            history.
          </Dialog.Description>
          <form onSubmit={submit}>
            <label>
              Name
              <input name="name" required defaultValue={snapshot.name} />
            </label>
            <label>
              Status
              <select name="status" defaultValue={snapshot.status}>
                <option value="owned">Owned</option>
                <option value="candidate">Candidate</option>
                <option value="archived">Archived</option>
              </select>
            </label>
            <label>
              Ring preset
              <select name="ring_preset" defaultValue={snapshot.ring_preset}>
                <option>1/3/5</option>
                <option>3/5/10</option>
              </select>
            </label>
            <label>
              Team notes
              <textarea name="notes" defaultValue={snapshot.notes} rows={4} />
            </label>
            {mutation.error && <ErrorNotice error={mutation.error} />}
            {mutation.error instanceof ApiError &&
              mutation.error.status === 409 && (
                <button
                  className="button secondary"
                  type="button"
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
            <button className="button" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save changes"}
              <Check size={16} />
            </button>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
