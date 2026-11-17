# 05 · Experience Requirements

**Purpose:** Define the workflows, information hierarchy, essential screens and quality bar. **Visual design, layout details, component choices and branding belong to the implementing agent.** This document defines outcomes, not pixels.

## 1. Experience principles
1. **Answer first, evidence one click away.** Lead with what changed and why it matters. The supporting numbers, source and period sit directly behind it.
2. **Calm, executive-grade, map-forward.** A busy owner should understand any screen in 10 seconds. A few strong elements beat many charts. Visual polish matters: this should feel like a premium tool, not an admin panel.
3. **Honest by design.** Uncertainty, staleness and gaps are visible and plainly worded, never hidden.
4. **Portfolio as the yardstick.** Wherever a number appears, show how it compares with Paragon's own properties.
5. **Few clicks.** The Monday review is about 3 minutes; a screen with evidence summary is under 5 minutes.

## 2. Information architecture

Primary navigation (desktop: persistent; phone: compact):
1. **This Week** (home): the brief.
2. **Portfolio**: map and list of owned (and optionally candidate) locations.
3. **Screen**: address search into a profile, plus the saved candidates list.
4. **Compare**: comparison workspace.
5. **Data Sources**: sources, freshness and status.
6. **Admin** (admins only): users, job runs, tenant-to-SEC mapping, settings (ring presets, thresholds read-only in P0).

Global search (FR-36) is always available.

## 3. Essential screens

| Screen | Must show (in priority order) | Key interactions |
|---|---|---|
| **SCR-1 This Week** | Headline ("N items need attention across M properties", brief date, or "Baseline" or "No material changes"); ranked signal cards (doc 04 §5.4) showing severity, property, what changed, why it matters, data period; collapsed FYI items; "Sources updated since last brief"; link to past briefs | Open evidence; open property; (P1) mark reviewed or dismissed; (P1) "useful?" |
| **SCR-2 Portfolio** | Map with all locations colored or marked by attention level; list or table with name, city/state, type, attention, 3-mi population, 3-mi mean HH income, population trend, confirmed badge; filters | Click marker or row to open the profile; filter; add location; confirm or archive (bulk confirm on first run) |
| **SCR-3 Location profile** | Header (name, address, status, attention, pin method, "check the pin" prompt if unverified); **Summary** (active signals plus evidence summary); then sections in FR-08 order. Map with pin, rings and nearby businesses by category group. Each section shows its data period and last-checked date. | Drag the pin (with confirm); switch ring preset; open evidence; toggle map layers; add to compare; save as candidate (screens); edit attributes and tenants |
| **SCR-4 Screen** | Address input with autocomplete if the geocoder supports it (otherwise a submit button); recent screens; saved candidates. The result is SCR-3 in "unsaved" mode with progressive loading. | Save as candidate; compare |
| **SCR-5 Compare** | Columns: 2–4 locations plus portfolio median and range; rows grouped (Trade area, Economy, Retail, Access, Hazards, Signals); the evidence summary per location at the top | Add or remove locations; open cell evidence; (P1) print or export |
| **SCR-6 Evidence drawer/panel** | All fields in doc 04 §6.1 | Open source link; view contributing records |
| **SCR-7 Data Sources** | Per source: purpose, coverage, licence and attribution, data period, last check, next expected, status; recent incidents (e.g. "Overture broad data change") | Admin: re-run job |
| **SCR-8 Admin** | Users and roles; job run log; tenant-to-SEC mapping with suggestions; settings | Invite or remove; re-run; map or unmap |
| **SCR-9 Sign-in** | Product name; sign-in method; "invite only" note | n/a |

## 4. Quality bar

- **Accessibility:** WCAG 2.2 AA. Full keyboard operation; visible focus; color never the only carrier of meaning (severity carries a text label or icon too); text alternatives for map and chart content (e.g. the list view mirrors the map); contrast ≥ 4.5:1; screen-reader labels on controls; respect reduced motion.
- **Responsive:** desktop ≥ 1280 px is primary. Tablet 768 px and phone 375 px must fully support This Week, the profile summary, evidence and Portfolio. On phones, Compare may scroll horizontally **inside** its table container, never the whole page.
- **Loading:** a skeleton for every section. Progressive profile loading: geocode and pin first, then trade area, then the rest. Show which source is still loading. Time out into an error state per doc 06 §5.
- **Errors:** plain language, what still works, what the system will do (retry), with no stack traces. A failed source never blanks the whole page.
- **Empty states:** a first-run portfolio ("36 properties imported from your public website: please confirm"), no tenants ("Add tenants to enable tenant watch"), no signals ("No material changes"), no candidates ("Screen an address to start"). No fake or sample numbers in any empty state.
- **Performance perception:** the cached profile is interactive within 2 s (doc 06 §5).
- **Units and formatting:** US formats; currency with $ and thousands separators; percentages to one decimal; distances in miles to one decimal; dates like "Nov 17, 2026"; data periods exactly as defined in doc 04 §4.

## 5. Map
- Base map tiles from a provider whose licence allows this use, with attribution displayed (FR-33). The implementing agent chooses the provider.
- Layers: pin; rings; nearby businesses by category group (clustered); (P1) FEMA flood overlay; optional contributing block groups.
- Clicking a business shows its details (doc 04 §6.2). Closed or possibly-closed places are visually distinct.

## 6. Presenting uncertainty and avoiding misleading conclusions
1. Show MOE (±) or a reliability badge with every ACS value. Use tooltips or legends that explain it in one sentence.
2. Trends always name both periods ("2015–19 → 2020–24") and say whether the change is statistically significant.
3. Labels on every value: Estimate, Reported, Modelled, Map data, User-provided or Possible (doc 04 §8).
4. Area and company indicators carry an "about the area, not this property" note in the evidence. Never use the words vacancy, occupancy, rent or value for external data.
5. Signals from map data say "Possible … verify."
6. Comparison highlighting applies only to directional metrics. Neutral metrics are never colored as good or bad.
7. Percentiles always state the base ("of your 31 properties").
8. Do not use dramatic chart scaling (e.g. truncated axes that exaggerate small changes) or red/green on small, non-significant changes.
9. Stale or failed data is visibly marked wherever it is shown, not only on the Data Sources page.
