# Release 2.0 progress (2026-11-21)

Plan approved 2026-11-21 (items 1-26). Merged, PRs #52-#67:

| # | Item | Result on the 35-property preview |
|---|---|---|
| 1 | Observability | Job failure counts, operational alerts on Admin, logs without locations |
| 2 | Security lockdown | Shared password local-only; proxied-IP throttle; 12 h / 14 d sessions; API throttles |
| 3 | Cache freshness | No more endless refetching; newest content wins |
| 4 | Job routing | Foreground cluster for screens/computes; renewable leases; one Overture scan at a time |
| 5 | Alert identity | Stable subjects; dismissals survive new months; episodes |
| 6, 15 | Closure de-noising | Closure alerts 94 -> 5 (two-release confirmation, brand-wide drops ignored) |
| 7 | Flood | High only inside a FEMA high-risk zone (Cypress Lake); others Watch with distance |
| 8 | Brief | 18 attention items; county figures grouped, not on property badges; resolved section |
| 9 | ACS rollover | Ready for the December 2021-2025 release; switches all properties together |
| 10 | Tenants | Edits no longer force recomputes; SEC mapping per brand |
| 11 | Traffic | CVS-Graham uses NC-87 (21,000, not an I-85 ramp); 24 roads say "estimate carried forward" |
| 12 | Small fixes | Brand matching, labels, duplicate concerns |
| 13 | Snapshot table | Summary 84 -> 15 queries, list 44 -> 9, compare 92 -> 17 |
| 14 | Overture storage | 1,324 MB -> 77 MB; full recompute peaks ~400 MB RAM |
| 16 | Ingestion | One-pass ACS, LODES parsed once, SEC stored only on change |

Remaining before deploy: items 17-23 (executive UX), then 24-26 (droplet, backups, go-live).

# Delivery status: Release 1 (2026-11-19)

## Done (merged to `main`, PRs #43–#50)
- **T1 Source health:** every fetch records health, and a failed refresh shows the last good data marked Stale.
- **T2 Scheduled refreshes:** economy, businesses, hazards, annual sources (ACS, LODES, HPMS, NRI), brief and SEC.
- **T3 Portfolio comparison:** percentiles against your other owned properties, and strengths and concerns.
- **T4 Signal engine:** SIG-01 to SIG-13, with lifecycle, attention levels and review or dismiss.
- **T5 This Week brief:** baseline, new or changed items, grouped county items, history, evidence, and attention on the portfolio.
- **T6 Screen:** any US address, auto-geocode, auto-compute, save as candidate, 30-day expiry.
- **T7 Compare:** 2–4 locations with the portfolio median and range, and direction-aware highlighting.
- **T8 Tenants:** API and UI over the existing tenant domain, plus the public-listing import.
- **T9 SEC tenant watch:** admin filer mapping, daily filing check, bankruptcy and closure signals.
- **T10 Hardening:** accessibility (0 axe violations at desktop and phone width), performance, data-integrity test, real-data run for all 35 properties, worker pipeline verified (`docs/TEST_REPORT.md`).
- **T11 Deployment readiness:** single-container web, worker and scheduler, `bootstrap_data`, runbook (`docs/DEPLOYMENT.md`).

## Waiting on Adi (minimum actions)

### 1. Hosting approval and account (blocks a working URL)
- **What:** approve a host and plan, then connect it to this repo. The repo is configured for Render (`render.yaml`). The earlier quote is about **$14.55/month** for a 512 MB web service, small Postgres and a 5 GB disk. With the background worker, a **1 GB plan** is safer (check the current price).
- **How:**
  1. Create a Render account at render.com.
  2. Choose "New → Blueprint" and pick `AdiY10/Paragon.AI`.
  3. Review the resources shown and approve.
  4. Add the secrets in the next steps.
- **Time:** about 15 minutes.

### 2. SEC contact email (turns on tenant watch)
- **What:** the SEC requires automated clients to declare a contact email.
- **How:** in the host's environment settings, set `SEC_USER_AGENT` to `Paragon Radar your-email@example.com`, using an inbox you check. No signup is needed.

### 3. First admin login
- **How:** set `ACCESS_BOOTSTRAP_EMAIL` (your email) and `ACCESS_BOOTSTRAP_PASSWORD` (a strong password) in the host settings, deploy, sign in once, then delete both settings (see `docs/PASSWORD_ACCESS.md`).

### 4. Copy the saved business history (before about mid-January 2027)
- **What:** `var/overture-archive` on your Mac holds 105 captures (about 1.3 GB). Overture deletes the September release from its public bucket in about two months.
- **How:** after the host is created, upload the folder to the service disk at `/app/var/overture-archive` (Render shell or `scp`), then run `python backend/manage.py bootstrap_data --overture-archive /app/var/overture-archive`.

### 5. Optional: a BLS API key
- **What:** free, and raises BLS rate limits.
- **How:** register at https://data.bls.gov/registrationEngine/, then set `BLS_API_KEY`. Not needed for 35 properties.

### 6. From John (does not block anything)
- Confirm which listed properties are still owned (archive the rest).
- Confirm tenants: they were imported as unconfirmed listing claims.
- Map key public-company tenants to their SEC filers on each property's Tenants panel.

## Known limitations
- **Not deployed:** no URL until item 1 is done. The temporary OpenAI Site is a separate, older version.
- **PostGIS:** the test suite was not run on this machine. Run `make test-postgis` (or rely on the first deploy's migrations) before cutover.
- **Overture data:** coarse categories; anchors depend on a curated brand list. Monthly diffs show "possible" closures that need verifying.
- **County figures:** economy figures are county-level (Connecticut planning regions), not neighborhood-level.
- **Trends:** compare 2015–19 with the current ACS vintage. When the 2021–25 vintage is published (expected December 2026), `annual_sources_check` ingests it for every portfolio state and switches all properties together (`demographics/vintage.py`); percentiles never mix vintages.
- **Tenant edits:** since R2.10 they bump the record version only; data sections stay valid and only tenant-dependent alerts are re-evaluated. SEC filer mappings apply to the same brand at every property.
- **Not built (P1):** email digest, FEMA flood overlay on the map, CSV export.
- **Coordination:** Amit's agent has unpushed tenant API and seed work in a local stash. It should reconcile with `apps/insights/tenant_views.py` and `import_listing_tenants` rather than duplicate them.
