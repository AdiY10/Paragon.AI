import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { api } from "./api/client";
import { dateLabel } from "./lib/format/dates";
import type { Location } from "./types";

export interface SecEvent {
  filed: string;
  form: string;
  items: string[];
  watched: string[];
  url: string;
}
export interface TenantRow {
  id: string;
  name: string;
  is_anchor: boolean | null;
  confirmed: boolean;
  archived: boolean;
  origin: string;
  presence: string;
  version: number;
  source_url: string;
  sec: { cik: string; company: string; events: SecEvent[]; checked_at: string | null } | null;
}

export const ITEM_LABELS: Record<string, string> = {
  "1.03": "Bankruptcy or receivership",
  "2.05": "Exit or disposal costs",
  "2.06": "Material impairment",
};
export function presenceLabel(p: string): string {
  return (
    {
      listed_unverified: "From public listing (unverified)",
      neighbor_or_cotenant: "Listing may mean a neighbor",
      planned_unverified: "Listed as opening soon",
      name_only: "From the property name",
    }[p] ?? "User-provided"
  );
}

export default function TenantsPanel({ location, isAdmin }: { location: Location; isAdmin: boolean }) {
  const cache = useQueryClient();
  const key = ["tenants", location.id];
  const q = useQuery({ queryKey: key, queryFn: () => api<{ results: TenantRow[]; owned: boolean }>(`/api/locations/${location.id}/tenants/`) });
  const refresh = () => {
    cache.invalidateQueries({ queryKey: key });
    cache.invalidateQueries({ queryKey: ["location", location.id] });
  };
  const add = useMutation({
    mutationFn: (b: { name: string; is_anchor: boolean | null }) => api(`/api/locations/${location.id}/tenants/`, "POST", b),
    onSuccess: refresh,
  });
  const act = useMutation({
    mutationFn: ({ t, kind }: { t: TenantRow; kind: "confirm" | "archive" }) =>
      kind === "confirm"
        ? api(`/api/locations/${location.id}/tenants/${t.id}/confirm/`, "POST", { expected_version: t.version })
        : api(`/api/locations/${location.id}/tenants/${t.id}/`, "PATCH", { expected_version: t.version, archived: true }),
    onSuccess: refresh,
  });
  if (location.status !== "owned") return null;
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const d = new FormData(form);
    // Clear the form only once the tenant is saved, so a failed save keeps what was typed.
    add.mutate({ name: String(d.get("name") ?? ""), is_anchor: d.get("anchor") ? true : null }, { onSuccess: () => form.reset() });
  }
  const rows = (q.data?.results ?? []).filter((t) => !t.archived);
  return (
    <div className="tenants-panel">
      <p className="small muted">
        Tenants imported from the public listing are unverified claims; verify or archive each one. Public-company
        tenants mapped to their SEC filer are checked daily for bankruptcy and closure filings (company-level, not
        store-level).
      </p>
      {(add.error || act.error) && (
        <p className="notice error" role="alert">
          {((add.error || act.error) as Error).message}
        </p>
      )}
      {rows.length === 0 ? (
        <p className="muted">No tenants entered. Add tenants to enable tenant watch.</p>
      ) : (
        <ul className="tenant-list">
          {rows.map((t) => (
            <li key={t.id}>
              <div className="tenant-main">
                <strong>{t.name}</strong>
                <span className="card-badges">
                  {t.is_anchor && <span className="badge">Anchor</span>}
                  <span className={`badge ${t.confirmed ? "green" : "unverified"}`}>
                    {t.confirmed ? "Verified" : presenceLabel(t.presence)}
                  </span>
                </span>
                <span className="tenant-actions">
                  {!t.confirmed && (
                    <button
                      className="text-button small"
                      aria-label={`Verify ${t.name} is a tenant`}
                      onClick={() => act.mutate({ t, kind: "confirm" })}
                    >
                      Verify
                    </button>
                  )}
                  <button
                    className="text-button small"
                    aria-label={`Archive ${t.name}`}
                    onClick={() => act.mutate({ t, kind: "archive" })}
                  >
                    Archive
                  </button>
                </span>
              </div>
              <SecLine tenant={t} />
              {isAdmin && <SecMapper location={location} tenant={t} onDone={refresh} />}
            </li>
          ))}
        </ul>
      )}
      <form className="tenant-form" onSubmit={submit}>
        <input name="name" required maxLength={200} placeholder="Add a tenant (e.g. CVS Pharmacy)" aria-label="Tenant name" />
        <label className="small">
          <input type="checkbox" name="anchor" /> Anchor
        </label>
        <button className="btn btn-primary btn-sm" disabled={add.isPending}>
          <Plus size={14} /> Add
        </button>
      </form>
    </div>
  );
}

function SecLine({ tenant }: { tenant: TenantRow }) {
  if (!tenant.sec) return <small className="muted">Not mapped to an SEC filer.</small>;
  const ev = tenant.sec.events;
  return (
    <div className="sec-line">
      <small>
        SEC filer: {tenant.sec.company} (CIK {tenant.sec.cik}) ·{" "}
        {tenant.sec.checked_at ? `checked ${dateLabel(tenant.sec.checked_at)}` : "not checked yet"}
      </small>
      {ev.length > 0 && (
        <ul className="evidence-list">
          {ev.slice(0, 5).map((e) => (
            <li key={e.url}>
              <a href={e.url} target="_blank" rel="noreferrer">
                {e.form} filed {e.filed}
              </a>
              : {e.watched.map((i) => `Item ${i} ${ITEM_LABELS[i] ?? ""}`).join("; ")}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SecMapper({ location, tenant, onDone }: { location: Location; tenant: TenantRow; onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(tenant.name);
  const search = useQuery({
    queryKey: ["sec-search", query],
    enabled: open && query.length > 1,
    queryFn: () => api<{ results: { cik: string; name: string }[]; error?: string; detail?: string }>(`/api/sec/search/?q=${encodeURIComponent(query)}`),
  });
  const map = useMutation({
    mutationFn: (b: { cik: string; company_name: string }) => api(`/api/locations/${location.id}/tenants/${tenant.id}/sec/`, "POST", b),
    onSuccess: () => {
      setOpen(false);
      onDone();
    },
  });
  if (!open)
    return (
      <button className="text-button small" onClick={() => setOpen(true)}>
        {tenant.sec ? "Change SEC filer" : "Map to SEC filer"}
      </button>
    );
  return (
    <div className="sec-mapper">
      <input value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search SEC companies" />
      {search.data?.error && <small className="notice">{search.data.detail}</small>}
      <ul className="anchor-list">
        {(search.data?.results ?? []).map((r) => (
          <li key={r.cik}>
            <span>
              {r.name} <small>CIK {r.cik}</small>
            </span>
            <button className="text-button small" onClick={() => map.mutate({ cik: r.cik, company_name: r.name })}>
              Use this filer
            </button>
          </li>
        ))}
      </ul>
      <small className="muted">Check the legal entity carefully: brands often differ from their filer (e.g. Marshalls → The TJX Companies).</small>
    </div>
  );
}
