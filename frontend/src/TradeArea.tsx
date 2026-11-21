import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ComputeStatus, POLL_MS, SectionState, useComputeJob } from "./useComputeJob";
import * as Dialog from "@radix-ui/react-dialog";
import {
  ArrowDownRight,
  ArrowUpRight,
  Info,
  RefreshCw,
  Users,
  X,
} from "lucide-react";
import { api, dateLabel } from "./api";
import type { Location } from "./types";
import {
  METRIC_ROWS,
  TREND_ROWS,
  formatChange,
  formatMoe,
  formatValue,
  reliabilityLabel,
  ringLabel,
  significanceText,
  trendTone,
  type Demographics,
  type Ring,
} from "./demographics";

const POLL_LIMIT_MS = 180_000;

export default function TradeArea({ location, autoStart = false }: { location: Location; autoStart?: boolean }) {
  const [polling, setPolling] = useState(false);
  const query = useQuery({
    queryKey: ["demographics", location.id, location.analysis_version],
    queryFn: () => api<Demographics>(`/api/locations/${location.id}/demographics/`),
    refetchInterval: (q) => (polling && q.state.data?.status !== "available" ? POLL_MS : false),
  });
  const data = query.data;
  const job = useComputeJob({
    start: () => api(`/api/locations/${location.id}/demographics/`, "POST"),
    done: data?.status === "available",
    limitMs: POLL_LIMIT_MS,
    invalidate: [["summary", location.id], ["location", location.id]],
  });
  useEffect(() => setPolling(job.polling), [job.polling]);

  const placed = location.current_revision.lat !== null;
  const notComputed = data?.status === "unavailable" && data.reason === "NOT_COMPUTED";
  useEffect(() => {
    // Screens load progressively: start the calculation as soon as the page opens.
    if (autoStart && placed && notComputed && !job.computing) job.run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart, placed, notComputed]);

  return (
    <section className="panel trade-area" aria-labelledby="trade-area-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">TRADE AREA · DEMOGRAPHICS</span>
          <h2 id="trade-area-title">Who lives around this property</h2>
        </div>
        <Users size={22} />
      </div>
      <SectionState loading={!data && !query.error} error={query.error} retry={() => query.refetch()} what="Ring demographics" />
      {data?.status === "unavailable" && (
        <div className="trade-empty">
          <ComputeStatus
            job={job}
            canRun={placed && data.reason !== "NOT_PROVIDED"}
            idleText={
              data.reason === "STALE"
                ? "The pin or trade-area rings changed since this was calculated."
                : data.message
            }
            actionLabel={data.reason === "STALE" ? "Recalculate for the new pin" : "Calculate ring demographics"}
          />
        </div>
      )}
      {data?.status === "available" && <Available data={data} />}
    </section>
  );
}

function Available({
  data,
}: {
  data: Extract<Demographics, { status: "available" }>;
}) {
  const rings = data.rings;
  const hasTrends = rings.some((r) =>
    Object.values(r.trends ?? {}).some((t) => t.value !== null),
  );
  const trendMessage = rings[0]?.trends?.population_change?.message;
  return (
    <>
      <p className="trade-meta">
        <span className="badge">Estimate</span>
        <span>
          {data.data_period} · Calculated {dateLabel(data.computed_at)} ·
          Describes the area, not this property
        </span>
      </p>
      <div className="table-wrap">
        <table className="ring-table">
          <caption className="sr-only">
            Demographics by distance ring, {data.data_period}
          </caption>
          <thead>
            <tr>
              <th scope="col">Within</th>
              {rings.map((r) => (
                <th scope="col" key={r.radius_miles}>
                  {ringLabel(r.radius_miles)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {METRIC_ROWS.map((row) => (
              <tr key={row.key}>
                <th scope="row">
                  {row.label}
                  <small>{row.hint}</small>
                </th>
                {rings.map((r) => {
                  const m = r.metrics[row.key];
                  const moe = formatMoe(m);
                  const rel = reliabilityLabel(m?.reliability ?? null);
                  return (
                    <td
                      key={r.radius_miles}
                      className={m?.value === null ? "unavailable" : ""}
                    >
                      <strong>{formatValue(m)}</strong>
                      {moe && <small>{moe}</small>}
                      {rel && <span className="badge amber">{rel}</span>}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
          {hasTrends && (
            <tbody className="trend-rows">
              <tr>
                <th scope="colgroup" colSpan={rings.length + 1}>
                  Change, 2015–2019 → 2020–2024
                </th>
              </tr>
              {TREND_ROWS.map((row) => (
                <tr key={row.key}>
                  <th scope="row">
                    {row.label}
                    <small>
                      {row.key === "real_mean_income_change"
                        ? "Adjusted for inflation (CPI-U)"
                        : "Statistically tested at 90%"}
                    </small>
                  </th>
                  {rings.map((r) => {
                    const t = r.trends?.[row.key];
                    const tone = trendTone(t);
                    // Arrows only for significant changes; a flat icon next to a
                    // minus sign read as a double negative.
                    const Icon =
                      tone === "up"
                        ? ArrowUpRight
                        : tone === "down"
                          ? ArrowDownRight
                          : null;
                    return (
                      <td key={r.radius_miles} className={`trend ${tone}`}>
                        <strong>
                          {Icon && <Icon size={13} aria-hidden="true" />}
                          {formatChange(t)}
                        </strong>
                        {significanceText(t) && (
                          <small>{significanceText(t)}</small>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          )}
        </table>
      </div>
      {!hasTrends && trendMessage && (
        <p className="small muted">Trends unavailable: {trendMessage}</p>
      )}
      <Evidence data={data} />
    </>
  );
}

function Evidence({
  data,
}: {
  data: Extract<Demographics, { status: "available" }>;
}) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button className="text-button">
          <Info size={16} /> How these numbers are calculated
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="drawer">
          <div className="drawer-head">
            <Dialog.Title>Trade-area evidence</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label="Close evidence">
              <X />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">
            Sources, method and uncertainty behind the ring demographics.
          </Dialog.Description>
          <dl className="facts">
            <dt>Pin used</dt>
            <dd>
              {data.pin.lat.toFixed(6)}, {data.pin.lon.toFixed(6)}
            </dd>
            <dt>Data period</dt>
            <dd>{data.data_period}</dd>
            <dt>Calculated</dt>
            <dd>{dateLabel(data.computed_at)}</dd>
            {data.trend_baseline && (
              <>
                <dt>Inflation adjustment</dt>
                <dd>
                  CPI-U 2024 ÷ 2019 = {data.trend_baseline.cpi_ratio.toFixed(4)}
                </dd>
              </>
            )}
          </dl>
          <h3>Method by ring</h3>
          <ul className="evidence-list">
            {data.rings.map((r: Ring) => (
              <li key={r.radius_miles}>
                <strong>{ringLabel(r.radius_miles)}:</strong>{" "}
                {r.method.block_groups} block groups, {r.method.blocks_inside}{" "}
                census blocks inside the ring. Weighted by 2020 Census block
                population
                {r.method.land_area_weighted_block_groups > 0 &&
                  ` (${r.method.land_area_weighted_block_groups} by land area)`}
                .
              </li>
            ))}
          </ul>
          <h3>Sources</h3>
          <ul className="evidence-list">
            {data.sources.map((s) => (
              <li key={s.id + s.period}>
                <a href={s.url} target="_blank" rel="noreferrer">
                  {s.name}
                </a>{" "}
                · {s.period}
                {s.tables && ` · tables ${s.tables.join(", ")}`}
              </li>
            ))}
          </ul>
          <h3>Read with care</h3>
          <ul className="evidence-list">
            {data.caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
            <li>
              “±” is the 90% margin of error. A change marked “Not significant”
              may be survey noise.
            </li>
          </ul>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
