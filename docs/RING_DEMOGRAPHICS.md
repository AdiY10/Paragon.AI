# Ring demographics and trends (FR-09, MET-01 to MET-07)

Backend implementation of the trade-area ring demographics defined in `docs/04` §3.3 and §4.

## What it produces
For each location's ring preset (1/3/5 or 3/5/10 miles), using ACS 2020–2024 5-year estimates:

| Metric | ID | Method |
|---|---|---|
| Population | MET-01 | Σ weighted B01003 |
| Households | MET-02 | Σ weighted B11001 |
| Median household income | MET-03 | Linear interpolation over weighted B19001 brackets; "≥ $200,000" if open-ended |
| Mean household income | MET-04 | Σ B19025 / Σ B11001 over block groups where Census publishes B19025; withheld if they cover < 95% of households |
| Bachelor's degree or higher, 25+ | MET-05 | B15003 (022–025) / B15003 001 |

Every value carries a 90% MOE (where computable), a reliability class (CV-based, `docs/04` §4.2), a label, and a reason code when unavailable (`docs/04` §7). Nothing is filled in or guessed.

**Apportionment:** block-group estimates are weighted by the share of each block group's 2020 Census population whose block internal points fall inside the ring (land-area share for zero-population block groups). MOEs are combined as `sqrt(Σ (w·MOE)²)`, with Census ratio and proportion approximations.

**Connecticut:** 2020 blocks use legacy county codes; ACS 2022+ uses planning regions. Block groups are matched by tract and block-group number among ACS block groups intersecting the same search area. Any weighted block group that cannot be matched unambiguously withholds the ring with `GEOGRAPHY_CHANGED`.

## Trends (MET-06, MET-07)
Each ring also carries, when the baseline is available:
- **Population change** (MET-06): ACS 2015–2019 → 2020–2024.
- **Real mean household income change** (MET-07): the 2015–19 value and its MOE are scaled by CPI-U annual averages (2024: 313.689 / 2019: 255.657 = 1.2270, BLS series CUUR0000SA0) before comparing.

Each vintage is apportioned with its own geography: 2010 blocks for 2015–19, 2020 blocks for 2020–24. Significance follows `docs/04` §4.1: `Z = |Δ| / sqrt(SE₁² + SE₂²)`, significant if Z > 1.645. Very-low-reliability inputs are never marked significant. If the baseline cannot be built (state not ingested, source outage), current metrics are still stored and the trends say why they are unavailable.

The 2015–19 vintage predates the table-based files, so it comes from the per-state sequence-based summary zips. Only the 4 needed sequence files and the geography file are read, using HTTP range requests (about 7–10 s per state). The sequence layout is checked against Census's official lookup file in the tests.

## On screen
The property page has a **"Who lives around this property"** section (`frontend/src/TradeArea.tsx`):
- **Table:** a ring-by-ring table with ± margins of error and low-reliability flags. Missing values show their reason in words, never 0.
- **Trends:** a "Change, 2015–2019 → 2020–2024" block. Arrows and colour appear only for statistically significant changes.
- **Evidence drawer** ("How these numbers are calculated"): the pin used, data period, CPI ratio, block groups and blocks per ring, source links and caveats.
- **No result yet:** a **Calculate** button (or **Recalculate for the new pin** after a pin move) queues the background job and polls until the result appears. This needs the job worker running.
- **Phones:** checked in a browser at 1280 px and 375 px. All three rings fit on a phone without sideways scrolling.

## Data flow
1. `python manage.py ingest_acs [--states CT,NY] [--year 2024]`, then the same with `--year 2019` for the trend baseline, streams the five national keyless bulk tables once and publishes one immutable SRC-03 snapshot per state. With no `--states`, it uses the states of non-archived locations plus neighbouring states, since rings can cross state lines.
2. Computing a location fetches 2020 blocks (and, for the baseline, 2010 blocks), 2020 block-group totals and ACS block groups around the pin from TIGERweb. It publishes that capture as an SRC-04 snapshot (reused for the same pin and radius), computes all rings, and stores an immutable `RingDemographics` row keyed by the location's `analysis_version`.
3. Moving the pin or changing the ring preset bumps `analysis_version`, so the old result is reported as `STALE`, never silently reused.

Entry points:
- `python manage.py compute_ring_demographics [--location P03|<uuid>] [--force]`
- `GET /api/locations/<id>/demographics/` returns the current result or `{status: unavailable, reason, message}`
- `POST /api/locations/<id>/demographics/` enqueues the `compute_ring_demographics` job (deduplicated per analysis version)

## Verification (real data, 2026-11-19)
Ring population against Paragon's own listing figures (Esri 2021, paragonct.com), using the public reference pins in `data/seed`:

| Property | Rings | This engine (ACS 2020–24) | Listing (Esri 2021) |
|---|---|---|---|
| Staples Plaza, Norwalk CT | 1/3/5 | 10,719 / 85,544 / 136,533 | 11,474 / 84,256 / 132,645 |
| Kingston Marketplace NY | 3/5/10 | 25,102 / 48,595 / 98,956 | 25,573 / 47,484 / 98,114 |
| Barrington Plaza MA | 3/5/10 | 5,935 / 9,118 / 25,257 | 5,802 / 9,363 / 26,003 |
| Cherry Hill Retail NJ | 1/3/5 | 12,165 / 118,782 / 289,835 | 12,312 / 108,770 / 278,813 |
| Golden Mile Home Depot MD | 1/3/5 | 22,240 / 79,075 / 130,884 | 20,146 / 73,157 / 121,941 |
| Arrowhead SC, Minot ND | 3/5/10 | 41,830 / 52,007 / 57,733 | 43,398 / 51,772 / 58,093 |
| Cottman Plaza, Philadelphia PA | 1/3/5 | 54,641 / 331,629 / 670,978 | 55,368 / 324,010 / 670,086 |
| Cypress Lake SC, Fort Myers FL | 1/3/5 | 7,595 / 67,312 / 137,090 | 7,506 / 68,632 / 138,095 |
| Symmes Gate Station, Loveland OH | 1/3/5 | 6,272 / 46,371 / 118,502 | 4,932 / 45,841 / 119,030 |

Differences are mostly within ±10%, which is expected given different vintages (2021 vs 2020–24) and methods. The Symmes Gate 1-mile ring (+27%) is the outlier and should be checked against a corrected pin.

Trend check on real data (3-mile ring unless noted; "sig" = significant at 90%):

| Property | Population 2015–19 → 2020–24 | Real mean HH income |
|---|---|---|
| Staples Plaza, Norwalk CT | 79,937 → 85,544, +7.0% (sig) | +1.1% (not sig) |
| Kingston Marketplace NY | 25,972 → 25,102, −3.4% (not sig) | +8.8% (not sig); 10 mi +8.2% (sig) |
| Golden Mile Home Depot, Frederick MD | 70,425 → 79,075, +12.3% (sig); 5 mi +16.3% (sig) | +4.0% (not sig) |
| Cypress Lake, Fort Myers FL | 65,157 → 67,312, +3.3% (not sig); 5 mi +6.8% (sig) | 5 mi +7.9% (sig) |
| Cottman Plaza, Philadelphia PA | 335,840 → 331,629, −1.3% (not sig) | +3.6% (not sig) |

Tests: `backend/tests/test_ring_demographics.py` (37 tests: math, real ACS table slices, recorded real Norwalk geography and ACS rows, reference tolerances, stale and missing-data behaviour, auth). All tests run offline, including real 2010 geography, 2019 sequence-file slices and BLS CPI responses.

## Not done yet
- **Signals** SIG-01 and SIG-02 (`docs/04` §5.2) should be raised from these trends once the signal engine exists.
- **Portfolio percentiles** (MET-20) build on these results.
- Not yet run on the real PostGIS test database or in a deployed environment.
