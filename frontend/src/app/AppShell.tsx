import { useEffect, useRef, type ReactNode } from "react";
import type { Session, Source } from "../types";
import { TopNav } from "./TopNav";

/** Header + main landmark. Focus moves to #main and the page scrolls to the top only when the path changes. */
export function AppShell({
  session,
  sources,
  path,
  title,
  wide = false,
  children,
}: {
  session: Session;
  sources: Source[] | undefined;
  path: string;
  title: string;
  wide?: boolean;
  children: ReactNode;
}) {
  const previous = useRef(path);
  useEffect(() => {
    if (previous.current === path) return;
    previous.current = path;
    window.scrollTo(0, 0);
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [path]);
  useEffect(() => {
    if (title) document.title = `${title} · Paragon Radar`;
  }, [title]);
  const failing = (sources ?? []).some((source) => source.status === "Failing");
  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main"
        onClick={(event) => {
          // The hash belongs to the router, so move focus without changing it.
          event.preventDefault();
          document.getElementById("main")?.focus();
        }}
      >
        Skip to content
      </a>
      <TopNav session={session} path={path} />
      {failing && (
        <p className="source-banner" role="status">
          Some public data sources could not be refreshed. Affected figures show the last good values with their
          dates. <a href="#/sources">See data sources</a>
        </p>
      )}
      <main id="main" tabIndex={-1} className={wide ? "app-main wide" : "app-main"}>
        {children}
      </main>
      <footer className="app-footer">
        <span>Paragon Radar · private workspace</span>
        <span>Public data only. Radius rings and area figures describe the area, not the property.</span>
      </footer>
    </div>
  );
}
