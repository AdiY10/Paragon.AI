# Insights: portfolio comparison, summary, signals and brief

## Portfolio percentiles and evidence summary (T3; MET-20, FR-16, FR-26)
`backend/apps/insights/metrics.py` reads stored, sourced section results and never recomputes or estimates values.

- **Compared measures** (3-mile ring; county or road level where that is the metric):
  - population, households, median and average household income
  - population change and real income change (only when statistically significant)
  - jobs within 3 mi and their change
  - county private and retail job change, unemployment change (lower is better), housing permits change
  - main-road AADT
- **Percentile:** `(count below + ½ ties) / n` over the *other* owned, pinned properties with a value. Shown only when n ≥ 5.
- **Strengths:** favourable percentile ≥ 75. **Concerns:** ≤ 25. Hazard concerns (Special Flood Hazard Area, NRI Relatively High or Very High) and High or Watch signals rank first. Up to 5 of each, worded factually ("better than 81% of your 34 properties").
- **API:** `GET /api/locations/<id>/summary/` returns `metrics` (value, period, source, percentile, n), `strengths`, `concerns`, `signals`.
- **UI:** a "How this location compares" panel at the top of each property page, with an expandable percentile list.
- **Portfolio benchmarks** (median, min, max) via `metrics.benchmarks()`, used by Compare.

## Signal engine (T4; FR-19, FR-20, FR-23)

**Alert scope (redesign B7a):** alerts are High or Watch only, for actionable changes, and every alert
carries a `next_step` from `config/signals.yaml` (`rules:`). SIG-01/02 (trade-area trends), SIG-06 (jobs
nearby), SIG-07 (permits) and SIG-10 (openings) are no longer alerts; their data stays in the analysis.
The static flood zone (SIG-11) is a **risk badge** (`signals.risk_badges`). Open alerts outside the scope
are `retired` (never shown, never counted as "resolved"). `GET /api/signals/` adds `groups` (one entry per
county figure or shared place, with every property and `signal_ids`); `POST /api/signals/<id>/review/`
accepts `apply_to_group: true`. The weekly brief schedule is switched off (`enabled: false`).
On the preview this took active alerts from 95 to 17 rows shown as 7 alerts.
`backend/apps/insights/signals.py` derives signals only from stored section results. Thresholds live in `config/signals.yaml`, which holds the docs/04 §5.2 defaults (configuration, to validate with John).

| Rule | Source section | Fires when (defaults) | Severity |
|---|---|---|---|
| SIG-03 | Economy (county) | County private jobs YoY ≤ −2% | Watch |
| SIG-04 | Economy (county) | County retail jobs YoY ≤ −4% | Watch |
| SIG-05 | Economy (county) | Unemployment 3-month average up ≥ 1.0 pt vs a year earlier and ≥ 0.5 pt more than the state | Watch |
| SIG-08 | Traffic | Main road down ≥ 10% on a genuinely newer count (never SAME_COUNT), prior count ≥ 3,000/day | Watch |
| SIG-09 | Businesses | Confirmed closure of an anchor or grocer within 1 mi (Watch), or the tenant's own store within ~150 m (High if marked closed) | High / Watch |
| SIG-12/13 | SEC (T9) | Tenant bankruptcy (1.03) / restructuring (2.05, 2.06) within 90 days | High / Watch |

- **Lifecycle:** one row per (location, rule, subject).
  - Re-evaluation creates, updates or escalates a signal, or resolves it ("condition no longer holds"; "location corrected" after a pin move).
  - Event signals (SIG-09, 10, 12, 13) expire 90 days after the event date.
  - A dismissed signal stays hidden unless its severity increases.
- **When it runs:** evaluation runs automatically after every section computation. `python manage.py evaluate_signals` re-evaluates everything, for a baseline or after threshold edits.
- **API:**
  - `GET /api/signals/?status=active|resolved|all&location=<id>` (ranked per §5.4)
  - `POST /api/signals/<id>/review/` with `{"action": "reviewed" | "dismissed", "note": ""}`
  - Each location now has `attention` (High, Watch or Clear; FYI-only counts as Clear).
- **UI:** active signals appear at the top of the property Summary panel and rank first among concerns.

## This Week brief and attention (T5; FR-21, FR-35)
- **Generation:** `apps/insights/brief.py` runs from `brief_weekly` (schedule: Monday 07:00 US Eastern) or via `POST /api/briefs/generate/` (admin only).
- **Contents:** an immutable `Brief` with:
  - signals on **owned** properties that are new or changed since the previous brief, plus still-active High signals, ranked per docs/04 §5.4
  - High and Watch items in full, FYI items collapsed
  - the sources that published new periods since the previous brief
- **Titles:** the first brief is "Baseline: current conditions"; when nothing qualifies the title is "No material changes this week".
- **API:** `GET /api/briefs/latest/` (with a history of the last 26), `GET /api/briefs/<id>/`.
- **UI:**
  - The home page shows the brief, with an evidence drawer per item, past briefs, and the admin "Generate brief now" button.
  - Portfolio cards show a High or Watch attention badge, can be filtered by attention, and sort by attention first.

## Screen and Compare (T6, T7; FR-25, FR-27)
**Screen** (`#/screen`):
- Enter any US address. `POST /api/screens/` creates an **unsaved screen**: a candidate with `screening=true`.
- The address is geocoded with the Census geocoder. An exact match is pinned automatically and the demographics and area jobs are queued. An ambiguous or missing match leaves the pin to the user (Find address pin, or Correct / confirm pin).
- The property page loads progressively and starts calculations automatically for screens.
- Unsaved screens are not monitored, not in the portfolio list and not in briefs. `POST /api/screens/<id>/save/` makes one a monitored candidate. Unsaved screens older than 30 days are archived.
- For addresses in states not yet ingested, the background job ingests that state's ACS rows on demand.
- Analyses are automatic (redesign B3a, `backend/apps/area/analysis.py`): creating, re-pinning or re-ringing a
  location queues one `analyze_location` job (foreground when a person made the change, `analyze_location_bg`
  for seeds and bulk work) once the change commits. The job computes the five area sections and ring
  demographics for the current `analysis_version`, stops as stale if the pin moves meanwhile, and evaluates
  alerts once at the end. Job keys are `analyze:{location}:{analysis_version}:{attempt}`.
- The scheduler sweep (every 5 minutes, at most 2 live background analyses) fills missing sections, retries
  transient source failures (TIMEOUT, HTTP_ERROR, SOURCE_ERROR) after 10 min, 2 h, then 24 h, recomputes
  results whose `logic_version` is older than the code's, and raises an admin alert for an owned property
  without a pin. After 3 failed attempts in 24 hours a location is left alone until the window passes.
- `AUTO_ANALYZE=false` (environment) turns off the hooks and the sweep. `manage.py analyze_portfolio
  [--dry-run]` queues everything missing in one go (used after a rebuild).
- `POST /api/locations/<id>/area/` and `/demographics/` no longer force work: for a member they only queue
  what is missing; an administrator's POST recomputes those sections. The old `/compute/` route is gone.

**Compare** (`#/compare`):
- Pick 2–4 locations. The selection is kept in this browser, and "Add to compare" is available on every property page.
- `GET /api/compare/?ids=a,b,c` returns every comparable measure per location, with period and source, the portfolio median and range, the flood zone, attention level and top signals.
- Strongest and weakest are highlighted only for directional measures (lower is better for unemployment change).
- Print-friendly via the browser's print or save-as-PDF.

## Tenants and SEC tenant watch (T8, T9; FR-07, FR-22, SIG-12, SIG-13)
- **T8 finding:** the tenant domain (`apps/locations/tenants.py`, Amit's agent) exists, but no API, UI or listing import is on GitHub (Amit's in-progress API and seed are in a local stash). This adds a **thin API and UI over the existing service functions**, without new tenant rules. Amit's agent should reconcile its stash with `apps/insights/tenant_views.py` and the `import_listing_tenants` command.
- **API:**
  - `GET/POST /api/locations/<id>/tenants/`
  - `PATCH .../tenants/<tid>/` (name, anchor, notes, archived; `expected_version`)
  - `POST .../tenants/<tid>/confirm/`
  - Tenant edits advance the location's analysis version (existing domain behaviour), so the API queues a recompute from cached snapshots.
- **Listing import:** `python manage.py import_listing_tenants` imports tenants named on paragonct.com for owned seed properties as **unconfirmed listing claims**.
  - Presence values: `listed_unverified`; `neighbor_or_cotenant` where the listing says "Join"; `planned_unverified` for "soon to open"; `name_only`.
  - Anchors are marked only where the listing says "anchor". The import is idempotent.
- **SEC mapping:** admins search EDGAR entities (`GET /api/sec/search/?q=`) and map a tenant to a filer (`POST/DELETE .../tenants/<tid>/sec/`). Suggestions are never applied automatically.
- **Daily watch:** `sec_daily` (06:00 ET) fetches `data.sec.gov` submissions for mapped filers (at most 5 requests/s), stores SRC-14 snapshots, records health and re-evaluates affected properties.
  - **SIG-12 (High):** Item 1.03 within 90 days.
  - **SIG-13 (Watch):** Item 2.05 or 2.06.
  - Repeated filings collapse into one signal per tenant and rule. Older events are listed as past events with filing links.
- **Requires `SEC_USER_AGENT="<App name> <contact email>"`**. Without it the job fails with `NOT_CONFIGURED` and search shows a clear message. No request is sent to SEC.
- **Real-data tests:**
  - Leslie's (CIK 1821806): three 1.03 filings from 2026-09-30 to 2026-10-22 produce one SIG-12 High plus a SIG-13 Watch.
  - Rite Aid (CIK 84129): the 2023-10-16 Item 1.03 filing is listed as a past event with no signal.

## Data-quality gate (redesign B6a)
`python backend/manage.py qa_report [--strict] [--json]` (`backend/apps/insights/qa.py`) checks every owned,
pinned property from stored results only (no fetching). `--strict` exits 1 on any failure; run it after
every deploy and data rebuild.

| Check | Fails when |
|---|---|
| complete | a section is missing, outdated (`logic_version`) or failed transiently |
| rings_increase | population, households or jobs shrink from the 1- to the 3- to the 5-mile ring |
| households_per_person | households ÷ population outside 0.2–0.7 (rings with ≥1,000 people) |
| median_income_range / median_vs_mean_income | median outside $15k–$250k, or above 1.3 × the mean |
| headline_reliability | a 3-mile headline (population, households, median income) has very low reliability |
| acs_vintage | demographics are not on the current ACS vintage |
| aadt_plausible / road_distance / road_label | primary-road AADT implausible for its class, road >250 m away, or a label that is an inventory code ("K120 Birch St") |
| flood_zone_consistent | "inside a high-risk area" without an A or V zone |
| county_matches_tract | the economy county differs from the pin's census tract county |
| business_count_swing | the 3-mile business count moves >20% between Overture releases |
| fresh | a section is older than its refresh cadence (economy/businesses 21 days; traffic, jobs, hazards 45) |
| golden | a hand-verified value in `config/qa_golden.yaml` is off (Norwalk 1/3-mi population, Kingston US 9W 2024 AADT, Cypress Lake zone AE / BFE 9 ft, CVS–Graham NC-87) |

Preview, 2026-11-22: 35 properties, 0 failures, 0 warnings (after the traffic logic bump recomputed the
road labels that still carried inventory codes).
