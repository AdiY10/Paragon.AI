import { useState } from "react";
import { sectionRunState } from "../../../api/analysis";
import type { AnalysisBundle } from "../../../api/types";
import { BarList, GroupedBarList } from "../../../components/charts";
import { Segmented } from "../../../components/ui/Segmented";
import { formatInt } from "../../../lib/format/numbers";
import { SectionShell } from "../SectionShell";

type SectorRing = { sectors?: Record<string, number | null> };
const SECTOR_LABELS: Record<string, string> = {
  retail: "Retail",
  food_service: "Food service",
  health: "Health care",
  office: "Office & professional",
  other: "Other",
};

/** Residents vs people who work in each ring (LODES), and jobs by sector. Never "visitors". */
export function DaytimeSection({ bundle }: { bundle: AnalysisBundle }) {
  const jobs = bundle.sections.jobs;
  const demo = bundle.sections.demographics.data;
  const rings = jobs.data?.rings ?? [];
  const [radius, setRadius] = useState(rings.some((r) => r.radius_miles === 3) ? 3 : (rings[0]?.radius_miles ?? 3));
  const ring = rings.find((r) => r.radius_miles === radius) ?? rings[0];
  const residents = (miles: number) => demo?.rings.find((r) => r.radius_miles === miles)?.metrics.population?.value ?? null;
  const sectors = (ring as (typeof ring & SectorRing) | undefined)?.sectors;
  const sectorItems = ring
    ? sectors
      ? Object.entries(sectors).map(([key, value]) => ({
          key,
          label: SECTOR_LABELS[key] ?? key.replaceAll("_", " "),
          value: value ?? null,
          display: formatInt(value) ?? undefined,
        }))
      : [
          { key: "retail", label: "Retail", value: ring.retail, display: formatInt(ring.retail) ?? undefined },
          { key: "food_service", label: "Food service", value: ring.food_service, display: formatInt(ring.food_service) ?? undefined },
          {
            key: "other",
            label: "All other sectors",
            value: Math.max(0, ring.total - ring.retail - ring.food_service),
            display: formatInt(Math.max(0, ring.total - ring.retail - ring.food_service)) ?? undefined,
          },
        ]
    : [];
  return (
    <SectionShell
      id="daytime"
      title="Daytime population"
      run={sectionRunState(jobs)}
      reason={jobs.reason}
      stale={jobs.stale}
      computedAt={jobs.computed_at}
      sources={jobs.sources}
      intro={
        <p>
          People who live in each ring (Census ACS) next to people whose job is located there (Census LODES). This is the
          public stand-in for a home/work split; it does not measure visits.
        </p>
      }
    >
      {jobs.data && (
        <>
          <GroupedBarList
            label="Residents and workers by ring"
            series={["Residents", "Workers (jobs located here)"]}
            rows={rings.map((r) => {
              const people = residents(r.radius_miles);
              return {
                key: String(r.radius_miles),
                label: `Within ${r.radius_miles} mi`,
                values: [
                  { value: people, display: formatInt(people) ?? undefined, reason: "Residents not available yet" },
                  { value: r.total, display: formatInt(r.total) ?? undefined },
                ],
              };
            })}
          />
          <div className="subsection">
            <div className="subsection-head">
              <h3>Jobs by sector within {radius} mi</h3>
              {rings.length > 1 && (
                <Segmented
                  label="Ring"
                  hideLabel
                  options={rings.map((r) => ({ value: String(r.radius_miles), label: `${r.radius_miles} mi` }))}
                  value={String(radius)}
                  onChange={(value) => setRadius(Number(value))}
                />
              )}
            </div>
            <BarList label={`Jobs by sector within ${radius} mi`} items={sectorItems} />
            {ring && ring.change_pct !== null && jobs.data.prior_year && (
              <p className="fine-print">
                Total jobs changed {ring.change_pct > 0 ? "+" : ring.change_pct < 0 ? "−" : ""}
                {Math.abs(ring.change_pct * 100).toFixed(1)}% since {jobs.data.prior_year}.
              </p>
            )}
          </div>
          <p className="fine-print">
            LODES {jobs.data.year}. {jobs.data.note}
          </p>
        </>
      )}
    </SectionShell>
  );
}
