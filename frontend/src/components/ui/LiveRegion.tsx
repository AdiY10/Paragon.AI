/** Polite announcement region (e.g. "Retail landscape is ready"). Keep it mounted; change `message`. */
export function LiveRegion({ message, assertive = false }: { message: string; assertive?: boolean }) {
  return (
    <div className="sr-only" role={assertive ? "alert" : "status"} aria-live={assertive ? "assertive" : "polite"} aria-atomic="true">
      {message}
    </div>
  );
}
