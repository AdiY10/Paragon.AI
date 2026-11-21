import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink } from "lucide-react";
import { api } from "./api";
import type { Location } from "./types";

/**
 * "Confirm your portfolio" (R2 item 22): review the publicly listed properties in one
 * place, confirm the ones still owned and archive the rest (with undo), then check
 * each property's main tenants.
 */
export default function Onboarding({ locations }: { locations: Location[] }) {
  const cache = useQueryClient();
  const owned = locations.filter((l) => l.status === "owned");
  const toReview = owned.filter((l) => !l.confirmed).sort((a, b) => a.state.localeCompare(b.state) || a.name.localeCompare(b.name));
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [undo, setUndo] = useState<Location[]>([]);
  const [error, setError] = useState("");
  const tenantsToCheck = owned.filter((l) => l.confirmed && (l.unconfirmed_tenants ?? 0) > 0);

  const toggle = (id: string) =>
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const chosen = toReview.filter((l) => selected.has(l.id));

  async function apply(action: "confirm" | "archive", items: Location[]) {
    setBusy(true);
    setError("");
    let done = 0;
    try {
      for (const l of items) {
        if (action === "confirm") await api(`/api/locations/${l.id}/confirm/`, "POST", { expected_version: l.version });
        else await api(`/api/locations/${l.id}/`, "PATCH", { expected_version: l.version, status: "archived" });
        done += 1;
      }
    } catch (e) {
      setError(`${done} of ${items.length} saved. ${(e as Error).message}`);
    }
    setSelected(new Set());
    setMessage(
      action === "confirm"
        ? `${done} propert${done === 1 ? "y" : "ies"} confirmed as owned.`
        : `${done} propert${done === 1 ? "y" : "ies"} archived. They no longer appear in the brief.`,
    );
    setUndo(action === "archive" ? items.slice(0, done) : []);
    await cache.invalidateQueries({ queryKey: ["locations"] });
    setBusy(false);
  }

  async function undoArchive() {
    setBusy(true);
    const fresh = await Promise.all(undo.map((l) => api<Location>(`/api/locations/${l.id}/`)));
    for (const l of fresh) await api(`/api/locations/${l.id}/`, "PATCH", { expected_version: l.version, status: "owned" });
    setUndo([]);
    setMessage("Archive undone.");
    await cache.invalidateQueries({ queryKey: ["locations"] });
    setBusy(false);
  }

  return (
    <>
      <header className="page-head">
        <div>
          <span className="eyebrow">SETUP</span>
          <h1>Confirm your portfolio</h1>
          <p>
            These properties came from Paragon's public listings. Confirm the ones you still own and archive the
            rest, so the weekly brief covers exactly your portfolio.
          </p>
        </div>
      </header>
      {message && (
        <p className="notice success" role="status">
          {message}{" "}
          {undo.length > 0 && (
            <button className="text-button" disabled={busy} onClick={undoArchive}>
              Undo
            </button>
          )}
        </p>
      )}
      {error && (
        <p className="notice error" role="alert">
          {error}
        </p>
      )}
      <section className="panel" aria-labelledby="step1">
        <div className="section-heading">
          <h2 id="step1">Step 1 · Which of these do you own? ({toReview.length} to review)</h2>
        </div>
        {toReview.length === 0 ? (
          <p className="notice success">Every owned property is confirmed.</p>
        ) : (
          <>
            <div className="bulk-bar">
              <label>
                <input
                  type="checkbox"
                  checked={chosen.length === toReview.length}
                  onChange={(e) => setSelected(new Set(e.target.checked ? toReview.map((l) => l.id) : []))}
                />{" "}
                Select all
              </label>
              <span>{chosen.length} selected</span>
              <button className="button small-button" disabled={busy || !chosen.length} onClick={() => apply("confirm", chosen)}>
                <Check size={15} /> Confirm as owned
              </button>
              <button
                className="button secondary small-button"
                disabled={busy || !chosen.length}
                onClick={() => {
                  if (window.confirm(`Archive ${chosen.length} propert${chosen.length === 1 ? "y" : "ies"}? You can undo this.`))
                    apply("archive", chosen);
                }}
              >
                Archive (no longer owned)
              </button>
            </div>
            <ul className="review-list">
              {toReview.map((l) => (
                <li key={l.id}>
                  <label>
                    <input type="checkbox" checked={selected.has(l.id)} onChange={() => toggle(l.id)} />
                    <span>
                      <strong>{l.name}</strong>
                      <small>{l.address}</small>
                    </span>
                  </label>
                  <span className="review-links">
                    {l.source_url && (
                      <a href={l.source_url} target="_blank" rel="noreferrer">
                        Public listing <ExternalLink size={13} />
                      </a>
                    )}
                    <a href={`#/locations/${l.id}`}>Open</a>
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
      <section className="panel" aria-labelledby="step2">
        <h2 id="step2">Step 2 · Check the main tenants</h2>
        <p className="muted">
          Tenants were imported from public listings and are unconfirmed. Confirm the anchors at each property so
          tenant alerts (closures, SEC filings) focus on the right stores.
        </p>
        {tenantsToCheck.length === 0 ? (
          <p className="small muted">Nothing to check yet: confirm properties in step 1 first.</p>
        ) : (
          <ul className="review-list">
            {tenantsToCheck.map((l) => (
              <li key={l.id}>
                <span>
                  <strong>{l.name}</strong>
                  <small>{l.unconfirmed_tenants} unconfirmed tenants</small>
                </span>
                <a href={`#/locations/${l.id}`}>Review tenants</a>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
