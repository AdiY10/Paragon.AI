export interface Candidate {
  lat: number;
  lon: number;
  method: string;
  matched_address: string;
  match_quality: string;
  geographies: Record<
    string,
    { geoid: string; name: string; geography_vintage: string }
  >;
}
export function parseCensus(raw: string): {
  status: "matched" | "ambiguous" | "no_match";
  candidates: Candidate[];
  benchmark: { id: string; name: string };
  vintage: { id: string; name: string };
};
export function normalizeAddress(value: string): string;
export function locationAddress(record: {
  address: string;
  city: string;
  state: string;
}): string;
