# Paragon Radar: redesign plan (v3, approved 2026-11-21)

Two tracks: **PART B** backend (data, automation, speed, quality) and **PART F** frontend (the new
app). **PART C** is the shared API contract — the single source of truth both tracks build against.

## Context
Release 2.0 (PRs #52–#82) made the data trustworthy and the app deployable; it runs at
https://paragonai.duckdns.org on a 2 GB DigitalOcean droplet. Adi tried it and does not like it:
it is organised around a weekly brief, setup chores and "Calculate / Check area data" buttons,
and the production server has the 36 properties but none of their analysis.

Adi's direction for the redesign (2026-11-21):
1. All Paragon properties are confirmed (no confirmation chores anywhere).
2. The main page is all the properties: a map first, then a list of all of them.
3. Clicking a property opens a full, detailed analysis based on the data.
4. Data import happens on the website automatically — no "analyze" button — and it is fast.
5. A separate screen analyzes new places: type an address or click anywhere on the map and the
   analysis starts.
6. Alerts stay.
7. Quality over quantity in both the analysis and the alerts.
8. Learn from Placer.ai (the category leader in location analytics for CRE) and apply what fits a
   public-data product.

The plan must be detailed enough that implementation agents can build it item by item.

### Decisions already made (Adi, 2026-11-21)
- **Look:** "Clean analytics": white background, map-first, one accent color, dense data cards and
  simple charts, top horizontal navigation (Placer-like). **Accent: Paragon green `#0E6B4F`**;
  red and amber are reserved for alert levels.
- **Keep:** Tenants & SEC watch, Compare (up to 4), Data sources page. **Drop:** the weekly brief
  UI (This Week), onboarding/confirmation screens, the Screen page (replaced by Analyze).
- **New-place analyses:** kept in a "Recent analyses" history; a star keeps one forever,
  unstarred ones expire after 90 days. They never create alerts.

## What we take from Placer.ai (and what we must not pretend)
Placer (4,000+ customers, ~$100M ARR) sells foot-traffic analytics from a phone panel (~7% of US),
quote-only pricing ($12k–$126k+/yr), no free tier since Oct 2026. Their property report is a fixed
left menu (Overview → Property info → Variance → Visitor journey → Demographics → Trade area → Area
analysis → Ranking → Loyalty → Void analysis), KPI cards with value + change + sparkline, indexes
where 100 = US average, "rank N of M" cards, honest data notes on every AI narrative, side-by-side
compare, and a leasing playbook (benchmark → reach → rank → co-tenancy → void list).

**We copy (public data only):**
1. The fixed section menu and a predictable report layout for every property and every new place.
2. KPI cards: value, rank "N of M" in the portfolio, change where a real prior period exists.
3. Index columns: each demographic vs the US (100 = US average), next to its portfolio rank.
4. "Rank N of M" within the portfolio for population, income, jobs nearby, traffic, retail density.
5. Residents vs daytime workers (LODES) — the public stand-in for Placer's home/work split.
6. "Area analysis": road counts with trend, permits, flood/NRI, confirmed openings & closings.
7. Key takeaways written from the numbers, each with source + period ("data-honesty notes").
8. Assumptions on every widget: ring radius, data vintage, margin of error, "estimate carried forward".
9. Category-mix gaps vs similar portfolio properties (a void *hint*, not Placer's scored void list).

**We never imply:** visits, visitors, dwell time, loyalty, cross-shopping, visitor origins, sales
estimates, or a "true trade area". Rings are labelled "radius rings". Traffic counts are vehicles
on the road, never visits.

## Target experience (information architecture)
Top bar: **PARAGON RADAR · Properties · Analyze · Alerts · Compare** — right: user menu
(Data sources, Admin for admins, Sign out). Old routes redirect.

| Route | Page | Replaces |
|---|---|---|
| `#/` | **Properties**: full-width map of all owned properties (pins colored by attention), then a sortable table of all of them | This Week, Portfolio |
| `#/p/:id` | **Property analysis**: header + fixed section menu + full analysis, no buttons | `#/locations/:id` |
| `#/analyze` | **Analyze a place**: address search or click the map; recent analyses | Screen |
| `#/analyze/:id` | Same analysis page in "new place" mode (progressive) | screen profile |
| `#/alerts` | **Alerts**: High/Watch, grouped by property, evidence + review | Alerts (kept) |
| `#/compare` | Compare up to 4 properties or analyzed places | Compare (restyled) |
| `#/sources`, `#/admin` | Data sources, Admin (user menu) | restyled |
| `#/portfolio`, `#/locations/:id`, `#/screen`, `#/setup` | redirects | — |

## Delivery order (one PR per item; merge in this order within each track)

| Phase | Backend track (`backend/`, `config/`, `infra/`) | Frontend track (`frontend/`) |
|---|---|---|
| 1. Production correct & automatic | B0 → B1 → B3a → B4a → B7a → B6a → **B2 production rebuild** | WI-1 → WI-2 → WI-3 (no backend dependency) |
| 2. Fast new places | B3b → B5 → B9 → B4b (spike gate first) | WI-4 → WI-5 → WI-6 → WI-7 (need B3b/B5/B9) |
| 3. Depth & quality | B8 (before ACS 2021–2025 lands in December) → B6b → B7b | WI-8 → WI-9; sections render new fields as they arrive |
| 4. Go-live | Deploy, `qa_report --strict`, timing + memory measurements | Rewritten smoke + manual check on production |

The two tracks touch disjoint folders and can run in parallel sessions. If a frontend item needs a
backend endpoint that has not landed, it uses the temporary adapter in WI-5 rather than waiting.

---

# PART B — Backend (work items)

Paths under `backend/` unless they start with `config/`, `infra/`, `docs/`, `scripts/`. Every item:
tests added, `uv run python -m pytest -q` green, acceptance numbers recorded in the PR.

### B0 Baseline (½ day, droplet)
- Record `free -m`, `docker stats`, per-process RSS (`smem`), Postgres and disk size, one `compute_area`
  duration, production row counts → `docs/DEPLOYMENT.md`.
- `config/settings/base.py` `Q_CLUSTER`: add `max_rss: 350000` to both clusters (worker recycling).
- Accept: numbers recorded. If the idle app container uses >900 MB, set the foreground cluster to
  1 worker and rely on threads (B3b) for parallelism.

### B1 Owned means confirmed
- New `apps/locations/management/commands/confirm_portfolio.py` (`--actor-email` = an active admin,
  `--dry-run`): calls `apps/locations/service.py:confirm_location` with each row's `version`; idempotent.
- `apps/locations/service.py`: `create_location`/`update_location` auto-confirm when status becomes
  `owned`; an address change keeps `confirmed` for owned properties (the pin revision still starts
  unconfirmed). Update `tests/test_portfolio_seed.py`, `tests/test_location_api.py` expectations.
- Tests: second run is a no-op; creating an owned property confirms it; owned address change stays confirmed.
- Accept: 36/36 owned confirmed with audit events.

### B3a Automatic analysis plumbing (serial first)
- New `apps/area/analysis.py`:
  - `ensure_analysis(location_id, sections=None, interactive=True)`: lock the location row; skip archived or
    unplaced; return a live job for `analyze:{id}:{analysis_version}:*` if one exists; else enqueue
    `analyze:{id}:{av}:{n+1}`; refuse after 3 failed attempts in 24 h. (Do **not** change
    `apps/operations/service.py:enqueue_job` — scheduled jobs rely on its one-per-key dedup.)
  - `run_analysis(location_id, sections, heartbeat)`; `sweep(now, limit=2)`.
- `apps/operations/registry.py`: `analyze_location` (foreground, timeout 900 s, lease 300 s) and
  `analyze_location_bg` (maintenance, same handler, for bulk/sweep work), params
  `{location_id, analysis_version, sections}`; a heartbeat thread every 60 s; if fenced, a cancel flag is
  checked between sections.
- `apps/area/service.py`: split `compute_area` into `compute_section(...)` + loop with `evaluate=False`;
  add `SECTION_LOGIC` for economy/traffic/jobs; new `AreaSection.logic_version` (migration, default 1).
  `apps/demographics/service.py:compute_for_location(..., evaluate=False)`; `RingDemographics.logic_version`.
- Hooks: `create_location`, `change_pin`, ring-preset changes in `update_location`, and geocode
  `accept_lookup` call `ensure_analysis` via `transaction.on_commit`; gated by `settings.AUTO_ANALYZE`
  (False in `config/settings/test.py`).
- `apps/operations/scheduler.py:dispatch_due` runs `analysis.sweep()` at most every 5 min: missing sections;
  retryable failures (TIMEOUT/HTTP_ERROR/SOURCE_ERROR) after 10 min → 2 h → 24 h; outdated `logic_version`;
  trends pending >15 min; owned property with no pin → admin `AlertEvent`.
- Remove manual compute: delete route `api/locations/<id>/compute/`; POST on `apps/area/views.py:area` and
  `apps/demographics/views.py:demographics` becomes admin-only.
- Tests `tests/test_analysis.py`: attempt numbering (new attempt after a failure), 3-failure cap,
  after-commit hooks, pin moved mid-run → STALE, sweep backoff, heartbeat fencing.
- Accept: every pinned owned property has all 6 results with zero clicks; 20 runs → 0 job recoveries.

### B4a Ingestion and memory safety
- ACS, all 51 jurisdictions: `apps/demographics/acs.py:download_tables(year, dir)` streams the national
  files once to `var/cache/acs/{year}/` (resumable, size cap); `apps/demographics/service.py:ingest_acs_all(year)`
  feeds batches of ≤30,000 block groups (CA and TX alone) through `ingest_acs(batch, line_source=...)`;
  2019 one state per call. `ingest_acs --all-states`. `apps/area/refresh.py:refresh_annual` ingests all 51
  for a new vintage. `AUTO_INGEST` becomes a queued maintenance job `ingest_acs_states` (dedup
  `acs:{year}:{state}`) — never inside a foreground analysis; meanwhile the section shows "loading".
- LODES: `apps/area/jobs.py:parse_wac(raw, keep)` streams gzip/csv keeping only the ring's blocks; delete
  `_WAC`/`_parsed_wac` in `apps/area/service.py`.
- Probe caches through `Run.cached` (shared across processes, with provenance): SRC-13 `releases` 1 d;
  SRC-05 `lodes:latest:{st}` 7 d; SRC-10 `hpms:latest:{st}` 30 d; SRC-06 `qcew:latest` (probe `US000.csv`) 7 d.
- BLS: `apps/area/economy.py:fetch_laus_many(fips_list)` batches county + state series (25/request keyless,
  50 with `BLS_API_KEY`) in `refresh_economy`; set the 7-day caches to 6 days so weekly runs refresh.
- NRI: replace the per-pin `services.arcgis.com` query with FEMA's bulk census-tract table, ingested once
  and looked up by tract (faster; no third-party host sees pins).
- Tests: batch planner; filtered LODES parse == full parse restricted to the ring; cached probes don't
  refetch; LAUS batches split correctly; NRI tract lookup.
- Accept: 51 states × (2024, 2019) ingested in <45 min with worker RSS <400 MB; CA LODES parse <1.5 s;
  0 LODES probe requests for a second pin in the same state.

### B7a Alert re-scope (must ship before the first production brief)
- `config/signals.yaml`: enabled rules, thresholds, and a `next_step` sentence per rule.
- `apps/insights/signals.py` — alerts are High or Watch only, for actionable **changes**:
  - SIG-12/13 tenant SEC filings: unchanged.
  - SIG-09: only confirmed closures of anchors or grocers within 1 mi, or the tenant's own store within 150 m.
  - SIG-08: only a ≥10% decline on the primary road, only with a genuinely newer count (`SAME_COUNT`
    respected), only if the prior count ≥3,000/day.
  - SIG-03/04/05 stay Watch until B7b replaces them with one county alert.
  - Stop generating SIG-01/02/06/07/10 (their data stays in the analysis). Static "inside a flood zone"
    (SIG-11) becomes a **risk badge** in the analysis payload, not an alert.
- `apps/insights/models.py`: `Signal.next_step` field; new status `retired`; data migration retires removed
  rules without touching `last_changed_at` (so no brief lists them as "resolved").
- `apps/insights/views.py:signal_list`: grouped response (reuse `apps/insights/brief.py:group_by_subject`);
  a review can apply to the whole group. Disable the `brief_weekly` schedule (`config/schedules.yaml`);
  keep the models.
- Accept: preview active alerts 95 → ≤15; every alert has a `next_step`.

### B6a QA gate
- New `apps/insights/qa.py`, `apps/insights/management/commands/qa_report.py` (`--strict`, `--json`),
  `config/qa_golden.yaml`.
- Plausibility checks per property: ring population/households/jobs non-decreasing 1→3→5 mi; households ÷
  population in 0.2–0.7; median income $15k–$250k and ≤1.3× mean; no very-low-reliability headline metric
  on the 3-mi ring; AADT plausible for road class, road ≤250 m, label not an inventory code (e.g.
  "K120 Birch St" exists today); "inside flood zone" ⇒ zone A/V; business counts change ≤±20% between
  releases; TIGERweb county matches the pin's block; each section fresh vs its source `stale_after_days`.
- Golden values: Norwalk 1/3-mi population within ±10% of 11,500 / 84,000; Kingston US 9W 22,523 (2024);
  Cypress Lake inside AE, BFE 9 ft; CVS–Graham NC-87 within ±10% of 21,000.
- Accept: `qa_report --strict` exits 0 on preview and on production.

### B2 Production rebuild (replaces any database copy)
1. Deploy B1, B3a, B4a, B7a, B6a with `AUTO_ANALYZE=false`.
2. New `apps/area/management/commands/export_overture_history.py` (run on the preview): owned pins only;
   tar of compact files + `manifest.jsonl` (release, pin_key, record_count, summary, compact & raw sha256,
   retrieved_at, source_url). No screen data, no addresses.
3. New `apps/area/management/commands/import_overture_history.py` (production): verify checksums, store files,
   publish SRC-13 snapshots marked compact/imported, create `OvertureCapture` rows with `raw_pruned=True`
   (skip existing), recompute release pairs (`overture_store.pair(recompute=True)`); make
   `overture_store._raw_snapshot()` ignore compact snapshots.
4. Upload `var/overture-archive` (1.4 GB raw) to the off-box backup bucket only (needs the Backblaze keys).
5. `ingest_acs --all-states` (2024, 2019), `import_listing_tenants`, `confirm_portfolio`, then
   `AUTO_ANALYZE=true`; the sweep computes the 35 pinned properties.
6. Pin P21 (Bareburger, 445 Main St, Mount Kisco NY — Census tie) by choosing the right candidate in the UI;
   its analysis starts by itself. Re-enter the one SEC filer mapping made in the preview.
7. `qa_report --strict`; compare headline numbers with the preview per property.
- Accept: 36/36 complete; Sep/Oct/Nov 2026 Overture releases present for 35 pins; ≤10 active alerts.

### B3b Parallel, progressive analysis + bundle endpoint
- `run_analysis` uses a thread pool (4 threads, 3 if B0 shows pressure; serial on SQLite); each task closes
  its DB connection; the main thread submits dependent tasks as inputs finish. Waves: (1) 2020 blocks
  geography, 2010 geography, hazards, businesses, traffic, economy → (2) demographics (`trends_status=
  'pending'`) and jobs once 2020 blocks are ready → (3) trends once 2010 geography is ready → (4) signals
  evaluated once at the end.
- New `RingDemographics.trends_status` (migration), included in `inputs_sha256`; `candidates()` skips
  SIG-01/02 logic while trends are pending.
- New `GET /api/locations/<id>/analysis/` (`apps/area/views.py:analysis_bundle`) per PART C; a GET with no
  results and no live job calls `ensure_analysis`. Old endpoints stay read-only until WI-9.
- Accept: owned-property bundle <500 ms server time p95; new place in an ingested state (10 addresses,
  ≥5 states): first section ≤10 s; all sections median ≤30 s, p95 ≤60 s with B4b (≤90 s without).

### B5 New-place API
- Extend `POST /api/screens/` with alias `/api/analyses/` (`apps/insights/views.py:screens`;
  `apps/insights/screens.py:create_screen` accepts address **or** lat/lon) per PART C.
- Map click: reject points outside US bounds (400); new `apps/locations/census.py:fetch_point_geographies`
  (Census coordinates service, a government host) → name `Near {place}, {ST}`, address
  `Map point 41.20410, -73.72710`, pin method `manual`; nearest road added to `display_label` when traffic lands.
- New `Location.kept_at` (migration) + `POST /api/analyses/<id>/keep/`; `SCREEN_TTL_DAYS` 30 → 90 for
  unkept screens (archived, never deleted). New places never create alerts (signals skip `screening`).
- Throttling: existing per-user `ExpensiveThrottle` plus a global cap (≥6 live analyses → 429 + `retry_after`).
- Privacy: outbound host allowlist in `apps/area/http.py:fetch` (Census, BLS, FEMA, geo.dot.gov, SEC, the
  Overture bucket) + a host-recording test.
- Accept: an address queues its job within 3 s; a map click within 1.5 s.

### B9 Properties list data
- Extend `apps/insights/metrics.py:refresh_snapshot` values and `apps/locations/serializers.py:get_key_numbers`
  with `flood` (inside|near|none), `nearest_supermarket {name, distance_mi}`, `active_alerts`; keep one query
  for the list (the `metrics_snapshot` select-related already exists).
- Accept: `/api/locations/` list ≤12 queries (existing budget test extended).

### B4b Overture US places extract (spike gate first)
- One-hour spike, go/no-go: build ≤20 min, file ≤1 GB, container peak ≤1.1 GB, ≤4 row groups read per pin,
  per-pin query <1 s. Estimates (unmeasured): 14–18 M US places, 0.5–0.8 GB per release (3 kept: 1.5–2.4 GB),
  needs 2× file size free during build.
- New `apps/area/overture_extract.py`: `build(release)` copies `id, names.primary, basic_category,
  brand.names.primary, brand.wikidata, operating_status, confidence, bbox.ymin AS lat, bbox.xmin AS lon`
  within US bounding boxes to zstd Parquet, 65,536-row groups, DuckDB `memory_limit=512MB threads=1`,
  streaming, no sort (source files are spatially clustered); validate row count ±15% vs previous, record
  sha256, atomic rename, publish a manifest snapshot; `capture_local()` returns the same shape as
  `apps/area/overture.py:capture`.
- `businesses_section` uses the local extract when present (fallback S3); `refresh_businesses` builds missing
  extracts first; `maintenance_daily` keeps the newest 3. New pins get the two-release closure check locally.

### B8 ACS and LODES depth (ship before ACS 2021–2025 lands in December)
- First switch ACS artifacts to gzipped JSON lines sorted by block group, with
  `load_rows(snapshot, store, geoids)` parsing only the ring's block groups (adapter `acs-table-sf-v2`;
  old format still readable).
- New tables (table-based vintages only): B01001 (cells 001–049 → age bands <18, 18–34, 35–54, 55–64, 65+
  and interpolated median age), B25003 (001–003 → owner/renter share), B25075 (001–027 → interpolated median
  owner-estimated home value), B25063 (001–027 → interpolated median gross rent). Share of households
  ≥$100k from B19001 cells 014–017 (already ingested). Generalize `apps/demographics/rings.py:interpolated_median`.
  Raise `MAX_TABLE_BYTES` to 1.5 GB (streamed). Bump the demographics logic version (sweep recomputes);
  2019 untouched (no trends for depth metrics).
- LODES sector detail (CNS01–20) and earnings bands (CE01–03) from the already-stored raw files (parser +
  jobs logic bump; no download).
- Accept: a California pin's demographics step adds <60 MB RSS.

### B6b KPIs, takeaways and US index
- `apps/demographics/acs.py:extract_reference(year)` keeps nation/state/county rows from the same national
  files; index = ring value ÷ US value × 100 (income, home value, rent, education, median age); check the
  interpolated US median income within 3% of published B19013.
- `apps/insights/metrics.py`: `kpis(location)` (value, rank & of from portfolio percentiles, change where a
  real prior period exists) and `takeaways(location)` — ≤5 fixed-template sentences, each citing metric,
  value, source and period (no generative text). Both included in the bundle.
- KPI set (fixed order): People within 3 mi (+5-yr change, significance) · Median household income 3 mi
  (+ US index) · Households 3 mi · Jobs within 3 mi (+YoY) · Main-road traffic/day (+change or "estimate
  carried forward") · Retail & services within 1 mi (Overture count) · Nearest supermarket (distance) ·
  Flood status (badge, not ranked). Ranked KPIs need ≥5 owned properties with data (existing `MIN_PORTFOLIO`).
- Takeaway templates (examples): "3-mile population 67,312 — 4th of 35 properties, +3.1% since 2015–19
  (significant)"; "Inside FEMA high-risk flood zone AE (base flood elevation 9 ft)"; "Nearest supermarket:
  Publix, 0.5 mi"; "Main road NC-87 carries 21,000 vehicles/day (2025), −9.8% vs the prior count". Pick the
  ≤5 with the strongest signal (extreme percentile, significant change, risk badge, active alert).

### B7b New alert rules + precision review
- SIG-14 competing grocer: within 2 mi, present in the latest two releases and absent in the older one;
  Watch only if the property has a grocer of another brand.
- SIG-11 becomes a flood-zone **change** event: High when the zone changes into a high-risk zone.
- SIG-15 county economy: one alert per county when ≥2 of the SIG-03/04/05 conditions hold, or private jobs
  ≤−4%; SIG-03/04/05 retired.
- `GET /api/admin/alert-quality/` → per rule `{total, useful, not_useful, precision}` (from review feedback).
- `docs/ALERT_QUALITY.md`: review of ≥20 real alerts; target ≥80% judged useful; thresholds tuned from it.

---

# PART C — API contract (both tracks build against this)

**`GET /api/locations/`** (list) — each row adds:
`attention: "High"|"Watch"|"Clear"`, `key_numbers: {population, median_household_income, aadt,
flood: "inside"|"near"|"none"|null, nearest_supermarket: {name, distance_mi}|null, active_alerts}`.

**`GET /api/locations/<id>/analysis/`** — everything the analysis page needs, one request:
```json
{"location": {"…LocationSerializer": "…", "kind": "property|place", "display_label": "Near NC-87, Graham, NC",
              "kept": false, "expires_at": "2027-02-19T…"},
 "analysis": {"state": "unplaced|queued|running|partial|complete|failed", "analysis_version": 3,
              "job": {"id": "…", "status": "running", "started_at": "…", "attempt": 1},
              "next_retry_at": null, "poll_after_ms": 1500},
 "sections": {
   "demographics": {"status": "ready|running|pending|unavailable", "reason": null,
                    "trends": "ready|running|unavailable", "computed_at": "…", "data": {"…": "rings incl. index_vs_us"}, "sources": []},
   "economy":    {"status": "ready", "reason": null, "stale": false, "computed_at": "…", "data": {}, "sources": []},
   "traffic": {}, "hazards": {}, "businesses": {"…": "places within 3 mi incl. lat/lon"}, "jobs": {}},
 "kpis": [{"key": "population", "label": "People within 3 mi", "value": 67312, "unit": "people",
           "rank": 4, "of": 35, "percentile": 91, "direction": "up",
           "change": {"value": 0.031, "unit": "pct", "since": "2015–2019", "significant": true},
           "period": "ACS 2020–2024", "source": "SRC-03"}],
 "takeaways": [{"text": "…", "tone": "positive|neutral|caution", "section": "trade-area", "source": "SRC-03", "period": "ACS 2020–2024"}],
 "signals": [], "risk_badges": [{"kind": "flood", "label": "Inside FEMA zone AE", "source": "SRC-11"}],
 "tenants": [], "sources": []}
```
`poll_after_ms`: 1500 for the first 30 s, then 3000, `null` when complete/failed. No ETag.

**`POST /api/analyses/`** (alias of `/api/screens/`) — body `{address, name?}` or `{lat, lon, label?}`:
- 201 `{location, geocode: {status: "matched", matched_address}, analysis: {state: "queued", job_id}}`
- 200 ambiguous `{location, geocode: {status: "ambiguous", lookup_id, candidates: [{index, matched_address, lat, lon}]}}`
  → client calls existing `POST /api/locations/<id>/geocode/<lookup_id>/accept/ {expected_version, candidate_index}`
  (analysis starts via the B3a hook).
- 200/503 `{location, geocode: {status: "no_match"|"unavailable"}, next: "place_pin"}` → client drops a pin on the
  same record via existing `POST /api/locations/<id>/pin/` (analysis starts via the hook).
- 400 outside the US · 429 `{retry_after}` when throttled.

**`GET /api/analyses/`** → `[{id, name, display_label, address, lat, lon, created_at, kept, expires_at, state, key_numbers}]`
newest first. **`POST /api/analyses/<id>/keep/`** `{kept: bool}` → `{kept, expires_at}`.

**`GET /api/signals/`** → grouped `{groups: [{key, rule_id, title, severity, category, why, next_step,
evidence, period, source, status, locations: [{id, name, city, state}], signal_ids: []}]}`;
`POST /api/signals/<id>/review/` accepts `apply_to_group: true`.

**`GET /api/admin/alert-quality/`** (B7b) → `[{rule_id, total, useful, not_useful, precision}]`.

---

# PART F — Frontend build (work items WI-1 … WI-9)

All paths under `frontend/` unless noted. Each WI is one PR; every PR passes `npm test`, `npm run build`
(tsc + vite) and the updated browser smoke. Use the `dataviz` skill when building charts.

### F0. Architecture decisions (binding)
| Topic | Decision |
|---|---|
| Entry | Keep `src/main.tsx` (Django reads manifest key `src/main.tsx`, `backend/config/frontend.py`); it becomes a thin bootstrap. |
| Routing | Keep **hash routing** in a ~120-line `src/app/router.tsx` (no library): `matchRoute`, `legacyRedirect` (replaceState), `useRoute`, `useQueryState` (URL state without focus moves), `navigate`, `<Link>`. |
| Charts | **Custom components, no library** (HTML/CSS bars + small SVG): values always printed as text; bars start at 0. |
| Property pins | **HTML `<button>` markers** + screen-space clustering (`src/lib/cluster.ts`, 40 px): native focus/labels, ≥24 px targets, no glyph requests (CSP allows only self + tile.openstreetmap.org). |
| Businesses/rings/flood | GeoJSON sources with `circle`/`fill`/`line` layers only (no `symbol` layers → no glyphs). |
| Map lifecycle | One map per mount; updates via `setData`/`setFilter`/class toggles — never rebuilt on filter/hover/poll. |
| Font | `@fontsource-variable/inter` bundled (self-hosted, Latin ~48 KB). Only other new dep: dev `@types/geojson`. |
| Menus | Disclosure-pattern `MenuButton` (no new Radix package). |

### F1. Folder structure
```
src/main.tsx                     bootstrap (polyfill, font, styles, <App/>)
src/app/                         App AppShell TopNav UserMenu MobileNav GlobalSearch router.tsx queryClient.ts
src/api/                         client.ts types.ts analysis.ts keys.ts hooks.ts
src/lib/                         format/{numbers,dates,demographics,area,metrics,index}.ts scales.ts cluster.ts properties.ts
src/components/ui/               Button Badge AttentionBadge Card Skeleton EmptyState ErrorState MenuButton Drawer Segmented Stat LiveRegion
src/components/charts/           BarList GroupedBarList Dumbbell PercentileBullet IndexBar Sparkline Legend
src/components/map/              maplibre.ts baseStyle.ts useMapLibre.ts MapFrame PortfolioMap AnalysisMap PickMap PreviewMap MapPopup
src/features/properties/         PropertiesToolbar PropertiesTable PropertyList CompareTray
src/features/analysis/           AnalysisPage AnalysisHeader SectionNav SectionShell AnalysisProgress KpiCard TakeawayList useActiveSection sections.ts
src/features/analysis/sections/  Overview TradeArea Daytime Retail Access Risk Market Tenants Ranking Sources (*Section.tsx)
src/features/analysis/admin/     PropertyActionsMenu RecordDrawer (+ moved EditLocation, PinEditor, GeocodeDialog)
src/features/analyze/            AddressSearch CandidateList RecentAnalyses
src/features/alerts/             AlertEvidence.tsx alertText.ts AlertGroup.tsx
src/features/compare/            selection.ts CompareTable.tsx
src/features/tenants/            TenantsPanel.tsx
src/pages/                       PropertiesPage AnalyzePage AlertsPage ComparePage SourcesPage AdminPage NotFoundPage
src/styles/                      tokens.css base.css layout.css components.css charts.css map.css (legacy.css temporary)
```

### F2. Design tokens (`src/styles/tokens.css`; contrast ratios verified)
- Surfaces `--bg #FFFFFF`, `--surface-2 #F8FAFC`, `--surface-3 #F1F5F9`. Text `--text #0F172A` (17.9:1),
  `--text-2 #475569` (7.6), `--text-3 #64748B` (4.8; never on surface-3). Borders `--border #E2E8F0`
  (decorative), `--border-strong #8391A7` (3.2:1, inputs/buttons).
- Accent `--accent #0E6B4F` (6.5:1; white on it 6.5), hover `#0B5640`, press `#094A37`, soft `#E8F3EE`,
  second chart shade `#7DBFA4`; focus = 2 px accent outline, 2 px offset (white inner ring on maps).
- Attention (reserved): High text `#B42318` on `#FEF3F2`, pin `#C81E1E` + white "!"; Watch text `#8A5A00`
  on `#FFFAEB`, pin `#C98500` + dark "!"; Clear text `#475569` on `#F1F5F9`, pin `#64748B`
  (pair validated for colour-blind separation; do not substitute `#D92D20/#DC6803`).
- Change arrows: significant good = accent + arrow, significant bad = `#B42318` + arrow, else `--text-2`;
  metrics without a good direction are never coloured; reliability/stale badges are neutral.
- Type (Inter, then system-ui): 12/16 caption · 13/18 table · 14/20 body · 16/24 sub-heading ·
  20/28 section · 24/32 page · KPI 28/32 w600; tabular numbers in tables; nothing <12 px; inputs 16 px ≤640.
- Spacing 4·8·12·16·20·24·32·48; radius 4 (badges) 8 (cards/inputs/buttons) 12 (maps/drawers) 999 (chips/pins);
  shadows `0 1px 2px /.06`, `0 4px 12px /.10`, `0 12px 32px /.18`; `--topnav-h 56px`, `--rail-w 232px`,
  `--content-max 1120px`, `--map-h clamp(320px,52vh,560px)` (280 px ≤640); breakpoints 1280/1024/768/640;
  light only.

### F3. Data hooks (against the contracts in PART C)
- `src/api/client.ts` absorbs `api`, `ApiError`, `csrfToken`, `allLocations` from `src/api.ts` (no ETag:
  polling happens only while an analysis runs).
- `useAnalysis(id)`: key `["analysis", id]`; TanStack structural sharing keeps unchanged sections
  referentially equal, so memoised sections don't re-render; `refetchInterval = pollDelay(bundle.analysis)`:
  `false` unless `queued|running|partial`; else `poll_after_ms` clamped 1.5–30 s (default 3 s); after 15 min
  stop and show "Still processing · Check again" (refetch only). `refetchIntervalInBackground:false`.
  Section run state comes from `sections[key].status` (`ready|running|pending|unavailable` + `reason`).
- `useAnalysisTransitions`: polite live-region "Retail landscape is ready"; when all ready, invalidate
  `["locations"]`, `["signals"]`.
- Also `useSession`, `useLocations`, `useAnalyses`, `useCreateAnalysis`, `useKeepAnalysis` (optimistic),
  `useSignals(status)`, `useSources`, `useCompare(ids)`.

### WI-1 Shell, router, tokens (no backend dependency)
- Create `src/app/*`, `src/styles/{tokens,base,layout}.css`; move old `styles.css` → `src/styles/legacy.css`
  minus sidebar/topbar/footer rules. `main.tsx` → bootstrap. `backend/templates/application/index.html`
  theme-color `#FFFFFF`. Delete `src/pages/Home.tsx`, `src/ThisWeek.tsx`, `src/Onboarding.tsx`.
- Shell: skip link; header with brand + `nav[aria-label="Main"]` (Properties, Analyze, Alerts, Compare;
  `aria-current`; Properties active on `/p/*`); search button (FR-36, POST `/api/locations/search/`,
  never puts addresses in URLs, offers "Analyze this address"); "Account menu" (Data sources, Admin for
  admins, Sign out POST+CSRF); ≤640 "Open navigation" → Radix dialog "Workspace navigation"; failing-source
  banner kept; focus to `#main` + scroll top only when the *path* changes.
- Interim mapping until later WIs land: `/` → old Portfolio, `/p/:id` → old LocationPage, `/analyze` → old Screen.
- Tests: `tests/router.test.ts` (matching, UUID validation, redirects).

### WI-2 UI kit, formatters, scales, charts (additions only)
- Move formatters into `src/lib/format/*` (from `area.ts`, `demographics.ts`, `Summary.tsx` formatMetric/
  favourable/severityTone, `api.ts` dateLabel/checkedLabel); old files become re-export stubs until WI-9.
  New: `rankText(3,35)` "3 of 35", `rankSentence` "Ranks 3 of 35 owned properties", `perDay`, `indexText`,
  `floodShort`, `distanceMi`.
- `src/lib/scales.ts`: `niceMax`, `pctOf(v,max)` (clamped, zero-based), `indexSpan(index,[50,150])` + overflow flag.
- Charts (`src/components/charts/`): `BarList`, `GroupedBarList` (+Legend, portfolio-median tick), `Dumbbell`
  (before/after on a shared zero-based scale), `PercentileBullet` (0–100 track + median tick, rank text),
  `IndexBar` (diverging from 100, clamped 50–150), `Sparkline` (only when a series exists). Bars ≤24 px, values
  printed, no text in series colours, missing value → reason text, no bar.
- Tests: `tests/format.test.ts` (absorbs area/demographics/summary tests), `tests/scales.test.ts`,
  `tests/charts.test.tsx` via `renderToStaticMarkup` (no jsdom).

### WI-3 Map module
- `useMapLibre(el,{tileUrl,bounds,cooperativeGestures})` → `{map, ready, failed}` (created once; StrictMode-safe).
  `MapFrame`: skip-map link, labelled region pointing to its text alternative, WebGL/tile/disabled messages,
  OSM attribution + privacy line, `data-ready`/`data-pins`/`data-rings` for the smoke test. Base style: OSM
  raster saturation −0.9 on `#F1F5F9`, no glyphs/sprites.
- `PortfolioMap({locations, visibleIds, highlightId, onHover, onSelect})`: markers created once per id; filtering
  toggles `hidden`; debounced re-fit only on filter change; clusters are buttons "4 properties: … Zoom in";
  pins: High 18 px red "!", Watch 16 px amber diamond "!", Clear 12 px slate dot (hit area ≥24 px; hover/focus
  accent ring); one reused React-portal hover card (name, attention, people 3 mi, income, traffic, alerts,
  "Open analysis"); click opens analysis (touch: first tap shows card).
- `AnalysisMap({center, ringMiles, anchors, places, category, flood, layers, onPlaceSelect})`: subject marker;
  ring fills + dashed accent lines; business circles (selected category accent, others faded slate; anchors
  larger; closures hollow red); flood polygon fill when provided; click → popup with source; layer toggles are
  checkboxes outside the map; mounts when scrolled into view.
- `PickMap({initialBounds, draft, onPick})`: map click drops a draggable draft marker + popup "Analyze this
  point" / "Cancel"; keyboard path "Use map center"; default view = portfolio bounds, else US center
  `[-98.58, 39.83]` z3.2. `PreviewMap` replaces `LocationMap` in PinEditor/GeocodeDialog. Delete `src/LocationMap.tsx`.
- Tests: `tests/cluster.test.ts`, `tests/map.test.ts` (base style has no glyphs/sprites).

### WI-4 Properties page `#/`
- `src/pages/PropertiesPage.tsx`, `src/features/properties/*`, `src/lib/properties.ts` (`filterProperties`,
  `sortProperties` — missing values last, `attentionRank`), `src/features/compare/selection.ts` (+`useCompareSelection`).
- Layout: h1 "Properties" with counts (36 owned · N High · N Watch; each count applies its filter) → toolbar
  (search "Search properties", State, Attention, Clear filters, result count; all in URL) → full-width
  `PortfolioMap` + HTML legend → `PropertiesTable`.
- Table: caption "Owned properties"; columns Compare checkbox, Property (row header link + city), State,
  Attention, People within 3 mi, Median household income, Main-road traffic, Flood, Nearest supermarket,
  Active alerts (link to the property's alerts); sortable `th[aria-sort]` buttons; row hover/focus highlights
  the pin; 768–1279 focusable scroll region with sticky first column; <640 card list with "Sort by" select.
- Compare up to 4 (5th disabled, announces "Up to 4. Remove one first."); sticky `aside "Compare selection"`
  tray → "Compare N properties" `#/compare?ids=`. Missing numbers show "—" with hidden "Unavailable".
- Delete `src/pages/Portfolio.tsx`. Tests: `tests/properties.test.ts`, `tests/compare.test.ts`.

### WI-5 Data layer
- `src/api/*` per F3. Fallback only if the bundle endpoint is late: temporary `src/api/legacyAnalysis.ts` that
  assembles the bundle from `/demographics/`, `/area/`, `/summary/` (delete in WI-9).
- Tests: `tests/api.test.ts` (existing CSRF/pagination/error cases), `tests/analysis.test.ts` (`pollDelay`,
  section state mapping, 15-minute stop).

### WI-6 Analysis page `#/p/:id` and `#/analyze/:id`
- `AnalysisPage({id, mode})`; kind mismatch → redirect to the other route; unknown id → NotFound.
- Header: name, address, attention badge, "Data as of …". Property mode: Compare toggle + admin
  "Property actions" menu (Edit details, Correct pin, Find address pin, Record & history — EditLocation,
  PinEditor, GeocodeDialog become controlled dialogs; focus returns to the menu button). Place mode: Star
  (`aria-pressed`), Compare, note "New place · not monitored · removed after 90 days unless starred".
- Section menu: ≥1024 fixed left `nav "Analysis sections"` with status dot per section, `aria-current` via
  IntersectionObserver; 768–1023 sticky chip strip; <768 sticky "Jump to section" select; link → scroll, focus
  heading, `?section=` in URL; deep links work after load.
- `SectionShell({id,title,run,stale,computedAt,sources,skeleton})`: `aria-busy` + layout-sized skeleton while
  running/pending; failure → plain-language reason; stale note (neutral, clock icon); footer "Sources · checked {date}".
- Sections:

| id | Label | Content |
|---|---|---|
| overview | Overview | `AnalysisProgress` while busy; `TakeawayList` (ol "Key takeaways": tone icon+word, text, source·period, link to section); `KpiCard` grid (group "Key numbers", ≤8: value, change, "N of M", source); `AnalysisMap` (rings, anchors, flood toggle); active alerts (property); team notes |
| trade-area | Trade area & demographics | 1/3/5-mi radius-ring table: value ± MOE, neutral reliability badge; ring switch → `IndexBar` vs US (100 = US average) + portfolio rank; `Dumbbell` 2015–19 → 2020–24 with significance; age, tenure, home value, rent rows when present (label "about the area, not this property") |
| daytime | Daytime population | Residents vs workers within each ring; jobs by sector bars (retail, food service, health, office/professional, other) |
| retail | Retail landscape | Business map + category filter; share within 1 vs 3 mi vs portfolio median ("fewer grocery stores than 80% of your centers"); anchors with distances; nearest supermarket; confirmed openings/closures (≤3 months, "Possible … verify"); full list in `<details>` table |
| access | Access & traffic | Road cards: vehicles/day, year, year counted, distance, change or "Estimate carried forward" |
| risk | Risk | Flood card (inside / N m away / zone / BFE) + flood polygon on map; NRI rating + property-damage hazard bars |
| market | Market | County jobs YoY, retail jobs & weekly wage, unemployment vs state (3-mo avg), permits vs prior 12 months |
| tenants | Tenants & SEC watch | `TenantsPanel` restyled (property only) |
| ranking | Ranking vs portfolio | `PercentileBullet`s "Ranks N of M owned properties" (places: "Would rank …") |
| sources | Sources & methods | collapsed `<details>`: every source, period, checked date, caveats, method notes |

- Delete `src/pages/LocationPage.tsx` (RecordEvidence/History → `admin/RecordDrawer.tsx`), `src/TradeArea.tsx`,
  `src/AreaSections.tsx`, `src/Summary.tsx`, `src/PropertyHeader.tsx`, `src/useComputeJob.tsx`.
- Tests: `tests/takeaways.test.tsx`, `tests/kpi.test.tsx`.

### WI-7 Analyze page `#/analyze`
- `src/pages/AnalyzePage.tsx`, `src/features/analyze/{AddressSearch,CandidateList,RecentAnalyses}.tsx`.
- Left panel (360 px ≥1024, stacked below): h1 "Analyze a place"; form "Address" + "Analyze"; hint "or click
  anywhere on the map"; "Recent analyses" (link, date, status chip, star "Keep {name}", 90-day note).
  Right: `PickMap`.
- Flows (PART C): 201 → navigate to `#/analyze/:id` immediately (pin + rings at once, sections fill in).
  Ambiguous → radio list "Choose the matching address" → `POST …/geocode/<lookup_id>/accept/` → navigate.
  No match / geocoder down → message "We couldn't find that address. Click the map to place it." and
  `PickMap` in place-pin mode for the same record → `POST …/pin/` → navigate. Map click → "Analyze this
  point" → `POST /api/analyses/ {lat, lon}` → navigate. 400 (outside US) / 429 → field-level message.
- Remove ScreenPage/ScreenBanner/CompareButton from `src/Acquisitions.tsx`.

### WI-8 Alerts, Compare, Sources, Admin
- Alerts (`src/pages/AlertsPage.tsx`): URL filters Level (High+Watch default; FYI opt-in), Status (Active),
  Category, Property; grouped by property, worst first; county "Market" alerts shown once with the properties
  listed; evidence drawer → `src/features/alerts/AlertEvidence.tsx` (invalidates signals, analysis, locations);
  empty "No High or Watch alerts.".
- Compare (`src/pages/ComparePage.tsx`, `CompareTable.tsx`): `?ids=`; picker groups Properties / Analyzed
  places; sticky first column; best/worst only on rows with a direction (icon + hidden text).
- Sources (`ul "Sources"`) and Admin restyled; "Add a property" moves to Admin.

### WI-9 Cleanup
- Delete `legacy.css`, re-export stubs, `src/components/ui.tsx`, moved modules, merged old tests.
- Grep must find no `Calculate`, `Check area data`, `Confirm your portfolio`, `This Week`, `#/locations/` in `src/`.
- Update `docs/USER_INTERFACE.md`, `docs/MAPS.md`, `docs/DECISIONS.md` (D-033 nav & routes, D-034 charts/map/font,
  D-035 ACS rent/home-value wording vs doc 05 §6.4).

### F4. Cross-cutting UI rules
- Skeletons sized like final layout (no shift; no shimmer under reduced motion). A failed section never blanks
  the page. Empty states say what to do and never show numbers.
- Responsive: 1280 full nav, map + 10-col table, left menu, 4-col KPIs · 768 scrolling table, chip strip, 2-col
  KPIs · 375 hamburger, 280 px map + cards, jump select, 2-col KPIs. `min-width:0` on flex/grid children; only
  tables and chip strips scroll sideways (focusable, labelled).
- A11y: one h1 per page; sections labelled by h2; landmarks header/`nav "Main"`/`main#main`/`nav "Analysis
  sections"`/compare `aside`; WCAG 2.2 focus-not-obscured via `scroll-padding`; targets ≥24 px; dragging
  alternatives (typed coordinates, "Use map center"); every map item also exists as text; colour never the
  only signal; forced-colours borders.

### F5. Browser smoke (rewrite `tests/browser-smoke.mjs`; axe WCAG 2.2 AA + no overflow at 1280/768/375 per page)
- Nav: `nav "Main"` has Properties/Analyze/Alerts/Compare; "Account menu" has Data sources/Admin/Sign out;
  375 "Open navigation" → dialog "Workspace navigation" focus trap + return.
- Properties: heading "Properties"; `.location-map[data-ready=true][data-pins="35"]` (36 once P21 is pinned);
  table "Owned properties" has 36 rows; sort sets `aria-sort`; State=CT puts `state=CT` in the URL; two
  "Compare …" ticks → "Compare 2 properties" opens Compare.
- Analysis: heading = property name; "Analysis sections" has 10 links; "Key takeaways" or "Analysis progress"
  visible; **no button matching `/calculate|check area data|confirm/i`**; "Property actions" dialogs; port the
  notes/concurrent-edit/pin-drag/Census tests.
- Analyze: heading "Analyze a place"; map click shows "Analyze this point"; stars work. Alerts: High & Watch
  checked by default. Sources: 16 items. Old routes redirect. Tiles aborted → "Basemap tiles unavailable." and
  `data-pins` unchanged. No requests leave the origin except the tile server. Anonymous API → 403.
- Smoke DB has seeds but no computed data: assert loading/progress states, never data values.

---

## Needed from Adi
1. **BLS API key** (free, 2 minutes): register at https://data.bls.gov/registrationEngine/, then put
   `BLS_API_KEY=…` into `/etc/paragon/app.env` on the droplet (same way as the Backblaze keys). Without it the
   server is limited to 25 unemployment lookups a day, which new-place analyses would exhaust.
2. **Backblaze keys** in `/etc/paragon/backup.env` (instructions already given): needed for nightly backups
   and to store the original Overture archive off the server (B2 step 4).
3. **P21 pin check** when B2 runs: confirm which Census candidate is the Bareburger building at
   445 Main St, Mount Kisco (one click in the new property menu).

## Verification (end to end)
- **Every PR:** `uv run python -m pytest -q` (backend), `npm test` + `npm run build` (frontend), the rewritten
  browser smoke with axe WCAG 2.2 AA at 1280/768/375 for frontend PRs; acceptance numbers in the PR body.
- **Concurrency:** analysis tests also run on Postgres (`make test-postgis`, `config/settings/postgres_test.py`).
- **Data quality:** `python backend/manage.py qa_report --strict` exits 0 on the preview and on production;
  golden values in `config/qa_golden.yaml` hold.
- **Speed (on the droplet):** new script `scripts/verification/analysis_timing.py` — 10 addresses in ≥5 states,
  via `POST /api/analyses/` then polling the bundle: first section ≤10 s, complete median ≤30 s, p95 ≤60 s;
  owned-property bundle <500 ms p95.
- **Memory (on the droplet):** `docker stats` peak during the US extract build, ACS all-states ingest and
  4 parallel analyses: app container ≤1.1 GB, no OOM kills, swap-in minimal.
- **Alerts:** preview active alerts ≤15 after B7a; production ≤10 after B2; `docs/ALERT_QUALITY.md` shows
  ≥80% judged useful on ≥20 reviewed alerts.
- **Production walk-through (browser):** Properties shows the map (36 pins) and 36 table rows with key
  numbers; every property analysis is complete with no compute buttons anywhere; Analyze: an address in a
  new state and a map click both produce a full analysis that fills in progressively; Alerts grouped with
  next steps; Compare 2–4; Data sources; Admin access log.

## Risks and mitigations
- **2 GB memory:** B0 baseline; 3–4 threads; `max_rss` recycling; DuckDB capped at 512 MB; batched ACS;
  no in-memory LODES cache; filtered ACS loads; heavy work only on the maintenance queue.
- **Overture extract infeasible or schema change:** spike gate, row-count validation, keep last good
  extract, fall back to S3 scans.
- **Thread/DB bugs:** serial on SQLite, Postgres tests, close each thread's connection; duplicate snapshots
  are already tolerated.
- **Runaway jobs:** `ensure_analysis` row lock, attempt cap, global cap, sweep ≤2 per tick, bulk work on the
  background queue.
- **Source limits:** BLS key + batching; resumable night-time Census downloads.
- **ACS 2021–2025 in December:** the switch stays all-or-nothing (`current_acs_year`); B8 lands first so the
  all-states ingest runs once with the full table set.
- **Privacy:** outbound host allowlist, local NRI table and local places extract; OSM tiles remain the only
  third-party request from browsers.
