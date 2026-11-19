import "vite/modulepreload-polyfill";
import React, {
  lazy,
  Suspense,
  useState,
  useSyncExternalStore,
  type ReactNode,
  type FormEvent,
} from "react";
import { createRoot } from "react-dom/client";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useQueryClient,
  useMutation,
} from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Building2,
  Check,
  ChevronRight,
  Clock3,
  Compass,
  Database,
  FileText,
  Layers3,
  MapPin,
  Menu,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  X,
} from "lucide-react";
import PinEditor from "./PinEditor";
import GeocodeDialog from "./GeocodeDialog";
import TradeArea from "./TradeArea";
import AreaSections from "./AreaSections";
import SummaryPanel from "./Summary";
import ThisWeek from "./ThisWeek";
import { ComparePage, CompareButton, ScreenBanner, ScreenPage } from "./Acquisitions";
import TenantsPanel from "./Tenants";
import { ApiError, api, allLocations, csrfToken, dateLabel } from "./api";
import type { Audit, Location, Page, Session, Source } from "./types";
import "./styles.css";

const LocationMap = lazy(() => import("./LocationMap"));
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
  return useSyncExternalStore(
    subscribe,
    () => window.location.hash.slice(1) || "/",
  );
}
const titleCase = (text: string) =>
  text.replaceAll("_", " ").replace(/\b\w/g, (s) => s.toUpperCase());
function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
function ErrorNotice({ error }: { error: unknown }) {
  return (
    <p className="notice error" role="alert">
      {error instanceof Error ? error.message : "Unable to load this section."}
    </p>
  );
}
function Empty({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="empty">
      <Compass size={28} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function PageHead({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-head">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </header>
  );
}
function Drawer({
  trigger,
  title,
  children,
}: {
  trigger: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="drawer">
          <div className="drawer-head">
            <Dialog.Title>{title}</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label="Close evidence">
              <X />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">
            Source, context, and supporting records.
          </Dialog.Description>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
function RecordEvidence({ location }: { location: Location }) {
  return (
    <Drawer
      title="Property record evidence"
      trigger={
        <button className="text-button">
          <FileText size={15} /> View provenance
        </button>
      }
    >
      <dl className="facts">
        <dt>Source</dt>
        <dd>
          {location.origin === "public_seed"
            ? "Paragon public property listing"
            : "User-provided record"}
        </dd>
        {Boolean(location.source_context.address_override) && (
          <>
            <dt>Address origin</dt>
            <dd>
              User-edited; the original listing is historical reference. See
              change history.
            </dd>
          </>
        )}
        <dt>Reference period</dt>
        <dd>
          {location.source_context.source_as_of
            ? dateLabel(String(location.source_context.source_as_of))
            : "See the dated change history"}
        </dd>
        <dt>Ownership</dt>
        <dd>
          {location.confirmed
            ? "Confirmed by a team member"
            : "Unconfirmed; public listings may be outdated"}
        </dd>
        <dt>Pin method</dt>
        <dd>{titleCase(location.current_revision.method)}</dd>
        {location.current_revision.matched_address && (
          <>
            <dt>Matched address</dt>
            <dd>{location.current_revision.matched_address}</dd>
          </>
        )}
        {Boolean(location.current_revision.context.last_checked_at) && (
          <>
            <dt>Pin source checked</dt>
            <dd>
              {dateLabel(
                String(location.current_revision.context.last_checked_at),
              )}
            </dd>
            <dt>Original capture</dt>
            <dd>
              {dateLabel(
                String(location.current_revision.context.retrieved_at),
              )}
            </dd>
          </>
        )}
        <dt>Coordinate attribution</dt>
        <dd>
          {String(
            location.current_revision.context.coordinate_attribution ??
              "User-provided or unresolved",
          )}
        </dd>
      </dl>
      {location.source_url && (
        <a
          className="button secondary"
          href={location.source_url}
          target="_blank"
          rel="noreferrer"
        >
          Open original listing <ArrowUpRight size={16} />
        </a>
      )}
      <p className="small muted">
        The listing supplies an initial property record. It does not establish
        current ownership, tenancy, or current trade-area conditions.
      </p>
      <History locationId={location.id} />
    </Drawer>
  );
}
function History({ locationId }: { locationId: string }) {
  const query = useQuery({
    queryKey: ["history", locationId],
    queryFn: () => api<Page<Audit>>(`/api/locations/${locationId}/history/`),
  });
  return (
    <section className="history">
      <h3>Change history</h3>
      {query.error ? (
        <ErrorNotice error={query.error} />
      ) : (
        query.data?.results.map((item) => (
          <article key={item.id}>
            <strong>{titleCase(item.action)}</strong>
            <p>
              {item.actor ?? "Public seed import"} ·{" "}
              {dateLabel(item.created_at)}
            </p>
            <dl>
              {Object.entries(item.after)
                .filter(
                  ([key]) => !["revision", "analysis_version"].includes(key),
                )
                .map(([key, value]) => (
                  <React.Fragment key={key}>
                    <dt>{titleCase(key)}</dt>
                    <dd>{String(value ?? "Not provided")}</dd>
                  </React.Fragment>
                ))}
            </dl>
          </article>
        ))
      )}
    </section>
  );
}
function App() {
  const route = useRoute(),
    [mobile, setMobile] = useState(false),
    [search, setSearch] = useState(""),
    [searching, setSearching] = useState(false);
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
    ["/portfolio", "Portfolio", Building2],
    ["/screen", "Screen", Compass],
    ["/compare", "Compare", Layers3],
    ["/sources", "Data Sources", Database],
    ...(session.data.role === "admin"
      ? [["/admin", "Admin", Settings2] as [string, string, typeof Activity]]
      : []),
  ];
  let body: ReactNode;
  if (portfolio.error) body = <ErrorNotice error={portfolio.error} />;
  else if (portfolio.isPending)
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
                {route.startsWith("/locations/")
                  ? "Property profile"
                  : (nav.find((item) => item[0] === route)?.[1] ?? "This Week")}
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
function Overview({
  locations,
  sources,
  isAdmin,
}: {
  locations: Location[];
  sources: Source[];
  isAdmin: boolean;
}) {
  const owned = locations.filter((l) => l.status === "owned"),
    unconfirmed = owned.filter((l) => !l.confirmed),
    states = new Set(owned.map((l) => l.state).filter(Boolean)),
    missing = owned.filter((l) => l.current_revision.lat === null);
  const distribution = Object.entries(
    owned.reduce<Record<string, number>>((counts, item) => {
      if (item.state) counts[item.state] = (counts[item.state] ?? 0) + 1;
      return counts;
    }, {}),
  ).sort((a, b) => b[1] - a[1]);
  return (
    <>
      <PageHead
        eyebrow="Portfolio intelligence"
        title="Your portfolio, in focus."
        description="One place to understand your locations—and the evidence behind them."
        action={<AddLocation />}
      />
      <ThisWeek isAdmin={isAdmin} />
      <div className="stat-grid">
        {[
          [
            owned.length,
            "Owned records",
            Building2,
            "Public seed / team records",
          ],
          [
            states.size,
            "States represented",
            Compass,
            "Based on recorded addresses",
          ],
          [
            unconfirmed.length,
            "To confirm",
            ShieldCheck,
            "Ownership needs your review",
          ],
          [missing.length, "Missing pins", MapPin, "A location must be placed"],
        ].map(([value, label, Icon, detail]) => (
          <article className="stat" key={String(label)}>
            <div className="stat-top">
              <span>{String(label)}</span>
              {React.createElement(Icon as typeof Building2, { size: 18 })}
            </div>
            <strong>{String(value)}</strong>
            <small>{String(detail)}</small>
          </article>
        ))}
      </div>
      <div className="dashboard-columns">
        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">GETTING THE RECORD RIGHT</span>
              <h2>Your review queue</h2>
            </div>
            <Badge tone="amber">{unconfirmed.length} unconfirmed</Badge>
          </div>
          <p className="muted intro">
            Public listings are a starting point. Confirm what is still part of
            your portfolio.
          </p>
          {unconfirmed.length ? (
            unconfirmed.slice(0, 5).map((item) => (
              <a
                className="review-row"
                href={"#/locations/" + item.id}
                key={item.id}
              >
                <span className="property-icon">
                  <Building2 size={20} />
                </span>
                <span>
                  <strong>{item.name}</strong>
                  <small>
                    {item.city}, {item.state}
                  </small>
                </span>
                <ChevronRight size={17} />
              </a>
            ))
          ) : (
            <Empty title="No unconfirmed owned records">
              Every owned record has been reviewed. You can still update it from
              the portfolio.
            </Empty>
          )}
          <a className="panel-link" href="#/portfolio">
            Open portfolio <ArrowRight size={15} />
          </a>
        </section>
        <section className="panel">
          <div className="section-heading">
            <div>
              <span className="eyebrow">WHERE YOU ARE</span>
              <h2>Portfolio footprint</h2>
            </div>
            <Compass size={21} />
          </div>
          <div
            className="state-bars"
            role="img"
            aria-label={distribution
              .map(([state, n]) => `${state}: ${n} properties`)
              .join("; ")}
          >
            {distribution.slice(0, 6).map(([state, count]) => (
              <div key={state}>
                <span>{state}</span>
                <div>
                  <i
                    style={{
                      width: `${(count / Math.max(...distribution.map((d) => d[1]), 1)) * 100}%`,
                    }}
                  />
                </div>
                <strong>{count}</strong>
              </div>
            ))}
          </div>
          <p className="source-note">
            Property counts from portfolio records.{" "}
            {states.size > 6
              ? `${states.size - 6} additional states are represented.`
              : ""}
          </p>
          <div className="coverage-note">
            <Database size={20} />
            <div>
              <strong>Know what is behind each number.</strong>
              <p>
                Sources, periods, and uncertainty belong alongside the evidence.
              </p>
              <a href="#/sources">
                Explore {sources.length || "the"} data sources{" "}
                <ArrowRight size={14} />
              </a>
            </div>
          </div>
        </section>
      </div>
      <div className="section-heading wide-heading">
        <div>
          <span className="eyebrow">YOUR LOCATIONS</span>
          <h2>Start with a property</h2>
        </div>
        <a className="text-button" href="#/portfolio">
          View all <ArrowRight size={15} />
        </a>
      </div>
      <div className="property-grid">
        {owned.slice(0, 3).map((item) => (
          <PropertyCard key={item.id} location={item} />
        ))}
      </div>
    </>
  );
}
const rankAttention = (l: Location) => (l.attention === "High" ? 0 : l.attention === "Watch" ? 1 : 2);
function PropertyCard({ location }: { location: Location }) {
  return (
    <a className="property-card" href={"#/locations/" + location.id}>
      <div className="card-top">
        <span className="property-icon">
          <Building2 size={22} />
        </span>
        <span className="card-badges">
          {location.attention && location.attention !== "Clear" && (
            <Badge tone={location.attention === "High" ? "red" : "amber"}>{location.attention}</Badge>
          )}
          <Badge tone={location.confirmed ? "green" : "amber"}>
            {location.confirmed ? "Confirmed" : "Unconfirmed"}
          </Badge>
        </span>
      </div>
      <span className="eyebrow">
        {location.state} · {titleCase(location.asset_type)}
      </span>
      <h3>{location.name}</h3>
      <p>{location.address}</p>
      <div className="card-bottom">
        <span>
          <MapPin size={14} />
          {location.current_revision.lat === null
            ? "Pin needed"
            : "Reference pin available"}
        </span>
        <ArrowUpRight size={18} />
      </div>
    </a>
  );
}
function Portfolio({
  locations,
  candidates = false,
}: {
  locations: Location[];
  candidates?: boolean;
}) {
  const [state, setState] = useState(""),
    [status, setStatus] = useState(candidates ? "candidate" : "owned"),
    [type, setType] = useState(""),
    [attention, setAttention] = useState(""),
    [showMap, setShowMap] = useState(!candidates);
  const filtered = locations.filter(
    (item) =>
      (!state || item.state === state) &&
      (!status || item.status === status) &&
      (!type || item.asset_type === type) &&
      (!attention || (item.attention ?? "Clear") === attention),
  ).sort((a, b) => rankAttention(a) - rankAttention(b) || a.name.localeCompare(b.name));
  return (
    <>
      {!candidates && (
        <PageHead
          eyebrow="Location management"
          title="The portfolio."
          description="Your locations, their source records, and what still needs confirming."
          action={<AddLocation />}
        />
      )}
      <div className="filterbar">
        <span>
          <SlidersHorizontal size={17} />
          {filtered.length} locations
        </span>
        <label>
          State
          <select
            aria-label="State"
            value={state}
            onChange={(e) => setState(e.target.value)}
          >
            <option value="">All states</option>
            {[...new Set(locations.map((l) => l.state).filter(Boolean))]
              .sort()
              .map((s) => (
                <option key={s}>{s}</option>
              ))}
          </select>
        </label>
        {!candidates && (
          <label>
            Status
            <select
              aria-label="Status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="owned">Owned</option>
              <option value="candidate">Candidates</option>
              <option value="archived">Archived</option>
              <option value="">All statuses</option>
            </select>
          </label>
        )}
        <label>
          Asset type
          <select
            aria-label="Asset type"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            <option value="">All types</option>
            {[...new Set(locations.map((l) => l.asset_type))]
              .sort()
              .map((t) => (
                <option value={t} key={t}>
                  {titleCase(t)}
                </option>
              ))}
          </select>
        </label>
        <label>
          Attention
          <select aria-label="Attention" value={attention} onChange={(e) => setAttention(e.target.value)}>
            <option value="">Any attention</option>
            <option value="High">High</option>
            <option value="Watch">Watch</option>
            <option value="Clear">Clear</option>
          </select>
        </label>
      </div>
      <div className="map-toolbar">
        <span>Explore saved locations</span>
        <button
          className="button secondary small-button"
          aria-pressed={showMap}
          onClick={() => setShowMap(!showMap)}
        >
          {showMap ? "List only" : "Map + list"}
          <MapPin size={15} />
        </button>
      </div>
      {showMap && (
        <section className="portfolio-map panel">
          <Suspense
            fallback={<p className="notice">Loading interactive map…</p>}
          >
            <LocationMap locations={filtered} />
          </Suspense>
        </section>
      )}
      <div className="property-grid portfolio-grid">
        {filtered.map((item) => (
          <PropertyCard key={item.id} location={item} />
        ))}
      </div>
      {!filtered.length && (
        <section className="panel">
          <Empty title="No matching locations">
            Change the filters or add a location record.
          </Empty>
        </section>
      )}
      <p className="source-note">
        Publicly listed properties remain unconfirmed until reviewed. Pins and
        area data have separate verification requirements.
      </p>
    </>
  );
}
function LocationPage({ id }: { id: string }) {
  const session = useQuery({ queryKey: ["session"], queryFn: () => api<Session>("/api/session/") });
  const query = useQuery({
    queryKey: ["location", id],
    staleTime: 0,
    queryFn: () => api<Location>(`/api/locations/${id}/`),
  });
  const cache = useQueryClient(),
    [message, setMessage] = useState("");
  const confirm = useMutation({
    mutationFn: () =>
      api<Location>(`/api/locations/${id}/confirm/`, "POST", {
        expected_version: query.data!.version,
      }),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["location", id] });
      cache.invalidateQueries({ queryKey: ["locations"] });
      cache.invalidateQueries({ queryKey: ["history", id] });
      setMessage("Record confirmed.");
    },
  });
  if (query.error) return <ErrorNotice error={query.error} />;
  if (!query.data) return <p className="notice">Loading property record…</p>;
  const item = query.data,
    pin = item.current_revision;
  return (
    <>
      <a className="back-link" href="#/portfolio">
        Portfolio <ChevronRight size={14} /> Property record
      </a>
      <PageHead
        eyebrow={`${item.city}, ${item.state}`}
        title={item.name}
        description={item.address}
        action={
          <div className="actions">
            <Badge tone={item.confirmed ? "green" : "amber"}>
              {item.confirmed
                ? "Confirmed"
                : item.status === "owned"
                  ? "Ownership unconfirmed"
                  : "Record unconfirmed"}
            </Badge>
            <CompareButton id={item.id} />
            <EditLocation location={item} />
          </div>
        }
      />
      {message && (
        <p className="notice success" role="status">
          {message}
        </p>
      )}
      {confirm.error && <ErrorNotice error={confirm.error} />}
      <ScreenBanner location={item} />
      <SummaryPanel location={item} />
      <div className="location-columns">
        <section className="panel">
          <div className="section-heading">
            <h2>Property record</h2>
            <Building2 size={21} />
          </div>
          <dl className="facts">
            <dt>Status</dt>
            <dd>{titleCase(item.status)}</dd>
            <dt>Asset type</dt>
            <dd>{titleCase(item.asset_type)}</dd>
            <dt>Trade-area rings</dt>
            <dd>{item.ring_preset} miles</dd>
            <dt>Gross leasable area</dt>
            <dd>
              {item.gla_sqft === null
                ? "Not provided"
                : `${item.gla_sqft.toLocaleString()} SF · User-provided`}
            </dd>
            <dt>Reference period</dt>
            <dd>
              {item.source_context.source_as_of
                ? dateLabel(String(item.source_context.source_as_of))
                : "User-maintained record"}
            </dd>
          </dl>
          <RecordEvidence location={item} />
          {!item.confirmed && (
            <div className="confirm-box">
              <ShieldCheck size={22} />
              <div>
                <strong>
                  {item.status === "owned"
                    ? "Is this still part of your portfolio?"
                    : "Have you reviewed this record?"}
                </strong>
                <p>Confirm this record after reviewing its source.</p>
                <button
                  className="button small-button"
                  disabled={confirm.isPending}
                  onClick={() => confirm.mutate()}
                >
                  {confirm.isPending ? "Saving…" : "Confirm record"}
                  <Check size={15} />
                </button>
              </div>
            </div>
          )}
        </section>
        <section className="panel pin-panel">
          <div className="section-heading">
            <h2>Location reference</h2>
            <MapPin size={21} />
          </div>
          <Suspense
            fallback={<p className="notice">Loading interactive map…</p>}
          >
            <LocationMap locations={[item]} rings />
          </Suspense>
          <div className="pin-actions">
            <GeocodeDialog location={item} />
            <PinEditor location={item} />
          </div>
          <Badge>{titleCase(pin.method)}</Badge>
          <p>
            {pin.lat === null
              ? "This property needs a pin."
              : `${pin.lat.toFixed(6)}, ${pin.lon?.toFixed(6)}`}
          </p>
          <p className="small muted">
            {pin.confirmed
              ? "Pin confirmed by a team member."
              : "Check that the pin is on the building before relying on location-based screening."}
          </p>
        </section>
      </div>
      <TradeArea location={item} autoStart={item.screening} />
      <AreaSections location={item} autoStart={item.screening} />
      <TenantsPanel location={item} isAdmin={session.data?.role === "admin"} />
      {item.notes && (
        <section className="panel notes">
          <h2>Team notes</h2>
          <p>{item.notes}</p>
          <span className="source-note">
            User-provided · details in change history
          </span>
        </section>
      )}
    </>
  );
}
function Sources({
  sources,
  error,
}: {
  sources: Source[] | undefined;
  error: unknown;
}) {
  return (
    <>
      <PageHead
        eyebrow="Trust and transparency"
        title="The evidence, explained."
        description="See what each source covers, when it was checked, and where uncertainty remains."
      />
      <p className="notice">
        Map privacy: OpenStreetMap receives your IP and viewed map area when a
        map is open. Property names, notes, and account details stay in this
        workspace.
      </p>
      {error ? (
        <ErrorNotice error={error} />
      ) : !sources ? (
        <p>Loading source coverage…</p>
      ) : (
        <div className="source-grid">
          {sources.map((source) => (
            <section className="panel source-card" key={source.id}>
              <div className="section-heading">
                <span className="eyebrow">{source.provider}</span>
                <Badge
                  tone={
                    source.status === "OK"
                      ? "green"
                      : source.status === "Failing"
                        ? "red"
                        : "amber"
                  }
                >
                  {source.status}
                </Badge>
              </div>
              <h2>{source.name}</h2>
              <p>{source.purpose}</p>
              <span className="small muted">{source.coverage}</span>
              <Drawer
                title={source.name}
                trigger={
                  <button className="text-button">
                    Source details <ArrowUpRight size={15} />
                  </button>
                }
              >
                <dl className="facts">
                  <dt>Provider</dt>
                  <dd>{source.provider}</dd>
                  <dt>Coverage</dt>
                  <dd>{source.coverage}</dd>
                  <dt>Licence</dt>
                  <dd>{source.licence}</dd>
                  <dt>Attribution</dt>
                  <dd>{source.attribution}</dd>
                  <dt>Privacy</dt>
                  <dd>{source.privacy_note}</dd>
                </dl>
                <a
                  className="button secondary"
                  href={source.documentation_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Provider documentation <ArrowUpRight size={16} />
                </a>
                <h3>Recorded checks</h3>
                {source.health_scopes.length ? (
                  source.health_scopes.map((scope) => (
                    <div className="scope-row" key={scope.scope}>
                      <Badge>{scope.status}</Badge>
                      <p>
                        {scope.data_period ?? "No published data period"}
                        <small>
                          Last successful check:{" "}
                          {dateLabel(scope.last_success_at)}
                        </small>
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="notice">
                    No completed check is recorded for this source.
                  </p>
                )}
              </Drawer>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
function Admin() {
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () =>
      api<
        Page<{
          id: string;
          kind: string;
          status: string;
          records: number;
          created_at: string;
        }>
      >("/api/admin/jobs/"),
  });
  return (
    <>
      <PageHead
        eyebrow="Workspace administration"
        title="Keep the workspace reliable."
        description="Review recorded job activity and the results of completed runs."
      />
      <section className="panel">
        <h2>Recent job runs</h2>
        {jobs.error ? (
          <ErrorNotice error={jobs.error} />
        ) : jobs.isPending ? (
          <p className="muted">Loading recorded job activity…</p>
        ) : jobs.data?.results.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Status</th>
                  <th>Records</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {jobs.data.results.map((job) => (
                  <tr key={job.id}>
                    <td>{titleCase(job.kind)}</td>
                    <td>
                      <Badge>{titleCase(job.status)}</Badge>
                    </td>
                    <td>{job.records}</td>
                    <td>{dateLabel(job.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No job runs are recorded yet.</p>
        )}
      </section>
    </>
  );
}
function AddLocation() {
  const [open, setOpen] = useState(false);
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: (data: unknown) =>
      api<Location>("/api/locations/", "POST", data),
    onSuccess: (data) => {
      cache.invalidateQueries({ queryKey: ["locations"] });
      setOpen(false);
      window.location.hash = "/locations/" + data.id;
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    mutation.mutate({
      name: data.get("name"),
      address: data.get("address"),
      status: data.get("status"),
    });
  }
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button className="button">
          <Plus size={17} /> Add location
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="modal">
          <div className="drawer-head">
            <Dialog.Title>Add a location</Dialog.Title>
            <Dialog.Close
              className="icon-button"
              aria-label="Close add location"
            >
              <X />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">
            Save a property record for your team. A new address starts without a
            verified pin or area metrics.
          </Dialog.Description>
          <form onSubmit={submit}>
            <label>
              Property name
              <input name="name" required maxLength={200} />
            </label>
            <label>
              US address
              <input name="address" required maxLength={500} />
            </label>
            <label>
              Status
              <select name="status" defaultValue="candidate">
                <option value="candidate">Candidate</option>
                <option value="owned">Owned</option>
              </select>
            </label>
            {mutation.error && <ErrorNotice error={mutation.error} />}
            <button className="button" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save record"}
              <ArrowRight size={16} />
            </button>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
function EditLocation({ location }: { location: Location }) {
  const [open, setOpen] = useState(false);
  const [snapshot, setSnapshot] = useState(location);
  const cache = useQueryClient();
  const mutation = useMutation({
    mutationFn: (data: unknown) =>
      api<Location>(`/api/locations/${location.id}/`, "PATCH", data),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["locations"] });
      cache.invalidateQueries({ queryKey: ["location", location.id] });
      cache.invalidateQueries({ queryKey: ["history", location.id] });
      setOpen(false);
    },
  });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    mutation.mutate({
      expected_version: snapshot.version,
      name: data.get("name"),
      status: data.get("status"),
      ring_preset: data.get("ring_preset"),
      notes: data.get("notes"),
    });
  }
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (next) {
          setSnapshot(location);
          mutation.reset();
        }
        setOpen(next);
      }}
    >
      <Dialog.Trigger asChild>
        <button className="button secondary">
          Edit record <Settings2 size={16} />
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="modal">
          <div className="drawer-head">
            <Dialog.Title>Edit property record</Dialog.Title>
            <Dialog.Close
              className="icon-button"
              aria-label="Close edit record"
            >
              <X />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">
            Changes are attributed to your account and kept in the record
            history.
          </Dialog.Description>
          <form onSubmit={submit}>
            <label>
              Name
              <input name="name" required defaultValue={snapshot.name} />
            </label>
            <label>
              Status
              <select name="status" defaultValue={snapshot.status}>
                <option value="owned">Owned</option>
                <option value="candidate">Candidate</option>
                <option value="archived">Archived</option>
              </select>
            </label>
            <label>
              Ring preset
              <select name="ring_preset" defaultValue={snapshot.ring_preset}>
                <option>1/3/5</option>
                <option>3/5/10</option>
              </select>
            </label>
            <label>
              Team notes
              <textarea name="notes" defaultValue={snapshot.notes} rows={4} />
            </label>
            {mutation.error && <ErrorNotice error={mutation.error} />}
            {mutation.error instanceof ApiError &&
              mutation.error.status === 409 && (
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => {
                    cache.invalidateQueries({
                      queryKey: ["location", location.id],
                    });
                    setOpen(false);
                  }}
                >
                  Reload record
                </button>
              )}
            <button className="button" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save changes"}
              <Check size={16} />
            </button>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
