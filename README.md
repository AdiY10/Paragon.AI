# Paragon Radar

A private market-intelligence application in development for **John Nelson, Founder and CEO of [Paragon Realty Group](https://paragonct.com/)**.

**Status (2026-11-19):** implementation is underway. Invite-only access, source archives and health, durable jobs, schedules, private property management, and a responsive React UI are implemented and locally verified. The 36 public portfolio records remain unconfirmed until reviewed. **The full Django/PostGIS Release 1 is not deployed or ready for acceptance:** trade-area calculations, signals, screening, and metric comparisons are still being implemented. Named password access, Census pin review, and a tested Site-to-Django importer are ready; the user chose to continue on the current OpenAI Site, with external hosting deferred. See [progress.md](progress.md) for current evidence and blockers.

## Current workspace

[Open Paragon Radar on OpenAI Sites](https://paragon-radar-workspace.amitsch5.chatgpt.site) with ChatGPT sign-in. Its audience is public; each visitor gets an isolated workspace. The working temporary version supports real portfolio management, maps, persistent notes/pins, on-demand Census pin suggestions, and workspace export. Source refresh and full trade-area analysis remain unavailable. See [temporary deployment and migration](docs/TEMPORARY_SITE.md).

## Target Release 1 behavior
- **This Week:** a Monday brief of meaningful changes around Paragon's properties (tenant SEC bankruptcy or closure filings, possible nearby closures, flood exposure, local jobs, population and income trends, traffic, housing pipeline), each with evidence.
- **Location profiles:** current 1/3/5-mile (or 3/5/10-mile) trade-area data for any US address, sourced from Census, BLS, FHWA, FEMA, Overture Maps and SEC EDGAR, with periods, margins of error and freshness shown.
- **Screen and compare:** a first-pass read on any acquisition address with strengths and concerns benchmarked against Paragon's own portfolio, and side-by-side comparison of up to 4 locations.
- **Trust by design:** every number traces to a public source or labelled user input. Gaps show as "unavailable, with a reason." No fabricated data.

Out of scope for Release 1: rents, comps, listings, occupancy, financials, foot traffic. These need paid or private data (see `docs/03` §3).

## Start here
- **Implementing agent:** read [`AGENT_HANDOFF.md`](AGENT_HANDOFF.md). It contains the mission, reading order, owned decisions, definition of done and a kickoff prompt.
- **Adi:** read this README, then [`docs/02`](docs/02_PRODUCT_REQUIREMENTS.md) §5–6 (scope) and use [`docs/08`](docs/08_ADI_ACCEPTANCE_CHECKLIST.md) to test the deployed app.

## Recommended reading order
| # | File | Contents |
|---|---|---|
| 0 | [AGENT_HANDOFF.md](AGENT_HANDOFF.md) | Entry point for the implementing agent |
| 1 | [docs/01_RESEARCH_AND_DISCOVERY.md](docs/01_RESEARCH_AND_DISCOVERY.md) | Paragon facts (sourced), assumptions, open questions, workflow prioritization |
| 2 | [docs/02_PRODUCT_REQUIREMENTS.md](docs/02_PRODUCT_REQUIREMENTS.md) | Problem, users, JTBD, scope and exclusions, journeys, FRs, acceptance criteria, success measures |
| 3 | [docs/03_DATA_SOURCES.md](docs/03_DATA_SOURCES.md) | Source catalog, access and licensing, limits, **verification log with real retrievals** |
| 4 | [docs/04_DATA_AND_INSIGHT_REQUIREMENTS.md](docs/04_DATA_AND_INSIGHT_REQUIREMENTS.md) | Feature-to-source map, geography methods, metric and signal definitions, explainability, missing-data behaviour |
| 5 | [docs/05_EXPERIENCE_REQUIREMENTS.md](docs/05_EXPERIENCE_REQUIREMENTS.md) | Information architecture, screens, accessibility, responsiveness, uncertainty presentation |
| 6 | [docs/06_ENGINEERING_AND_OPERATIONS.md](docs/06_ENGINEERING_AND_OPERATIONS.md) | Security, privacy, secrets, jobs, monitoring, performance, deployment, cost |
| 7 | [docs/07_DELIVERY_AND_VERIFICATION.md](docs/07_DELIVERY_AND_VERIFICATION.md) | Milestones, prerequisites, risks, test plan, "Ready for Adi to test" |
| 8 | [docs/08_ADI_ACCEPTANCE_CHECKLIST.md](docs/08_ADI_ACCEPTANCE_CHECKLIST.md) | Plain-language checklist for Adi |
| 9 | [docs/NEXT_TASKS.md](docs/NEXT_TASKS.md) | Ordered task batch (T1–T11) with acceptance criteria and an agent kickoff prompt |

## Repository layout
```
AGENT_HANDOFF.md          entry point for the implementing agent
backend/                  Django, private APIs, jobs, and versioned models
frontend/                 React / TypeScript UI, Vite build, browser verification
docs/                     specification (01–08), implementation and operations guides
data/seed/                36 publicly listed Paragon properties (unconfirmed; from paragonct.com)
scripts/feasibility/      re-runnable probes that verify the core data sources
scripts/verification/     production, worker, and isolated UI smoke checks
config/                   source registry and job schedule definitions
```

## Build and verification

Use Python 3.12–3.13 and Node.js 22.12 or newer. Install the locked dependencies and build the UI before starting Django:

```sh
uv sync --locked
npm ci --prefix frontend
npm run build --prefix frontend
uv run pytest -q
npm test --prefix frontend
```

The default test suite uses isolated SQLite; the [database testing guide](docs/DATABASE_TESTING.md) covers the required real PostGIS checks. The [UI guide](docs/USER_INTERFACE.md) explains implemented screens, browser verification, and current limitations. See [deployment](docs/DEPLOYMENT.md) and [authentication](docs/AUTHENTICATION.md) for real environment configuration. A Vite development server alone does not provide authentication or backend APIs. The [workspace review guide](docs/TESTING_GUIDE.md) covers the currently implemented UI without claiming final acceptance.

## Key dependencies still open
- Owner: provide approved hosting access/budget, OIDC client configuration, the test-account email, and a contact email for SEC API access. GitHub access works; hosted CI publication needs workflow scope.
- John (not blocking): confirm which listed properties are still owned and current tenants (Q-01, Q-05 in doc 01).

No credentials are stored in this repository.
