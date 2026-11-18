# Address geocoding and pin evidence

The Census single-address adapter is implemented in `apps.locations.census`.
The persisted preview/acceptance workflow and UI are the next increment. No
geocoding result replaces a saved pin automatically.

## Provider contract

Use the fixed HTTPS Census geographies/onelineaddress endpoint, `Public_AR_Current`,
`Current_Current`, and named geography layers returned by the provider. Requests run
server-side: browser searches/lookup requests keep address text in POST bodies.
Census's GET request necessarily contains the address on the provider connection;
exceptions exposed by our adapter are sanitized codes without provider URLs or
address text. Redirects are refused. Reads are bounded to 1 MiB with a 10-second
network timeout; malformed JSON, invalid coordinates, bad geography IDs, and
mismatched request echoes are rejected.

The current single-address JSON does **not** expose the batch API's Exact/Non_Exact
classification. Use `census_interpolated` and `match_quality: not_reported`; do not
infer exactness from string similarity or silently label it an exact/rooftop match.
An interpolated street point still requires the user to check the building.

Statuses are matched, ambiguous, and no_match. Ambiguous results preserve all
validated alternatives; the first is never selected automatically. A valid result
without a given geography retains that gap for downstream resolution.

## Connecticut geography vintages

The live Norwalk response returns current county `09190` (Western Connecticut
Planning Region) and block group `091900435001`, while its **2020 block** is
`090010435001001`, using the former county code. Keep these separate, with their
own geography-vintage labels. Do not rewrite the old block prefix to the current
county or assume all GEOIDs in a response share a vintage. Returned current
benchmark/vintage IDs and names are retained in evidence.

## Verified public reference responses

Real responses captured 2026-11-18 in `tests/fixtures/real/census_geocoder/` include
retrieval time, parameters, original bytes, and SHA-256 manifests:

- 444 Westport Avenue, Norwalk: one match at 41.12661107292, -73.388299045728.
- 445 Main Street, Mount Kisco: two alternatives, requiring user choice.
- 1200 Ulster Avenue, Kingston: no match; manual pin remains available.

These are test evidence only, never fabricated application metrics or fake
production geocoding history. Thirty adapter tests cover real matches/geographies,
ambiguity/no match, source integrity, bounded reads, input checks, malformed data,
and sanitized network errors.

Provider documentation reviewed 2026-11-18:
https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html

Nominatim remains disabled until its policy-compliant application-wide throttling,
cache, identifying User-Agent, and confidential-address protections are implemented.
No candidate address is sent to Nominatim as an implicit workaround.
