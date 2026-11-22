import { rankSentence } from "../../lib/format/numbers";
import { position } from "../../lib/scales";

/**
 * Where a property sits among the owned portfolio: a 0–100 percentile track with the median (50)
 * marked, and the rank printed as a sentence. Higher percentile = higher value, not "better".
 */
export function PercentileBullet({
  label,
  value,
  percentile,
  rank,
  of,
  mode = "property",
  reason,
  scale = ["Lowest", "Median", "Highest"],
}: {
  /** Track captions, left to right (a "lower is better" figure reads e.g. Farthest → Closest). */
  scale?: [string, string, string];
  label: string;
  /** Printed value, e.g. "67,312". */
  value?: string | null;
  percentile: number | null;
  rank: number | null;
  of: number | null;
  mode?: "property" | "place";
  reason?: string;
}) {
  const sentence = rankSentence(rank, of, mode);
  const ready = percentile !== null && sentence !== null;
  return (
    <div className="bullet">
      <div className="bullet-head">
        <span className="bar-label">{label}</span>
        {value && <span className="bullet-value">{value}</span>}
      </div>
      {ready ? (
        <>
          <span className="bullet-track" aria-hidden="true">
            <span className="bullet-fill" style={{ width: `${position(percentile!, [0, 100])}%` }} />
            <span className="bullet-median" style={{ left: "50%" }} />
            <span className="bullet-marker" style={{ left: `${position(percentile!, [0, 100])}%` }} />
          </span>
          <span className="bullet-scale" aria-hidden="true">
            <span>{scale[0]}</span>
            <span>{scale[1]}</span>
            <span>{scale[2]}</span>
          </span>
          <p className="bullet-text">{sentence}</p>
        </>
      ) : (
        <p className="bar-missing">{reason ?? "Not ranked: not enough owned properties with this figure"}</p>
      )}
    </div>
  );
}
