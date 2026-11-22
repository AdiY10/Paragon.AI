import { lazy, Suspense, type ComponentProps } from "react";

/** Map components load MapLibre (~1 MB) on demand; the fallback keeps the final height. */
const LazyPortfolioMap = lazy(() => import("./PortfolioMap").then((m) => ({ default: m.PortfolioMap })));
const LazyAnalysisMap = lazy(() => import("./AnalysisMap").then((m) => ({ default: m.AnalysisMap })));
const LazyPickMap = lazy(() => import("./PickMap").then((m) => ({ default: m.PickMap })));
const LazyPreviewMap = lazy(() => import("./PreviewMap").then((m) => ({ default: m.PreviewMap })));

function Loading({ small = false }: { small?: boolean }) {
  return (
    <div className={small ? "map-loading small" : "map-loading"} role="status">
      Loading map…
    </div>
  );
}

export function PortfolioMap(props: ComponentProps<typeof LazyPortfolioMap>) {
  return (
    <Suspense fallback={<Loading />}>
      <LazyPortfolioMap {...props} />
    </Suspense>
  );
}
export function AnalysisMap(props: ComponentProps<typeof LazyAnalysisMap>) {
  return (
    <Suspense fallback={<Loading />}>
      <LazyAnalysisMap {...props} />
    </Suspense>
  );
}
export function PickMap(props: ComponentProps<typeof LazyPickMap>) {
  return (
    <Suspense fallback={<Loading />}>
      <LazyPickMap {...props} />
    </Suspense>
  );
}
export function PreviewMap(props: ComponentProps<typeof LazyPreviewMap>) {
  return (
    <Suspense fallback={<Loading small />}>
      <LazyPreviewMap {...props} />
    </Suspense>
  );
}
export type { MapPlace, FloodShape, AnalysisLayers } from "./AnalysisMap";
export type { PickPoint } from "./PickMap";
