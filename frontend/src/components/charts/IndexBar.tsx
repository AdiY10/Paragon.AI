import { indexText } from "../../lib/format/numbers";
import { indexSpan } from "../../lib/scales";

/**
 * Index vs the US (100 = US average), diverging from 100 and clamped to 50–150. A value beyond the
 * track gets an overflow cap and the exact index stays in the printed text.
 */
export function IndexBar({
  label,
  index,
  reason,
  range = [50, 150],
}: {
  label: string;
  index: number | null;
  reason?: string;
  range?: [number, number];
}) {
  if (index === null)
    return (
      <div className="index-bar">
        <span className="bar-label">{label}</span>
        <span className="bar-missing">{reason ?? "Unavailable"}</span>
      </div>
    );
  const span = indexSpan(index, range);
  return (
    <div className="index-bar">
      <span className="bar-label">{label}</span>
      <span className="index-track" aria-hidden="true">
        <span className="index-center" style={{ left: `${span.center}%` }} />
        <span
          className={`index-fill ${span.direction}${span.overflow ? " overflow-" + span.overflow : ""}`}
          style={{ left: `${span.left}%`, width: `${span.width}%` }}
        />
      </span>
      <span className="bar-value">{indexText(index)}</span>
    </div>
  );
}

/** Axis captions under a group of IndexBars. */
export function IndexScale({ range = [50, 150] }: { range?: [number, number] }) {
  return (
    <span className="index-scale" aria-hidden="true">
      <span>{range[0]}</span>
      <span>100 = US average</span>
      <span>{range[1]}+</span>
    </span>
  );
}
