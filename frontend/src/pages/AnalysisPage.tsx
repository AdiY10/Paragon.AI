import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";
import { useAnalysis, useAnalysisTransitions, useSession } from "../api/hooks";
import { keys } from "../api/keys";
import { navigate, parseHash } from "../app/router";
import { ErrorState } from "../components/ui/ErrorState";
import { LiveRegion } from "../components/ui/LiveRegion";
import { Skeleton } from "../components/ui/Skeleton";
import { AnalysisHeader } from "../features/analysis/AnalysisHeader";
import { SectionNav } from "../features/analysis/SectionNav";
import { isSectionId, sectionsFor } from "../features/analysis/sections";
import { AccessSection } from "../features/analysis/sections/AccessSection";
import { DaytimeSection } from "../features/analysis/sections/DaytimeSection";
import { MarketSection } from "../features/analysis/sections/MarketSection";
import { RankingSection, SourcesSection, TenantsSection } from "../features/analysis/sections/OtherSections";
import { OverviewSection } from "../features/analysis/sections/OverviewSection";
import { RetailSection } from "../features/analysis/sections/RetailSection";
import { RiskSection } from "../features/analysis/sections/RiskSection";
import { TradeAreaSection } from "../features/analysis/sections/TradeAreaSection";
import { goToSection, useActiveSection } from "../features/analysis/useActiveSection";
import type { Location } from "../types";
import { NotFoundPage } from "./NotFoundPage";

/**
 * `#/p/:id` (owned property) and `#/analyze/:id` (new place): the full analysis, no buttons to run
 * it. Sections fill in as the server finishes each part; the record itself comes from
 * /api/locations/<id>/ so edits and pin changes show at once.
 */
export function AnalysisPage({ id, mode }: { id: string; mode: "property" | "place" }) {
  const session = useSession();
  const cache = useQueryClient();
  const record = useQuery({
    queryKey: keys.location(id),
    staleTime: 0,
    queryFn: () => api<Location>(`/api/locations/${id}/`),
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 1,
  });
  const analysis = useAnalysis(id);
  const bundle = analysis.data;
  const announcement = useAnalysisTransitions(bundle);
  const kind = record.data ? (record.data.screening ? "place" : "property") : null;

  // A property opened on the place route (or the reverse) moves to its own route.
  useEffect(() => {
    if (kind && kind !== mode) navigate((kind === "place" ? "/analyze/" : "/p/") + id, { replace: true });
  }, [kind, mode, id]);

  // A moved pin or a changed ring preset means a new analysis version: fetch the bundle again.
  const version = record.data?.analysis_version;
  const seenVersion = useRef(version);
  useEffect(() => {
    if (version === undefined) return;
    if (seenVersion.current !== undefined && seenVersion.current !== version)
      void cache.invalidateQueries({ queryKey: keys.analysis(id) });
    seenVersion.current = version;
  }, [version, id, cache]);

  const name = record.data?.name;
  useEffect(() => {
    document.title = `${name ?? (mode === "property" ? "Property analysis" : "Place analysis")} · Paragon Radar`;
  }, [name, mode]);

  const sections = sectionsFor(mode);
  const active = useActiveSection(
    sections.map((s) => s.id),
    !!bundle,
  );

  // Deep link: ?section=risk scrolls there once the page has content.
  const jumped = useRef(false);
  useEffect(() => {
    if (jumped.current || !bundle) return;
    jumped.current = true;
    const wanted = parseHash(window.location.hash).query.get("section");
    if (wanted && isSectionId(wanted)) requestAnimationFrame(() => goToSection(wanted));
  }, [bundle]);

  if (record.error instanceof ApiError && record.error.status === 404) return <NotFoundPage />;
  if (record.error) return <ErrorState error={record.error} title="This record could not load." onRetry={() => void record.refetch()} />;
  if (!record.data)
    return (
      <div className="analysis-page" aria-busy="true">
        <Skeleton height={32} width="40%" />
        <Skeleton lines={6} height={20} />
      </div>
    );
  const isAdmin = session.data?.role === "admin";
  return (
    <div className="analysis-page">
      <AnalysisHeader record={record.data} bundle={bundle} mode={mode} isAdmin={isAdmin} />
      <div className="analysis-layout">
        <SectionNav sections={sections} active={active} bundle={bundle} />
        <div className="analysis-content">
          {analysis.error ? (
            <ErrorState error={analysis.error} title="The analysis could not load." onRetry={() => void analysis.refetch()} />
          ) : !bundle ? (
            <div aria-busy="true" className="analysis-loading">
              <p>Loading the analysis…</p>
              <Skeleton lines={8} height={20} />
            </div>
          ) : (
            <>
              <OverviewSection
                bundle={bundle}
                record={record.data}
                mode={mode}
                gaveUp={analysis.gaveUp}
                onCheckAgain={analysis.checkAgain}
              />
              <TradeAreaSection bundle={bundle} />
              <DaytimeSection bundle={bundle} />
              <RetailSection bundle={bundle} />
              <AccessSection bundle={bundle} />
              <RiskSection bundle={bundle} />
              <MarketSection bundle={bundle} />
              {mode === "property" && <TenantsSection location={record.data} isAdmin={isAdmin} />}
              <RankingSection bundle={bundle} mode={mode} />
              <SourcesSection bundle={bundle} />
            </>
          )}
        </div>
      </div>
      <LiveRegion message={announcement} />
    </div>
  );
}
