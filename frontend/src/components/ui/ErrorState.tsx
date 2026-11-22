import { AlertCircle } from "lucide-react";
import { Button } from "./Button";

/** A plain-language failure for one region; the rest of the page keeps working. */
export function ErrorState({
  error,
  title = "This part could not load.",
  onRetry,
}: {
  error?: unknown;
  title?: string;
  onRetry?: () => void;
}) {
  const detail = error instanceof Error ? error.message : null;
  return (
    <div className="error-state" role="alert">
      <AlertCircle size={18} aria-hidden="true" />
      <div>
        <p className="error-title">{title}</p>
        {detail && <p className="error-body">{detail}</p>}
        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Try again
          </Button>
        )}
      </div>
    </div>
  );
}

/** A one-line failure inside a form or dialog (the server's message, in plain words). */
export function InlineError({ error }: { error: unknown }) {
  return (
    <p className="inline-error" role="alert">
      <AlertCircle size={16} aria-hidden="true" />
      {error instanceof Error ? error.message : "This could not be completed. Please try again."}
    </p>
  );
}
