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
