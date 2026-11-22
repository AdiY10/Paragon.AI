import { type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ShieldCheck } from "lucide-react";
import AlertsPage from "../Alerts";
import { ComparePage, ScreenPage } from "../Acquisitions";
import { api, allLocations } from "../api";
import { Empty, ErrorNotice } from "../components/ui";
import { Admin } from "../pages/Admin";
import { LocationPage } from "../pages/LocationPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { Portfolio } from "../pages/Portfolio";
import { Sources } from "../pages/Sources";
import type { Session, Source } from "../types";
import { AppShell } from "./AppShell";
import { type Route, useRoute } from "./router";

const TITLES: Record<Route["name"], string> = {
  properties: "Properties",
  property: "Property analysis",
  analyze: "Analyze a place",
  place: "Place analysis",
  alerts: "Alerts",
  compare: "Compare",
  sources: "Data sources",
  admin: "Admin",
  notFound: "Page not found",
};

export function App() {
  const { path, route } = useRoute();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: () => api<Session>("/api/session/"),
    retry: false,
  });
  const sources = useQuery({
    queryKey: ["sources"],
    queryFn: () => api<Source[]>("/api/sources/"),
    enabled: !!session.data,
  });
  const needsPortfolio = route.name === "properties" || route.name === "analyze";
  const portfolio = useQuery({
    queryKey: ["locations"],
    queryFn: allLocations,
    enabled: !!session.data && needsPortfolio,
  });
  if (session.isPending)
    return (
      <div className="boot" role="status">
        <span className="brand-mark" aria-hidden="true">
          P
        </span>
        <p>Opening your private workspace…</p>
      </div>
    );
  if (session.error || !session.data)
    return (
      <main className="boot">
        <ShieldCheck size={36} aria-hidden="true" />
        <h1>Your workspace is private.</h1>
        <p>Sign in with your invited account to continue.</p>
        <a
          className="boot-action"
          href={document.querySelector<HTMLMetaElement>('meta[name="login-url"]')?.content ?? "/accounts/login/"}
        >
          Sign in <ArrowRight size={16} aria-hidden="true" />
        </a>
      </main>
    );
  const isAdmin = session.data.role === "admin";
  let body: ReactNode;
  if (needsPortfolio && portfolio.error) body = <ErrorNotice error={portfolio.error} />;
  else if (needsPortfolio && !portfolio.data)
    body = (
      <div className="skeleton-grid" role="status" aria-label="Loading properties">
        <div />
        <div />
        <div />
      </div>
    );
  else
    switch (route.name) {
      // Interim pages until WI-4 (Properties), WI-6 (analysis) and WI-7 (Analyze) replace them.
      case "properties":
        body = <Portfolio locations={portfolio.data ?? []} />;
        break;
      case "property":
      case "place":
        body = <LocationPage id={route.id} />;
        break;
      case "analyze":
        body = (
          <>
            <ScreenPage />
            <Portfolio
              locations={(portfolio.data ?? []).filter((item) => item.status === "candidate")}
              candidates
            />
          </>
        );
        break;
      case "alerts":
        body = <AlertsPage />;
        break;
      case "compare":
        body = <ComparePage />;
        break;
      case "sources":
        body = <Sources sources={sources.data} error={sources.error} />;
        break;
      case "admin":
        body = isAdmin ? (
          <Admin />
        ) : (
          <Empty title="Administrator access required">
            Your account can manage properties. User and system controls are restricted to administrators.
          </Empty>
        );
        break;
      default:
        body = <NotFoundPage />;
    }
  return (
    <AppShell session={session.data} sources={sources.data} path={path} title={TITLES[route.name]}>
      {body}
    </AppShell>
  );
}
