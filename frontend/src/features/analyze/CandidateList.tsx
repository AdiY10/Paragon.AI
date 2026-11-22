import { useState } from "react";
import { Button } from "../../components/ui/Button";

export interface Candidate {
  index: number;
  matched_address: string;
  lat: number;
  lon: number;
}

/** The Census geocoder found several matches: nothing is preselected. */
export function CandidateList({
  candidates,
  busy,
  onChoose,
  onCancel,
}: {
  candidates: Candidate[];
  busy: boolean;
  onChoose: (index: number) => void;
  onCancel: () => void;
}) {
  const [choice, setChoice] = useState<number | null>(null);
  return (
    <form
      className="candidate-list"
      onSubmit={(event) => {
        event.preventDefault();
        if (choice !== null) onChoose(choice);
      }}
    >
      <fieldset>
        <legend>Choose the matching address</legend>
        {candidates.map((c) => (
          <label key={c.index} className="candidate">
            <input type="radio" name="candidate" checked={choice === c.index} onChange={() => setChoice(c.index)} />
            <span>
              {c.matched_address}
              <small>
                {c.lat.toFixed(5)}, {c.lon.toFixed(5)}
              </small>
            </span>
          </label>
        ))}
      </fieldset>
      <div className="candidate-actions">
        <Button type="submit" disabled={choice === null || busy}>
          {busy ? "Starting…" : "Analyze this address"}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
