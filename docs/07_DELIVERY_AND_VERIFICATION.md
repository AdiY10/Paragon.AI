# 07 · Delivery and Verification Plan

## 1. Milestones (dependency order)

Each milestone ends with its tests passing and is committed. Deploy early (from M1) and keep the deployed app working.

| M | Milestone | Includes | Exit check |
|---|---|---|---|
| **M0** | Foundations | Repo structure, stack choice (documented), hosting, database, auth with an invite flow, CI, `.env.example`, secrets in the platform store, empty deployed app at an HTTPS URL | Signed-in "hello" page live; AC-01 and AC-02 |
| **M1** | Locations and geography core | Seed import (FR-04); geocoding chain plus manual pin (FR-05); location CRUD and tenants (FR-06, FR-07); ring engine with block-weighted apportionment (doc 04 §3.3); ACS ingestion for 2 vintages; **snapshot the currently available Overture releases right away** (doc 04 §5.5) | AC-03 to AC-06; reference values V1, V4 to V6 |
| **M2** | Source integrations | QCEW, LAUS, CPI, LODES, BPS, HPMS, NFHL, NRI, Overture (snapshot plus diff), SEC; run log; source status | Each source returns real data for 3 test locations; V7 to V17 |
| **M3** | Profile and portfolio UI | SCR-2, SCR-3, SCR-6, SCR-7; evidence for every value; missing-data states; freshness badges; attribution | AC-08 to AC-14, AC-21, AC-23, AC-24 |
| **M4** | Signals, brief and tenant watch | Signal engine with all rules; guards; lifecycle; baseline run; SCR-1; tenant-to-SEC mapping (SCR-8) | AC-15 to AC-17 |
| **M5** | Screen and compare | SCR-4, SCR-5; evidence summary; portfolio percentiles | AC-12, AC-18 to AC-20 |
| **M6** | Hardening | Accessibility pass, responsive pass, performance targets, failure injection, backups, alerts, security review | AC-22, AC-25; doc 06 §5 targets |
| **M7** | Production verification and handoff | Full job run on production; E2E suite against production; Adi's testing guide; limitations list; delivery report | §6 "Ready for Adi to test" |
| M8 (optional) | P1 items | FR-23, 24, 28, 29, 34, 37 | Their own ACs |

## 2. Prerequisites and external dependencies

| Item | Needed by | Who | Blocking? |
|---|---|---|---|
| Write access to this GitHub repo for Amit (and his agent) | M0 | Adi adds Amit as a collaborator | Yes |
| Hosting, database and job-runner accounts (and payment, if beyond free tiers) | M0 | Amit or Adi, on Adi's decision | Yes, if paid |
| Auth provider account (if external) | M0 | Amit | Usually free |
| Adi's email address for the test account | M7 | Adi gives it to Amit directly (not in the repo) | Yes, for M7 |
| `SEC_USER_AGENT` contact email | M2 | Adi or Amit | Yes, for SEC in production |
| BLS API v2 key (free) | M2 | Amit | No (v1 is keyless) |
| Census API key (free) | M1 | Amit | No (bulk files need no key) |
| Map tile provider key (if needed) | M3 | Amit | Depends on provider |
| Email provider (P1) | M8 | Amit | No |
| John's confirmation of the portfolio and tenants (Q-01, Q-05) | After M7 | Adi asks John | **No**; build with unconfirmed seed data |
| Domain name (optional) | M7 | Adi | No |

## 3. Risks and mitigations

| ID | Risk | Likelihood / impact | Mitigation |
|---|---|---|---|
| R-01 | The public portfolio list is outdated (sold or unlisted properties) | High / Med | Unconfirmed flags; easy confirm, edit and archive; ask John (Q-01) |
| R-02 | Few genuinely "new" weekly changes, so the brief feels empty | High / Med | Honest empty state; daily SEC data; Overture monthly; "sources updated" section; tune thresholds with John |
| R-03 | Overture noise (data additions or removals that look like real-world change) | Med / Med | "Possible… verify" language; artifact guard; confidence thresholds; ignore null→open |
| R-04 | Overture deletes older releases | High / Med | Snapshot every release we use; take the first snapshot at project start |
| R-05 | FEMA NFHL service unreliable | High / Low-Med | Envelope queries, retries, 30-day cache, stale labels; bulk-download fallback |
| R-06 | Geocoding inaccuracy (street interpolation, no-match) | Med / Med | Fallback chain; "check the pin" prompt; draggable pin; recompute on move |
| R-07 | ACS margins of error mislead users | Med / Med | Reliability badges, significance tests, exclusion of very-low-reliability values |
| R-08 | Connecticut geography change breaks trends | High (for CT) / Low | `GEOGRAPHY_CHANGED` state; match by location |
| R-09 | Source schema or URL changes (Overture schema, BLS paths, HPMS service names) | Med / Med | Schema checks that fail closed; configurable endpoints; alerts |
| R-10 | Government release delays (e.g. ACS 2020–24 published Jan 2026, later than the usual December) | Med / Low | Data-period labels; no assumptions about release dates |
| R-11 | Users read area indicators as property performance | Med / High | Labels and guardrails (doc 04 §8, doc 05 §6) |
| R-12 | Tenant-to-SEC mismatches (brand vs legal entity) | Med / Med | Admin-confirmed mappings; suggestions are never auto-applied |
| R-13 | Scope creep delays delivery | Med / High | P0 first; P1 only after §6 is met; extensions per AGENT_HANDOFF §5 |
| R-14 | Long-running Overture jobs exceed host limits | Med / Med | Choose a suitable job runner (doc 06 §4.2); per-location batching |
| R-15 | Low adoption by a busy CEO | Med / High | Brief-first home; email digest (P1); 3-minute review design |

## 4. Unresolved questions
See doc 01 §5 (Q-01 to Q-12). None blocks Release 1. Record any new product decision in `docs/DECISIONS.md` (created by the implementing agent) with date and rationale.

## 5. Test plan

### 5.1 Unit tests (fixtures, deterministic)
- Ring apportionment: synthetic blocks and block groups with known answers; the 0-population block-group fallback.
- MOE aggregation, ratio MOE, the significance test, reliability classes (doc 04 §4).
- Median interpolation from brackets, including the open-ended top bracket.
- CPI adjustment.
- Portfolio percentile with ties, n < 5.
- Every signal rule SIG-01 to SIG-13: at, above and below the threshold; resolution; expiry; guards (doc 04 §5.3).
- Brief ranking and composition, including the empty state.
- Missing-data reason codes (doc 04 §7), e.g. QCEW `N` suppression giving "Not disclosed."
- Brand normalization and category mapping.

### 5.2 Real-data integration tests
- **Recorded fixtures:** saved real responses from each source (from M2 runs) used in CI.
- **Live smoke tests** (scheduled, e.g. nightly, tolerant of transient failure): one request per source; schema check; reference values from doc 03 §5 marked "Yes", within tolerance.
- **Reference checks** (must pass at M7): V1 pin within 50 m; V4 exact; V5 and V6 within ±10%; V7 exact (or the documented revision); V9 exact; V11 AADT 22,523 for 2024; V12 zone AE; V14 rating; V16 diff fixture; V17 Rite Aid Item 1.03.

### 5.3 End-to-end tests (against the deployed app)
1. Sign in; an unauthenticated request is blocked.
2. First-run portfolio shows 36 unconfirmed; confirm one; archive one.
3. Add a location by address; drag the pin; values recompute.
4. Open a profile; every section loads with a period and last-checked date; open 5 evidence views.
5. This Week renders (baseline or new); open a signal's evidence.
6. Screen a new address; save as candidate; compare 3 locations plus the portfolio median.
7. Data Sources page lists every source with status.
8. Admin re-runs a job.

### 5.4 Failure-state tests
- Simulate a source timeout or 500 for each source type: the page still renders; the affected section shows `CACHED_AFTER_ERROR` or `SOURCE_ERROR`; the status page shows Failing; the alert fires after 2 consecutive failures.
- Schema change (a missing field) fails closed and keeps the old data.
- Geocoder no-match goes to the fallback, then the manual pin.
- Overture broad data change triggers the guard.

### 5.5 Non-functional checks
- Accessibility: automated checks (e.g. axe) on all screens plus a keyboard-only walkthrough.
- Responsive: 375, 768 and 1280 px screenshots of SCR-1, 2, 3 and 5.
- Performance: measure the doc 06 §5 targets on production.
- Security: auth on all routes (automated route sweep), secrets scan of the repo, dependency vulnerability scan.
- **Data-integrity audit (AC-25):** an automated check that every rendered metric has source, period and value provenance; plus a manual spot check of 20 values against the original sources.

## 6. Definition of "Ready for Adi to test"

**All** of the following must be true. Anything less is not complete.

1. **Deployed:** a working HTTPS URL, reachable from Adi's devices.
2. **Access:** Adi has an account (invited to the email Adi provides). Sign-in instructions are delivered privately, not in the repo.
3. **Core workflows work end to end on real data:** This Week, Portfolio, Location profile, Screen, Compare, Data Sources (all P0 FRs).
4. **Real data connected:** every source in doc 03 §1 is integrated, or is explicitly listed as blocked with the reason, and the UI shows it as unavailable. Sources and freshness are visible on every section. **No fabricated, sample or placeholder data anywhere.**
5. **Verified:** all P0 acceptance criteria (doc 02 §9) pass on production; reference checks pass; essential calculations are covered by passing tests; the test report is committed (`docs/TEST_REPORT.md`).
6. **Scheduled jobs running in production,** with at least one successful run of each job, and a baseline brief generated.
7. **Testing guide for Adi:** `docs/TESTING_GUIDE.md`, a short plain-language walkthrough with the URL, a sign-in note, and 10–15 minutes of steps based on doc 08.
8. **Limitations documented:** `docs/KNOWN_LIMITATIONS.md` lists remaining issues, unbuilt P1 items, blocked sources and data caveats.
9. **Delivery report** (in the final message and `docs/DELIVERY_REPORT.md`): URL, what was built, test results, monthly cost, open blockers, next steps.

Not acceptable as completion: planning documents only, mockups, an app that runs only locally, a dashboard with fabricated or sample data, or a deployment where core workflows fail.
