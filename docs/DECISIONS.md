# Engineering decisions

## 2026-11-17 — implementation baseline
Follow docs/IMPLEMENTATION_PLAN.md, subject to AGENT_HANDOFF.md and the original acceptance criteria. Preserve public Overture history before interface development. Store large source captures outside Git, with record-level attribution and checksums. Seed coordinates remain explicitly unconfirmed public references. A missing seed pin is reported, never guessed.

Use focused PRs with clear validation and honest AI authorship. The requested 115-PR target does not justify empty or duplicate changes.

## Location identity and revision storage
Use finite latitude/longitude doubles as canonical pins and immutable numbered
revisions. PostGIS reference assets will supply indexed spatial queries; a separate
point column on the small location table is unnecessary. Keep optimistic edit version
separate from analysis generation so descriptive edits do not invalidate computations.
Seed-reference pins remain explicitly unconfirmed until a lookup or user confirmation.
