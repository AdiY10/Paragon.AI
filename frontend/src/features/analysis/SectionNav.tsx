import { useId } from "react";
import type { AnalysisBundle } from "../../api/types";
import { sectionStatus, STATUS_TEXT, type SectionDef, type SectionId } from "./sections";
import { goToSection } from "./useActiveSection";

/**
 * Section menu: a fixed left `nav "Analysis sections"` (≥1024), a sticky chip strip (768–1023), and
 * a "Jump to section" select (<768). Links scroll, focus the heading and set ?section=.
 */
export function SectionNav({
  sections,
  active,
  bundle,
}: {
  sections: SectionDef[];
  active: SectionId;
  bundle: AnalysisBundle | undefined;
}) {
  const selectId = useId();
  return (
    <>
      <nav className="section-nav" aria-label="Analysis sections">
        <ul>
          {sections.map((s) => {
            const status = sectionStatus(s, bundle);
            return (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  aria-current={active === s.id ? "location" : undefined}
                  onClick={(event) => {
                    event.preventDefault();
                    goToSection(s.id);
                  }}
                >
                  {status !== "none" && <span className={`status-dot ${status}`} aria-hidden="true" />}
                  <span>{s.label}</span>
                  {status !== "none" && status !== "ready" && <span className="sr-only">, {STATUS_TEXT[status]}</span>}
                </a>
              </li>
            );
          })}
        </ul>
      </nav>
      <div className="section-jump">
        <label htmlFor={selectId}>Jump to section</label>
        <select id={selectId} value={active} onChange={(event) => goToSection(event.target.value as SectionId)}>
          {sections.map((s) => (
            <option key={s.id} value={s.id}>
              {s.label}
            </option>
          ))}
        </select>
      </div>
    </>
  );
}
