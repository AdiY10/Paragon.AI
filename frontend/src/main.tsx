import "vite/modulepreload-polyfill";
import React, { useState, useSyncExternalStore, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Activity, ArrowRight, Bell, Building2, ChevronRight, Compass, Database, Layers3, Menu, Search, Settings2, ShieldCheck, X } from "lucide-react";
import AlertsPage from "./Alerts";
import { ErrorNotice, Empty, titleCase } from "./components/ui";
import { Overview } from "./pages/Home";
import { Portfolio } from "./pages/Portfolio";
import { LocationPage } from "./pages/LocationPage";
import { Sources } from "./pages/Sources";
import { Admin } from "./pages/Admin";
import Onboarding from "./Onboarding";
import { ComparePage, ScreenPage } from "./Acquisitions";
import { api, allLocations, csrfToken } from "./api";
import type { Location, Page, Session, Source } from "./types";
import "./styles.css";

const client = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: true, staleTime: 30000 },
  },
});
const subscribe = (fn: () => void) => {
  window.addEventListener("hashchange", fn);
  return () => window.removeEventListener("hashchange", fn);
};
function useRoute() {
  const full = useSyncExternalStore(subscribe, () => window.location.hash.slice(1) || "/");
  return full.split("?")[0] || "/";
}
/** Query parameters after the hash route, e.g. #/portfolio?attention=High. */
function App() {
  const route = useRoute(),
    [mobile, setMobile] = useState(false),
    [search, setSearch] = useState(""),
    [searching, setSearching] = useState(false);
  const firstRoute = React.useRef(true);
  React.useEffect(() => {
    // Screen readers and keyboard users land at the top of the new page, not the old link.
    if (firstRoute.current) {
      firstRoute.current = false;
      return;
    }
    window.scrollTo(0, 0);
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [route]);
  const session = useQuery({
    queryKey: ["session"],
    queryFn: () => api<Session>("/api/session/"),
    retry: false,
  });
  const portfolio = useQuery({
    queryKey: ["locations"],
    queryFn: allLocations,
    enabled: !!session.data,
  });
  const sources = useQuery({
    queryKey: ["sources"],
    queryFn: () => api<Source[]>("/api/sources/"),
    enabled: !!session.data,
  });
  const searchResults = useQuery({
    queryKey: ["search", search],
    queryFn: () =>
      api<Page<Location>>("/api/locations/search/", "POST", { q: search }),
    enabled: searching && search.trim().length > 0,
  });
  if (session.isPending)
    return (
      <div className="boot">
        <div className="brand-mark">P</div>
        <p>Opening your private workspace…</p>
      </div>
    );
  if (session.error)
    return (
      <div className="boot">
        <ShieldCheck size={36} />
        <h1>Your workspace is private.</h1>
        <p>Sign in with your invited account to continue.</p>
        <a
          className="button"
          href={
            document.querySelector<HTMLMetaElement>('meta[name="login-url"]')
              ?.content ?? "/accounts/login/"
          }
        >
          Sign in <ArrowRight size={16} />
        </a>
      </div>
    );
  const nav: [string, string, typeof Activity][] = [
    ["/", "This Week", Activity],
    ["/alerts", "Alerts", Bell],
    ["/portfolio", "Portfolio", Building2],
    ["/screen", "Screen", Compass],
    ["/compare", "Compare", Layers3],
    ["/sources", "Data Sources", Database],
    ...(session.data.role === "admin"
      ? [["/admin", "Admin", Settings2] as [string, string, typeof Activity]]
      : []),
  ];
  let body: ReactNode;
  const needsPortfolio = route === "/" || route === "/portfolio" || route === "/screen" || route === "/setup";
  if (needsPortfolio && portfolio.error) body = <ErrorNotice error={portfolio.error} />;
  else if (needsPortfolio && portfolio.isPending)
    body = (
      <div className="skeleton-grid" aria-label="Loading portfolio">
        <div />
        <div />
        <div />
      </div>
    );
  else if (route.startsWith("/locations/"))
    body = <LocationPage id={route.split("/")[2]} />;
  else if (route === "/portfolio")
    body = <Portfolio locations={portfolio.data ?? []} />;
  else if (route === "/sources")
    body = <Sources sources={sources.data} error={sources.error} />;
  else if (route === "/screen")
    body = (
      <>
        <ScreenPage />
        <Portfolio
          locations={(portfolio.data ?? []).filter((item) => item.status === "candidate")}
          candidates
        />
      </>
    );
  else if (route === "/compare") body = <ComparePage />;
  else if (route === "/alerts") body = <AlertsPage />;
  else if (route === "/setup") body = <Onboarding locations={portfolio.data ?? []} />;
  else if (route === "/admin")
    body =
      session.data.role === "admin" ? (
        <Admin />
      ) : (
        <Empty title="Administrator access required">
          Your account can manage properties. User and system controls are
          restricted to administrators.
        </Empty>
      );
  else
    body = (
      <Overview locations={portfolio.data ?? []} sources={sources.data ?? []} isAdmin={session.data.role === "admin"} />
    );
  const pageTitle = route.startsWith("/locations/")
    ? "Property profile"
    : route === "/setup"
      ? "Confirm your portfolio"
      : (nav.find((item) => item[0] === route)?.[1] ?? "This Week");
  const sidebarContent = (
    <>
      <a className="brand" href="#/">
        <span className="brand-mark">
          P<span />
        </span>
        <span>
          PARAGON<small>RADAR</small>
        </span>
      </a>
      <div className="workspace-label">YOUR WORKSPACE</div>
      <nav aria-label="Main navigation">
        {nav.map(([path, label, Icon]) => (
          <a
            key={path}
            className={
              route === path ||
              (path === "/portfolio" && route.startsWith("/locations/"))
                ? "active"
                : ""
            }
            href={"#" + path}
            onClick={() => setMobile(false)}
          >
            <Icon size={19} />
            {label}
          </a>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="privacy">
          <ShieldCheck size={17} />
          <span>
            Private workspace<small>Invite-only access</small>
          </span>
        </div>
        <div className="user">
          <span className="avatar">
            {session.data.email.slice(0, 1).toUpperCase()}
          </span>
          <div>
            <strong>{session.data.email.split("@")[0]}</strong>
            <small>{titleCase(session.data.role)}</small>
          </div>
          <form
            action={session.data.logout_url ?? "/accounts/logout/"}
            method="post"
          >
            <input
              type="hidden"
              name="csrfmiddlewaretoken"
              value={csrfToken()}
            />
            <button className="text-button" type="submit">
              Sign out
            </button>
          </form>
        </div>
      </div>
    </>
  );
  return (
    <Dialog.Root open={mobile} onOpenChange={setMobile}>
      <div className="app">
        <a
          className="skip-link"
          href="#main"
          onClick={(event) => {
            event.preventDefault();
            document.getElementById("main")?.focus();
          }}
        >
          Skip to content
        </a>
        <aside className="sidebar desktop-sidebar">{sidebarContent}</aside>
        <Dialog.Portal>
          <Dialog.Overlay className="navigation-overlay" />
          <Dialog.Content className="sidebar mobile-sidebar">
            <Dialog.Title className="sr-only">
              Workspace navigation
            </Dialog.Title>
            <Dialog.Description className="sr-only">
              Choose a workspace screen or sign out.
            </Dialog.Description>
            <Dialog.Close
              className="icon-button navigation-close"
              aria-label="Close navigation"
            >
              <X />
            </Dialog.Close>
            {sidebarContent}
          </Dialog.Content>
        </Dialog.Portal>
        <div className="workspace">
          <header className="topbar">
            <Dialog.Trigger asChild>
              <button
                className="icon-button mobile-menu"
                aria-label="Open navigation"
              >
                <Menu />
              </button>
            </Dialog.Trigger>
            <div className="breadcrumb">
              Workspace <ChevronRight size={14} />{" "}
              <strong>
                {pageTitle}
              </strong>
            </div>
            <form
              className="global-search"
              onSubmit={(event) => {
                event.preventDefault();
                setSearching(true);
              }}
            >
              <Search size={17} />
              <input
                aria-label="Search portfolio by name or address"
                placeholder="Search a property or address"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setSearching(false);
                }}
              />
              <kbd>↵</kbd>
            </form>
            <span className="private-label">
              <span /> PRIVATE
            </span>
          </header>
          {searching && search.trim() && (
            <section className="search-results">
              <div className="section-heading">
                <h2>Search results</h2>
                <button
                  className="icon-button"
                  aria-label="Close search"
                  onClick={() => setSearching(false)}
                >
                  <X size={18} />
                </button>
              </div>
              {searchResults.error ? (
                <ErrorNotice error={searchResults.error} />
              ) : searchResults.isPending ? (
                <p>Searching…</p>
              ) : searchResults.data?.results.length ? (
                searchResults.data.results.map((item) => (
                  <a
                    href={"#/locations/" + item.id}
                    key={item.id}
                    onClick={() => setSearching(false)}
                  >
                    {item.name}
                    <small>{item.address}</small>
                  </a>
                ))
              ) : (
                <p>No matching property records.</p>
              )}
            </section>
          )}
          {(sources.data ?? []).some((s) => s.status === "Failing") && (
            <p className="source-banner" role="status">
              Some public data sources could not be refreshed. Affected figures show the last good values with
              their dates. <a href="#/sources">See data sources</a>
            </p>
          )}
          <PageTitle title={pageTitle} />
          <main id="main" tabIndex={-1}>
            {body}
          </main>
          <footer className="footer">
            <span>PARAGON RADAR</span>
            <p>Evidence for the area. Perspective for your portfolio.</p>
            <span>Private · US locations</span>
          </footer>
        </div>
      </div>
    </Dialog.Root>
  );
}
function PageTitle({ title }: { title: string }) {
  React.useEffect(() => {
    document.title = `${title} · Paragon Radar`;
  }, [title]);
  return null;
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
