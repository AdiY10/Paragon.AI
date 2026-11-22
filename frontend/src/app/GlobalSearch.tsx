import { useState, type FormEvent } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, Search, X } from "lucide-react";
import { api } from "../api/client";
import type { Location, Page } from "../types";
import { setPendingAddress } from "./nav";
import { navigate } from "./router";

/**
 * FR-36 search. The query is POSTed (never placed in a URL). When nothing matches, the typed text
 * can be handed to the Analyze page as a new place.
 */
export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const search = useMutation({
    mutationFn: (q: string) => api<Page<Location>>("/api/locations/search/", "POST", { q }),
  });
  const submitted = search.variables ?? "";
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = text.trim();
    if (q) search.mutate(q);
  }
  function onOpenChange(next: boolean) {
    setOpen(next);
    if (!next) {
      setText("");
      search.reset();
    }
  }
  const results = search.data?.results ?? [];
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Trigger asChild>
        <button type="button" className="nav-button search-trigger" aria-label="Search">
          <Search size={16} aria-hidden="true" />
          <span className="search-label" aria-hidden="true">
            Search
          </span>
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="shell-overlay" />
        <Dialog.Content className="search-dialog">
          <div className="search-dialog-head">
            <Dialog.Title>Search properties</Dialog.Title>
            <Dialog.Close className="icon-btn" aria-label="Close search">
              <X size={18} aria-hidden="true" />
            </Dialog.Close>
          </div>
          <Dialog.Description className="sr-only">
            Find an owned property or analyzed place by name or address.
          </Dialog.Description>
          <form className="search-form" role="search" onSubmit={submit}>
            <input
              aria-label="Search by name or address"
              placeholder="Name or address"
              value={text}
              maxLength={200}
              onChange={(event) => setText(event.target.value)}
              autoComplete="off"
            />
            <button className="btn btn-primary btn-md" type="submit" disabled={search.isPending}>
              Search
            </button>
          </form>
          <div aria-live="polite">
            {search.isPending && <p className="search-status">Searching…</p>}
            {search.error && (
              <p className="search-status" role="alert">
                {(search.error as Error).message}
              </p>
            )}
            {search.isSuccess &&
              (results.length ? (
                <ul className="search-results-list" aria-label="Search results">
                  {results.map((item) => (
                    <li key={item.id}>
                      <a
                        href={(item.screening ? "#/analyze/" : "#/p/") + item.id}
                        onClick={() => onOpenChange(false)}
                      >
                        {item.name}
                        <small>{[item.address, item.city, item.state].filter(Boolean).join(", ")}</small>
                      </a>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="search-status">No matching property records.</p>
              ))}
          </div>
          {search.isSuccess && submitted && (
            <div className="search-analyze">
              <button
                type="button"
                className="btn btn-secondary btn-md"
                onClick={() => {
                  setPendingAddress(submitted);
                  onOpenChange(false);
                  navigate("/analyze");
                }}
              >
                Analyze this address <ArrowRight size={16} aria-hidden="true" />
              </button>
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
