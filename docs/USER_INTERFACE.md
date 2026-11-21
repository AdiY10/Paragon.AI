# Private workspace UI

The repository now includes a React/TypeScript application served by the authenticated
Django root. It uses the existing private APIs; there is no separate public data
feed or browser sign-in bypass. The UI is an implementation milestone, not a claim
that Release 1's data calculations or production deployment are complete.

## Implemented experience (Release 2.0, items 17-23)

- **This Week (home):** the page heading is the brief's headline ("3 items need attention
  across 3 properties"), followed by the attention items, "Resolved since the last brief",
  an FYI count, then portfolio health (High / Watch / Clear tiles that open a filtered
  portfolio) and a one-card setup reminder.
- **Alerts:** every alert across the portfolio, filtered by status, level, category and
  property (filters in the URL). Each alert opens "Evidence and actions": plain-English
  evidence, the source, glossary terms, Mark reviewed, Dismiss with a note, Reopen and
  "Was this useful?".
- **Portfolio:** attention-ranked cards with key numbers (3-mile population, median
  income, traffic), map, and state/status/type/attention filters that persist in the URL.
- **Confirm your portfolio (#/setup):** bulk confirm or archive (with undo) the publicly
  listed properties, then check each confirmed property's unconfirmed tenants.
- **Property page:** a key-facts strip (attention, latest alert, population and 5-year
  change, median income, main-road traffic, flood, nearest supermarket, active alerts),
  a sticky section menu, and sections in FR-08 order: summary, trade area, economy and
  jobs, retail, traffic, hazards, tenants (owned only), then the property record, map
  pin and change history. "Refresh data" uses one flow with a live timer and a
  persistent message when the background worker is slow or stopped.
- **Screen / Compare / Data Sources / Admin:** as described in INSIGHTS.md and
  DEPLOYMENT.md; a banner appears when a public source is failing.

Accessibility: route changes move focus to the main content and update the tab title;
the map has a "Skip map" link; text is at least 12 px (body 14 px, phone inputs 16 px);
the browser smoke runs axe with WCAG 2.2 AA tags, including a property page at 375 px.
Code layout: `src/main.tsx` holds routing and the shell; pages live in `src/pages/`,
shared pieces in `src/components/`.

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
and no-match behavior. The same review control is now published on the temporary Site with its separate
Worker adapter and persistent source evidence. See GEOCODING.md for privacy and provenance.
