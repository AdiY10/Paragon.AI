import { type ReactNode } from "react";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { AlertsPage } from "../pages/AlertsPage";
import { ComparePage } from "../pages/ComparePage";
import { AnalyzePage } from "../pages/AnalyzePage";
import { useLocations, useSession, useSources } from "../api/hooks";
import { Empty, ErrorNotice } from "../components/ui";
import { AdminPage } from "../pages/AdminPage";
import { AnalysisPage } from "../pages/AnalysisPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { PropertiesPage } from "../pages/PropertiesPage";
import { SourcesPage } from "../pages/SourcesPage";
import { AppShell } from "./AppShell";
import { type Route, useRoute } from "./router";

const TITLES: Record<Route["name"], string> = {
  properties: "Properties",
  // Analysis pages set their own title (the property's name).
  property: "",
  analyze: "Analyze a place",
  place: "",
  alerts: "Alerts",
  compare: "Compare",
  sources: "Data sources",
  admin: "Admin",
  notFound: "Page not found",
};

export function App() {
  const { path, route } = useRoute();
  const session = useSession();
  const sources = useSources(!!session.data);
  const needsPortfolio = route.name === "properties";
  const portfolio = useLocations(!!session.data && needsPortfolio);
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
      case "properties":
        body = <PropertiesPage locations={portfolio.data ?? []} />;
        break;
      case "property":
        body = <AnalysisPage key={route.id} id={route.id} mode="property" />;
        break;
      case "place":
        body = <AnalysisPage key={route.id} id={route.id} mode="place" />;
        break;
      case "analyze":
        body = <AnalyzePage />;
        break;
      case "alerts":
        body = <AlertsPage />;
        break;
      case "compare":
        body = <ComparePage />;
        break;
      case "sources":
        body = <SourcesPage />;
        break;
      case "admin":
        body = isAdmin ? (
          <AdminPage />
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
    <AppShell
      session={session.data}
      sources={sources.data}
      path={path}
      title={TITLES[route.name]}
      wide={route.name === "property" || route.name === "place"}
    >
      {body}
    </AppShell>
  );
}
