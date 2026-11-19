# Area profile: economy, traffic, hazards and nearby businesses (FR-11 to FR-15)

Backend `backend/apps/area/`, screen `frontend/src/AreaSections.tsx`. Each section is computed independently and stored as an immutable `AreaSection` row keyed by the location's `analysis_version`. One failing source never blanks the others: a failed part is stored with its reason code (`docs/04` §7).

| Section | Metrics | Source (verified 2026-11-19) |
|---|---|---|
| Economy | MET-10 private jobs + YoY, MET-11 retail jobs + YoY (latest QCEW quarter) | BLS QCEW open data CSV, county / CT planning region |
| | MET-12 unemployment rate + change vs the same month a year earlier (not seasonally adjusted, preliminary flagged) | BLS LAUS API (v1 keyless; v2 if `BLS_API_KEY` is set) |
| | MET-13 residential units authorized, trailing 12 months vs prior 12 months | Census BPS county year-to-date files (5 small files) |
| Traffic | MET-14 AADT on up to 2 named roads within 250 m, with change vs the prior HPMS year on the same route and milepoints | FHWA HPMS per-state services on geo.dot.gov (newest year found automatically; 2025 at time of writing) |
| Hazards | MET-17 FEMA flood zone at the pin (±30 m envelope) and within ~100 m; concern if in a Special Flood Hazard Area | FEMA NFHL layer 28 (envelope queries; point queries were unreliable) |
| | MET-18 National Risk Index tract rating, percentile and top 3 hazards | FEMA NRI tracts (December 2025) |

| Businesses | MET-15 retail and service businesses by group within 1 and 3 mi; MET-16 anchors and national chains with distance, nearest supermarket chain; possible closures (SIG-09 evidence) and new key businesses (SIG-10 evidence) between the two newest monthly releases | Overture Maps Places (GeoParquet; CDLA-Permissive-2.0, Apache-2.0, CC0) |

**Businesses method** (`backend/apps/area/businesses.py`, `docs/04` §3.7, §5.2, §5.3):
- **Category groups:** Overture `basic_category` values are mapped to 11 retail-relevant groups. Supermarkets are filed under the broad `food_and_beverage_store`, so **anchors are identified from a curated brand list** (grocery chains plus big boxes and pharmacies), with whole-word prefix matching ("Lowe's Home Improvement" → lowes). Unbranded plazas or clinics in key categories are counted but not listed as anchors.
- **Counts** exclude closed places and confidence below 0.5.
- **Possible closures:** a retail-relevant branded or key place that had confidence ≥ 0.7 in the prior release and is now marked closed, or has disappeared. Severity is High if the brand matches a tenant on this property's roster within 150 m, Watch within 0.5 mi, otherwise FYI. A disappearance is one level lower than an explicit closure. Null → open changes are ignored.
- **New key businesses:** a key place newly appearing within 3 mi with confidence ≥ 0.8. Always FYI ("may be a new opening or a data addition").
- **Broad-change guard:** if ≥ 30% of monitored pins change their 1-mile count by more than 15% in the same direction, new-business signals are suppressed and closures are capped at FYI.
- **Captures:** seed properties use archived 3-mile captures imported with `import_overture_captures`. New or moved pins are captured on demand from the public bucket with DuckDB (about 10–60 s, in the background job), then stored as SRC-13 snapshots, because Overture keeps only about two prior releases.

**County at the pin** comes from TIGERweb ACS 2024 counties, which returns Connecticut planning regions (e.g. 09190), the same codes BLS and BPS use.

**Caching:** every raw response is published as a source snapshot. It is reused for 7 days (QCEW, LAUS, latest BPS month), 30 days (HPMS, flood) or 90 days (NRI). Published BPS year-to-date files and the county at a pin are reused indefinitely. A recomputation that finds everything fresh makes no network calls (tested).

**TLS:** `geo.dot.gov` chains to a root that is missing from some system trust stores. The area adapters use the `certifi` bundle (now an explicit dependency).

Businesses, real data (Nov 2026 vs Oct 2026 releases): Staples Plaza 472 retail/service businesses within 1 mi, nearest supermarket Whole Foods 0.44 mi, anchors Petco, Staples, Marshalls (matching the listing's tenants). Cypress Lake 940 within 1 mi, Costco 0.17 mi, Publix 0.5 mi, 4 possible closures (all FYI disappearances). Kingston: Hannaford 0.22 mi; the Sep → Oct 2026 diff flags the real Regal Cinemas Hudson Valley Mall 12 closure (0.25 mi, Watch).

## Run
- `python manage.py compute_area_profile [--location P20] [--section economy]`
- `GET /api/locations/<id>/area/` returns all three sections. `POST` queues the `compute_area_profile` job (one per analysis version).
- The property page shows a **Check economy, traffic and hazards** button when sections are missing or out of date.

## Real-data check (2026-11-19)

| | Kingston Marketplace NY | Cypress Lake SC, Fort Myers FL | Staples Plaza, Norwalk CT |
|---|---|---|---|
| County | Ulster County | Lee County | Western CT Planning Region |
| Private jobs, 2026 Q1 | 47,301 (+4.8%) | 275,732 (−0.5%) | 253,911 (−0.5%) |
| Unemployment, Sep 2026 (P) | 3.8% (+0.2 pts) | 4.8% (±0.0) | 4.5% (+1.0 pts) |
| Homes permitted, 12 mo to Sep 2026 | 739 (prior 421) | 10,868 (prior 14,844) | 1,504 (prior 2,521) |
| Traffic, 2025 | Ulster Ave US 9W 22,422 (−0.4%) | Cypress Lake Dr 25,000 (+4.2%) | Route 1 20,600 (+2.0%) |
| Flood zone at pin | X (minimal) | **AE, SFHA, BFE 9 ft** | X (minimal) |
| NRI | Relatively Moderate | Relatively Moderate; Hurricane Very High | Very Low |

Tests: `backend/tests/test_area_profile.py` (13 tests). They replay recorded real responses through a fixture opener: parsers, field aliases across HPMS years, suppression, BPS arithmetic, snapshot reuse with zero network calls, partial failure, stale-after-pin-move, auth and job deduplication. Frontend: `frontend/tests/area.test.ts`.

## Not done yet
- Signals SIG-03 to SIG-05, SIG-07, SIG-08 and SIG-11 from these values (needs the signal engine).
- Jobs located in each ring (LODES).
- Map markers for nearby businesses; Overture brand coverage is partial, so the anchor list depends on the curated brand list.
- Place-level (city/town) building permits; county only for now.
