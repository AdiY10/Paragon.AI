# 04 · Data and Insight Requirements

**Purpose:** Define exactly how data becomes metrics, comparisons, signals and evidence, and how the product behaves when data is missing, stale, contradictory or inaccessible. Sources are defined in [03](03_DATA_SOURCES.md); requirements in [02](02_PRODUCT_REQUIREMENTS.md).

Thresholds and parameters in this document are **defaults stored as configuration**, not hard-coded. They are starting points to validate with John (A-11, Q-06).

---

## 1. Principles (non-negotiable)

1. **Real data or nothing.** Every value comes from a source in doc 03 or from labelled user input. Never fabricate, impute silently or fill gaps with plausible numbers. Sample or demo data must never appear in the deployed product.
2. **Provenance travels with every value:** source, data period, last checked, geography and method.
3. **Area indicators are not property results.** Population, jobs, traffic and nearby closures describe the **area**. SEC events describe the **company**. Neither is the property's occupancy, rent or value.
4. **Deterministic insights.** Signals, rankings and evidence summaries come from documented rules over stored data, are reproducible, and can be tested. Do not use generative AI to compute or write numbers, signals or summaries in Release 1.
5. **Show uncertainty.** Survey estimates show margins of error or reliability. Modelled or possibly-noisy data is labelled as such.
6. **Fail visibly.** A failure shows the last good value with its date, or "unavailable" with a reason. It never fails silently.

## 2. Feature-to-source mapping

| Capability / FR | Metrics / signals | Sources | User input |
|---|---|---|---|
| Locations (FR-03 to FR-07) | Pin, geography codes | SRC-01, SRC-02, SRC-04 | Address, pin correction, name, type, ring preset, GLA, tenants |
| Trade area (FR-09) | MET-01 to MET-07, SIG-01, SIG-02 | SRC-03, SRC-04, SRC-08 | Ring preset |
| Jobs (FR-10) | MET-08, MET-09, SIG-06 | SRC-05, SRC-04 | n/a |
| County economy (FR-11) | MET-10 to MET-12, SIG-03 to SIG-05 | SRC-06, SRC-07 | n/a |
| Housing pipeline (FR-12) | MET-13, SIG-07 | SRC-09 | n/a |
| Traffic (FR-13) | MET-14, SIG-08 | SRC-10 | Optional user-provided count (labelled) |
| Retail landscape (FR-14) | MET-15, MET-16, SIG-09, SIG-10 | SRC-13 | Tenant roster (matching own tenants) |
| Hazards (FR-15) | MET-17, MET-18, SIG-11 | SRC-11, SRC-12 | Pin correction |
| Tenant watch (FR-22) | MET-19, SIG-12, SIG-13 | SRC-14 | Tenant roster, tenant-to-SEC mapping |
| Portfolio benchmark (FR-16, FR-27) | MET-20 | Derived from the metrics above | Owned or confirmed status |
| Evidence summary (FR-26) | §6.3 rules | Derived | n/a |
| Data Sources page (FR-30) | Source status | Job run log | n/a |

**Excluded data** (doc 02 §6): rents, comps, listings, occupancy, foot traffic, financials. If a user looks for these, the UI says they are outside Release 1. It never shows a placeholder value.

## 3. Geography and matching

### 3.1 Location pin
- One point per location: the geocoded point, or a user-adjusted one.
- Store the method (`census_exact`, `census_non_exact`, `nominatim`, `manual`), the matched address and the timestamp.
- **Pin accuracy matters.** The Census geocoder interpolates along the street, so the UI prompts the user to "Check the pin is on the building" for every new location and shows the pin on satellite or aerial imagery if the chosen tile provider allows it. Moving the pin triggers recomputation (FR-05).

### 3.2 Rings
- **Presets:** `1/3/5` miles (default) or `3/5/10` miles, per location. **The 3-mile ring is the standard comparison ring** (present in both presets) for portfolio percentiles, evidence summaries and ring-based signals.
- Distances are great-circle (haversine) from the pin. Drive-time areas are out of scope.

### 3.3 Ring apportionment of ACS block-group estimates (required method)
Verification showed that a block-group-centroid method undercounts the 1-mile ring by about 20% (doc 03 SRC-04). Use **decennial block-population-weighted apportionment**:

For each ACS vintage *v* and ring *r*:
1. Take the census blocks of the matching decennial geography: **2020 blocks for ACS 2020–2024**, **2010 blocks for ACS 2015–2019**.
2. For each block group *g*, weight `w(g,r) = Σ POP(blocks of g whose internal point is inside r) / Σ POP(all blocks of g)`. If a block group has 0 decennial population, use the share of its block land area inside the ring.
3. **Count estimates:** `X_r = Σ_g w(g,r) · X_g`.
4. **MOE of sums** (Census approximation): `MOE_r = sqrt( Σ_g (w(g,r) · MOE_g)² )`.
5. **Ratios and means** (e.g. mean HH income = aggregate income ÷ households): compute from the ring sums. Ratio MOE uses the Census ratio approximation `MOE(R) = sqrt(MOE_num² + R²·MOE_den²) / den`. If the term under the root is negative, use the proportion formula variant per Census guidance.
6. **Ring medians** (MET-03): aggregate the bracket counts (B19001) with the weights, then linearly interpolate within the bracket containing the 50th percentile. If the median falls in the open-ended top bracket, display "≥ $200,000." Ring-median MOEs are not computed in Release 1; show the reliability of the underlying household count and label it "Interpolated median."

Each vintage uses its own geography, which accounts for 2010→2020 boundary changes. Expect some extra noise. That is one reason trend signals require statistical significance (§5).

### 3.4 County, planning region and place
- County comes from the Census geocoder `geographies` at the pin (current vintage). For manual or Nominatim pins, resolve it with a spatial lookup (TIGERweb) at the pin.
- **Connecticut:** current federal statistics (ACS 2022+, QCEW, LAUS, BPS) use **planning regions** (`09110`–`09190`); LODES block codes and pre-2022 data use legacy counties (`09001`–`09015`). Rules: (a) display the planning region for CT economic metrics; (b) compute a trend only between periods published for the **same geography code**. If the prior period does not exist for that code, show `GEOGRAPHY_CHANGED` (§7); (c) match block-level data by **location**, not county code.
- **Building permits place:** match the permit-issuing place to the Census place or, in New England, the county subdivision (town) containing the pin. If there is no match, show the county only and label it.

### 3.5 Traffic segment selection
Among HPMS segments within 250 m of the pin, choose up to 2 distinct named routes, preferring the lowest `f_system` (highest functional class), then the highest AADT. Show route name, AADT, `data_year` and distance. For year-over-year comparison (SIG-08), compare the **same route ID with overlapping begin and end points** in consecutive data years. Otherwise show "segment changed: no comparison."

### 3.6 Flood and hazard
- Flood: query a small envelope at the pin (≈ ±30 m) for the "at pin" result, and a ~100 m envelope for "nearby." Report the highest-risk zone found in each.
- NRI: spatial query for the tract at the pin.

### 3.7 Businesses (Overture)
- For each monitored location, snapshot every place within **3 miles** of the pin for each processed release, storing the GERS `id`, name, normalized brand, `basic_category`, `operating_status`, `confidence`, coordinates and release ID.
- **Brand normalization:** casefold, strip punctuation and legal suffixes, and apply a curated alias table (e.g. "dick's sporting goods" ← both observed variants; "the home depot" ↔ "home depot"). The alias table is configuration and is extended over time.
- **Category groups:** map `basic_category` (and `taxonomy` where needed) to these Release 1 groups: Grocery and food stores · Pharmacy and drug · General merchandise, discount and big box · Apparel and accessories · Home, hardware and furniture · Restaurants and cafés · Personal services · Medical and health · Banks and financial · Fitness and entertainment · Auto services · Other. **Key categories** (used by signals) are grocery, pharmacy, general merchandise, discount and big box, cinema and entertainment, and department stores. The implementing agent documents the full mapping table in the repo.
- **Filters:** exclude places with `confidence < 0.5` from counts. Treat `operating_status = permanently_closed` as closed, and `null` as "status unknown" (counted as present).

## 4. Metric definitions

"Direction" says which way counts as more favourable for comparison highlighting and evidence summaries: **↑** higher is favourable, **↓** lower is favourable, **–** neutral (never highlighted).

| ID | Metric | Definition / formula | Source | Geography | Period shown | Dir. | Uncertainty |
|---|---|---|---|---|---|---|---|
| MET-01 | Population | Σ weighted B01003_E001 | SRC-03, SRC-04 | Ring | ACS 2020–2024 | ↑ | MOE (sum); reliability |
| MET-02 | Households | Σ weighted B11001_E001 | SRC-03 | Ring | ACS 2020–2024 | ↑ | MOE; reliability |
| MET-03 | Median household income | Interpolated from weighted B19001 brackets (§3.3) | SRC-03 | Ring | ACS 2020–2024 (2024 $) | ↑ | "Interpolated"; household-count reliability |
| MET-04 | Mean household income | Σ B19025 / Σ B11001 | SRC-03 | Ring | ACS 2020–2024 (2024 $) | ↑ | Ratio MOE |
| MET-05 | Bachelor's degree or higher, age 25+ | (B15003_022..025) / B15003_001 | SRC-03 | Ring | ACS 2020–2024 | – | Proportion MOE |
| MET-06 | Population change | (MET-01 for 2020–24 − same for 2015–19) / 2015–19 | SRC-03 | Ring | "2015–19 → 2020–24" | ↑ | Significance test (§4.1) |
| MET-07 | Real mean HH income change | (MET-04 2020–24 − MET-04 2015–19 × CPI₂₀₂₄/CPI₂₀₁₉) / (MET-04 2015–19 × CPI ratio) | SRC-03, SRC-08 | Ring | "2015–19 → 2020–24, inflation-adjusted" | ↑ | Significance test |
| MET-08 | Jobs located in ring | Σ C000 of 2020 blocks inside ring; also retail (CNS07) and food service (CNS18) | SRC-05, SRC-04 | Ring | LODES year (e.g. 2024) | ↑ | Label "Noise-protected estimate" |
| MET-09 | Jobs in ring change | (Year Y − Y−1) / Y−1 | SRC-05 | Ring | "2023 → 2024" | ↑ | Shown only if both years ≥ 1,000 jobs |
| MET-10 | County private employment and YoY | QCEW own 5, industry 10, `month3_emplvl`; YoY % vs the same quarter a year earlier | SRC-06 | County / planning region | e.g. "Q1 2026" | ↑ (YoY) | Suppression handling |
| MET-11 | County retail trade employment and YoY | Same as MET-10, industry 44-45 | SRC-06 | County | Quarter | ↑ (YoY) | Suppression handling |
| MET-12 | Unemployment rate and change | LAUS rate; change in percentage points vs the same month a year earlier | SRC-07 | County | e.g. "Sep 2026 (preliminary)" | ↓ | Preliminary flag |
| MET-13 | Residential units authorized | Sum of units over the last 12 months vs the prior 12 months; % change | SRC-09 | County; permit place | "12 months to Sep 2026" | ↑ | Imputed estimates noted |
| MET-14 | Traffic (AADT) | Per §3.5 | SRC-10 | Segment | HPMS data year | ↑ | "May be estimated by the state DOT" |
| MET-15 | Nearby businesses by category | Count by category group within 1 and 3 mi (excluding closed and low-confidence places) | SRC-13 | 1 mi, 3 mi | Overture release | – | Label "Map data; may be incomplete" |
| MET-16 | Key brands and anchors nearby | Branded and key-category places with distance; "nearest grocery" | SRC-13 | Up to 3 mi | Overture release | – | Same |
| MET-17 | FEMA flood zone | Zone, subtype, SFHA flag, BFE at pin and within ~100 m | SRC-11 | Pin | Effective map (DFIRM ID), checked date | SFHA = unfavourable | Disclaimer |
| MET-18 | Natural hazard risk (NRI) | Overall rating, percentile; top 3 hazards by rating | SRC-12 | Tract | NRI version | – (Very High or Relatively High = concern) | "Modelled, relative" |
| MET-19 | Tenant SEC events | 8-Ks with items 1.03, 2.05 or 2.06 for mapped filers; last 5 years shown | SRC-14 | Company | Filing dates | n/a | "Company-level" |
| MET-20 | Portfolio percentile | `pct = (count(v_i < v) + 0.5·count(v_i = v)) / n` over non-archived Owned locations with a value for the same metric and the 3-mi ring. Requires n ≥ 5. | Derived | 3-mi ring | Same period as the metric | Follows the metric | "Based on n properties" |

### 4.1 Statistical significance for ACS trends
- `SE = MOE / 1.645`. `Z = |X₂ − X₁| / sqrt(SE₁² + SE₂²)`. The change is **significant at 90%** if `Z > 1.645`.
- For MET-07, scale the earlier estimate and its MOE by the CPI ratio before testing.
- Display: "Statistically significant increase / decrease" or "No statistically significant change." Signals require significance.

### 4.2 Reliability badges for ACS-derived values
`CV = (MOE / 1.645) / estimate`. **High** CV ≤ 15% · **Medium** 15–30% · **Low** 30–40% · **Very low** > 40%. A Very low value is shown greyed with "Very low reliability" and is excluded from signals, evidence summaries and comparison highlighting.

## 5. Signals

### 5.1 Severity
- **High**: likely direct impact on an owned property's tenancy, insurance or financing. Review this week.
- **Watch**: a meaningful change in the trade area or in a tenant's company that could affect demand or leasing.
- **FYI**: context worth knowing; no action implied.

Each signal also has a **direction** (Positive, Negative or Neutral) and **applies to** Owned and Candidate locations (the brief covers Owned; candidate signals appear on their profiles and comparisons).

### 5.2 Rules (defaults)

| ID | Name | Trigger (defaults) | Severity | Evaluated when | Resolves / expires | "Why it matters" text (template) |
|---|---|---|---|---|---|---|
| SIG-01 | Trade-area population change | MET-06 (3-mi) significant **and** abs ≥ 3.0% | Watch if negative; FYI if positive | New ACS vintage | Replaced at the next vintage | "Fewer (more) residents within 3 miles can reduce (increase) demand for neighborhood retail." |
| SIG-02 | Real income change | MET-07 (3-mi) significant **and** ≤ −5% / ≥ +5% | Watch / FYI | New ACS vintage | Next vintage | "Household spending power in the trade area has changed after inflation." |
| SIG-03 | County private employment trend | MET-10 YoY ≤ −2.0% (Watch) or ≥ +3.0% (FYI) | Watch / FYI | New QCEW quarter | Next quarter outside threshold | "Local job losses (gains) affect household income and daytime traffic." |
| SIG-04 | County retail employment decline | MET-11 YoY ≤ −4.0% | Watch | New QCEW quarter | Next quarter above threshold | "Falling retail employment can indicate retail contraction in the county." |
| SIG-05 | Rising unemployment | MET-12 ≥ +1.0 percentage point YoY | Watch | New LAUS month (re-evaluate on revision) | Next month below threshold | "Rising unemployment can weaken local spending." |
| SIG-06 | Jobs near the site | MET-09 (3-mi) ≤ −5% (Watch) or ≥ +5% (FYI); both years ≥ 1,000 jobs | Watch / FYI | New LODES year | Next year | "Fewer (more) people work near the center, affecting weekday traffic." |
| SIG-07 | Housing pipeline shift | MET-13 (place if available, else county) ≥ +25% **and** ≥ +50 units (FYI, positive) or ≤ −25% **and** ≤ −50 units (FYI, negative) | FYI | New BPS month | Next month outside threshold | "New housing adds future households to the trade area." |
| SIG-08 | Traffic change | Primary segment AADT ≤ −10% (Watch) or ≥ +10% (FYI), same segment (§3.5) | Watch / FYI | New HPMS year | Next year | "Traffic past the site affects visibility and convenience trips." |
| SIG-09 | Possible nearby closure | A place present in the previous snapshot (confidence ≥ 0.7, status open or null) is now `permanently_closed`, **or** disappears, **and** it is branded or in a key category, within 1 mi (key categories: within 3 mi). | **High** if the brand matches a tenant on this property's roster and the place is within 150 m of the pin; **Watch** if key-category or branded within 0.5 mi; **FYI** otherwise. A disappearance (not an explicit closure) is one level lower. | New Overture release | Expires from "active" after 90 days; stays in history | "Possible closure; verify. A nearby anchor or traffic driver closing can reduce shopping trips (co-tenancy)." For a tenant match: "Data suggests your tenant's location may have closed; confirm with the tenant." |
| SIG-10 | New nearby key business | A new GERS ID in a key category within 3 mi, confidence ≥ 0.8, not closed | FYI | New Overture release | Expires after 90 days | "Newly appears in map data (may be a new opening or a data addition); possible competitor or traffic driver." |
| SIG-11 | Flood exposure | At pin: SFHA (zones A*, V*) → **High**. Within 100 m only → **Watch**. Zone at pin changed since the last check → **High**. | High / Watch | Location created or pin moved; monthly recheck for monitored locations | When the condition no longer holds | "Special Flood Hazard Areas usually require flood insurance for financed properties and carry higher physical risk. Screening only, not a flood determination." |
| SIG-12 | Tenant bankruptcy filing | A mapped tenant's filer submits an 8-K with **Item 1.03** filed within the last 90 days | **High** | Daily SEC check | Expires after 90 days; stays in tenant history | "The parent company of a tenant at this property reported a bankruptcy or receivership. Store closures and lease rejections are possible. This location may or may not be affected." |
| SIG-13 | Tenant restructuring or impairment | 8-K **Item 2.05** or **2.06** within 90 days | Watch | Daily SEC check | Expires after 90 days | "The company reported exit or disposal costs or impairments, which often accompany store closures. Company-level; check whether this location is affected." |

Optional P1 rule: **SIG-14**, an 8-K, 10-Q or 10-K for a mapped filer containing "store closure(s)" (EDGAR full-text search) within 90 days → FYI.

### 5.3 Guards against false signals
1. **Overture artifact guard:** if, in one release, ≥ 30% of monitored locations show a > 15% change in their 1-mile place count in the same direction, the release is flagged **"broad data change."** SIG-10 is suppressed for that release, SIG-09 is capped at FYI, and the Data Sources page notes the event.
2. Ignore `null → open` status changes. These are enrichment, not real-world change (observed in verification).
3. GERS ID changes: if Overture publishes ID bridge or changelog files for a release, use them to avoid counting a re-identified place as closed plus new.
4. **Preliminary data:** LAUS preliminary values carry "(P)". SIG-05 is re-evaluated when revisions arrive and is resolved if the revision falls below the threshold.
5. **Suppressed or very-low-reliability inputs never trigger a signal.**
6. **Pin moved:** recompute all location-based signals. Signals that existed only because of the old pin resolve with the reason "location corrected."

### 5.4 Brief composition and ranking
- **Included:** signals on **Owned** locations that are new since the previous brief, or whose severity increased, plus all still-active High signals (marked "still active").
- **Order:** severity (High, Watch, FYI) → category priority (Tenant, Closure near property, Hazard, Economy, Housing, Demographics, Traffic) → newest detection → property name.
- **Layout:** High and Watch shown in full. FYI collapsed behind a count ("6 other updates").
- **Each item:** property name and city, one-line "what changed" with the key numbers and period, the "why it matters" text, data period, and a link to the evidence.
- **"Sources updated since last brief":** each source whose data period advanced, with old and new periods.
- **Empty state:** "No material changes this week across N properties" plus the sources-updated list. This is a valid, honest outcome. Most public data updates monthly to annually.

### 5.5 Lifecycle and first run
- A signal key is `(rule_id, location_id, subject)`, where the subject is e.g. the GERS ID, CIK plus accession number, or data period. Re-detecting the same key updates the existing signal rather than creating a duplicate.
- States: **Active → Resolved** (condition cleared) or **Expired** (event signals after 90 days). P1 adds **Reviewed** and **Dismissed** (FR-23).
- **First run (baseline):** at launch, evaluate every rule against the history available: ACS 2015–19 vs 2020–24; latest QCEW quarter vs the same quarter a year earlier; LAUS latest vs a year earlier; LODES latest year vs the prior year; BPS last 24 months; HPMS latest vs prior year, if the prior-year service exists; Overture the previous release vs the latest; SEC the last 90 days. The first brief is titled **"Baseline: current conditions"** so nobody mistakes these for brand-new changes.
- **Time-sensitive:** Overture keeps only about two prior releases (doc 03 SRC-13). Snapshot the currently available releases **at the start of implementation** so the Sep→Oct 2026 diff fixture (AC-10) and a first-run baseline exist.

## 6. Explainability

### 6.1 Evidence view (every value, signal and summary item)
| Field | Example |
|---|---|
| What it is | "Mean household income: total household income ÷ households" |
| Value and uncertainty | "$142,300 ± $9,800 (Reliability: High)" |
| Geography and method | "3-mile ring around pin (41.1266, −73.3883); 62 block groups, block-population-weighted (2020 Census)" |
| Source | "U.S. Census Bureau, ACS 5-year, tables B19025 and B11001" + link |
| Data period | "2020–2024" |
| Last checked | "Nov 17, 2026" |
| Comparison | "Higher than 78% of your 31 properties (3-mi ring)" |
| Caveats | "Survey estimate. Describes the area, not this property." |
| For signals | Rule text, threshold, input values and periods, detection date, status, links to source records (SEC filing URL, Overture place on the map with GERS ID) |

### 6.2 Inspecting supporting records
- Nearby businesses: clicking a map point shows name, brand, category, status, confidence, Overture release and GERS ID.
- SEC: link to the filing index and primary document.
- Flood: zone, DFIRM ID, and a link to the FEMA Map Service Center for an official FIRMette.
- Rings: an optional overlay showing the block groups that contributed.

### 6.3 Evidence summary rules (FR-26)
Computed on the 3-mile ring against non-archived Owned locations (n ≥ 5):
- **Strength:** a directional metric (MET-01, 02, 03, 04, 06, 07, 08, 14, and the YoY forms of MET-10, 11 and 13) with a portfolio percentile **≥ 75**, or ≤ 25 for ↓ metrics (MET-12). It must not be Very low reliability, and MET-06 and MET-07 must be statistically significant.
- **Concern:** percentile **≤ 25** (≥ 75 for ↓ metrics), same conditions. Also: SFHA at the pin or within 100 m (SIG-11); NRI overall "Relatively High" or "Very High"; any active High or Watch signal.
- **Ordering:** hazards and High signals first, then by distance of the percentile from 50. Maximum 5 of each.
- **Wording:** a factual template, e.g. "3-mile population: 84,055, higher than 81% of your properties (ACS 2020–24)." Never "good investment" or "buy."
- If n < 5: show only hazard- and signal-based items, plus "Portfolio benchmark needs at least 5 confirmed properties."

## 7. Missing, stale, contradictory and inaccessible data

| Code | When | UI text (example) | Behaviour |
|---|---|---|---|
| `NOT_COVERED` | The source has no data for the area (no digital flood map, no HPMS segment within 250 m, LODES state-year missing) | "No federal traffic count within 250 m of this site." | No value; excluded from comparisons and percentiles |
| `SUPPRESSED` | BLS disclosure `N`; ACS suppressed cell | "Not disclosed by BLS (confidentiality)." | No value; never 0 |
| `LOW_RELIABILITY` | ACS CV > 40% | Value greyed plus "Very low reliability" | Shown; excluded from signals and highlights |
| `SAME_COUNT` | The two HPMS years rest on the same traffic count (`aadt_vd`): the state estimated the newer year | "No new count: the state carried the last count forward." | Current value shown; no year-over-year change; SIG-08 does not fire |
| `GEOGRAPHY_CHANGED` | Prior period unavailable for the same geography (CT), or the segment changed | "Trend unavailable: Connecticut moved to planning regions in 2022." | Current value shown; no trend |
| `NOT_ENOUGH_DATA` | Percentile with n < 5; jobs trend under 1,000 | "Needs at least 5 confirmed properties to benchmark." | No percentile |
| `CACHED_AFTER_ERROR` | Latest refresh failed; earlier data exists | Badge "Stale: last updated Nov 2 (source unavailable since Nov 14)" | Last good value shown with its date |
| `SOURCE_ERROR` | Failed with nothing cached | "Flood data temporarily unavailable. We'll retry automatically." | No value; retried by the job |
| `STALE` | Last successful check older than the source's stale threshold (§9) | Amber "Stale" badge with dates | Value shown |
| `NOT_PROVIDED` | User input missing (GLA, tenants) | "No tenants entered. Add tenants to enable tenant watch." | Prompts an action |
| `NOT_APPLICABLE` | e.g. tenants for a candidate | Hidden or "n/a" | n/a |
| `LOADING` | Progressive load | Skeleton plus "Loading traffic data…" | Times out into `SOURCE_ERROR` |

**Contradictions.** Show both values with their sources. Never average or silently pick one.
- An Overture closure for a brand the user lists as a tenant here → SIG-09 High "verify" (tenants know best; P1 lets the user dismiss with "verified open").
- A user-provided traffic count next to HPMS → both shown, each labelled.
- A public listing's tenant list next to Overture (e.g. a listed tenant not found nearby) → the Tenants section shows "Not found in map data near the site; confirm tenant" as an FYI note, not a signal.
- A source revision changes a value (LAUS, QCEW): show the latest value. Signal evidence keeps the value used at detection time, marked "since revised to X."

## 8. Presentation guardrails (also in doc 05 §6)
- Label each value's nature: **Estimate** (ACS), **Reported** (BLS, BPS, SEC, FEMA), **Modelled** (NRI), **Map data** (Overture), **User-provided**, **Possible** (signals from map data).
- Never use property-level words for area data: no "vacancy," "occupancy," "rent," "NOI" or "value" derived from external data.
- Never present a correlation as a cause ("population fell, so sales will fall"). Use "can," "may," "often" in "why it matters" text.
- Absolutely no generated or placeholder numbers in production, including on empty states, in screenshots or in onboarding.

## 9. Freshness model and quality checks

### 9.1 Two dates on every section
**Data period** (what time the data describes) and **Last checked** (when the system last confirmed it has the latest available).

| Source | Check schedule | Stale if last successful check older than |
|---|---|---|
| SRC-14 SEC | Daily | 3 days |
| SRC-13 Overture | Weekly check for a new release; process within 7 days of publication | 21 days, or a new release unprocessed for > 14 days |
| SRC-07 LAUS · SRC-09 BPS | Weekly check | 21 days |
| SRC-06 QCEW | Weekly check | 21 days |
| SRC-03 ACS · SRC-05 LODES · SRC-10 HPMS · SRC-12 NRI · SRC-08 CPI | Monthly check for new vintages | 45 days |
| SRC-11 NFHL | On demand, plus monthly recheck of monitored locations | 45 days |
| SRC-01/02 Geocoders | On demand | n/a |

### 9.2 Ingestion quality checks (each job)
1. Schema check: expected fields are present. Fail closed, keeping the previous data, if they are missing.
2. Record count within ±20% of the previous load of the same type; otherwise warn in the run log.
3. Range checks: unemployment 0–40%; AADT 0–400,000; population ≥ 0; percentages 0–100.
4. Geography validity: GEOIDs have the right length and exist in the reference geography; CT code handling per §3.4.
5. Reference checks: the regression values in doc 03 §5 (marked "Yes") run in the test suite against fixtures, and periodically against live sources with tolerances.
6. Idempotency: re-running a job for the same period yields the same stored result.
