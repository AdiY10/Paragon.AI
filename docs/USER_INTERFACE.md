# Private workspace UI

The repository now includes a React/TypeScript application served by the authenticated
Django root. It uses the existing private APIs; there is no separate public data
feed or browser sign-in bypass. The UI is an implementation milestone, not a claim
that Release 1's data calculations or production deployment are complete.

## Implemented experience

- **This Week:** real portfolio counts, a confirmation queue, state-distribution
  bars, property cards, and a source-coverage link. Until the signal pipeline runs,
  the brief says **unavailable**, rather than claiming no material changes.
- **Portfolio:** all saved records, state/status/asset filters, property cards, and
  an add-location dialog. Counts use all API pages, including archived records
  when the corresponding filter is selected.
- **Property record:** source period, pin method/coordinates, confirmation status,
  ring preset, user-provided GLA/notes, record confirmation, version-checked
  editing, and previewed manual pin correction/confirmation, and source-backed Census suggestion review. The provenance drawer includes the original listing and change history.
- **Data Sources:** the real 16-entry registry, recorded scoped health, periods,
  last successful check, licensing, attribution, and privacy notes. No check is
  displayed as “Not checked,” never as healthy.
- **Admin:** recorded job activity; role restrictions are also enforced by the API.
- **Screen / Compare:** clearly explain that area checks and comparable metrics
  remain unavailable. Candidate record creation works; screening scores do not
  exist yet.

Portfolio and property screens now include interactive MapLibre maps with OSM
raster tiles, linked reference pins, and geodesic distance rings. The list remains
available when tiles or WebGL fail. See [MAPS.md](MAPS.md) for attribution, privacy,
and display-geometry limits.
Tenant management, signal evidence, comparison,
and complete administrator controls remain in the implementation plan.

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

Visual choices: pine navigation, warm neutral surfaces, restrained green/brass,
visible source labels, text-labelled status, native form controls, Radix accessible
dialogs, reduced-motion support, and system fonts. No analytics or third-party font
requests are made. No invented metrics, photographs, or “live” activity are shown.

Census lookup/review is now implemented in the canonical Django UI. The browser
smoke contacts Census for three real public addresses and verifies match, ambiguity,
and no-match behavior. The temporary Site needs its separate adapter update before
this control is available there. See GEOCODING.md for privacy and provenance.
