import { useId, useState, type FormEvent } from "react";
import { Search } from "lucide-react";
import { takePendingAddress } from "../../app/nav";
import { Button } from "../../components/ui/Button";

/** "Address" + "Analyze". The address goes only into the POST body, never the URL. */
export function AddressSearch({
  busy,
  error,
  onSubmit,
}: {
  busy: boolean;
  /** Field-level message (outside the US, throttled, not found…). */
  error: string | null;
  onSubmit: (address: string) => void;
}) {
  const [address, setAddress] = useState(takePendingAddress);
  const inputId = useId(),
    errorId = useId(),
    hintId = useId();
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = address.trim();
    if (value) onSubmit(value);
  }
  return (
    <form className="address-search" onSubmit={submit} noValidate>
      <label htmlFor={inputId}>Address</label>
      <div className="address-row">
        <input
          id={inputId}
          name="address"
          value={address}
          onChange={(event) => setAddress(event.target.value)}
          placeholder="e.g. 1200 Ulster Avenue, Kingston, NY"
          maxLength={500}
          autoComplete="street-address"
          required
          aria-invalid={error ? true : undefined}
          aria-describedby={[hintId, error ? errorId : null].filter(Boolean).join(" ")}
        />
        <Button type="submit" disabled={busy || !address.trim()}>
          <Search size={16} aria-hidden="true" />
          {busy ? "Starting…" : "Analyze"}
        </Button>
      </div>
      <p id={hintId} className="field-hint">
        Any US street address, or click anywhere on the map. The address is sent only to the U.S. Census geocoder.
      </p>
      {error && (
        <p id={errorId} className="field-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
