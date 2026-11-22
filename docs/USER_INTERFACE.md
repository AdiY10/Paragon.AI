# Private workspace UI

The repository now includes a React/TypeScript application served by the authenticated
Django root. It uses the existing private APIs; there is no separate public data
feed or browser sign-in bypass. The UI is an implementation milestone, not a claim
that Release 1's data calculations or production deployment are complete.

## Implemented experience (redesign, WI-1 to WI-9)

The approved redesign (docs/REDESIGN_PLAN.md, PART F) replaced the Release 2.0 screens.

- **Shell:** white top bar with PARAGON RADAR, `nav "Main"` (Properties · Analyze · Alerts ·
  Compare; Properties stays current on property analyses), a POST-only search dialog that can
  hand a typed address to Analyze (never through the URL), and an "Account menu" (Data sources,
  Admin for administrators, Sign out). At 640 px and below the navigation opens as the
  "Workspace navigation" dialog. Hash routes: `#/`, `#/p/:id`, `#/analyze`, `#/analyze/:id`,
  `#/alerts`, `#/compare`, `#/sources`, `#/admin`; `#/portfolio`, `#/locations/:id`, `#/screen`
  and `#/setup` redirect.
- **Properties (`#/`):** "36 owned · N High · N Watch" (each count filters), a toolbar whose
  search, State, Attention and sort live in the URL, the portfolio map (HTML pins, clusters,
  hover card), and the "Owned properties" table (sortable, missing values last, row ↔ pin
  highlight; cards with "Sort by" on phones). Compare up to four through a sticky tray.
- **Analysis (`#/p/:id`, `#/analyze/:id`):** one bundle request (GET /api/locations/<id>/analysis/)
  polled only while the analysis runs. Ten fixed sections with a status dot each (Overview,
  Trade area & demographics, Daytime population, Retail landscape, Access & traffic, Risk,
  Market, Tenants & SEC watch for owned properties, Ranking vs portfolio, Sources & methods),
  a left menu / chip strip / "Jump to section" select by width, deep links with `?section=`.
  There is no button that runs an analysis; sections fill in by themselves and a polite live
  region says when each is ready. Administrators get a "Property actions" menu (Edit details,
  Correct pin, Find address pin, Record & history).
- **Analyze (`#/analyze`):** type an address or click the map; ambiguous addresses ask which
  match, unmatched ones are placed by clicking the map; recent analyses with a star that keeps
  one beyond 90 days.
- **Alerts:** High and Watch by default (FYI opt-in), grouped by property, worst first; shared
  county or nearby-place alerts once with every property; next step on every alert; evidence
  drawer with review (a review of a shared alert applies to the whole group).
- **Compare, Data sources, Admin:** restyled; "Add location" lives in Admin.

Design: tokens in `src/styles/tokens.css` (white surfaces, accent Paragon green #0E6B4F, red
#C81E1E and amber #C98500 reserved for attention), self-hosted Inter, custom charts with printed
values (no chart library). Accessibility: one h1 per page, labelled landmarks, focus to `#main`
on route changes, focus returned from every dialog and menu, ≥24 px targets, colour never the
only signal, scroll padding so the sticky bars never hide focus. Code layout: `src/app` (shell,
router), `src/api` (client, PART C types, hooks), `src/lib` (formatters, scales, clustering,
filters), `src/components` (ui kit, charts, map), `src/features/*`, `src/pages/*`.

## Build and serve

```sh
npm ci --prefix frontend
npm run build --prefix frontend
uv run python backend/manage.py collectstatic --noinput
```

The Vite manifest and hashed assets are generated under `backend/static/ui/` and
are intentionally ignored by Git. Django reads the manifest and WhiteNoise serves
the generic JS/CSS after collection. No property or account data is embedded in
these public static files. Business data is fetched only through private APIs.
The application HTML is never cached and supplies a masked CSRF token while the
CSRF cookie stays HttpOnly. Address search uses POST JSON rather than URL query
strings. A missing/invalid build produces a private 503 with a clear message.

Docker builds the frontend in a Node stage before collecting assets in the Python
image. Docker execution remains unverified in this environment because its daemon
is inaccessible. Authentication/HTTPS settings remain those in AUTHENTICATION.md;
no development sign-in method was added.

## Verify and inspect visuals

```sh
npm test --prefix frontend
uv run pytest -q
cd frontend
npx playwright install chromium
cd ..
UI_SCREENSHOT_DIR=var/ui-review uv run python scripts/verification/ui_smoke.py
```

Alternatively set `CHROMIUM_PATH` to an existing Chromium executable. The command
requires Node on PATH. It creates a disposable SQLite test database, imports the
actual public portfolio CSV and catalog, and creates one **test-only** member in
that temporary database. It launches Gunicorn on loopback, exercises the real APIs
from Chromium, and removes the database and server afterward. It never modifies
the configured production/local portfolio database or creates a production user.

The browser check also verifies pin dragging, explicit pin verification, immutable
revision/analysis generations, an actual concurrent edit conflict after background
refresh, and mobile menu focus trapping/restoration. Editing dialogs keep the version
seen on opening; a background refresh cannot silently authorize stale form contents.

The browser check covers 375/768/1280 widths, horizontal overflow, automated WCAG
A/AA rules, filters, provenance, editing, confirmation, source cards, body-based
search, anonymous API denial, actual map-worker loading, three displayed rings, and
retention of saved pins when tile requests fail. Screenshots are optional local review artifacts
and are not deployed. Automated accessibility checks supplement manual keyboard,
focus, screen-reader, and production acceptance checks; they do not certify full
WCAG 2.2 conformance.

Visual choices (redesign): white surfaces, one accent green, red/amber only for attention
levels, visible source labels, text-labelled status, native form controls, Radix accessible
dialogs, reduced-motion support, and Inter served from this application (Latin subset). No
analytics or third-party font requests are made. No invented metrics, photographs, or “live” activity are shown.

Census lookup/review is now implemented in the canonical Django UI. The browser
smoke contacts Census for three real public addresses and verifies match, ambiguity,
and no-match behavior. The same review control is now published on the temporary Site with its separate
Worker adapter and persistent source evidence. See GEOCODING.md for privacy and provenance.
