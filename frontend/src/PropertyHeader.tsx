import { useQuery } from "@tanstack/react-query";
import { api, dateLabel } from "./api";
import type { Area } from "./area";
import { formatMetric, severityTone, type Summary } from "./Summary";
import type { Location } from "./types";

/** At-a-glance key numbers for a property (R2 item 18). Reads the same cached queries as the panels below. */
export default function PropertyHeader({ location }: { location: Location }) {
  const summary = useQuery({
    queryKey: ["summary", location.id, location.analysis_version],
    queryFn: () => api<Summary>(`/api/locations/${location.id}/summary/`),
  });
  const area = useQuery({
    queryKey: ["area", location.id, location.analysis_version],
    queryFn: () => api<Area>(`/api/locations/${location.id}/area/`),
  });
  const metric = (key: string) => summary.data?.metrics.find((m) => m.key === key);
  const pop = metric("population"),
    change = metric("population_change"),
    income = metric("median_household_income"),
    traffic = metric("aadt");
  const hz = area.data?.sections.hazards;
  const biz = area.data?.sections.businesses;
  const flood =
    hz?.status !== "available" || !hz.data
      ? "Not checked"
      : hz.data.flood_at_pin.in_sfha
        ? "Inside high-risk zone"
        : hz.data.flood_nearby.sfha && hz.data.flood_nearby.distance_m != null
          ? `High-risk zone ${hz.data.flood_nearby.distance_m} m away`
          : "Outside high-risk zones";
  const grocer = biz?.status === "available" ? biz.data?.nearest_supermarket : undefined;
  const signals = summary.data?.signals ?? [];
  const alerts = signals.filter((s) => s.severity !== "FYI");
  const latest = [...alerts].sort((a, b) => b.detected_at.localeCompare(a.detected_at))[0];
  const attention = location.attention ?? "Clear";
  const facts: [string, string, string?][] = [
    [
      "People within 3 miles",
      pop?.value != null ? formatMetric(pop) : "Not computed",
      change?.value != null ? `${formatMetric(change)} over 5 years` : undefined,
    ],
    ["Median household income", income?.value != null ? formatMetric(income) : "Not computed"],
    ["Main road traffic", traffic?.value != null ? `${formatMetric(traffic)}/day` : "Not checked", traffic?.detail ?? undefined],
    ["Flood", flood],
    [
      "Nearest supermarket",
      grocer ? (grocer.brand ?? grocer.name ?? "Supermarket") : biz?.status === "available" ? "None within 3 miles" : "Not checked",
      grocer ? `${grocer.distance_mi.toFixed(1)} mi` : undefined,
    ],
    ["Active alerts", String(alerts.length), alerts.length ? `${alerts.filter((a) => a.severity === "High").length} High` : undefined],
  ];
  return (
    <section className="property-header" aria-label="Key facts">
      <div className="attention-line">
        <span className={`badge ${severityTone(attention) || "green"}`}>
          {attention === "Clear" ? "No attention needed" : `${attention} attention`}
        </span>
        {latest && (
          <span className="what-changed">
            Latest:{" "}
            <a href="#alerts" onClick={(e) => (e.preventDefault(), scrollToSection("alerts"))}>
              {latest.title}
            </a>{" "}
            · {dateLabel(latest.detected_at)}
          </span>
        )}
      </div>
      <dl className="key-facts">
        {facts.map(([label, value, note]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>
              {value}
              {note && <small>{note}</small>}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export const SECTIONS: [string, string][] = [
  ["alerts", "Summary"],
  ["trade-area", "Trade area"],
  ["economy", "Economy & jobs"],
  ["retail", "Retail"],
  ["traffic", "Traffic"],
  ["hazards", "Hazards"],
  ["tenants", "Tenants"],
  ["details", "Record & pin"],
];

export function SectionNav({ owned }: { owned: boolean }) {
  return (
    <nav className="section-nav" aria-label="Sections on this page">
      {SECTIONS.filter(([id]) => owned || id !== "tenants").map(([id, label]) => (
        <a
          key={id}
          href={`#${id}`}
          onClick={(e) => {
            e.preventDefault();
            scrollToSection(id);
          }}
        >
          {label}
        </a>
      ))}
    </nav>
  );
}

/** Hash routing owns location.hash, so in-page links scroll and move focus without changing it. */
export function scrollToSection(id: string) {
  const el = document.getElementById(id);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
  el.focus({ preventScroll: true });
}
