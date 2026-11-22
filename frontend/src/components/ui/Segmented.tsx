import { useId } from "react";

/** A small set of mutually exclusive choices: native radios styled as a segmented control. */
export function Segmented<T extends string>({
  label,
  options,
  value,
  onChange,
  hideLabel = false,
}: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  hideLabel?: boolean;
}) {
  const name = useId();
  return (
    <fieldset className="segmented">
      <legend className={hideLabel ? "sr-only" : "segmented-legend"}>{label}</legend>
      <div className="segmented-options">
        {options.map((option) => (
          <label key={option.value} className={option.value === value ? "selected" : undefined}>
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={option.value === value}
              onChange={() => onChange(option.value)}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
