import React, { lazy, Suspense, useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { ArrowUpRight, Building2, Check, ChevronRight, FileText, MapPin, ShieldCheck } from "lucide-react";
import PinEditor from "../PinEditor";
import GeocodeDialog from "../GeocodeDialog";
import TradeArea from "../TradeArea";
import AreaSections from "../AreaSections";
import SummaryPanel from "../Summary";
import PropertyHeader, { SectionNav } from "../PropertyHeader";
import { CompareButton, ScreenBanner } from "../Acquisitions";
import TenantsPanel from "../Tenants";
import { api, dateLabel } from "../api";
import { type Audit, type Location, type Page, type Session, type Source } from "../types";
import { titleCase, Badge, ErrorNotice, PageHead, Drawer } from "../components/ui";
import { EditLocation } from "../components/LocationForms";

const LocationMap = lazy(() => import("../LocationMap"));

export function RecordEvidence({ location }: { location: Location }) {
  return (
    <Drawer
      title="Property record evidence"
      trigger={
        <button className="text-button">
          <FileText size={15} /> View provenance
        </button>
      }
    >
      <dl className="facts">
        <dt>Source</dt>
        <dd>
          {location.origin === "public_seed"
            ? "Paragon public property listing"
            : "User-provided record"}
        </dd>
        {Boolean(location.source_context.address_override) && (
          <>
            <dt>Address origin</dt>
            <dd>
              User-edited; the original listing is historical reference. See
              change history.
            </dd>
          </>
        )}
        <dt>Reference period</dt>
        <dd>
          {location.source_context.source_as_of
            ? dateLabel(String(location.source_context.source_as_of))
            : "See the dated change history"}
        </dd>
        <dt>Ownership</dt>
        <dd>
          {location.confirmed
            ? "Confirmed by a team member"
            : "Unconfirmed; public listings may be outdated"}
        </dd>
        <dt>Pin method</dt>
        <dd>{titleCase(location.current_revision.method)}</dd>
        {location.current_revision.matched_address && (
          <>
            <dt>Matched address</dt>
            <dd>{location.current_revision.matched_address}</dd>
          </>
        )}
        {Boolean(location.current_revision.context.last_checked_at) && (
          <>
            <dt>Pin source checked</dt>
            <dd>
              {dateLabel(
                String(location.current_revision.context.last_checked_at),
              )}
            </dd>
            <dt>Original capture</dt>
            <dd>
              {dateLabel(
                String(location.current_revision.context.retrieved_at),
              )}
            </dd>
          </>
        )}
        <dt>Coordinate attribution</dt>
        <dd>
          {String(
            location.current_revision.context.coordinate_attribution ??
              "User-provided or unresolved",
          )}
        </dd>
      </dl>
      {location.source_url && (
        <a
          className="button secondary"
          href={location.source_url}
          target="_blank"
          rel="noreferrer"
        >
          Open original listing <ArrowUpRight size={16} />
        </a>
      )}
      <p className="small muted">
        The listing supplies an initial property record. It does not establish
        current ownership, tenancy, or current trade-area conditions.
      </p>
      <History locationId={location.id} />
    </Drawer>
  );
}
export function History({ locationId }: { locationId: string }) {
  const query = useQuery({
    queryKey: ["history", locationId],
    queryFn: () => api<Page<Audit>>(`/api/locations/${locationId}/history/`),
  });
  return (
    <section className="history">
      <h3>Change history</h3>
      {query.error ? (
        <ErrorNotice error={query.error} />
      ) : (
        query.data?.results.map((item) => (
          <article key={item.id}>
            <strong>{titleCase(item.action)}</strong>
            <p>
              {item.actor ?? "Public seed import"} ·{" "}
              {dateLabel(item.created_at)}
            </p>
            <dl>
              {Object.entries(item.after)
                .filter(
                  ([key]) => !["revision", "analysis_version"].includes(key),
                )
                .map(([key, value]) => (
                  <React.Fragment key={key}>
                    <dt>{titleCase(key)}</dt>
                    <dd>{String(value ?? "Not provided")}</dd>
                  </React.Fragment>
                ))}
            </dl>
          </article>
        ))
      )}
    </section>
  );
}
export function LocationPage({ id }: { id: string }) {
  const session = useQuery({ queryKey: ["session"], queryFn: () => api<Session>("/api/session/") });
  const query = useQuery({
    queryKey: ["location", id],
    staleTime: 0,
    queryFn: () => api<Location>(`/api/locations/${id}/`),
  });
  const cache = useQueryClient(),
    [message, setMessage] = useState("");
  const confirm = useMutation({
    mutationFn: () =>
      api<Location>(`/api/locations/${id}/confirm/`, "POST", {
        expected_version: query.data!.version,
      }),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["location", id] });
      cache.invalidateQueries({ queryKey: ["locations"] });
      cache.invalidateQueries({ queryKey: ["history", id] });
      setMessage("Record confirmed.");
    },
  });
  const name = query.data?.name;
  React.useEffect(() => {
    if (name) document.title = `${name} · Paragon Radar`;
  }, [name]);
  if (query.error) return <ErrorNotice error={query.error} />;
  if (!query.data) return <p className="notice">Loading property record…</p>;
  const item = query.data,
    pin = item.current_revision;
  return (
    <>
      <a className="back-link" href="#/">
        Properties <ChevronRight size={14} /> Property record
      </a>
      <PageHead
        eyebrow={[[item.city, item.state].filter(Boolean).join(", "), titleCase(item.status)].filter(Boolean).join(" · ")}
        title={item.name}
        description={item.address}
        action={
          <div className="actions">
            <CompareButton id={item.id} />
            <EditLocation location={item} />
          </div>
        }
      />
      {message && (
        <p className="notice success" role="status">
          {message}
        </p>
      )}
      {confirm.error && <ErrorNotice error={confirm.error} />}
      <ScreenBanner location={item} />
      <PropertyHeader location={item} />
      {!item.confirmed && item.status === "owned" && (
        <div className="confirm-strip" role="note">
          <ShieldCheck size={18} />
          <span>Is this still part of your portfolio?</span>
          <button className="button small-button" disabled={confirm.isPending} onClick={() => confirm.mutate()}>
            {confirm.isPending ? "Saving…" : "Yes, confirm"} <Check size={15} />
          </button>
        </div>
      )}
      <SectionNav owned={item.status === "owned"} />
      <div id="alerts" className="page-section" tabIndex={-1}>
        <SummaryPanel location={item} />
      </div>
      <div id="trade-area" className="page-section" tabIndex={-1}>
        <TradeArea location={item} autoStart={item.screening} />
      </div>
      <AreaSections location={item} autoStart={item.screening} />
      {item.status === "owned" && (
        <div id="tenants" className="page-section" tabIndex={-1}>
          <TenantsPanel location={item} isAdmin={session.data?.role === "admin"} />
        </div>
      )}
      {item.notes && (
        <section className="panel notes">
          <h2>Team notes</h2>
          <p>{item.notes}</p>
          <span className="source-note">User-provided · details in change history</span>
        </section>
      )}
      <details id="details" className="page-section property-details" tabIndex={-1}>
        <summary>
          <strong>Property record and map pin</strong>
          <small>Status, source record, pin placement and change history</small>
        </summary>
        <div className="location-columns">
          <section className="panel">
            <div className="section-heading">
              <h2>Property record</h2>
              <Building2 size={21} />
            </div>
            <dl className="facts">
              <dt>Status</dt>
              <dd>{titleCase(item.status)}</dd>
              <dt>Asset type</dt>
              <dd>{titleCase(item.asset_type)}</dd>
              <dt>Trade-area rings</dt>
              <dd>{item.ring_preset} miles</dd>
              <dt>Gross leasable area</dt>
              <dd>
                {item.gla_sqft === null ? "Not provided" : `${item.gla_sqft.toLocaleString()} SF · User-provided`}
              </dd>
              <dt>Reference period</dt>
              <dd>
                {item.source_context.source_as_of
                  ? dateLabel(String(item.source_context.source_as_of))
                  : "User-maintained record"}
              </dd>
            </dl>
            <RecordEvidence location={item} />
            {!item.confirmed && item.status !== "owned" && (
              <button className="button small-button" disabled={confirm.isPending} onClick={() => confirm.mutate()}>
                {confirm.isPending ? "Saving…" : "Confirm record"} <Check size={15} />
              </button>
            )}
          </section>
          <section className="panel pin-panel">
            <div className="section-heading">
              <h2>Location reference</h2>
              <MapPin size={21} />
            </div>
            <Suspense fallback={<p className="notice">Loading interactive map…</p>}>
              <LocationMap locations={[item]} rings />
            </Suspense>
            <div className="pin-actions">
              <GeocodeDialog location={item} />
              <PinEditor location={item} />
            </div>
            <Badge>{titleCase(pin.method)}</Badge>
            <p>
              {pin.lat === null ? "This property needs a pin." : `${pin.lat.toFixed(6)}, ${pin.lon?.toFixed(6)}`}
            </p>
            <p className="small muted">
              {pin.confirmed
                ? "Pin confirmed by a team member."
                : "Check that the pin is on the building before relying on location-based screening."}
            </p>
          </section>
        </div>
      </details>
    </>
  );
}
