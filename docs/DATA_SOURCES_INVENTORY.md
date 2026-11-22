# Data sources inventory (2026-11-21)

What Paragon Radar uses today, exactly what each source can provide, what we take from it, how
we get it and how fresh it is; then the sources we could add. Written as the input to the
website redesign. "In the app now" reflects the 35-property preview data on 2026-11-21.

**Legend:** *Type*: API (live request per query), Bulk file (downloaded files), Map service
(ArcGIS REST query), Cloud dataset (files queried in place). *Provider updates*: how often the
publisher releases new data. *Our refresh*: when Paragon Radar checks (Eastern time).

---

## Part 1. Sources in use today (16)

### Summary

| # | Source | Provider | Type | Provider updates | Our refresh | Latest data in the app | Cost |
|---|---|---|---|---|---|---|---|
| SRC-01 | Census Geocoder | Census Bureau | API | Address ranges updated continuously | On demand (Screen, "Find from address") | Current | Free |
| SRC-02 | Nominatim (OpenStreetMap) | OSM Foundation | API | Continuous | **Not used** (catalogued fallback only) | n/a | Free, strict limits |
| SRC-03 | American Community Survey 5-year | Census Bureau | Bulk file | Yearly (December) | Checked monthly (1st, 04:00) | ACS 2020–2024 and 2015–2019 | Free |
| SRC-04 | TIGERweb geography | Census Bureau | Map service | Census blocks fixed per decade; counties yearly | On demand per pin, cached | 2020 and 2010 blocks; 2024 counties | Free |
| SRC-05 | LODES workplace jobs | Census Bureau | Bulk file | Yearly, about 2 years behind | Checked monthly | 2024 vs 2023 | Free |
| SRC-06 | QCEW employment | Bureau of Labor Statistics | Bulk file (CSV) | Quarterly, about 5–6 months behind | Weekly (Mon 05:00) | 2026 Q1 | Free |
| SRC-07 | LAUS unemployment | Bureau of Labor Statistics | API | Monthly, about 1 month behind | Weekly (Mon 05:00) | Sep 2026 (preliminary) | Free (25 queries/day without key) |
| SRC-08 | CPI-U inflation | Bureau of Labor Statistics | API | Monthly; annual averages each January | When incomes are compared | 2019 and 2024 averages | Free |
| SRC-09 | Building Permits Survey | Census Bureau | Bulk file (text) | Monthly | Weekly (Mon 05:00) | Year to date Sep 2026 | Free |
| SRC-10 | HPMS road traffic | FHWA / USDOT | Map service | Yearly, about 1–2 years behind | Checked monthly | HPMS 2025 vs 2024 | Free |
| SRC-11 | National Flood Hazard Layer | FEMA | Map service | Continuously as flood-map revisions take effect | Monthly (15th, 04:00) | Current effective maps | Free |
| SRC-12 | National Risk Index | FEMA | Map service | About yearly | Cached 90 days | December 2025 release | Free |
| SRC-13 | Overture Places | Overture Maps Foundation | Cloud dataset (GeoParquet on AWS S3) | Monthly releases; old ones deleted after ~2 months | Weekly (Thu 03:00) | Sep, Oct, Nov 2026 releases | Free |
| SRC-14 | SEC EDGAR | Securities and Exchange Commission | API | Continuously (filings within minutes) | Daily (06:00) | Through 2026-11-19 | Free (needs contact email) |
| SRC-15 | User-provided facts | Paragon team | In-app entry | Whenever edited | Immediate | Live | n/a |
| SRC-16 | Paragon public listings | Paragon Realty Group website | One-time import | Website changes occasionally | One time (seed) | 36 properties, 60+ tenants | n/a |

Not in the catalog but used for display: **OpenStreetMap map tiles** (the map background),
loaded by the viewer's browser from tile.openstreetmap.org; free under OSM's tile policy.

---

### SRC-01 Census Geocoder
- **What it is:** the Census Bureau's address-to-coordinates service.
- **Access:** API, `geocoding.geo.census.gov` (one address per request), JSON. No key.
- **What it can give:** matched address, latitude/longitude, match quality (exact / non-exact),
  and the census geographies at that point (state, county, tract, block).
- **What we use:** coordinates and match quality to place a pin; the user reviews and confirms
  every match ("Find from address", Screen).
- **Caveats:** interpolated along street ranges, so pins can sit on the street, not the building;
  no business names. Addresses are sent only when a user asks for a lookup.

### SRC-02 Nominatim (OpenStreetMap)
- **Status: catalogued but not implemented.** Policy allows 1 request/second, no bulk, no
  autocomplete. Kept as a possible fallback when the Census Geocoder finds nothing.

### SRC-03 American Community Survey (ACS) 5-year estimates
- **What it is:** the Census Bureau's survey of households, published as 5-year averages down to
  block groups (a few hundred households each).
- **Access:** bulk summary files from `www2.census.gov` (2024: one national file per table;
  2015–2019: per-state "sequence" zip files read with partial downloads). No key.
- **What it can give:** thousands of tables: population, age, race/ethnicity, households and
  families, income distribution and median/mean income, poverty, education, employment and
  occupation, commute mode and time, vehicles, housing units, tenure, home values, rents,
  vacancy, year built, language, disability, internet access, and more; each with a margin of error.
- **What we use (5 tables):**
  - B01003 total population → *People within 1/3/5 miles*.
  - B11001 households → *Households*.
  - B19001 income brackets → *Median household income*.
  - B19025 aggregate income → *Average household income*.
  - B15003 education → *Share with a bachelor's degree or higher*.
- **How:** each ring (1/3/5 mi, or 3/5/10) is built from 2020 census blocks weighted by
  population, then block-group values are apportioned with margins of error.
- **Trends:** 2015–19 vs 2020–24 population and inflation-adjusted average income, flagged only
  when statistically significant (90%).
- **Where it shows:** Trade area panel, property key facts, portfolio percentiles, alerts
  SIG-01 (population) and SIG-02 (real income).
- **Freshness:** a new 5-year vintage every December (2021–2025 due December 2026; the app
  switches all properties together once every needed state is in). Estimates are averages
  over five years, so they move slowly.

### SRC-04 TIGERweb geography
- **What it is:** the Census Bureau's online geography service.
- **Access:** map service (ArcGIS REST) at `tigerweb.geo.census.gov`. No key.
- **What it can give:** boundaries and codes for states, counties, tracts, block groups and
  blocks, places, ZIP-code areas (ZCTAs), school districts, and more; 2010 and 2020 block
  populations.
- **What we use:** 2020 and 2010 census blocks (population and location) around each pin to
  weight the rings; the county (or Connecticut planning region) for each pin; ACS block-group
  codes.
- **Freshness:** block populations change once a decade; cached per pin.

### SRC-05 LODES workplace jobs
- **What it is:** the Census Bureau's count of jobs by workplace census block (from
  unemployment-insurance records).
- **Access:** bulk files, one gzipped CSV per state and year (`lehd.ces.census.gov`). No key.
- **What it can give:** jobs located in each block by industry (20 sectors), worker age, earnings
  band, race, education; also where workers live (residence files) and home-to-work flows.
- **What we use:** total jobs located within 1/3/5 miles and the year-over-year change.
- **Where it shows:** Jobs panel; alert SIG-06; percentiles.
- **Freshness:** yearly, about two years behind (now 2024 vs 2023). Noise is added at block
  level for privacy, so small areas are approximate.

### SRC-06 QCEW (Quarterly Census of Employment and Wages)
- **What it is:** BLS count of jobs, establishments and wages from employer tax filings.
- **Access:** bulk CSV per county and quarter (`data.bls.gov/cew/data/api`). No key.
- **What it can give:** employment by month, establishments, total and average weekly wages, by
  detailed industry (NAICS) and ownership, for every county, plus year-over-year changes.
- **What we use:** private-sector jobs and retail-trade jobs (NAICS 44-45) with year-over-year
  change; retail establishments and average weekly wage.
- **Where it shows:** Local economy panel; alerts SIG-03 and SIG-04; percentiles.
- **Freshness:** quarterly, about 5–6 months behind (now 2026 Q1). County level only.

### SRC-07 LAUS (Local Area Unemployment Statistics)
- **What it is:** BLS monthly unemployment estimates.
- **Access:** BLS Public Data API (JSON). Without a key: 25 queries/day, 10 years; with a free
  key: 500 queries/day, 20 years.
- **What it can give:** labor force, employed, unemployed, unemployment rate for counties,
  metros, cities over 25,000, and states, monthly.
- **What we use:** the county rate, its change vs a year earlier, the 3-month average, and the
  state's change for comparison (an alert fires only when the county worsens 0.5 pts more than
  the state).
- **Where it shows:** Local economy panel; alert SIG-05.
- **Freshness:** monthly, about one month behind; the newest month is preliminary.

### SRC-08 CPI-U (Consumer Price Index)
- **What it is:** BLS inflation index.
- **Access:** BLS Public Data API.
- **What we use:** annual averages for the two ACS periods, to compare incomes in today's dollars.

### SRC-09 Building Permits Survey
- **What it is:** Census Bureau monthly count of new housing units authorized by permit.
- **Access:** bulk text files per month (county files at `www2.census.gov/econ/bps`). No key.
- **What it can give:** units and buildings by structure type (1-unit, 2, 3–4, 5+) and their
  value, for counties, metros and individual permit-issuing places (towns and cities).
- **What we use:** total units permitted in the last 12 months vs the 12 months before, per county.
- **Where it shows:** Local economy panel; alert SIG-07.
- **Freshness:** monthly (now through September 2026). Town-level files exist but are not used yet.

### SRC-10 HPMS (Highway Performance Monitoring System)
- **What it is:** the traffic and road database every state reports to the Federal Highway
  Administration.
- **Access:** map service per state and year (`geo.dot.gov`). No key.
- **What it can give:** for each road segment: average daily traffic (AADT), truck share, the
  year of the actual count, road class, lanes, speed limit, access control, ramps, pavement and more.
- **What we use:** AADT of up to two roads that serve the site (ramps and limited-access
  highways skipped), distance from the pin, road class, lanes, and year-over-year change only
  when the count itself is newer ("estimate carried forward" otherwise).
- **Where it shows:** Traffic panel, key facts, alert SIG-08, percentiles.
- **Freshness:** yearly, 1–2 years behind (now 2025 vs 2024). Most roads are counted every 3–6
  years, with estimates in between (24 of 34 main roads in the portfolio carry an old count forward).

### SRC-11 National Flood Hazard Layer (NFHL)
- **What it is:** FEMA's official digital flood maps.
- **Access:** map service (`hazards.fema.gov`, layer 28 "Flood Hazard Zones"). No key.
- **What it can give:** flood zone (A, AE, V, X…), whether it is a Special Flood Hazard Area
  (the 1%-a-year "high-risk" zone), base flood elevation, map panel and effective date; also
  levees, cross-sections and map-revision letters.
- **What we use:** zone at the pin, the nearest high-risk polygon within 150 m and its distance,
  inside/outside test, base flood elevation, map panel.
- **Where it shows:** Hazards panel, key facts, alert SIG-11 (High only when the pin is inside).
- **Freshness:** changes when FEMA adopts map revisions; we recheck monthly. Screening only,
  not an official flood determination.

### SRC-12 National Risk Index (NRI)
- **What it is:** FEMA's modelled natural-hazard risk by census tract.
- **Access:** map service (ArcGIS Online). No key. Read in bulk, one state at a time (paged, 1–5
  requests per state); the pin's tract comes from TIGERweb (Census), so FEMA's hosting service never
  receives a property location. FEMA's former bulk download now redirects away (checked 2026-11-21).
- **What it can give:** composite risk score, expected annual loss, social vulnerability and
  community resilience, plus ratings for 18 hazards (floods, hurricane, tornado, wildfire,
  earthquake, hail, heat wave, winter weather…).
- **What we use:** the composite rating and percentile, the top three hazards, and a concern only
  when a property-damaging hazard (flooding, hurricane, wildfire, earthquake, landslide) rates high.
- **Freshness:** about yearly (December 2025 release); each state's copy cached 90 days.

### SRC-13 Overture Places
- **What it is:** an open map dataset of ~60 million places worldwide, combining Meta, Microsoft
  and other contributors.
- **Access:** cloud dataset: GeoParquet files on AWS S3, queried in place with DuckDB (no key).
  We store compact copies (1.3 GB → 77 MB for the portfolio).
- **What it can give:** name, category, brand (with Wikidata ID), address, phone, website,
  social links, confidence score, operating status (open / permanently closed), and the
  contributing sources, for every place.
- **What we use:** places within 3 miles: counts by category group (1 and 3 miles), anchors and
  key brands with distances, the nearest supermarket, places marked closed, and month-to-month
  changes (possible closures and new key businesses), with de-noising (confidence thresholds,
  two-release confirmation for disappearances, brand-wide data drops ignored).
- **Where it shows:** Retail panel, key facts (nearest supermarket), alerts SIG-09 and SIG-10.
- **Freshness:** monthly releases; older releases are **deleted from S3 after about two
  months**, so history exists only in our stored copies (archive kept since September 2026).
- **Caveats:** coverage and categories are uneven; disappearing from the data is not proof of a
  closure; no sales, foot traffic or square footage.

### SRC-14 SEC EDGAR
- **What it is:** the SEC's public filing system.
- **Access:** API: `data.sec.gov` submissions (JSON per company) and full-text search. No key,
  but every request must declare a contact email (set: adijoshua1010@gmail.com); max 10
  requests/second (we use 5).
- **What it can give:** every filing by public companies: 10-K/10-Q (store counts, risk factors),
  8-K events (bankruptcy, store closures, impairments, executive changes), and XBRL financial data.
- **What we use:** for tenants an admin has mapped to a public company: 8-K items 1.03
  (bankruptcy) → alert SIG-12 High; 2.05 (exit/closure costs) and 2.06 (impairments) → SIG-13 Watch.
- **Freshness:** checked daily. Only public companies; most local tenants are not covered.

### SRC-15 User-provided facts
Ownership confirmation, tenants (name, anchor, confirmed), pin corrections, square footage,
notes, alert reviews and feedback. Every change keeps who and when.

### SRC-16 Paragon public property listings
A one-time import of the 36 properties and their listed tenants from paragonct.com, kept as
"unconfirmed" until someone confirms them. Listing claims (traffic counts, demographics) are
deliberately not imported as measurements.

---

## Part 2. Sources we could add

Grouped by the question they would answer for John. **Effort:** S = days, M = about a week,
L = several weeks. **Cost:** Free unless stated.

### A. More from sources we already use (cheapest wins)

| Source | What it would add | Access | Updates | Effort | Cost |
|---|---|---|---|---|---|
| **More ACS tables** (same files) | Age profile (kids, seniors), home values, rents, renters vs owners, vehicles per household, commute times, poverty, households with children | Bulk file (already ingested format) | Yearly | S | Free |
| **Census Population Estimates (PEP)** | Population for counties and cities **every year** (fresher than 5-year ACS) | Census Data API (free key required) | Yearly (spring) | S | Free |
| **BPS town-level permits** | New housing in the property's own town, not just the county | Bulk file (same source) | Monthly | S | Free |
| **LODES industry detail** | What kind of jobs are near the site (retail, health, office…), daytime spending power by earnings | Bulk file (same files) | Yearly | S | Free |
| **QCEW detail** | Restaurants, grocery and other retail sub-sectors by county | Bulk file (same files) | Quarterly | S | Free |
| **SEC 10-K store counts** | Each public tenant's store count trend (expanding or shrinking chain) | API (same) | Yearly | M | Free |
| **Overture extra fields** | Phone, website and social links for leasing prospect lists | Cloud dataset (same) | Monthly | S | Free |

### B. Business landscape and tenants

| Source | What it would add | Access | Updates | Effort | Cost |
|---|---|---|---|---|---|
| **Foursquare Open Source Places** | A second, independent places dataset (100M+ places) to confirm closures and openings and fill gaps | Parquet download (Apache 2.0; now gated, contact details required) | About monthly | M | Free |
| **OpenStreetMap places** | Third check on businesses; good for shopping-center outlines and parking | Bulk extracts or Overpass API | Continuous | M | Free |
| **County / ZIP Business Patterns (CBP/ZBP)** | Establishments and employment by industry per county (ZIP: totals only) | Census Data API (free key) | Yearly, ~2 years behind | S | Free |
| **WARN layoff notices** | Large layoffs and closures by employers near a property (60-day advance notice) | State portals; aggregators (e.g. API Ninjas, free key) | Weekly-ish, varies by state | M | Free / freemium |
| **State business registrations** (Secretary of State) | New and dissolved businesses by town | State open-data portals (CT, NY, PA have APIs) | Daily–weekly | M per state | Free |
| **City open data: building permits, business licenses, code violations** | Construction and new businesses next to a center | City portals (Socrata/ArcGIS); varies | Daily–monthly | M per city | Free |
| **GDELT news** | News mentions of tenants and centers (closures, openings) | API | 15 minutes | M | Free |
| **Google Places API** | Ratings, review counts, open hours, "permanently closed" flags | API | Live | M | Paid per call (~$17–32 per 1,000) |
| **Placer.ai / Advan / Pass_by (foot traffic)** | Visits per property and per tenant, trends, trade-area origin | API / dashboard | Weekly–monthly | M | Paid (typically $10k+/year) |

### C. Housing, income and the trade area

| Source | What it would add | Access | Updates | Effort | Cost |
|---|---|---|---|---|---|
| **IRS ZIP-code income (SOI)** | Income and tax-filer counts per ZIP, yearly | Bulk file | Yearly, ~2 years behind | S | Free |
| **IRS county migration** | Where people move in from and out to | Bulk file | Yearly | S | Free |
| **FHFA House Price Index** | Home-price trend by county/ZIP | Bulk file | Quarterly | S | Free |
| **Zillow research data (ZHVI, ZORI)** | Home values and rents by ZIP, monthly | Bulk file (attribution) | Monthly | S | Free |
| **BEA personal income** | County income and spending power, yearly | API (free key) | Yearly | S | Free |
| **HUD USPS vacancy data** | Vacant residential and **business addresses** per tract, quarterly | API | Quarterly | M | Free, but **only government, nonprofit and academic users** |
| **Drive-time areas** (OpenRouteService) | 5/10/15-minute drive areas instead of circles | API (free key) | Live | M | Free tier |

### D. Hazards and physical risk

| Source | What it would add | Access | Updates | Effort | Cost |
|---|---|---|---|---|---|
| **OpenFEMA disaster declarations** | Federal disasters declared in the county (history and new) | API, no key | Daily | S | Free |
| **NFIP flood claims (redacted)** | Past flood-insurance claims by ZIP/tract: has this area actually flooded? | API, no key | Every 40–60 days | S | Free |
| **FEMA map revisions (LOMR)** | Upcoming flood-map changes near a property | Map service (same NFHL) | Continuous | S | Free |
| **NOAA storm events** | Recorded storms, floods and hail by county | Bulk file | Monthly | S | Free |
| **USGS earthquakes** | Nearby earthquakes | API | Live | S | Free |
| **EPA Envirofacts (Superfund, brownfields, regulated sites)** | Environmental issues next to a property (acquisitions due diligence) | API | Varies | M | Free |
| **First Street (flood, fire, heat, wind)** | Property-level climate risk scores | API | Yearly | M | Paid |

### E. Real estate and leasing (mostly paid or per-county)

| Source | What it would add | Access | Updates | Effort | Cost |
|---|---|---|---|---|---|
| **County assessor / parcel records** | Parcel lines, owner, assessed value, land use, sales; free per county, uneven | County portals; Regrid aggregates nationally | Varies | L | Free per county / Regrid paid |
| **CoStar, Crexi, LoopNet** | Comparable rents, vacancy, listings, sale comps | Licensed data | Continuous | L | Paid (licensing restricts automated use) |
| **Paragon's own rent roll and leases** | Lease expirations, rents, co-tenancy clauses: the highest-value data for John | Upload (CSV/Excel) | When leases change | M | Free (private) |

### Recommendations

1. **Quick, free, high value:** more ACS tables, town-level permits, LODES industry detail,
   OpenFEMA disasters and NFIP claims, Population Estimates. These deepen the property page
   without new vendors.
2. **Most valuable for leasing and closures:** Foursquare Open Source Places (to confirm
   closures), WARN notices, and the rent roll when John is ready to share it.
3. **Worth a demo before paying:** a foot-traffic provider (Placer.ai or Advan), the biggest
   step up for retail, but a real budget item.

## Sources consulted for Part 2
- HUD USPS vacancy data access: https://www.huduser.gov/apps/public/usps/home
- Foursquare Open Source Places: https://huggingface.co/datasets/foursquare/fsq-os-places
- OpenFEMA datasets: https://www.fema.gov/about/openfema/data-sets ; NFIP claims: https://catalog.data.gov/dataset/fima-nfip-redacted-claims-openfema
- WARN notice options: https://api-ninjas.com/api/layoffnotices ; https://catalog.data.gov/dataset/warn
- County/ZIP Business Patterns API: https://www.census.gov/data/developers/data-sets/cbp-zbp.html
