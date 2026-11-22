/**
 * A small trend line. Renders only when a real series exists (≥2 points); the latest point is
 * marked. `label` describes the whole series for screen readers, e.g. "Traffic 2019 to 2025".
 */
export function Sparkline({
  values,
  label,
  width = 96,
  height = 28,
}: {
  values: (number | null)[];
  label: string;
  width?: number;
  height?: number;
}) {
  const points = values.map((v, i) => [i, v] as const).filter((p): p is readonly [number, number] => p[1] !== null);
  if (points.length < 2) return null;
  const pad = 4;
  const ys = points.map((p) => p[1]);
  const lo = Math.min(...ys),
    hi = Math.max(...ys);
  const x = (i: number) => pad + (i / Math.max(1, values.length - 1)) * (width - 2 * pad);
  const y = (v: number) => (hi === lo ? height / 2 : pad + (1 - (v - lo) / (hi - lo)) * (height - 2 * pad));
  const d = points.map(([i, v], n) => `${n ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const [lastI, lastV] = points[points.length - 1];
  return (
    <svg className="sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
      <path d={d} fill="none" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(lastI)} cy={y(lastV)} r={4} />
    </svg>
  );
}
