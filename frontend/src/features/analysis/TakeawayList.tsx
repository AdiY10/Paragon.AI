import { AlertTriangle, CircleCheck, Info } from "lucide-react";
import type { Takeaway } from "../../api/types";
import { periodLabel } from "../../lib/format/dates";
import { sourceName } from "../../lib/format/sources";
import { isSectionId } from "./sections";
import { goToSection } from "./useActiveSection";

const TONE = {
  positive: { word: "Strength", Icon: CircleCheck },
  caution: { word: "Concern", Icon: AlertTriangle },
  neutral: { word: "Note", Icon: Info },
} as const;

/** Numbered "Key takeaways": tone icon + word, the sentence, source · period, and a link to its section. */
export function TakeawayList({ takeaways }: { takeaways: Takeaway[] }) {
  if (!takeaways.length) return null;
  return (
    <div className="takeaways">
      <h3 id="takeaways-title">Key takeaways</h3>
      <ol className="takeaway-list" aria-labelledby="takeaways-title">
        {takeaways.slice(0, 5).map((t, index) => {
          const { word, Icon } = TONE[t.tone] ?? TONE.neutral;
          const target = isSectionId(t.section) ? t.section : null;
          return (
            <li key={index} className={`takeaway tone-${t.tone}`}>
              <span className="takeaway-tone">
                <Icon size={14} aria-hidden="true" />
                {word}
              </span>
              <p className="takeaway-text">{t.text}</p>
              <p className="takeaway-meta">
                {[sourceName(t.source), periodLabel(t.period)].filter(Boolean).join(" · ")}
                {target && target !== "overview" && (
                  <>
                    {(t.source || t.period) && " · "}
                    <a
                      href={`#${target}`}
                      onClick={(event) => {
                        event.preventDefault();
                        goToSection(target);
                      }}
                    >
                      See details
                    </a>
                  </>
                )}
              </p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
