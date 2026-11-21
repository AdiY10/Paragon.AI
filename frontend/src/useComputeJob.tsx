import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

export const POLL_MS = 4000;

/**
 * One "refresh data" flow for every section (R2 item 21): start a background job, poll
 * until the section reports done, show a real timer, and keep a "taking too long"
 * message on screen until the user retries (it never flickers away).
 */
export function useComputeJob({
  start,
  done,
  limitMs,
  invalidate = [],
}: {
  start: () => Promise<unknown>;
  done: boolean;
  limitMs: number;
  invalidate?: unknown[][];
}) {
  const cache = useQueryClient();
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const [now, setNow] = useState(Date.now());
  const mutation = useMutation({
    mutationFn: start,
    onSuccess: () => {
      setTimedOut(false);
      setStartedAt(Date.now());
    },
  });
  const running = startedAt !== null;
  useEffect(() => {
    if (!running) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [running]);
  useEffect(() => {
    if (running && done) {
      setStartedAt(null);
      // Dependent views (summary, key facts, attention) refresh when the data lands.
      for (const key of invalidate) cache.invalidateQueries({ queryKey: key });
    } else if (running && now - startedAt! > limitMs) {
      setStartedAt(null);
      setTimedOut(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, done, now]);
  return {
    run: () => mutation.mutate(),
    computing: running || mutation.isPending,
    polling: running,
    elapsed: running ? Math.max(0, Math.round((now - startedAt!) / 1000)) : 0,
    timedOut,
    error: mutation.error as Error | null,
  };
}

/** Consistent loading / waiting / error / timeout feedback with a retry button. */
export function ComputeStatus({
  job,
  idleText,
  actionLabel,
  canRun = true,
}: {
  job: ReturnType<typeof useComputeJob>;
  idleText: ReactNode;
  actionLabel: string;
  canRun?: boolean;
}) {
  return (
    <div className="compute-status">
      {job.computing ? (
        <p role="status">
          Checking public sources… {job.elapsed > 0 && <strong>{job.elapsed}s</strong>}
          <small> This usually takes under a minute. The page updates on its own.</small>
        </p>
      ) : (
        <p>{idleText}</p>
      )}
      {job.timedOut && (
        <p className="notice error" role="alert">
          This is taking longer than usual. The background worker may be busy or stopped. Your request is still
          queued; try again in a few minutes, or ask an administrator to check the Admin page.
        </p>
      )}
      {job.error && (
        <p className="notice error" role="alert">
          {job.error.message}
        </p>
      )}
      {canRun && !job.computing && (
        <button className="button small-button" onClick={job.run}>
          <RefreshCw size={15} /> {job.timedOut ? "Try again" : actionLabel}
        </button>
      )}
    </div>
  );
}

/** Loading / error state for a panel's data, with the server's explanation and a retry. */
export function SectionState({
  loading,
  error,
  retry,
  what,
}: {
  loading: boolean;
  error: unknown;
  retry: () => void;
  what: string;
}) {
  if (error)
    return (
      <div className="notice error" role="alert">
        <p>
          {what} could not be loaded.{" "}
          {error instanceof Error && error.message ? error.message : "Please try again."}
        </p>
        <button className="button secondary small-button" onClick={retry}>
          Retry
        </button>
      </div>
    );
  if (loading) return <p className="notice">Loading {what.toLowerCase()}…</p>;
  return null;
}
