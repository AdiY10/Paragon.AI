# 02 · Product Requirements: Release 1

**Working name:** *Paragon Radar*. The implementing agent may rename it.
**One-line summary:** a private web app that keeps a **current, sourced picture of the trade area around every Paragon property and every acquisition candidate**, flags **meaningful changes each week**, and lets John **compare locations against his own portfolio**, with the evidence one click away.

Related: research and assumptions in [01](01_RESEARCH_AND_DISCOVERY.md) · sources in [03](03_DATA_SOURCES.md) · metric and signal definitions in [04](04_DATA_AND_INSIGHT_REQUIREMENTS.md) · experience in [05](05_EXPERIENCE_REQUIREMENTS.md) · engineering in [06](06_ENGINEERING_AND_OPERATIONS.md) · delivery in [07](07_DELIVERY_AND_VERIFICATION.md).

---

## 1. Problem

Paragon owns about 2 million SF, mostly neighborhood and community shopping centers spread over 12 states, and keeps evaluating new acquisitions. The external evidence it uses today to describe a location is **static and dated**: listing demographics are Esri 2021 figures, traffic counts are years old, and tenant lists are not maintained (doc 01, F9 and F12). Nobody systematically watches the neighborhoods around 30+ properties. When a deal arrives, a first-pass read on the location takes manual work and is not benchmarked against what Paragon already owns. As a result:

- Changes that affect tenant demand or vacancy risk, such as an anchor's parent filing for bankruptcy, a nearby theater or grocer closing, or local jobs falling, can be noticed late.
- Acquisition locations are compared inconsistently and without a portfolio baseline.
- Evidence is hard to trace back to a source and date, which makes it hard to trust or forward.

## 2. Target users

- **Primary: John Nelson, Founder and CEO.** Time-poor, experienced and sceptical of black boxes. Wants "what changed, why it matters, and the proof." (A-01)
- **Secondary: Adam Nelson, Principal, Acquisitions,** plus other principals. Run screens and comparisons and keep the portfolio and tenant lists accurate. (A-02)

## 3. Jobs to be done

| ID | When… | I want to… | So that… |
|---|---|---|---|
| JTBD-1 | It's Monday morning | see the few changes around my properties that could affect tenant demand, vacancy risk or attractiveness | I can act early (call a tenant, adjust leasing, investigate) |
| JTBD-2 | A broker sends a deal | get a credible first-pass read on the location in minutes, benchmarked against my portfolio | I can decide whether it deserves underwriting time |
| JTBD-3 | I'm weighing locations | compare them side by side on the same measures | I can see which is stronger and why |
| JTBD-4 | Something is flagged | see the underlying evidence, source and date | I can trust it, verify it and forward it |
| JTBD-5 | A national tenant hits trouble | know right away which of my properties it occupies | I can assess exposure |

## 4. Intended outcomes

1. **Earlier awareness:** material external changes reach John within a week of the data being published (within a day for SEC filings).
2. **Faster screening:** a first-pass location read with a portfolio benchmark in **under 5 minutes** of user time.
3. **Consistent comparison:** every location measured the same way, with a stated method.
4. **Trust:** every number shows its source, period and uncertainty, and nothing is fabricated.

## 5. Release 1 scope (prioritized)

**P0** = required for "ready for Adi to test" (doc 07 §6). **P1** = should-have; build after every P0 item works, and leave it out if time or blockers require.

| Capability | Priority | Workflows |
|---|---|---|
| C1 Secure, invite-only access | P0 | all |
| C2 Portfolio and location management (seeded from the public website, confirm or edit, add by address, pin correction, tenant roster) | P0 | W1–W5 |
| C3 Trade-area profile for any US location (rings, economy, retail landscape, access, hazards, tenants) with evidence | P0 | W1, W3 |
| C4 Change signals and property attention level | P0 | W2 |
| C5 "This Week" brief (in app), with archive | P0 | W2 |
| C6 Tenant watch (SEC filings for public-company tenants) | P0 | W5 |
| C7 Acquisition screen with evidence summary (strengths and concerns vs portfolio) | P0 | W3 |
| C8 Side-by-side comparison (2–4 locations plus portfolio benchmark) | P0 | W4 |
| C9 Data sources and freshness transparency | P0 | all |
| C10 Mark signals reviewed or dismissed | P1 | W2 |
| C11 Weekly brief by email | P1 | W2 |
| C12 Print/PDF view and CSV export | P1 | W3, W4 |
| C13 FEMA flood overlay on the map | P1 | W1, W3 |
| C14 "Was this useful?" feedback | P1 | measurement |

## 6. Explicit exclusions (Release 1)

These are **out of scope**. The product must not imply that it does them.

1. Market rents, asking rents, comps, availability, submarket vacancy or absorption (no permitted free source; doc 03 §3).
2. Property listings or deal sourcing; any scraping of CoStar, LoopNet, Crexi or similar sites.
3. Property financials: rent rolls, NOI, leases, tenant sales, underwriting, valuation, cap rates, pro formas.
4. Property-level occupancy or vacancy calculated from external data. Only user-entered facts may describe the property itself.
5. Foot traffic, mobile location data, consumer spending.
6. Drive-time or custom-drawn trade areas (rings only).
7. Zoning, entitlements, commercial permits, news monitoring.
8. Credit ratings or financial analysis of tenants beyond SEC filing events.
9. Composite "investment scores," buy/sell recommendations, forecasts or AI-generated predictions.
10. A generative-AI chat assistant or AI-written numbers. Any optional AI-written prose is out of scope for Release 1 (doc 04 §8).
11. Native mobile apps (responsive web only), offline mode, multi-company tenancy, public sharing links.
12. Connecticut-only enrichments (sale comps, parcels); deferred to Release 1.1.

## 7. User journeys

### J1 · Monday brief (John, about 3 minutes)
1. John opens the app on Monday and lands on **This Week**.
2. The header reads, for example: "3 items need attention across 3 properties · 2 data sources updated this week."
3. The top card says: *"Tenant watch: the parent company of [anchor tenant] at [property] filed an 8-K reporting bankruptcy (Item 1.03) on [date]."* (Illustrative. The real historical equivalent in today's data is Rite Aid at Southside Shopping Center, which filed on 2023-10-16. That is too old to count as "new," so it shows as a past event on the property's Tenants section.)
4. He opens the evidence drawer: the rule that fired, the filing date, a link to the SEC filing, and which of his properties list this tenant.
5. He opens the second card: "Possible closure nearby: Regal Cinemas Hudson Valley Mall 12, 0.4 mi from Kingston Marketplace, marked permanently closed in Overture Maps (Oct 2026 release); verify." (Distance illustrative.)
6. (P1) He marks both reviewed and adds a note.

### J2 · Screen a deal (Adam or John, under 5 minutes)
1. A broker sends an offering memo. The user clicks **Screen a location** and types the address.
2. The geocoded pin appears with match quality. If the match is ambiguous, the user confirms or drags the pin.
3. The core trade-area metrics appear within the performance target (doc 06 §5); retail landscape and hazards finish loading progressively.
4. The **Evidence summary** lists strengths and concerns, each benchmarked: e.g. "3-mile mean household income $118k: higher than 78% of your owned properties (ACS 2020–2024)" and "Concern: pin is in FEMA zone AE (Special Flood Hazard Area)."
5. The user clicks **Save as candidate**, then **Compare** with two other candidates and the portfolio median.
6. (P1) The user prints or saves a PDF of the comparison for John.

### J3 · Investigate an owned property
From the **Portfolio** map, the user selects a property and reviews its profile sections, active signals and history, then opens the evidence for any value.

### J4 · First-run setup (admin)
1. The admin signs in and sees 36 properties marked **Unconfirmed: from public website**.
2. The admin confirms, archives or edits each one. Two properties need a pin (no geocoder match or a tie).
3. The admin reviews the seeded tenant lists, marks anchors, and maps public-company tenants to SEC filers.
4. The admin sets the ring preset per property (1/3/5 or 3/5/10).

### J5 · Check data trust
A section shows a **Stale** badge. The user opens **Data Sources** and sees, for example, "FEMA flood service failing since Nov 14; showing results cached on Nov 2." The user knows exactly how far to rely on the data.

## 8. Functional requirements

| ID | Pri | Requirement |
|---|---|---|
| **Access** | | |
| FR-01 | P0 | Only invited, signed-in users can see any page, API response or data. Sign-in uses a standard, secure method (doc 06 §1). |
| FR-02 | P0 | Admins can invite and remove users and assign the **Admin** or **Member** role. Members can do everything except manage users and system settings. |
| **Locations and portfolio** | | |
| FR-03 | P0 | Each location has a status of **Owned**, **Candidate** or **Archived**. Owned and Candidate locations are monitored by scheduled jobs. Unsaved screens are not monitored. |
| FR-04 | P0 | On first deploy, the 36 properties in `data/seed/paragon_public_properties.csv` are imported as Owned, flagged **Unconfirmed**, with the source URL. Users can confirm, edit or archive each one. The listing's demographic and traffic figures are **not** imported as data. |
| FR-05 | P0 | Adding a location by address geocodes it with SRC-01, then SRC-02 on failure, then asks for a manual pin. The match quality is shown (exact, non-exact, fallback or manual). The user can drag the pin at any time; moving it recomputes all location-dependent results. |
| FR-06 | P0 | Editable attributes: name, address, asset type (retail center, single-tenant retail, office, mixed-use, other), ring preset (1/3/5 mi or 3/5/10 mi), GLA (optional, labelled user-provided), notes. |
| FR-07 | P0 | A tenant roster per owned location: tenant or brand name, anchor flag, confirmed flag, source (public listing or user), and an optional SEC filer mapping (FR-22). |
| FR-35 | P0 | A portfolio overview with a map and list of locations: attention level, key metrics (3-mi population, 3-mi mean HH income, population trend), confirmed status, and filters by state, asset type, attention level and status. |
| FR-36 | P0 | Global search jumps to an existing location by name or address, or starts a screen for a new address. |
| **Trade-area profile** | | |
| FR-08 | P0 | Every location has a profile with these sections in this order: **Summary** (attention level, active signals, evidence summary) · **Trade area** · **Economy and jobs** · **Retail landscape** · **Access and traffic** · **Hazards** · **Tenants** (owned only) · **Sources**. |
| FR-09 | P0 | Trade area shows MET-01 to MET-07 for each ring of the location's preset, with uncertainty (MOE or reliability) and trend where defined. |
| FR-10 | P0 | Jobs located in each ring (MET-08) and the year-over-year change (MET-09). |
| FR-11 | P0 | County private employment and retail employment with YoY change (MET-10, MET-11) and the unemployment rate with YoY change (MET-12), each showing the county or planning-region name and period. |
| FR-12 | P0 | Residential units authorized, trailing 12 months versus the prior 12 months, for the county and, where available, the permit-issuing place (MET-13). |
| FR-13 | P0 | Traffic: AADT of up to two nearby segments, with road name and data year (MET-14). |
| FR-14 | P0 | Retail landscape: a map of nearby businesses by category group within the location's middle ring, capped at 3 miles; counts by category group within 1 mi and 3 mi; key brands and anchors with distances (MET-15, MET-16); and changes between the stored monthly snapshots. |
| FR-15 | P0 | Hazards: FEMA flood zone at the pin and within ~100 m (MET-17), and NRI tract ratings (MET-18), each with the standard disclaimer. |
| FR-16 | P0 | For comparable metrics, show where the location ranks against owned properties (MET-20), e.g. "higher than 78% of your portfolio." |
| FR-17 | P0 | Every displayed value, signal and summary statement opens an **evidence view** with: definition, formula or method, source name and link, data period, last checked date, geography used, uncertainty and caveats (doc 04 §6). |
| FR-18 | P0 | A missing, suppressed, stale, failed or not-applicable value is shown as such, with the reason code and explanation from doc 04 §7. It is never shown as zero, blank or an invented value. |
| **Signals, brief, tenant watch** | | |
| FR-19 | P0 | A deterministic signal engine evaluates the rules SIG-01 to SIG-13 (doc 04 §5) after each relevant data refresh. It creates, updates and resolves signals, storing the evidence (inputs, thresholds, periods, links) for each. |
| FR-20 | P0 | Each location shows an attention level (**High**, **Watch** or **Clear**) equal to the highest severity among its active signals. |
| FR-21 | P0 | The **This Week** brief is generated every Monday at 07:00 US Eastern and on demand by an admin. It contains: signals that are new or changed in severity since the previous brief, ranked per doc 04 §5.4; still-active High signals; sources updated since the previous brief; and an explicit "No material changes" state. Past briefs remain viewable. |
| FR-22 | P0 | Tenant watch: a daily SEC EDGAR check for every tenant mapped to an SEC filer. Admins map a tenant to a filer by searching company name or ticker; the seed suggests mappings for listed national brands, which an admin must confirm. Signals SIG-12 and SIG-13 apply to every property where that tenant is listed. |
| FR-23 | P1 | Users can mark a signal **Reviewed** (with an optional note) or **Dismissed** (with a reason). Reviewed and dismissed signals do not reappear as "new" unless their severity increases. |
| FR-24 | P1 | Opted-in users receive the weekly brief by email: titles and severities only, linking into the app (sign-in required). |
| **Acquisition screen and comparison** | | |
| FR-25 | P0 | **Screen a location:** any US address or a map click produces a full profile without saving. Results load progressively within the targets in doc 06 §5. **Save as candidate** keeps it and starts monitoring. |
| FR-26 | P0 | **Evidence summary** on every profile: up to 5 strengths and 5 concerns generated by the deterministic rules in doc 04 §6.3. Each item links to its evidence. Where no rule applies, show "No notable strengths or concerns by the standard rules." |
| FR-27 | P0 | **Compare** 2–4 locations (owned, candidate or unsaved screen) using the same ring set, plus **portfolio median** and **portfolio range** columns. Better or worse highlighting applies only to metrics with a defined direction (doc 04 §4). Every cell opens its evidence. |
| FR-28 | P1 | A print or PDF-friendly layout for a profile and a comparison, including sources and data periods. |
| FR-29 | P1 | CSV export of a comparison, including source and period columns. |
| **Transparency and operations** | | |
| FR-30 | P0 | A **Data Sources** page listing, per source: purpose, coverage, licence and attribution, data period, last successful check, next expected update and status (OK, Stale or Failing). |
| FR-31 | P0 | Each profile section shows its data period and last-checked date. Stale or failing data shows a visible badge, and the page shows a banner if any source used on it is failing. |
| FR-32 | P0 | Scheduled refresh jobs run per doc 06 §4. Admins can see a run log (start, end, status, records, errors) and trigger a manual re-run. |
| FR-33 | P0 | Required attributions (OpenStreetMap for Nominatim results, Overture, map tiles, federal sources) are displayed where the data is shown and on the Data Sources page. |
| FR-34 | P1 | A "Was this useful?" control on signals and briefs, recorded per user for success measurement. |
| FR-37 | P1 | FEMA flood hazard overlay on the profile map. |

## 9. Acceptance criteria

All criteria are tested on the **deployed** application with real data unless a criterion says "fixture." The test suite (doc 07 §5) automates every criterion that can be automated.

| AC | FR | Given / When / Then |
|---|---|---|
| AC-01 | FR-01 | Given a visitor who is not signed in, when they request any app page or data endpoint, they are redirected to sign-in or receive 401, and no portfolio data is returned. |
| AC-02 | FR-02 | Given an admin, when they invite a new email address, that person can sign in and has the Member role. When the admin removes them, their next request is denied. |
| AC-03 | FR-04 | Given a fresh deployment, the portfolio shows 36 locations flagged "Unconfirmed," each with its paragonct.com source link. No location shows Esri 2021 numbers. |
| AC-04 | FR-05 | Given the address "444 Westport Avenue, Norwalk, CT", the pin lands within 50 m of (41.12661, −73.38830) and shows "Exact match (US Census)." Given "1200 Ulster Avenue, Kingston, NY", the app uses the fallback or asks for a pin and labels the method. |
| AC-05 | FR-05 | Given a location, when the user drags the pin about 500 m and saves, the trade-area metrics, flood result and nearby businesses are recalculated, and the evidence shows the new coordinates. |
| AC-06 | FR-09 | Given 444 Westport Ave with 1/3/5 rings, the 1-mile population is within ±10% of 11,500 and the 3-mile population within ±10% of 84,000 (reference values, doc 03 V5 and V6), each with an MOE and the period "ACS 2020–2024." |
| AC-07 | FR-09 | Population change and real mean-income change are shown only as comparisons between non-overlapping 5-year periods (2015–2019 vs 2020–2024), with significance labelled per doc 04 §4. |
| AC-08 | FR-11 | Given Kingston Marketplace, the economy section shows Ulster County, NY private employment for the latest QCEW quarter with YoY %, and the latest LAUS unemployment rate marked "(preliminary)" where applicable. Given any CT property, the county shown is a **planning region** (e.g. "Western Connecticut Planning Region"). |
| AC-09 | FR-13 | Given Kingston Marketplace, the traffic section shows "Ulster Ave (US 9W)" with AADT 22,523 (2024) or a newer HPMS year if one has been released. |
| AC-10 | FR-14 | Given Kingston Marketplace, the retail landscape shows more than 300 businesses within 1 mile, category counts, and at least 5 recognized brands with distances. The Sep→Oct 2026 snapshot diff (fixture) lists Regal Cinemas Hudson Valley Mall 12 as a possible closure. |
| AC-11 | FR-15 | Given Cypress Lake Shopping Center (pin at the geocoded point), the hazards section shows "FEMA zone AE: Special Flood Hazard Area, BFE 9 ft" with the disclaimer, and SIG-11 is active at **High**. |
| AC-12 | FR-16 | Given at least 5 confirmed owned locations, each comparable metric on a profile shows a portfolio percentile. A test fixture with known values produces the expected percentiles. |
| AC-13 | FR-17 | For a random sample of 20 displayed values across 3 profiles, each opens an evidence view with all fields listed in FR-17 populated, and each source link resolves. |
| AC-14 | FR-18 | Given a QCEW cell with `disclosure_code = N` (fixture), the UI shows "Not disclosed by BLS," not 0. Given a location with no HPMS segment within 250 m, the UI shows "No federal traffic count within 250 m." |
| AC-15 | FR-19, FR-20 | For each signal rule SIG-01 to SIG-13, a fixture that meets the rule creates the signal with the right severity and evidence; a fixture just below the threshold does not; and when the condition clears, the signal is resolved. The attention level equals the highest active severity. |
| AC-16 | FR-21 | Given new signals since the last brief, the generated brief lists them in rank order with the location, what changed, why it matters and an evidence link. Given none, it shows "No material changes this week" and still lists the sources updated. The previous brief remains viewable. |
| AC-17 | FR-22 | Given the tenant "Rite Aid" at Southside Shopping Center mapped to CIK 84129, the Tenants section lists the 2023-10-16 8-K (Item 1.03) as a **past event** with a link to the filing and a "Confirm this tenant is still in place" prompt. Given a fixture 8-K with Item 1.03 dated within the last 90 days for a mapped tenant, a SIG-12 **High** signal is created for every property listing that tenant. |
| AC-18 | FR-25 | Given a new US address not in the portfolio, the screen shows the core trade-area metrics within the target time and the rest progressively, without saving. "Save as candidate" adds it to monitoring. |
| AC-19 | FR-26 | Given a location whose 3-mi mean HH income is above the portfolio's 75th percentile (fixture), a strength appears citing the percentile and source. Given a location in an SFHA, a concern appears. |
| AC-20 | FR-27 | Given 3 locations, the comparison shows them with the portfolio median and range using the same ring set. Only directional metrics are highlighted. Each cell opens its evidence. |
| AC-21 | FR-30, FR-31 | The Data Sources page lists SRC-01 to SRC-14 with period, last check and status. If a source job is made to fail (fault injection), its status becomes Failing, affected sections show a badge, and the last good values remain visible with their dates. |
| AC-22 | FR-32 | An admin sees each job's last run and can trigger a re-run, which completes and updates "last checked." |
| AC-23 | FR-33 | Map views show the tile and Overture attribution. Any Nominatim-derived pin shows "© OpenStreetMap contributors" in its evidence. |
| AC-24 | FR-35, FR-36 | The portfolio map shows every non-archived location with its attention level. Filters change the list and map together. Search finds a location by partial name. |
| AC-25 | all | No page shows a number without a source and period available in the evidence view, and none shows a value that did not come from a source in doc 03 or from user input. Verified by an automated check over the rendered data model plus a manual audit (doc 07 §5). |

P1 items, if built, get their own ACs written by the implementing agent in the same style.

## 10. Success measures

| Measure | Target | How measured |
|---|---|---|
| Delivery | All P0 acceptance criteria pass on the deployed URL; Adi's checklist (doc 08) passes | Test report plus Adi |
| Weekly engagement | John opens the brief in ≥ 6 of the first 8 weeks after onboarding | Brief view events (first-party, no third-party analytics) |
| Screening use | ≥ 4 screens or comparisons per month (assumption; calibrate with Q-03 and Q-08) | Usage events |
| Usefulness | ≥ 50% of High and Watch signals rated useful (if FR-34 is built), or at least one decision or action informed by the product in the first 8 weeks (interview) | Feedback plus interview |
| Speed | Median screen-to-evidence-summary ≤ 60 s system time; ≤ 5 min user task | Timing logs; observed session |
| Trust | 0 unsourced or fabricated values; ≥ 95% of days with all sources within their freshness window | Audit plus job log |

## 11. Assumptions requiring validation

The key assumptions are A-01 (primary user and loops), A-05 and A-06 (portfolio and tenants from the public site), A-07 (rings are enough), A-08 (Monday cadence), A-09 (free data only) and A-11 (thresholds). All are listed with their effects in doc 01 §4, with open questions in doc 01 §5. None blocks building Release 1.
