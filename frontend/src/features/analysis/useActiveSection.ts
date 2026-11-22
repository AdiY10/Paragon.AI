import { useEffect, useState } from "react";
import { navigate, parseHash } from "../../app/router";
import type { SectionId } from "./sections";

/** The section nearest the top of the viewport, tracked with an IntersectionObserver. */
export function useActiveSection(ids: SectionId[], ready: boolean): SectionId {
  const [active, setActive] = useState<SectionId>(ids[0]);
  const key = ids.join(",");
  useEffect(() => {
    if (!ready || typeof IntersectionObserver === "undefined") return;
    const visible = new Map<string, number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) visible.set(entry.target.id, entry.boundingClientRect.top);
          else visible.delete(entry.target.id);
        }
        const first = ids.find((id) => visible.has(id));
        if (first) setActive(first);
      },
      // A section counts once its top passes under the sticky bar, until it leaves the upper half.
      { rootMargin: "-72px 0px -55% 0px" },
    );
    for (const id of ids) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, ready]);
  return active;
}

/** Scroll to a section, move focus to its heading and record it as ?section= (no new history entry). */
export function goToSection(id: SectionId) {
  const section = document.getElementById(id);
  if (!section) return;
  const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  section.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  const heading = section.querySelector<HTMLElement>("h2");
  if (heading) {
    heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: true });
  }
  const { path, query } = parseHash(window.location.hash);
  query.set("section", id);
  navigate(`${path}?${query.toString()}`, { replace: true });
}
