/** Placeholder sized like the final layout (no layout shift). Decorative; pair with aria-busy on the region. */
export function Skeleton({
  height = 16,
  width = "100%",
  lines = 1,
  className = "",
}: {
  height?: number | string;
  width?: number | string;
  lines?: number;
  className?: string;
}) {
  return (
    <span className={`skeleton-stack ${className}`.trim()} aria-hidden="true">
      {Array.from({ length: lines }, (_, index) => (
        <span
          key={index}
          className="skeleton"
          style={{ height, width: lines > 1 && index === lines - 1 ? "60%" : width }}
        />
      ))}
    </span>
  );
}
