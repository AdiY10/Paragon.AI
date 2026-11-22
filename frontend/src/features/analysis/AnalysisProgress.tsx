import { CircleCheck, CircleDashed, CircleSlash, LoaderCircle } from "lucide-react";
import { SECTION_LABELS, sectionRunState } from "../../api/analysis";
import { SECTION_KEYS, type AnalysisBundle } from "../../api/types";
import { Button } from "../../components/ui/Button";

/** Shown while the analysis is still filling in: one line per data part, plus "Check again" after 15 min. */
export function AnalysisProgress({
  bundle,
  gaveUp,
  onCheckAgain,
}: {
  bundle: AnalysisBundle;
  gaveUp: boolean;
  onCheckAgain: () => void;
}) {
  const parts = SECTION_KEYS.map((key) => ({ key, run: sectionRunState(bundle.sections[key]) }));
  const done = parts.filter((p) => p.run !== "loading").length;
  return (
    <div className="analysis-progress" role="group" aria-labelledby="progress-title">
      <h3 id="progress-title">Analysis progress</h3>
      <p className="progress-summary">
        {gaveUp
          ? "Still processing. Public sources can be slow; the analysis keeps running on the server."
          : `${done} of ${parts.length} data parts ready. Sections fill in as each part arrives; there is nothing to click.`}
      </p>
      <progress max={parts.length} value={done} aria-label="Data parts ready">
        {done} of {parts.length}
      </progress>
      <ul className="progress-parts">
        {parts.map(({ key, run }) => (
          <li key={key} className={`part-${run}`}>
            {run === "ready" ? (
              <CircleCheck size={15} aria-hidden="true" />
            ) : run === "unavailable" ? (
              <CircleSlash size={15} aria-hidden="true" />
            ) : bundle.sections[key]?.status === "running" ? (
              <LoaderCircle size={15} aria-hidden="true" className="spin" />
            ) : (
              <CircleDashed size={15} aria-hidden="true" />
            )}
            <span>{SECTION_LABELS[key]}</span>
            <span className="part-state">
              {run === "ready" ? "Ready" : run === "unavailable" ? "Unavailable" : bundle.sections[key]?.status === "running" ? "In progress" : "Waiting"}
            </span>
          </li>
        ))}
      </ul>
      {gaveUp && (
        <Button variant="secondary" size="sm" onClick={onCheckAgain}>
          Check again
        </Button>
      )}
    </div>
  );
}
