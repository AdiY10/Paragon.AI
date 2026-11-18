# Address geocoding and pin evidence

The Census single-address adapter is implemented in `apps.locations.census`.
Persisted private preview/acceptance APIs are implemented; the review UI is implemented. No
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

## Persisted private preview and acceptance

`POST /api/locations/<id>/geocode/` takes only `expected_version`. It geocodes the
saved address server-side and returns a private preview with source hash, published
snapshot, original retrieval date, last actual check, expiry, benchmark/vintage,
validated alternatives, and the interpolation caveat. No pin or confirmation changes.
Only its requester can accept that preview through
`POST /api/locations/<id>/geocode/<lookup-id>/accept/` with `expected_version` and
`candidate_index`. Client-supplied coordinates/method/provenance are not accepted.

Acceptance creates one unconfirmed `census_interpolated` pin revision and advances
analysis generation. Even a single match needs explicit acceptance. A replay of the
same accept returns the current accepted revision; competing accepts cannot create
two revisions. Wrong owner, record, version, choice, or expired evidence is rejected.
Changes during the HTTP call preserve valid source evidence but reject a stale preview.

Census previews cache for 30 days from the last actual check. Cache hits do not
create source checks or reset age. A real re-fetch with identical bytes can reuse
an immutable content snapshot, while retaining its distinct later check time and
new expiry. Network and storage failures retain saved pins and record sanitized
source failures. Nominatim is not contacted. Manual placement remains available.

Raw responses are published through the private content-addressed artifact store
before snapshot/preview rows, with `SOURCE_ARTIFACT_ROOT` configurable for the full
backend. Production requires durable private storage, not an ephemeral container
filesystem. Geocode evidence is not exposed through public static assets.

Run `uv run python scripts/verification/geocode_smoke.py` for the live public Staples
Plaza lookup-to-preview-to-acceptance check in a disposable database. It creates only
a test identity in that temporary database and removes it after verification.

## Review interface

Property records expose **Find address pin**. The dialog discloses that Census
receives the saved address, then waits for **Find suggestions**. It shows the returned
matched address/coordinates, an unsaved map, actual check/capture dates, and expandable
benchmark, exactness, geography-vintage, and response-hash evidence. Two or more
matches start with no selected radio and acceptance disabled. A no-match result
explains that the saved pin is unchanged and points back to manual placement.

**Use selected Census pin** performs the explicit acceptance API call. It does not
confirm ownership/building position. The property evidence drawer retains matched
address and source check/capture dates after the dialog closes. Preview-map popups
do not link to nonexistent preview records. All controls work at phone width;
provider errors and record conflicts leave saved pins intact.

The isolated browser smoke now performs live Census requests for the three actual
public reference properties. It checks explicit ambiguous selection, no-match pin
retention, source-backed acceptance without manufactured confirmation, mobile overflow,
and automated A/AA rules. Test artifacts stay inside the disposable test directory.
