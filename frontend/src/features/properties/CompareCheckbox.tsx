import type { Location } from "../../types";

/**
 * "Compare {name}" checkbox. When four are already chosen the others stay focusable but
 * aria-disabled, and choosing one announces the limit instead of silently dropping another.
 */
export function CompareCheckbox({
  location,
  checked,
  full,
  onToggle,
  showText = false,
}: {
  location: Location;
  checked: boolean;
  full: boolean;
  onToggle: (id: string) => void;
  /** Show the word "Compare" next to the box (phone cards). */
  showText?: boolean;
}) {
  const blocked = full && !checked;
  return (
    <label className="compare-check" title={blocked ? "Up to 4. Remove one first." : undefined}>
      <input
        type="checkbox"
        checked={checked}
        aria-disabled={blocked || undefined}
        onChange={() => onToggle(location.id)}
      />
      {showText ? (
        <>
          <span>Compare</span>
          <span className="sr-only"> {location.name}</span>
        </>
      ) : (
        <span className="sr-only">Compare {location.name}</span>
      )}
    </label>
  );
}
