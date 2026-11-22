import React from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight } from "lucide-react";
import { api } from "../../../api/client";
import { Drawer } from "../../../components/ui/Drawer";
import { ErrorNotice, titleCase } from "../../../components/ui";
import { dateLabel } from "../../../lib/format/dates";
import type { Audit, Location, Page } from "../../../types";

/** "Record & history": where the record came from, how the pin was placed, and every change. */
export function RecordDrawer({
  location,
  open,
  onOpenChange,
  returnFocus,
}: {
  location: Location;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  returnFocus?: () => void;
}) {
  return (
    <Drawer
      title="Record & history"
      description="Where this record came from, how its pin was placed, and every change."
      open={open}
      onOpenChange={onOpenChange}
      onCloseAutoFocus={returnFocus}
    >
      <h3>Property record evidence</h3>
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
          className="btn btn-secondary btn-sm"
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
