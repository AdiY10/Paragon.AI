export interface LegendItem {
  label: string;
  /** "a" = accent, "b" = second chart shade, "tick" = portfolio-median tick, "before" = hollow dot. */
  mark: "a" | "b" | "tick" | "before" | "after";
}

/** Legend for charts with ≥2 encodings. Text stays in text colours; the swatch carries identity. */
export function Legend({ items, label = "Legend" }: { items: LegendItem[]; label?: string }) {
  return (
    <ul className="chart-legend" aria-label={label}>
      {items.map((item) => (
        <li key={item.label}>
          <span className={`legend-mark legend-${item.mark}`} aria-hidden="true" />
          {item.label}
        </li>
      ))}
    </ul>
  );
}
