export interface Session {
  email: string;
  role: "admin" | "member";
  csrfToken: string;
}
export interface Pin {
  id: string;
  number: number;
  lat: number | null;
  lon: number | null;
  method: string;
  matched_address: string;
  confirmed: boolean;
  context: Record<string, unknown>;
  created_at: string;
}
export interface Location {
  id: string;
  seed_id: string | null;
  name: string;
  address: string;
  city: string;
  state: string;
  status: "owned" | "candidate" | "archived";
  asset_type: string;
  ring_preset: string;
  gla_sqft: number | null;
  notes: string;
  confirmed: boolean;
  confirmed_at: string | null;
  origin: string;
  source_url: string;
  source_context: Record<string, unknown>;
  version: number;
  analysis_version: number;
  current_revision: Pin;
  created_at: string;
  updated_at: string;
}
export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export interface HealthScope {
  scope: string;
  status: string;
  last_checked_at: string | null;
  last_success_at: string | null;
  consecutive_failures: number;
  error_code: string | null;
  data_period: string | null;
  needs_alert: boolean;
}
export interface Source {
  id: string;
  name: string;
  provider: string;
  purpose: string;
  coverage: string;
  documentation_url: string;
  licence: string;
  attribution: string;
  cadence: string;
  stale_after_days: number | null;
  privacy_note: string;
  status: string;
  health_scopes: HealthScope[];
}
export interface Audit {
  id: string;
  action: string;
  actor: string | null;
  created_at: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}
