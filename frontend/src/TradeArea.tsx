import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
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

const POLL_MS = 4000;
const POLL_LIMIT_MS = 180_000;

export default function TradeArea({ location }: { location: Location }) {
  const [pollingSince, setPollingSince] = useState<number | null>(null);
  const query = useQuery({
    queryKey: ["demographics", location.id, location.analysis_version],
    queryFn: () =>
      api<Demographics>(`/api/locations/${location.id}/demographics/`),
    refetchInterval: (q) =>
      pollingSince !== null && q.state.data?.status !== "available"
        ? POLL_MS
        : false,
  });
  const compute = useMutation({
    mutationFn: () =>
      api<{ job_id: string }>(
        `/api/locations/${location.id}/demographics/`,
        "POST",
      ),
    onSuccess: () => setPollingSince(Date.now()),
  });
  const data = query.data;
  const timedOut =
    pollingSince !== null &&
    data?.status !== "available" &&
    Date.now() - pollingSince > POLL_LIMIT_MS;
  useEffect(() => {
    if (data?.status === "available" || timedOut) setPollingSince(null);
  }, [data?.status, timedOut]);

  const placed = location.current_revision.lat !== null;
  const computing = pollingSince !== null || compute.isPending;

  return (
    <section className="panel trade-area" aria-labelledby="trade-area-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">TRADE AREA · DEMOGRAPHICS</span>
          <h2 id="trade-area-title">Who lives around this property</h2>
        </div>
        <Users size={22} />
      </div>
      {query.error ? (
        <p className="notice error" role="alert">
          Ring demographics could not be loaded. Please try again.
        </p>
      ) : !data ? (
        <p className="notice">Loading ring demographics…</p>
      ) : data.status === "unavailable" ? (
        <div className="trade-empty">
          <p>{computing ? "Calculating ring demographics…" : data.message}</p>
          {computing && (
            <p className="small muted" role="status">
              This usually takes under a minute. The page updates on its own.
            </p>
          )}
          {timedOut && (
            <p className="notice error" role="alert">
              The calculation has not finished. The background worker may be
              busy or stopped; try again later.
            </p>
          )}
          {compute.error && (
            <p className="notice error" role="alert">
              {(compute.error as Error).message}
            </p>
          )}
          {placed && !computing && data.reason !== "NOT_PROVIDED" && (
            <button
              className="button small-button"
              onClick={() => compute.mutate()}
            >
              <RefreshCw size={15} />
              {data.reason === "STALE"
                ? "Recalculate for the new pin"
                : "Calculate ring demographics"}
            </button>
          )}
        </div>
      ) : (
        <Available data={data} />
      )}
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
