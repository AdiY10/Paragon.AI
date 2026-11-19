# Next tasks: batch plan for an implementing agent

**Written:** 2026-11-19 · **Starting point:** `main` after PR #41 (ring jobs) is merged.
**Purpose:** a self-contained, ordered set of tasks an agent can run in one go. Each task has scope, dependencies, files, acceptance criteria and verification, so the agent doesn't need to ask what to do next.

Read first: [`AGENT_HANDOFF.md`](../AGENT_HANDOFF.md) (non-negotiables, blocker format), [`docs/02`](02_PRODUCT_REQUIREMENTS.md) (FRs and ACs), [`docs/04`](04_DATA_AND_INSIGHT_REQUIREMENTS.md) (signal rules, evidence summary, missing-data codes), [`docs/RING_DEMOGRAPHICS.md`](RING_DEMOGRAPHICS.md) and [`docs/AREA_PROFILE.md`](AREA_PROFILE.md) (what already exists).

---

## Where things stand

**Built and merged:** auth, jobs and schedules framework, source snapshots and health, locations and pins, portfolio map, plus six property-page data sections, each stored as immutable results keyed by `analysis_version`:

| Section | Backend | API |
|---|---|---|
| Ring demographics and trends (MET-01–07) | `apps/demographics` | `/api/locations/<id>/demographics/` |
| Economy, traffic, hazards, businesses, ring jobs (MET-08–18) | `apps/area` (`AreaSection` rows) | `/api/locations/<id>/area/` |

**Not built yet (this plan):** source-health wiring for the new adapters, scheduled refreshes, portfolio percentiles and evidence summary, the signal engine, the This Week brief, attention levels, screening and comparison, SEC tenant watch, hardening and deployment.

**Parallel work by Amit's agent:** the tenant roster. Its domain model is merged, and `origin/feat/tenant-roster-domain` plus a stash on `feat/tenant-seed-and-api` hold the API and seed work. Do not rebuild it. T10 checks its status first.

---

## How to run this batch

1. Work **in order** (later tasks depend on earlier ones), **one branch and one PR per task**, named `feat/<task-id>-<slug>`, based on the latest `main`.
2. For every task:
   - Run the full suite: `uv run python -m pytest -q` and `npm test --prefix frontend`.
   - Verify on real data, not only fixtures: record real responses as fixtures under `tests/fixtures/real/…`.
   - Check every UI change in a browser at 1280 px and 375 px, with no page-level horizontal overflow.
   - Update the relevant `docs/*.md` and append a short entry to `progress.md`.
3. **Merging:** open each PR and continue to the next task on a branch stacked on the previous one. Do not merge unless Adi has said merging is fine for this batch.
4. **Never fabricate data.** Missing or failed values use the reason codes in `docs/04` §7. No sample numbers in the UI.
5. **Blockers** (credentials, hosting, payment, product decisions): finish all unaffected tasks, then report using the BLOCKER format in `AGENT_HANDOFF.md` §7.
6. **Stop condition:** all tasks done, or only blocked tasks remain. End with a summary listing each PR, what it verified, and open blockers.

**Local preview with real data:** build a SQLite preview DB (see the setup in `scripts/verification/ui_smoke.py`), import the seed, run `ingest_acs --year 2024` and `--year 2019`, then `import_overture_captures --directory var/overture-archive` and `compute_area_profile`. Note that `var/overture-archive` exists only on Adi's machine; elsewhere, sections capture on demand.

---

## Batch A: from data to insight

### T1 · Source health for all area adapters
- **Why:** the Data Sources page (FR-30, FR-31) shows health only for sources that call `record_check`. The new adapters (SRC-03–13 via `apps/area`, `apps/demographics`) mostly don't.
- **Do:**
  - Call `apps.sources.health.record_check` for every fetch in `apps/area/service.py` (`Run.cached`) and `apps/demographics/service.py`, on both success and failure, with a sanitized error code.
  - Use stable scopes, e.g. `qcew:{fips}`, `hpms:{pin}`, `lodes:wac:{st}:{year}`.
  - On failure, keep the last good snapshot.
  - Show "stale" and "failing" badges on the property-page sections when their source health says so.
- **Acceptance:**
  - (a) After computing a location, the Data Sources page shows a last check and status for SRC-03, 04, 05, 06, 07, 09, 10, 11, 12 and 13.
  - (b) Fault injection (an opener raising `OSError`) marks the scope Failing, and the section still shows the last good values with their date (AC-21).
- **Tests:** health rows created on success and failure; a stale badge appears in the API payload when `last_success_at` is older than the source's `stale_after_days`.

### T2 · Scheduled refresh handlers
- **Why:** `config/schedules.yaml` defines `annual_sources_check`, `bls_bps_check`, `overture_check` and `flood_recheck`, but they have no handlers, so data never refreshes by itself (doc 06 §4.1).
- **Do:** implement each handler in `apps/operations/registry.py`. Each must be idempotent, call `context.heartbeat()`, and recompute affected sections only for **monitored** locations (Owned plus Candidate, not archived, with a pin).
  - **`bls_bps_check`** (weekly): detect a new QCEW quarter, LAUS month or BPS month, then recompute `economy`.
  - **`overture_check`** (weekly): detect a new release in the bucket, capture all monitored pins (reuse `apps/area/overture.capture`), then recompute `businesses`. Captures must be stored before older releases expire.
  - **`annual_sources_check`** (monthly): detect a new ACS vintage (bulk-file existence), LODES year, HPMS year or NRI version, then ingest and recompute `demographics` and `jobs` / `traffic` / `hazards` as relevant.
  - **`flood_recheck`** (monthly): recompute `hazards`.
  - Enable these schedules. Leave `sec_daily` and `brief_weekly` for T9 and T5.
- **Acceptance:**
  - Admin "rerun" executes each handler.
  - A fixture where a newer period appears triggers recomputation exactly once.
  - Running again with no new period does nothing (no new rows).
- **Tests:** fixture openers per source; schedule definitions validate; no network in tests.

### T3 · Portfolio percentiles and evidence summary (MET-20, FR-16, FR-26)
- **Do:**
  - Add `apps/insights` (or similar) computing, for each comparable metric on the **3-mile ring** (or county / road level where that is the metric's geography), the percentile against non-archived **Owned** locations that have a value.
  - Formula and the n ≥ 5 rule are in `docs/04` §4 MET-20.
  - Directional metrics:
    - population, households, median and mean income
    - population and real-income change (significant only)
    - ring jobs and jobs change
    - primary-road AADT
    - county private and retail job YoY, unemployment change (lower is better), permits change
  - Build the **Evidence summary**: up to 5 strengths and 5 concerns using `docs/04` §6.3, plus hazard concerns (SFHA, NRI Relatively High or Very High) and active High or Watch signals once T4 exists.
  - Expose `GET /api/locations/<id>/summary/`.
  - Add a **Summary** panel at the top of the property page, and "higher than X% of your N properties" next to metrics.
- **Acceptance:**
  - AC-12: a fixture portfolio with known values gives the expected percentiles; with n < 5 the UI says "needs at least 5 confirmed properties".
  - AC-19: strength and concern templates cite the percentile and source.
  - Very-low-reliability or non-significant values are never used.
- **Note:** recompute percentiles whenever any owned location's section result changes (cheap: read stored rows).

### T4 · Signal engine (FR-19, FR-20)
- **Do:**
  - Add a `Signal` model: `rule_id`, `location`, `subject_key`, `severity` (High / Watch / FYI), `direction`, `evidence` (JSON with inputs, thresholds, periods, source links), `first_detected_at`, `status` (active / resolved / expired), `resolved_reason`.
  - Rules are deterministic, with thresholds in configuration (`config/signals.yaml`), from `docs/04` §5.2:
    - SIG-01, 02 (demographics trends)
    - SIG-03, 04, 05, 07 (economy section)
    - SIG-06 (jobs section)
    - SIG-08 (traffic section)
    - SIG-09, 10 (businesses section `changes`)
    - SIG-11 (hazards)
    - SIG-12, 13 come in T9.
  - Evaluate after every section computation. Key signals by `(rule_id, location, subject)`. Apply the resolve and expire lifecycle and the guards in §5.3. A pin move resolves location-based signals with "location corrected".
  - Add `attention_level` to the location API (highest active severity).
- **Acceptance:** AC-15. For each rule: at threshold fires, just below doesn't, clearing resolves, the guard suppresses. Real data: Cypress Lake gets SIG-11 High; the Kingston Sep → Oct Regal fixture gets SIG-09 Watch.
- **UI:** a signals list in the property Summary panel with an evidence drawer.

### T5 · This Week brief (FR-21) and attention on the portfolio (FR-35)
- **Do:**
  - Add a `Brief` model and a `brief_weekly` handler (Monday 07:00 US Eastern, plus an admin "generate now").
  - Composition and ranking per `docs/04` §5.4: new or escalated signals since the previous brief, still-active High signals, sources updated since the last brief, and the "No material changes" empty state. The first brief is titled "Baseline: current conditions".
  - Replace the "Weekly brief unavailable" home card (SCR-1) with the brief. Keep past briefs viewable.
  - Show attention-level markers and filters on the Portfolio map and list.
- **Acceptance:** AC-16 and AC-24. A real-data baseline brief lists Cypress Lake's flood signal. With no new signals the empty state shows, still listing sources updated.

## Batch B: acquisitions

### T6 · Screen a location (FR-25)
- **Do:**
  - Add a **Screen** page (SCR-4): address input, then geocode preview (reuse the existing Census flow and manual pin), then a full profile with progressive loading. Demographics, area sections and summary each enqueue their job and poll; reuse `TradeArea` and `AreaSections`.
  - Screens are **not monitored** until "Save as candidate". Add a `screening` status, or an `unsaved` flag excluded from schedules and the brief, and expire unsaved screens after 30 days.
  - Add a recent-screens list.
- **Acceptance:** AC-18. A new US address shows core demographics within the doc 06 §5 target and the rest progressively. Saving moves it to Candidate and it starts being monitored.

### T7 · Compare (FR-27)
- **Do:** a **Compare** page (SCR-5) for 2–4 locations (owned, candidate or screen), plus **portfolio median** and **range** columns.
  - Rows are grouped: Trade area, Jobs, Economy, Access, Hazards, Businesses, Signals.
  - Use the same ring set; for mixed presets use the 3-mile ring.
  - Highlight only directional metrics; every cell opens its evidence.
  - Add "Add to compare" buttons on profiles. P1: a print-friendly layout.
- **Acceptance:** AC-20, and no page-level overflow at 375 px (the table may scroll inside its container).

## Batch C: tenants and SEC (coordinate with Amit's agent)

### T8 · Tenant roster: check status before building
- First check whether Amit's agent has merged the tenant roster API and UI. Look at `main`, `origin/feat/tenant-roster-domain` and `progress.md`.
- **If merged:** skip to T9.
- **If not:** report it as a BLOCKER ("tenant roster API/UI owned by Amit's agent"), skip T9, and continue with T10. **Do not duplicate it.**

### T9 · SEC tenant watch (FR-22, SIG-12, SIG-13)
- **Depends on:** a tenant roster API.
- **Do:**
  - Map tenants to SEC filers. Show admin suggestions from the EDGAR company list; a suggestion is never applied automatically.
  - Add a `sec_daily` handler reading `data.sec.gov/submissions/CIK##########.json` with the `SEC_USER_AGENT` env var (fail as `NOT_CONFIGURED` if it is missing), at most 5 requests per second.
  - Raise SIG-12 for Item 1.03 and SIG-13 for Items 2.05 / 2.06, within 90 days, for every property listing the tenant.
  - List past events (last 5 years) in the Tenants section with filing links.
- **Acceptance:** AC-17. Rite Aid (CIK 84129) shows the 2023-10-16 Item 1.03 filing as a past event; a fixture filing dated within 90 days creates a High signal.
- **Prerequisite from Adi:** a contact email for `SEC_USER_AGENT`.

## Batch D: release readiness

### T10 · Hardening and acceptance pass
- Extend `scripts/verification/ui_smoke.py` to cover every new section, Summary, the brief, Screen and Compare. Run axe (WCAG A/AA) and check 375, 768 and 1280 px.
- Run the real PostGIS suite (`docs/DATABASE_TESTING.md`).
- Measure the doc 06 §5 performance targets.
- Run a data-integrity check: every rendered number has a source and a period (AC-25).
- Write `docs/TEST_REPORT.md` listing each P0 acceptance criterion with pass/fail and evidence.

### T11 · Deployment and data transfer (needs Adi)
- **Blocked** on the hosting decision. The password-protected, regular-hosting setup already exists (`render.yaml`, `docs/DEPLOYMENT.md`).
- **When unblocked:**
  - Deploy the web app **and a running job worker**.
  - Run `sync_sources`, the seed import, `ingest_acs` for 2024 and 2019, and `import_overture_captures` (copy `var/overture-archive` from Adi's machine, about 1.3 GB of captures).
  - Run `compute_area_profile` for all locations and generate the baseline brief.
  - Deliver `docs/TESTING_GUIDE.md` and `docs/DELIVERY_REPORT.md` per `AGENT_HANDOFF.md` §8.
- **Minimum action from Adi:** a host account or approval and budget; a password or sign-in decision; a contact email for SEC; a decision on where the Overture archive is uploaded.

---

## Dependency map

```
T1 health ─┐
T2 refresh ┼─> T4 signals ─> T5 brief + attention
T3 percentiles + summary ─┘        │
T6 screen ─> T7 compare            │
T8 tenant check ─> T9 SEC watch ───┘ (adds SIG-12/13 to brief)
all ─> T10 hardening ─> T11 deploy (blocked on Adi)
```

Suggested batches: **A (T1–T5)** gives a working This Week brief. **B (T6–T7)** delivers the acquisition workflows. **C (T8–T9)** depends on Amit's tenant work. **D** is last.

---

## Kickoff prompt (copy and paste to the agent)

```text
You are continuing Paragon Radar in this repository. Read AGENT_HANDOFF.md (non-negotiables and the BLOCKER
format), then docs/NEXT_TASKS.md, then the docs it links. Execute docs/NEXT_TASKS.md tasks in order, starting with
<FIRST TASK, e.g. T1> and continuing through <LAST TASK, e.g. T5>.

For each task: branch from the latest main (or stack on the previous task's branch if it is not merged yet), implement
it fully, verify on real data (record real responses as fixtures; no fabricated or sample values), run the full
backend and frontend test suites, check UI changes in a browser at 1280px and 375px, update the docs and progress.md,
commit, push, and open one PR per task. Do not merge PRs unless I say so.

Resolve routine problems yourself. If something needs credentials, payment, hosting or a product decision, finish
all unaffected tasks, report it in the BLOCKER format, and move on. Do not duplicate the tenant roster work owned by
Amit's agent (task T8 explains how to check). When done, give a summary: each PR link, what it verified, test
counts, and any blockers.
```
