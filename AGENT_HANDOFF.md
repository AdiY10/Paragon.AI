# AGENT_HANDOFF: Paragon Radar, Release 1

**To:** Amit's implementing agent
**From:** product research and definition (prepared for Adi, 2026-11-17)
**Your job:** design, build, integrate, test, **deploy and verify** a working Release 1 that Adi can test at a real URL. Do not stop at plans or mockups.

---

## 1. What you are building (30-second version)

A private web app for **John Nelson, Founder and CEO of Paragon Realty Group** (Westport, CT; about 2M SF, mostly neighborhood and community shopping centers in 12 states). It:

1. Keeps a **current, sourced trade-area profile** for every owned property and acquisition candidate: ring demographics, jobs, county economy, housing pipeline, traffic, nearby businesses, flood and hazard risk, and tenant SEC events.
2. Flags **meaningful changes** with deterministic rules and delivers a **Monday "This Week" brief**.
3. **Screens any US address** and **compares locations side by side against Paragon's own portfolio**, with a strengths and concerns evidence summary.
4. Shows the **source, period, freshness and uncertainty** of every number, and never fabricates.

All Release 1 data sources are free or public, and the core ones were **verified with real retrievals** (doc 03 §5).

## 2. What to read (in order)

| # | Document | Why | Time |
|---|---|---|---|
| 1 | This file | Mission, ownership, completion rules | 10 min |
| 2 | [docs/02_PRODUCT_REQUIREMENTS.md](docs/02_PRODUCT_REQUIREMENTS.md) | Scope, FRs, **acceptance criteria** | 20 min |
| 3 | [docs/04_DATA_AND_INSIGHT_REQUIREMENTS.md](docs/04_DATA_AND_INSIGHT_REQUIREMENTS.md) | Exact metric, signal, ring and missing-data definitions | 25 min |
| 4 | [docs/03_DATA_SOURCES.md](docs/03_DATA_SOURCES.md) | Source endpoints, limits, verification log | 20 min |
| 5 | [docs/05_EXPERIENCE_REQUIREMENTS.md](docs/05_EXPERIENCE_REQUIREMENTS.md) | Screens, hierarchy, UX quality bar | 10 min |
| 6 | [docs/06_ENGINEERING_AND_OPERATIONS.md](docs/06_ENGINEERING_AND_OPERATIONS.md) | Security, jobs, performance, deployment, cost | 10 min |
| 7 | [docs/07_DELIVERY_AND_VERIFICATION.md](docs/07_DELIVERY_AND_VERIFICATION.md) | Milestones, prerequisites, risks, tests, **definition of done** | 10 min |
| 8 | [docs/01_RESEARCH_AND_DISCOVERY.md](docs/01_RESEARCH_AND_DISCOVERY.md) | Business context, assumptions (A-xx), open questions (Q-xx) | 10 min |
| 9 | [docs/08_ADI_ACCEPTANCE_CHECKLIST.md](docs/08_ADI_ACCEPTANCE_CHECKLIST.md) | How Adi will judge the result | 5 min |
| n/a | [data/seed/paragon_public_properties.csv](data/seed/paragon_public_properties.csv) | Seed portfolio (public, unconfirmed) | n/a |
| n/a | [scripts/feasibility/](scripts/feasibility/) | Re-run the source probes | n/a |

If documents conflict: **this file and doc 02's acceptance criteria take precedence**, then doc 04, then the rest. Record how you resolved a conflict in `docs/DECISIONS.md`.

## 3. Decisions you own

You decide, document briefly in `docs/DECISIONS.md`, and proceed without asking:

- Visual design, branding, layout, component library, charts and map styling (meet doc 05's bar: **visually impressive, calm, executive-grade**).
- Architecture, language, framework, database, ORM, job runner, hosting, auth provider, map library and tile provider, geocoding fallback provider.
- Data storage model, caching, ingestion approach (bulk files vs APIs), code structure, testing tools.
- Product name, and copy within the guardrails in doc 04 §8.
- Defaults not specified here, provided they don't contradict the docs.

## 4. Non-negotiables

1. **Real data only.** No fabricated, sample, mock or placeholder values in the deployed app, including empty states and onboarding. Fixtures belong in tests only.
2. **Provenance and freshness visible** for every value (source, period, last checked).
3. **Missing means "unavailable, with a reason,"** never 0 or a guess (doc 04 §7).
4. **Area and company indicators are never presented as property-level results** (no external "vacancy," "rent" or "value").
5. **Deterministic signals and summaries.** No generative AI producing numbers, signals or evidence text in Release 1.
6. **No scraping** of CoStar, LoopNet, Crexi or any site whose terms forbid it. Respect SEC (≤ 10 requests/s, User-Agent with contact) and Nominatim (≤ 1 request/s) policies, plus licence attributions.
7. **Auth on everything; no secrets in the repo.**
8. **No paid sign-ups, purchases or payment details** without Adi's explicit approval.

## 5. This scope is a starting point: you may expand it

The documents define a **minimum, focused Release 1**, not a ceiling. You are encouraged to improve and extend the product where it makes the experience more useful or more impressive for John. Examples:

- Building P1 items (doc 02 §5).
- Adding further **legitimate, free data sources** (e.g. the Connecticut sale comps verified in doc 03 §3, or EPA FRS).
- Richer visualizations, better map interactions, smarter (still deterministic and explainable) signals, an email digest, or a polished onboarding for the 36-property confirmation.
- Improving definitions or thresholds where you find a better-supported method.

**Rules for expanding:** (a) get all P0 requirements working and deployed first, and never trade P0 quality or delivery for extras; (b) every addition obeys the non-negotiables in §4; (c) any new source gets the same documentation as doc 03 (provider, coverage, licence, cadence, limits, verification); (d) log each expansion and its rationale in `docs/DECISIONS.md` and the delivery report; (e) don't remove or weaken an acceptance criterion. If you think one is wrong, implement the closest faithful version and explain why.

## 6. How to work

- Follow the milestones in doc 07 §1 in order. **Deploy early (M0) and keep production working.**
- **Snapshot the available Overture releases at the very start** (they expire after about 2 months; doc 04 §5.5).
- **Resolve routine issues yourself:** library choices, API quirks, failing tests, layout problems, data edge cases, minor ambiguity (pick the reasonable reading and log it). Keep going.
- Commit in small, descriptive commits. Keep `main` deployable. Use feature branches and PRs if you prefer; Adi's repos use `main` as the default branch.
- Keep a short `progress.md` (milestone status, next step, blockers) so anyone can see where things stand.

## 7. Blockers: what to do

A **genuine blocker** is something only a human can provide: credentials or an account Adi must own, payment, access (repo collaborator, domain), or a product decision that changes scope or cost. When you hit one:

1. **Complete all unaffected work first.**
2. Report the blocker in exactly this form, in `progress.md` and your message to Amit or Adi:
   ```
   BLOCKER: <one line>
   Impact: <what can't be done / which ACs are affected>
   Minimum action needed: <exact step, who, estimated time>
   Workaround in place: <if any>
   ```
3. Resume as soon as it is resolved.
4. Never ship a fake workaround, such as sample data standing in for a blocked source. Show the source as "unavailable, blocked: <reason>" instead.

Expected human inputs (doc 07 §2): adding Amit to the GitHub repo; hosting or payment decisions beyond free tiers; Adi's email for the test account; a contact email for `SEC_USER_AGENT`.

## 8. Definition of done

You are done **only** when every item in doc 07 §6 ("Ready for Adi to test") is true:

1. A deployed HTTPS URL that works.
2. Adi can sign in (instructions delivered privately).
3. All P0 workflows work end to end on real data: This Week, Portfolio, Location profile, Screen, Compare, Data Sources.
4. Sources and freshness are visible; no fabricated data; blocked sources are shown as unavailable.
5. All P0 acceptance criteria and reference checks pass on production; `docs/TEST_REPORT.md` is committed.
6. Scheduled jobs are running in production, each with at least one successful run; a baseline brief exists.
7. `docs/TESTING_GUIDE.md` for Adi (10–15 minutes, plain language).
8. `docs/KNOWN_LIMITATIONS.md`.
9. `docs/DELIVERY_REPORT.md` plus a final message containing: URL, what was built (including any scope expansions), test results, monthly cost, limitations, open blockers, and recommended next steps.

**Do not claim completion while any of these is missing.** If a blocker prevents an item, say so explicitly with the blocker format in §7.

## 9. How to verify (summary)

- Automated: unit, integration (recorded real responses), live smoke, E2E against production, and failure injection (doc 07 §5).
- Reference values from real data (doc 03 §5, e.g. 3-mile population near 444 Westport Ave ≈ 84,000; Kingston US 9W AADT 22,523 in 2024; Cypress Lake in FEMA zone AE).
- Walk through doc 08 yourself on production before handing over.

---

## 10. Kickoff prompt (copy and paste to start the implementing agent)

```text
You are the implementing agent for "Paragon Radar" (working name), a private web app for John Nelson,
CEO of Paragon Realty Group. This repository contains a complete product and data specification.

1. Read AGENT_HANDOFF.md fully, then the documents in the order it lists (docs/02, 04, 03, 05, 06, 07, 01, 08).
2. Your goal is not a plan: design, build, integrate real data, test, DEPLOY, and VERIFY Release 1 until
   every item in docs/07_DELIVERY_AND_VERIFICATION.md §6 ("Ready for Adi to test") is true.
3. You own all design, architecture, stack, hosting, and implementation decisions; record them briefly in
   docs/DECISIONS.md and keep moving. Respect the non-negotiables in AGENT_HANDOFF.md §4 (real data only,
   visible provenance, no fabricated values, auth everywhere, no secrets in git, no paid sign-ups without
   Adi's approval).
4. The documented scope is a starting point, not a ceiling. Deliver all P0 requirements first; then you may
   expand the product (P1 items, additional legitimate data sources, richer UX) following AGENT_HANDOFF.md §5.
5. First actions: set up the repo and a deployed HTTPS skeleton with auth (M0), and immediately snapshot the
   currently available Overture Maps places releases for the seed locations (they expire).
6. Resolve routine problems yourself. For genuine blockers (credentials, payment, access, scope decisions),
   finish all unaffected work, report using the BLOCKER format in AGENT_HANDOFF.md §7, and resume when
   unblocked. Keep progress.md current.
7. Do not claim completion until the app is deployed, the P0 acceptance criteria and reference checks pass on
   production, and TESTING_GUIDE.md, KNOWN_LIMITATIONS.md, TEST_REPORT.md and DELIVERY_REPORT.md are committed.
   End with the delivery report: URL, what was built, test results, monthly cost, limitations, blockers, next steps.
```
