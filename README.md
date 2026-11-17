# Paragon Radar: Release 1 product and data specification

A ready-to-build documentation package for a private market-intelligence web app for **John Nelson, Founder and CEO of [Paragon Realty Group](https://paragonct.com/)**.

**Status (2026-11-17):** research, data verification and specification are complete. **Nothing has been built yet.** Implementation is handed to Amit's agent.

## What Release 1 does
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

## Repository layout
```
AGENT_HANDOFF.md          entry point for the implementing agent
docs/                     specification (01–08)
data/seed/                36 publicly listed Paragon properties (unconfirmed; from paragonct.com)
scripts/feasibility/      re-runnable probes that verify the core data sources
```

## Key dependencies still open
- Adi: add Amit as a collaborator on this repo; approve any paid hosting; give Amit the email for the test account and a contact email for SEC API access.
- John (not blocking): confirm which listed properties are still owned and current tenants (Q-01, Q-05 in doc 01).

No credentials are stored in this repository.
