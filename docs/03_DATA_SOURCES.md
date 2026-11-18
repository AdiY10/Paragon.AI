# 03 · Data Source Catalog and Verification

**Purpose:** Every external data source Release 1 depends on: what it provides, how to access it, its limits, and whether it was **verified with a real retrieval**.
**Verification date:** 2026-11-17. Raw commands and results are in §5. A re-runnable script is in [`scripts/feasibility/`](../scripts/feasibility/).

**Status labels**

- ✅ **Verified**: a real request on 2026-11-17 returned the expected data for a Paragon-relevant location.
- 🟡 **Verified with caveat**: works, but with a limitation the implementation must handle.
- ⬜ **Documented only**: reviewed from documentation, not retrieved.
- ❌ **Excluded**: not usable for Release 1 (reason given).

**Rule for all sources:** neighborhood, county and company indicators describe the **area or the company**, not the property's own financial performance. The product must never present them as property-level results (see doc 04 §8).

---

## 1. Summary table: Release 1 core sources

| ID | Source | What it powers | Geography | Cadence | Access | Status |
|---|---|---|---|---|---|---|
| SRC-01 | US Census Geocoder | Address → coordinates and census geography | Address / point | Continuous | Free, no key | ✅ (34 of 36 Paragon addresses matched; see §5) |
| SRC-02 | OSM Nominatim (fallback geocoder) | Coordinates when SRC-01 fails | Address / point | Continuous | Free, strict usage policy | ✅ |
| SRC-03 | ACS 5-year estimates (Census) | Ring demographics and trends | Block group | Annual | Free; API needs a free key, bulk files need none | 🟡 API requires key; bulk ✅ |
| SRC-04 | TIGERweb / TIGER/Line (Census) | Block group and block geometry; 2020 block population weights | Block | Decennial / annual | Free, no key | ✅ |
| SRC-05 | LEHD LODES (Census) | Jobs located in each ring | Block | Annual | Free, no key | ✅ (2024 files present) |
| SRC-06 | BLS QCEW | County employment, establishments, wages by industry | County | Quarterly | Free, no key | ✅ (2026 Q1 latest) |
| SRC-07 | BLS LAUS | County unemployment rate | County | Monthly | Free; v1 API keyless, v2 free key | ✅ (Sep 2026 preliminary) |
| SRC-08 | BLS CPI-U | Inflation adjustment for income trends | US | Monthly / annual | Same API as SRC-07 | ⬜ (same API as SRC-07, verified) |
| SRC-09 | Census Building Permits Survey | New residential units authorized (housing pipeline) | County, permit-issuing place | Monthly | Free, no key | ✅ (Sep 2026) |
| SRC-10 | FHWA HPMS (via USDOT geo.dot.gov) | Traffic (AADT) on nearby roads | Road segment | Annual | Free, no key | ✅ (2024 data; all 12 portfolio states respond) |
| SRC-11 | FEMA National Flood Hazard Layer | Flood zone at site | Polygon | Continuous | Free, no key | 🟡 (intermittent server failures) |
| SRC-12 | FEMA National Risk Index | Natural-hazard risk ratings | Census tract | ~Annual | Free, no key | ✅ (Dec 2025 version) |
| SRC-13 | Overture Maps Places | Nearby businesses, anchors and brands; month-to-month changes | Point (POI) | Monthly | Free; open licences | ✅ (Oct 2026 release; change detection demonstrated) |
| SRC-14 | SEC EDGAR | Tenant credit events (bankruptcy, exit/closure items) | Company | Daily | Free; User-Agent with contact email required | ✅ |
| SRC-15 | User input | Portfolio, tenants, GLA, notes, pin corrections | Property | On demand | n/a | n/a |
| SRC-16 | Paragon public website | One-time seed of properties and listed tenants | Property | One-time | Public web page | ✅ (`data/seed/paragon_public_properties.csv`) |

---

## 2. Source details

Each entry follows the same template: **Provider and links · Coverage and geography · Fields used → decisions supported · Access, cost and licence · Cadence, history and limitations · Integration and fallback · Verification.**

### SRC-01 · US Census Geocoder

- **Provider and links:** U.S. Census Bureau. Service: https://geocoding.geo.census.gov/geocoder/ · Docs: https://geocoding.geo.census.gov/geocoder/Geocoding_Services_API.html
- **Coverage and geography:** US addresses. Returns an interpolated point on the street segment plus census geographies (state, county, tract, block group, block).
- **Fields used → decisions:** `coordinates.x/y`, `matchedAddress`, `geographies` (STATE, COUNTY, TRACT, BLKGRP, GEOID). Places every property and candidate on the map and links it to census geography.
- **Access, cost and licence:** Free, no key, public domain. Single-address and batch endpoints; batch accepts up to 10,000 addresses per file.
- **Cadence, history and limitations:** Based on the Census address file (TIGER), refreshed periodically. **Limitations:** (1) points are **interpolated along the street centerline**, not on the rooftop or parcel, which matters for flood-zone checks; (2) some commercial addresses fail (Kingston Marketplace gave No_Match; 445 Main St, Mt. Kisco gave a Tie); (3) street-name variants can produce non-exact matches (e.g. "Church Hill Road" matched "Church Rd").
- **Integration and fallback:** Use first. On No_Match or Tie, try SRC-02, then ask the user to drop or confirm a pin on the map. The user can always drag the pin onto the building (FR-05).
- **Verification:** ✅ Batch of 36 Paragon addresses: 34 matched (31 exact, 3 non-exact), 1 no match, 1 tie. The single-address call for 444 Westport Ave, Norwalk returned (41.126611, −73.388299), block group `091900435001`, in about 0.25 s.

### SRC-02 · OpenStreetMap Nominatim (fallback geocoder)

- **Provider and links:** OpenStreetMap Foundation. API: https://nominatim.org/release-docs/latest/api/Search/ · Usage policy: https://operations.osmfoundation.org/policies/nominatim/ · Licence: https://www.openstreetmap.org/copyright
- **Coverage and geography:** Global; address and POI points.
- **Fields used → decisions:** `lat`, `lon`, `display_name`. Fallback geocoding only.
- **Access, cost and licence:** Free. **Usage policy:** at most 1 request per second, an identifying User-Agent, results cached, no bulk geocoding. Data is ODbL and requires "© OpenStreetMap contributors" attribution wherever these coordinates are displayed.
- **Cadence, history and limitations:** Community-maintained, so coverage varies. A candidate (deal) address is sent to a third party, so disclose this in the privacy note (doc 06 §2).
- **Integration and fallback:** Used only after SRC-01 fails, at most one request per lookup. If the team expects volume, the implementing agent may substitute a commercial geocoder whose terms allow storing results, but must then document its cost and terms. The final fallback is a manual pin.
- **Verification:** ✅ "1200 Ulster Avenue, Kingston, NY" returned (41.9651857, −73.9889473), a building in the Kingston Marketplace area.

### SRC-03 · American Community Survey (ACS) 5-year estimates

- **Provider and links:** U.S. Census Bureau. Program: https://www.census.gov/programs-surveys/acs · API: https://www.census.gov/data/developers/data-sets/acs-5year.html · Key signup: https://api.census.gov/data/key_signup.html · Bulk table-based summary files: https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/ · Terms: https://www.census.gov/data/developers/about/terms-of-service.html
- **Coverage and geography:** All US; **block group** is the smallest geography for 5-year data. Every estimate comes with a 90% margin of error (MOE).
- **Fields used → decisions** (detailed tables):

  | Table | Field(s) | Metric (doc 04) |
  |---|---|---|
  | B01003 | Total population | MET-01, MET-06 |
  | B11001 | Households | MET-02 |
  | B19001 | Household income brackets (16 bins) | MET-03 (interpolated ring median) |
  | B19025 | Aggregate household income | MET-04 (mean HH income), MET-07 |
  | B15003 | Educational attainment, 25+ | MET-05 |

  Decisions supported: size and affluence of the trade area, growth or decline, comparison with the existing portfolio.
- **Access, cost and licence:** Free, public domain. **Finding:** as of 2026-11-17 the Data API **rejects keyless requests** (HTTP 302 to `missing_key.html`). A free key is needed for API use. The **bulk table-based summary files need no key** and contain every block group nationally (for example `acsdt5y2024-b01003.dat`, 18 MB, pipe-delimited, columns `GEO_ID|B01003_E001|B01003_M001`).
- **Cadence, history and limitations:** Annual. The latest is **2020–2024** (bulk files dated 2026-01-29; the 2025 vintage API returns 404). The next vintage (2021–2025) is expected around Dec 2026 to early 2027; the release date is not confirmed. **Limitations:** (1) block-group estimates have large MOEs (e.g. BG `091900435001` median HH income $97,000 ± $29,003); (2) Census advises against comparing **overlapping** 5-year periods, so trends compare 2015–2019 with 2020–2024; (3) 2015–2019 uses 2010 block groups and 2020–2024 uses 2020 block groups, so each vintage must be apportioned to rings with its own geography (doc 04 §3); (4) **Connecticut** switched from 8 counties to 9 planning regions starting with 2022 data. 2020–2024 CT geographies use new county codes (e.g. `09190`, Western Connecticut Planning Region) while tract and block-group numbers are unchanged (verified: tract `043500` exists under both `09001` and `09190`).
- **Integration and fallback:** Preferred approach: annual bulk ingestion of the five tables (two vintages) into the app database, which needs no key. Alternative: the API with `CENSUS_API_KEY`. Fallback: if a vintage fails to load, keep serving the previous vintage, labelled with its period.
- **Verification:** ✅ Bulk files downloaded. Block groups `091900435001` = 1,103 people (MOE 172), `091900435002` = 1,123 (MOE 498); 242,297 block-group rows nationally. Ring test: the 3-mile population around 444 Westport Ave (block-group internal-point method) was **84,055 ± 3,838**, against **84,256** on Paragon's own listing (Esri 2021), a 0.2% difference. See SRC-04 for the 1-mile accuracy issue.

### SRC-04 · TIGERweb and TIGER/Line geography

- **Provider and links:** U.S. Census Bureau. REST services: https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb · Docs: https://tigerweb.geo.census.gov/tigerwebmain/TIGERweb_restmapservice.html · Bulk shapefiles: https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html
- **Coverage and geography:** All US. Block groups (ACS 2024 layer 10), 2020 Census blocks (`tigerWMS_Census2020` layer 10, with `POP100`, `HU100`, `INTPTLAT/LON`). The 2010 equivalents are needed for the 2015–2019 vintage.
- **Fields used → decisions:** `GEOID`, `INTPTLAT/INTPTLON` (internal points), `POP100` (2020 block population, used as apportionment weights).
- **Access, cost and licence:** Free, no key, public domain.
- **Cadence, history and limitations:** Blocks are decennial; block groups follow ACS vintages. Spatial queries return at most a server-defined number of features (no `exceededTransferLimit` was hit in tests up to 3 miles). The bulk shapefiles avoid any limits.
- **Integration and fallback:** Either query REST on demand and cache, or load national (or portfolio-state) shapefiles once. **Decision for the implementing agent.** Fallback: the bulk files.
- **Verification:** ✅ 78 block groups within 3 miles of 444 Westport Ave in 0.14 s. 150 blocks within 1 mile; **2020 block population with internal points within 1 mile = 11,521**, against **11,474** on Paragon's listing (Esri 2021). The block-group internal-point method gave only **9,138** (−20%). **Conclusion: rings must use block-population-weighted apportionment (doc 04 §3), especially for 1-mile rings.**

### SRC-05 · LEHD Origin-Destination Employment Statistics (LODES 8)

- **Provider and links:** U.S. Census Bureau, LEHD program. Data: https://lehd.ces.census.gov/data/#lodes · Files: `https://lehd.ces.census.gov/data/lodes/LODES8/{st}/wac/{st}_wac_S000_JT00_{year}.csv.gz`
- **Coverage and geography:** States; **jobs by workplace census block** (2020 blocks).
- **Fields used → decisions:** `w_geocode` (block), `C000` (total jobs), `CNS07` (retail trade jobs), `CNS18` (accommodation and food services). Supports MET-08 and MET-09: the daytime worker population that feeds lunch and convenience retail, and job growth or loss near the site.
- **Access, cost and licence:** Free, no key, public domain.
- **Cadence, history and limitations:** Annual, with about a 2-year lag. **2024 files are present** for CT and NY (file stamp 2026-10-14). History goes back to 2002 for most states. **Limitations:** noise is added to block-level values for confidentiality, so values must be aggregated to rings and never shown per block. Some state-years are missing, so check per state. Federal employment is handled differently from other jobs. **CT block codes in LODES use the legacy county FIPS** (e.g. `09001…`), unlike ACS 2022+, so match by block internal-point location (from SRC-04 2020 blocks), not by county code.
- **Integration and fallback:** Annual download of one WAC file per portfolio state (plus states of saved candidates, on demand). Join to 2020 block internal points and sum blocks within each ring. Fallback: show the last loaded year.
- **Verification:** ✅ Directory listing shows `ct_wac_S000_JT00_2021–2024` and `ny_wac_…_2023–2024`. The CT 2024 file header and first row were read successfully.

### SRC-06 · BLS Quarterly Census of Employment and Wages (QCEW)

- **Provider and links:** U.S. Bureau of Labor Statistics. Program: https://www.bls.gov/cew/ · Open data access: https://www.bls.gov/cew/additional-resources/open-data/ · Layout: https://www.bls.gov/cew/about-data/downloadable-file-layouts/quarterly/naics-based-quarterly-layout.htm · Example: `https://data.bls.gov/cew/data/api/2025/4/area/36111.csv`
- **Coverage and geography:** County (and state, MSA), by NAICS industry and ownership. CT uses planning-region codes (`09110`–`09190`) for recent data; `09001` returned 404 for 2025 Q4.
- **Fields used → decisions:** `own_code=5` (private), `industry_code` (`10` total, `44-45` retail trade, `722` food services), `month3_emplvl`, `qtrly_estabs`, `oty_month3_emplvl_pct_chg`, `avg_wkly_wage`, `disclosure_code`. Supports MET-10 and MET-11 and signals SIG-03 and SIG-04: is the local economy (and local retail employment) growing or shrinking.
- **Access, cost and licence:** Free, no key, public domain.
- **Cadence, history and limitations:** Quarterly, about 5–6 months after the quarter ends. **2026 Q1 is the latest** as of 2026-11-17. Long history. **Limitations:** county-level only (not neighborhood); cells can be suppressed (`disclosure_code = N`), and suppressed cells must show as "Not disclosed by BLS," never as zero.
- **Integration and fallback:** Quarterly fetch of one CSV per county in the portfolio and candidate set. Fallback: the previous quarter, labelled.
- **Verification:** ✅ Ulster County, NY (36111), 2025 Q4: private total employment 47,329 (month 3), +1.9% year over year, average weekly wage $1,144. Retail trade 8,142 (−0.3%). Western CT Planning Region `09190` also returned data.

### SRC-07 · BLS Local Area Unemployment Statistics (LAUS)

- **Provider and links:** BLS. Program: https://www.bls.gov/lau/ · API: https://www.bls.gov/developers/ · Key registration (v2): https://data.bls.gov/registrationEngine/ · Series format: `LAUCN{5-digit county FIPS}0000000003` (unemployment rate).
- **Coverage and geography:** County (also cities and towns in New England). CT uses planning-region codes.
- **Fields used → decisions:** monthly unemployment rate and the `(P)` preliminary footnote. Supports MET-12 and SIG-05: is local labour-market stress rising.
- **Access, cost and licence:** Free. API v1 is keyless (25 queries/day, 10 years, 25 series per query). **v2 with a free key** allows 500 queries/day and 50 series per query, and is recommended.
- **Cadence, history and limitations:** Monthly, about a 1–2 month lag. The latest month is **preliminary** and revised the next month, with annual benchmark revisions. County data is **not seasonally adjusted**, so compare **the same month a year earlier**, never month to month.
- **Integration and fallback:** Monthly batch for all relevant counties (2 queries for the whole portfolio). Fallback: the last loaded month, labelled.
- **Verification:** ✅ v1 keyless request returned Ulster Co. NY Sep 2026 = 3.8% (P), Western CT Planning Region Sep 2026 = 4.5% (P), Philadelphia Co. Sep 2026 = 4.3% (P).

### SRC-08 · BLS Consumer Price Index (CPI-U)

- **Provider and links:** BLS. Series `CUUR0000SA0` (CPI-U, US city average, not seasonally adjusted). Annual average period `M13`. Same API as SRC-07.
- **Use:** Convert 2015–2019 ACS dollars to 2020–2024 dollars for MET-07 (real income change). Census's own guidance prefers CPI-U-RS for ACS comparisons. **Decision for the implementing agent:** use CPI-U-RS if it can be obtained programmatically, otherwise CPI-U. The UI must label which index was used.
- **Status:** ⬜ Not separately retrieved (same API and auth as SRC-07, which was verified).

### SRC-09 · Census Building Permits Survey (BPS)

- **Provider and links:** U.S. Census Bureau. Program: https://www.census.gov/construction/bps/ · Files: https://www2.census.gov/econ/bps/ (`County/co{yymm}c.txt`, `Place/{Region}/{rr}{yymm}c.txt`)
- **Coverage and geography:** County and permit-issuing place (city or town), for all US permit-issuing jurisdictions.
- **Fields used → decisions:** buildings, units and value for 1-unit, 2-unit, 3–4-unit and 5+-unit structures (estimates with imputation; "rep" columns are reported-only). Supports MET-13 and SIG-07: the residential construction pipeline, meaning future rooftops (demand) near a center.
- **Access, cost and licence:** Free, no key, public domain.
- **Cadence, history and limitations:** Monthly, with a ~1-month lag (**Sep 2026 is the latest**). Annual files exist. **Limitations:** residential only (no commercial permits nationally); authorizations are not completions; place boundaries do not equal rings.
- **Integration and fallback:** Monthly download of the county file (national, small) and the regional place files. Fallback: the last month, labelled.
- **Verification:** ✅ `co2609c.txt` (Sep 2026): Western CT Planning Region 33 single-family units and 17 units in 5+-unit buildings authorized. Ulster Co. NY 19 single-family and 49 units in 5+-unit buildings.

### SRC-10 · FHWA Highway Performance Monitoring System (HPMS), via USDOT

- **Provider and links:** Federal Highway Administration. Program: https://www.fhwa.dot.gov/policyinformation/hpms.cfm · Field manual: https://www.fhwa.dot.gov/policyinformation/hpms/fieldmanual/ · Per-state services: `https://geo.dot.gov/server/rest/services/Hosted/HPMS_FULL_{ST}_{YEAR}/FeatureServer/0`
- **Coverage and geography:** All states. Road segments with Annual Average Daily Traffic.
- **Fields used → decisions:** `aadt`, `data_year`, `routename`, `routenumber`, `f_system` (functional class), `through_lanes`. Supports MET-14 and SIG-08: access, visibility and traffic exposure of the site.
- **Access, cost and licence:** Free, no key, public.
- **Cadence, history and limitations:** Annual. **2024 is the latest verified** (services exist for all 12 portfolio states). **Limitations:** AADT values may be estimated or factored rather than counted that year (state practice varies); a segment-level value is not the count at the property's entrance; older listing counts may differ (Kingston: listing 32,930 VPD against HPMS 2024 22,523 on the US 9W segment). Note: an Esri-hosted "HPMS_2024_Data" service found by search is **Arizona-only**. Do not use it.
- **Integration and fallback:** Query segments within ~250 m of the pin (on demand, cached for a year). Show the top two segments by functional class. Fallback: "No federal traffic count within 250 m," plus an optional user-entered count labelled "user-provided."
- **Verification:** ✅ NY 2024: segment "ULSTER AVE US 9W", AADT **22,523**, 4 through lanes, functional class 3, near Kingston Marketplace.

### SRC-11 · FEMA National Flood Hazard Layer (NFHL)

- **Provider and links:** FEMA. Program: https://www.fema.gov/flood-maps/national-flood-hazard-layer · REST: https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer (layer **28**, Flood Hazard Zones)
- **Coverage and geography:** Areas with digital FIRMs, which covers most of the US population. Some areas have no digital map, and that must show as "No digital flood map," not "no risk."
- **Fields used → decisions:** `FLD_ZONE`, `ZONE_SUBTY`, `SFHA_TF` (in a Special Flood Hazard Area), `STATIC_BFE`, `DFIRM_ID`. Supports MET-17 and SIG-11: insurance cost, lender requirements, physical risk.
- **Access, cost and licence:** Free, no key, public.
- **Cadence, history and limitations:** Updated continuously as map revisions take effect. **Limitations:** (1) the service is **unreliable for point queries**: during verification, 5 of 7 point-geometry queries failed (HTTP 400 "Failed to execute query" or connection reset or timeout), including all 3 attempts at 444 Westport Ave, while a **small-envelope query at the same location succeeded**; (2) the screening result depends on pin accuracy; (3) it is not an official flood determination.
- **Integration and fallback:** Query a small envelope around the pin (≈ ±30 m) plus a ~100 m buffer envelope, with retries, exponential backoff and a 30-day cache. On failure, show the last cached result with its date, or "Flood data temporarily unavailable." A WMS overlay on the map is optional (P1). Bulk NFHL downloads per county are a heavier fallback if the REST service stays unusable.
- **Verification:** 🟡 Cypress Lake Shopping Center (Fort Myers, FL) geocoded point is in **zone AE, coastal floodplain, SFHA = T, BFE 9 ft**. 299 Riverside Ave, Westport (geocoded street point) is in zone X. The waterfront building should be re-checked with a corrected pin. An envelope query at 444 Westport Ave returned zone X.

### SRC-12 · FEMA National Risk Index (NRI)

- **Provider and links:** FEMA. https://hazards.fema.gov/nri/ · Data: https://hazards.fema.gov/nri/data-resources · Service: https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Census_Tracts/FeatureServer/0
- **Coverage and geography:** All US census tracts (and counties).
- **Fields used → decisions:** `RISK_RATNG`, `RISK_SPCTL`, `EAL_RATNG`, `SOVI_RATNG`, `RESL_RATNG`, per-hazard ratings such as `CFLD_RISKR` (coastal flood), `HRCN_RISKR` (hurricane) and `RFLD_RISKR` (riverine flood), and `NRI_VER`. Supports MET-18: broad natural-hazard context.
- **Access, cost and licence:** Free, no key, public.
- **Cadence, history and limitations:** About once a year (**"December 2025"** version verified). **Limitations:** tract-level modelled ratings, relative nationally; context only and never a property risk score. The tract vintage (2010 vs 2020 codes) was not checked, so look up by **spatial query on the pin**, not by joining tract codes. Use field names exactly as published (a query with a wrong `outFields` list returns HTTP 400).
- **Integration and fallback:** Spatial lookup at the pin; cache until `NRI_VER` changes. Fallback: "Unavailable."
- **Verification:** ✅ Lee County, FL tract `12071000303`: overall "Relatively Moderate" (56.8 percentile), hurricane "Relatively High", coastal flood "Relatively Moderate", version "December 2025."

### SRC-13 · Overture Maps Places

- **Provider and links:** Overture Maps Foundation (Linux Foundation). Guide: https://docs.overturemaps.org/guides/places/ · Schema: https://docs.overturemaps.org/schema/ · Release notes: https://docs.overturemaps.org/blog/ · Attribution: https://docs.overturemaps.org/attribution/ · Data: `s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*` (GeoParquet, also on Azure)
- **Coverage and geography:** Global POI points (businesses, services, amenities).
- **Fields used → decisions:** `id` (GERS ID, stable across releases), `names.primary`, `basic_category` / `taxonomy`, `brand.names.primary`, `operating_status` (`open`, `permanently_closed`, `temporarily_closed`, or null), `confidence` (0–1, existence likelihood), `addresses`, `geometry`. Supports MET-15, MET-16, SIG-09 and SIG-10: retail landscape, anchors and competitors nearby, possible closures and new openings near owned and candidate sites.
- **Access, cost and licence:** Free. The theme is published under **CDLA-Permissive-2.0, Apache-2.0 (Foursquare-sourced records) and CC0 (some sources)**. It **contains no OpenStreetMap data and no ODbL share-alike**. Attribution is required (per the attribution page and each record's `sources`).
- **Cadence, history and limitations:** **Monthly** releases. The latest on 2026-11-17 is `2026-10-21.0`. **Only about two prior releases remain in the bucket** (`2026-09-23.0/.1`, `2026-10-21.0`), so **the app must snapshot each release it uses**; history cannot be fetched later. **Limitations:** (1) it is not a business registry; a record newly appearing does not mean a business newly opened; (2) `operating_status` is null where Overture has no signal (98 of 565 records in the probe), and the schema changed through 2026 (the `categories` property was removed in favour of `taxonomy`/`basic_category`), so pin to the schema version and test after each release; (3) brand names vary (e.g. "DICK'S Sporting Goods" vs "Dick's Sporting Goods") and need normalization; (4) dataset-wide changes (a new source added) can look like neighborhood change. Doc 04 §5 defines a guard against this.
- **Integration and fallback:** A monthly job reads the new release with bounding-box filtering (DuckDB or another GeoParquet reader) for every monitored location (owned plus saved candidates, out to 3 miles) and stores the snapshot. On-demand candidate screens query the latest release directly (~10–30 s; load progressively). Fallback: the last stored snapshot, labelled with its release.
- **Verification:** ✅ Release `2026-10-21.0`, ±0.012° box (about 0.8 mi) around Kingston Marketplace: **565 places in 9.7 s** (DuckDB 2.0 from a laptop). 448 open, 19 permanently closed, 98 null status. Brands present include ALDI, Hannaford, CVS, Dollar Tree, HomeGoods, Barnes & Noble. **Month-over-month diff `2026-09-23.1` → `2026-10-21.0`:** 554 → 565 records; all 554 IDs persisted; 11 added; 23 status changes, including **"Regal Cinemas Hudson Valley Mall 12": open → permanently_closed** (a real co-tenancy-type signal) and many null → open changes (enrichment, not real change, so the rules must ignore them).

### SRC-14 · SEC EDGAR

- **Provider and links:** U.S. Securities and Exchange Commission. APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces · Submissions: `https://data.sec.gov/submissions/CIK##########.json` · Full-text search UI: https://efts.sec.gov/LATEST/search-index?q=… (backs https://www.sec.gov/edgar/search/) · Form 8-K items: https://www.sec.gov/files/form8-k.pdf · Fair access: https://www.sec.gov/os/accessing-edgar-data
- **Coverage and geography:** SEC registrants (public companies and some private issuers with public debt). Company-level, not store-level.
- **Fields used → decisions:** `filings.recent.form`, `filingDate`, `items` (8-K item numbers), `primaryDocument`, `accessionNumber`. Key 8-K items: **1.03 Bankruptcy or Receivership**, **2.05 Costs Associated with Exit or Disposal Activities** (often store closures or restructuring), **2.06 Material Impairments**. Supports MET-19, SIG-12 and SIG-13: credit and closure risk for anchors and national tenants.
- **Access, cost and licence:** Free, public domain. **Fair access policy:** at most 10 requests per second, and a **declared User-Agent with organization name and contact email** is required. `www.sec.gov/files/company_tickers.json` returned **403** for a generic User-Agent without an email, while `data.sec.gov` and `efts.sec.gov` accepted it. Production must set `SEC_USER_AGENT="<App name> <contact email>"` using an address Adi or Amit provides.
- **Cadence, history and limitations:** Real-time (filings appear the same day). **Limitations:** private tenants (local businesses, many franchisees, private chains) are not covered; an 8-K item says nothing about **which** stores are affected; tenant-to-filer mapping needs care (brand ≠ legal entity, e.g. Marshalls/HomeGoods/TJ Maxx → The TJX Companies).
- **Integration and fallback:** A daily job fetches submissions for every mapped tenant CIK and flags new 8-Ks containing the watched items. Optional (P1): full-text search for "store closures" mentions. Tenant-to-CIK mapping uses a seed table plus an admin lookup (FR-22). Fallback: "SEC check failed on DATE; last successful check DATE."
- **Verification:** ✅ CVS Health (CIK 64803): 1,001 recent filings; latest 10-Q 2026-11-04; 8-K items parsed (e.g. `2.02,9.01`). **Rite Aid (CIK 84129): 8-K with items `1.01,1.03,2.04,…` on 2023-10-16**; Southside Shopping Center lists Rite Aid as an anchor, so this signal would have fired. Full-text search for "store closures" in 8-Ks from 2026-09-01 to 2026-11-16 returned **37 hits**, including **Leslie's, Inc. 8-K 2026-09-30 with item 1.03**.

### SRC-15 · User input

The portfolio list and status, property names, pin corrections, ring preset, gross leasable area (GLA), tenant roster and anchor flags, tenant-to-company mapping, notes, and optional user-provided values (e.g. a traffic count from a broker package). Every user-entered value is labelled **"User-provided"** with who entered it and when. It is never mixed silently with sourced data.

### SRC-16 · Paragon public website (seed)

A one-time seed of the 36 publicly listed properties and their listed tenants: [`data/seed/paragon_public_properties.csv`](../data/seed/paragon_public_properties.csv). Imported records are marked **"Unconfirmed: from paragonct.com, 2026-11-17"** until a user confirms each property (A-05, A-06). The listing's Esri 2021 demographics and old traffic counts must **not** be imported as data.

---

## 3. Evaluated and deferred or excluded

| Source | What it would add | Finding | Decision |
|---|---|---|---|
| **CT Real Estate Sales 2001–2024** (data.ct.gov `5mzw-sjtu`, [link](https://data.ct.gov/d/5mzw-sjtu)) | Actual sale prices, including commercial and industrial, for CT towns | ✅ Verified: e.g. "54 Wilton Road, Westport, Commercial, $16.5M, recorded 2025-09-12." Covers Oct 2024–Sep 2025 sales (dataset updated 2026-08-12). Annual; address-only (needs geocoding); CT only. | **Deferred to Release 1.1** as "Connecticut sale comps." |
| **CT Business Registry** (`n7gp-d28j`) | New business formations | ✅ Verified, updated daily. But the location is a **mailing or billing city**, not the place of business, and most entries are holding LLCs, so it is too noisy as a neighborhood signal. | Excluded |
| **Census County / ZIP Business Patterns** | Establishments by NAICS by ZIP | Latest 2023 (2024 not yet posted); overlaps with QCEW (quarterly, fresher). | Excluded (redundant) |
| **HUD Aggregated USPS Vacancy Data** | Tract-level vacant business addresses | Access is restricted to registered governmental, educational and non-profit users ([HUD](https://www.huduser.gov/portal/datasets/usps.html)). Paragon is not eligible. | Excluded |
| **EPA EJScreen** | Environmental indicators | Removed from EPA in Feb 2025; a lawsuit over the removal was dismissed in Mar 2026. Only third-party archives remain. | Excluded |
| **EPA FRS / ECHO** | Nearby regulated or contaminated sites | Available, but Phase I environmental assessments already cover this in diligence. | Deferred (later release) |
| **FBI Crime Data Explorer** | Crime trends | Agency-level, uneven NIBRS reporting; easily misread at neighborhood level. | Deferred, with caveats |
| **Transit GTFS feeds** | Transit access for urban sites | Relevant to a few urban sites only. | Deferred |
| **CT statewide parcels / CAMA** | Assessor attributes | Not tested; CT only. | Possible Release 1.1 candidate (⬜) |
| **CoStar / LoopNet / Crexi** | Listings, rents, comps, vacancy | Paid; no permitted public API; terms prohibit scraping. | **Excluded. Never scrape.** |
| **Placer.ai** (foot traffic) | Visits, trade-area origin | Paid subscription. | Excluded (optional upgrade) |
| **Esri Business Analyst** | Current-year demographic estimates and projections, consumer spending | Paid. Paragon's listings used Esri 2021 data, so Paragon or its brokers may have access (Q-04). | Excluded (optional upgrade) |
| **Regrid / ATTOM** (parcels, ownership, sales) | National parcels and transactions | Paid. | Excluded (optional upgrade) |
| **Dodge / ConstructConnect** | Commercial construction pipeline | Paid. | Excluded |
| **News scraping / Google Places** | Openings and closures | Licensing and terms restrictions; Google Places terms limit storage and display. | Excluded |

## 4. Optional paid upgrades (post-Release 1, John's decision)

Ask vendors for quotes. **Prices were not verified** and none should be assumed.

1. **Esri Business Analyst or a demographics API**: current-year estimates, 5-year projections, consumer spending by category.
2. **Placer.ai**: foot-traffic trends for owned centers and competitors.
3. **CoStar**, if Paragon already subscribes and the licence permits: market rent, vacancy, comps. Integrate only under licence terms; never scrape.
4. **Regrid**: national parcels for accurate site footprints, which would also improve flood screening.

---

## 5. Verification log (2026-11-17)

Reproduce with [`scripts/feasibility/probe_public_sources.sh`](../scripts/feasibility/probe_public_sources.sh) and [`scripts/feasibility/overture_places_probe.py`](../scripts/feasibility/overture_places_probe.py). Values can change with source revisions.

| # | Request | Result | Use as regression reference? |
|---|---|---|---|
| V1 | Census Geocoder, single: "444 Westport Avenue, Norwalk, CT 06851" | (41.126611, −73.388299); BG `091900435001`; county `190` | Yes (±0.0005°) |
| V2 | Census Geocoder, batch: 36 public Paragon addresses | 34 matched (31 exact), 1 No_Match (1200 Ulster Ave, Kingston), 1 Tie (445 Main St, Mt. Kisco) | Yes |
| V3 | Census Data API, keyless | HTTP 302 → `missing_key.html` | No (access fact) |
| V4 | ACS 2020–24 bulk `acsdt5y2024-b01003.dat` | BG `091900435001` = 1,103 (MOE 172) | Yes (exact) |
| V5 | Ring test, 444 Westport Ave, 3 mi, BG internal points | 62 BGs, 84,055 ± 3,838 (listing: 84,256) | Yes (±5%) |
| V6 | 2020 block population within 1 mi (block internal points) | 150 blocks, 11,521 (listing: 11,474; BG-only method 9,138) | Yes (±5%) |
| V7 | QCEW 2025 Q4, area 36111 | Private total 47,329, +1.9% OTY; retail 8,142, −0.3% | Yes (exact unless revised) |
| V8 | LAUS v1, Sep 2026 | 36111: 3.8% (P); 09190: 4.5% (P); 42101: 4.3% (P) | No (preliminary, will be revised) |
| V9 | BPS `co2609c.txt` | 09190 1-unit = 33; 36111 1-unit = 19 | Yes |
| V10 | LODES8 directory | CT 2021–2024, NY 2023–2024 WAC files present | Yes |
| V11 | HPMS NY 2024, 250 m of Kingston pin | ULSTER AVE US 9W, AADT 22,523 | Yes |
| V12 | NFHL layer 28, Cypress Lake pin | Zone AE, SFHA T, BFE 9 | Yes |
| V13 | NFHL reliability | 5 of 7 point queries failed (HTTP 400, reset or timeout), all 3 at 444 Westport Ave; envelope query there succeeded (zone X) | Reliability note |
| V14 | NRI tract `12071000303` | Relatively Moderate; hurricane Relatively High; Dec 2025 | Yes |
| V15 | Overture `2026-10-21.0`, Kingston box | 565 places, 9.7 s; 19 permanently closed | Yes (count ±10%) |
| V16 | Overture diff `2026-09-23.1` → `2026-10-21.0` | +11 IDs, 0 removed; Regal Cinemas Hudson Valley Mall 12 → permanently_closed | Yes (fixture) |
| V17 | EDGAR submissions, CIK 84129 (Rite Aid) | 8-K 2023-10-16 items include 1.03 | Yes |
| V18 | EDGAR full-text "store closures", 8-K, 2026-09-01→2026-11-16 | 37 hits; Leslie's 8-K 2026-09-30 includes item 1.03 | No (search index changes) |
| V19 | data.ct.gov `5mzw-sjtu` latest commercial sale | Max recorded date 2025-09-30; 9,664 commercial rows | Release 1.1 |
| V20 | `www.sec.gov/files/company_tickers.json` with a generic User-Agent | HTTP 403 | Access fact: a contact email is required |

## Basemap delivery (implementation choice, 2026-11-18)

OpenStreetMap standard raster tiles supply visual context only; they do not produce
property or trade-area metrics. Provider policy, attribution, coverage, privacy,
caching, configuration, failures, and verification are documented in [MAPS.md](MAPS.md).
This does not add a metric source or change the 16-source ingestion catalog.
