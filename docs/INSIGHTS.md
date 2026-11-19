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
`backend/apps/insights/signals.py` derives signals only from stored section results. Thresholds live in `config/signals.yaml`, which holds the docs/04 §5.2 defaults (configuration, to validate with John).

| Rule | Source section | Fires when (defaults) | Severity |
|---|---|---|---|
| SIG-01 | Demographics (3 mi) | Population change is significant and abs ≥ 3% | Watch if down, FYI if up |
| SIG-02 | Demographics (3 mi) | Real income change is significant and ≤ −5% or ≥ +5% | Watch / FYI |
| SIG-03 | Economy | County private jobs YoY ≤ −2% or ≥ +3% | Watch / FYI |
| SIG-04 | Economy | County retail jobs YoY ≤ −4% | Watch |
| SIG-05 | Economy | Unemployment up ≥ 1.0 pt vs a year earlier (preliminary flagged) | Watch |
| SIG-06 | Jobs (3 mi) | Jobs change ≤ −5% or ≥ +5% (both years ≥ 1,000) | Watch / FYI |
| SIG-07 | Economy | Permits ±25% and ±50 units vs prior 12 months | FYI |
| SIG-08 | Traffic | Main-road AADT ≤ −10% or ≥ +10%, same route | Watch / FYI |
| SIG-09 | Businesses | Possible closure (severity from the closure rules, tenant match → High) | per item |
| SIG-10 | Businesses | New key business | FYI |
| SIG-11 | Hazards | Pin in a Special Flood Hazard Area → High; one within ~100 m → Watch | High / Watch |
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
