# 06 · Engineering and Operational Requirements

**Purpose:** Constraints and targets for security, data operations, performance, reliability, deployment and cost. **Architecture, stack, hosting provider, database, auth provider, map library and job runner are the implementing agent's decisions,** within these requirements.

## 1. Security, authentication and access control
1. **Authentication on everything** (FR-01): every page, API route, export and map data request requires a valid session. The only unauthenticated routes are sign-in and a health check that returns no data.
2. **Invite-only:** users are created by an admin (an email allowlist). Use a mature auth method or provider (passwordless email link, OAuth with Google or Microsoft, or similar). **Do not build password storage from scratch.** MFA support is desirable if the provider offers it.
3. **Roles:** Admin and Member (FR-02), enforced on the server.
4. **Sessions:** secure, HttpOnly, SameSite cookies, or the provider's equivalent. Idle timeout ≤ 30 days. Users can sign out.
5. **Transport:** HTTPS only, with HSTS.
6. **Web security:** protect against CSRF where relevant, parameterize all queries, validate input on the server, apply a Content-Security-Policy, and rate-limit sign-in and screen endpoints.
7. **Least privilege:** the database user and cloud credentials have only the permissions they need.

## 2. Privacy and confidentiality
- **Candidate (deal) addresses and notes are confidential.** Only signed-in users can see them.
- Do not send location data to third parties except the data lookups this product needs (Census, Nominatim as a fallback, FEMA, USDOT, Overture's public bucket, SEC, map tiles). List these in a short privacy note on the Data Sources page.
- **No third-party analytics, ad trackers or session replay.** First-party usage events only (for success measures, doc 02 §10).
- No tenant personal data. Tenant entries are business names.
- Logs must not contain secrets or session tokens. Keep addresses out of error-tracking services that are external to the hosting platform.

## 3. Credentials and secrets
- **Never commit secrets.** Use the hosting platform's secret store or environment variables. Commit a `.env.example` listing every variable with a description and no values.
- Expected variables:

| Variable | Required | Notes |
|---|---|---|
| `SEC_USER_AGENT` | Yes | `"<App name> <contact email>"`; the email is provided by Adi or Amit. Required by SEC fair-access rules. |
| `CENSUS_API_KEY` | Optional | Only if the Census Data API is used instead of bulk files. Free signup. |
| `BLS_API_KEY` | Recommended | BLS API v2 (free) for higher limits. |
| Map tiles key | Depends | If the chosen tile provider needs one. |
| Email provider key | P1 | For FR-24. |
| Auth provider secrets, DB URL, session secret | Yes | Per the chosen stack. |

- Keys stay **server-side**. The browser never receives data-provider keys except publishable map-tile tokens restricted by domain.
- Test login credentials for Adi are delivered **outside the repo** (doc 07 §6).

## 4. Data ingestion, refresh, monitoring and recovery

### 4.1 Jobs
| Job | Schedule (US Eastern) | Work |
|---|---|---|
| `sec_daily` | Daily 06:00 | Submissions for mapped CIKs; detect new 8-K items; SIG-12 and SIG-13 |
| `brief_weekly` | Monday 07:00 | Generate the brief (doc 04 §5.4) |
| `overture_check` | Weekly, Thu 03:00 | Detect a new release; snapshot all monitored locations within 3 mi; diff; SIG-09 and SIG-10; artifact guard |
| `bls_bps_check` | Weekly, Tue 05:00 | LAUS (monthly), QCEW (quarterly), BPS (monthly): fetch if a new period exists; SIG-03 to SIG-05, SIG-07 |
| `annual_sources_check` | Monthly, 1st, 04:00 | ACS, LODES, HPMS, NRI, CPI vintages; ingest if new; SIG-01, 02, 06, 08 |
| `flood_recheck` | Monthly, 15th | NFHL for monitored locations; SIG-11 |
| On-demand profile build | When a location is created, screened or its pin moves | Geocode, rings, all sections; cache |

### 4.2 Job requirements
- **Idempotent** and safe to re-run. Store each source snapshot with its data period. **Keep history**, because change detection depends on it.
- **Retries:** 3 attempts with exponential backoff. Per-source timeouts.
- **Fail safe:** on error, keep the last good data, mark the source status, and write the run log entry (start, end, status, records, error summary).
- **Rate limits:** SEC ≤ 10 requests/s (use ≤ 5); Nominatim ≤ 1 request/s; BLS per API version limits.
- **Monitoring:** the Data Sources page shows status. Admins are alerted (email or the platform's alerting) when a job fails twice in a row or a source goes Stale.
- **Recovery:** admins can re-run any job (FR-32). A full rebuild of derived data from stored snapshots must be possible with a single documented command.
- **Compute note:** the Overture read uses GeoParquet over HTTPS or S3 (verified with DuckDB: about 10 s per 0.8-mile box from a laptop). Budget roughly 1–2 GB RAM and up to 30 minutes for a full monthly snapshot of about 50 locations. Choose a job runner that allows this. Short-lived serverless functions may not.
- **Backups:** daily database backups with ≥ 7-day retention. User-entered data (portfolio, tenants, mappings, reviews) is the critical part.

## 5. Performance and reliability targets (test release)

| Item | Target |
|---|---|
| Cached profile or brief, server response | p95 < 1.5 s; interactive < 2 s on broadband |
| New screen: pin plus trade-area metrics | p95 < 20 s |
| New screen: full profile including Overture | p95 < 90 s, with progressive display |
| Comparison of 4 cached locations | < 2 s |
| Availability during the testing period | ≥ 99% monthly (best effort; no on-call) |
| Scheduled jobs | ≥ 95% of runs succeed without manual intervention |
| Data correctness | All reference checks pass (doc 07 §5) |

## 6. Deployment
- A publicly reachable **HTTPS URL** on managed hosting, with a production environment. Preview environments are optional.
- **Infrastructure as code** or a documented, repeatable setup (`docs/DEPLOYMENT.md` written by the implementing agent).
- **CI:** lint, unit tests and integration tests (fixtures) on every push; deploys from `main` (or a release branch) after tests pass.
- **Database migrations** are versioned and applied automatically on deploy.
- **Seed:** the first deploy imports `data/seed/paragon_public_properties.csv` (FR-04) and runs all source jobs to build the baseline.
- A health endpoint and an admin "system status" view.

## 7. Cost considerations

| Item | Expected cost |
|---|---|
| All Release 1 data sources | **$0** (public or free; doc 03) |
| Hosting, database and job runner | Free tier to about $25–50/month, depending on provider (estimate; verify current pricing) |
| Map tiles | $0 on free or open tiers within limits; verify terms |
| Email (P1) | Free tier is usually enough for under 10 users |
| Optional paid data (doc 03 §4) | Requires John's decision and vendor quotes |

The implementing agent must record the actual monthly cost of its chosen setup in the delivery report. It **must not** sign up for paid plans or enter payment details without Adi's explicit approval (doc 07 §3).
