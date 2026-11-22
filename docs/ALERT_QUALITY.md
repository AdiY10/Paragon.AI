# Alert quality review (redesign B7a/B7b)

Goal: an alert is worth John's time only if it reports a **real, recent change** that a property owner
can **act on**. Target: at least 80% of alerts judged useful. This review covers every alert the rules
produced on the real 35-property portfolio (preview data, 2026-11-19 to 2026-11-22). It is Claude's
assessment against that standard; John's "useful / not useful" feedback in the app
(`GET /api/admin/alert-quality/`) replaces it as it accumulates.

## 1. The rules before the re-scope: 95 active alerts

| Rule | Alerts | Judgement | Why |
|---|---|---|---|
| SIG-01 population change (3 mi) | 10 | Not useful as alerts | A 5-year census trend, not a change since last month; belongs in the analysis. |
| SIG-02 real income change | 4 | Not useful as alerts | Same: slow 5-year trend. |
| SIG-03 county private jobs | 3 (1 FYI rise) | Partly | A single county figure; rises are not actionable. |
| SIG-04 county retail jobs | 1 | Partly | Single county figure. |
| SIG-05 county unemployment | 11 | Not useful one by one | One preliminary 1.0-pt rise in western Connecticut flagged 11 properties separately. |
| SIG-06 jobs within 3 mi | 5 | Not useful as alerts | Annual LODES change; context. |
| SIG-07 housing permits | 23 | Not useful | Mostly FYI; permits are context, not a property risk. |
| SIG-08 main-road traffic | 2 | Mixed | See §3: one is real, one compared counts 11 years apart. |
| SIG-09 possible closures | 3 | Mixed | Two unconfirmed or non-anchor closures; one confirmed anchor (Walgreens). |
| SIG-10 new businesses | 26 | Not useful | Map-data additions, not openings; never actionable. |
| SIG-11 inside a flood zone | 7 | Not useful as alerts | A standing condition, not a change; now a risk badge on the analysis. |
| **Total** | **95** | **≈ 5 useful (≈ 5%)** | |

## 2. After B7a + B7b

Rules that remain: SIG-08 traffic decline, SIG-09 anchor/grocer closure or the tenant's own store,
SIG-11 flood **zone change**, SIG-12/13 tenant SEC filings, SIG-14 competing grocer (confirmed across two
releases, only for centers with a grocer of another brand), SIG-15 one county alert when at least two
economic conditions hold or private jobs fall ≥4%. Every alert carries a next step.

Preview, 2026-11-22: **2 alerts**.

| Alert | Evidence | Judgement |
|---|---|---|
| Watch · Locust Retail · Possible closure nearby: Walgreens (0.2 mi) | Marked permanently closed in the Nov 2026 Overture release; a pharmacy anchor 0.25 mi away | Useful: an anchor near the center; next step is to confirm and review co-tenancy. |
| Watch · Wadsworth Plaza · Traffic on Wadsworth Av −21.2% (counts 2022 → 2025) | 11,148 → 8,780 vehicles/day, two real counts three years apart | Useful: a real measured decline on the road that serves the center. |

Production, 2026-11-22 (before B7b was deployed): 6 alerts — the two above, the 2014 → 2025 Birch St
comparison (now excluded, §3) and three single-figure county alerts that SIG-15 replaces.

**Judged useful: 2 of 2 (100%)** on the current rules. The sample is small because the portfolio is
quiet this month; quality is tracked per rule from reviewer feedback from here on.

## 3. Changes made because of this review
- **Traffic (SIG-08)**: the Birch St alert compared a 2014 count with a 2025 count but was labelled
  "(2024–2025)". Traffic alerts now need two counts at most 5 years apart, and titles show the count
  years ("counts 2022 → 2025").
- **County figures (SIG-15)**: one alert per county, only when at least two of private jobs ≤ −2%,
  retail jobs ≤ −4%, or unemployment up ≥ 1 pt beyond the state hold (or private jobs ≤ −4%). A single
  preliminary unemployment rise no longer flags eleven properties.
- **Closures (SIG-09)**: only anchors or grocers within 1 mile, or the tenant's own store.
- Titles use a real minus sign.

## 4. How to keep it honest
- Reviewers mark each alert **Useful / Not useful** in the alert drawer.
- `GET /api/admin/alert-quality/` gives per rule: total, useful, not useful, precision.
- Any rule below 80% precision over 10+ judged alerts gets its threshold revisited in
  `config/signals.yaml` (configuration, not code).
