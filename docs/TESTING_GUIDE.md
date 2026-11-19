# Testing guide for Adi (Release 1, about 15 minutes)

**Where:** once the host is set up (see `docs/DELIVERY_STATUS.md`), open its HTTPS URL, sign in with the password access you created, then follow these steps. Until then, the same steps work on a local preview: see "Local preview" at the end.

1. **This Week (home).** You should see "Baseline: current conditions" with High items first: Cypress Lake and Saugatuck Restaurant in FEMA flood zone AE. Open **Evidence** on any item to see the rule, values, period and a source link. Unemployment in Western Connecticut appears once, listing the affected properties.
2. **Portfolio.** Filter by **Attention = High**, then Watch. Cards show attention badges. Archive any property John no longer owns.
3. **A property** (try Cypress Lake Shopping Center).
   - **Summary:** "How this location compares" lists strengths and concerns against your other properties.
   - **Who lives around this property:** 1/3/5-mile figures with ±, and trends marked significant or not.
   - **Jobs, Economy, Traffic, Flood and hazards, Nearby businesses:** each with "Sources · checked [date]".
   - **Tenants:** listing tenants are marked unverified. Confirm or archive them. Admins can map a public company to its SEC filer.
4. **Southside Shopping Center → Tenants.** Rite Aid shows its 2023 bankruptcy filing as a past event, with a link to the SEC filing.
5. **Screen.** Enter a real address (e.g. "7 Backus Avenue, Danbury, CT 06810"). Figures fill in within about a minute. Click **Save as candidate** to keep monitoring it.
6. **Compare.** Click **Add to compare** on 2–4 properties or screens, then open Compare. The best and weakest values are tinted only where higher or lower is clearly better, and a portfolio median and range column appears on the right.
7. **Data Sources.** Every source shows OK, Stale or Failing and when it was last checked.
8. **Phone.** Repeat steps 1 and 3 on your phone. Nothing should scroll sideways.

**What not to expect:** rents, vacancy, sales or property financials. These are out of scope, and the app never estimates them.

## Local preview (developers)
See `docs/DEPLOYMENT.md`, "First-time data bootstrap". Locally, run `bootstrap_data` against a SQLite settings module, then `python infra/start_all.py` with `RUN_BACKGROUND_WORKERS=true`.

---

# Access and workspace review

Use the existing Site: https://paragon-radar-workspace.amitsch5.chatgpt.site

The user chose to continue here on 2026-11-19. Sign in with ChatGPT; each visitor has
an isolated workspace even though the Site audience is public. No external hosting
account or separate password is needed. Export important saved work before a future
move. The prepared Django password option is deferred; see PASSWORD_ACCESS.md only
if an external migration is later authorized.

# Reviewing the implemented workspace (about 10 minutes)

**Current status:** this guide covers working UI features. It is not the final
Release 1 acceptance walkthrough. The current Site is live with ChatGPT sign-in.
External hosting is deferred. Data calculations, signals, screening, and comparison
workflows remain incomplete; use docs/08 for the full acceptance requirements.

Developers can run the isolated browser review described in USER_INTERFACE.md.
Use the steps below in your signed-in Site workspace.
No test account, password, or bypass is provided by this guide.

1. Open the Site and sign in with ChatGPT. Confirm you see your own workspace.
   Other visitors must not see your private notes or edits. Requests without
   sign-in must not receive business data.
2. On **This Week**, review the real record counts and confirmation queue. The
   initial imported portfolio contains 36 public records across 12 states, with
   35 reference pins. These counts change as your team edits records. The brief
   currently says “unavailable”; it must not claim there were no changes.
3. Open **Portfolio**. Filter by state, status, or asset type. The map and cards
   should represent the same selection. A missing pin must not remove a record
   from the list. Choose **List only** to hide the interactive map.
4. Open a property. Read its source period and **View provenance**, including the
   original listing and change history. A public listing does not establish
   current ownership. Confirm the record only after your own review.
5. Open **Correct / confirm pin**. Review the clearly labelled unsaved preview.
   Drag the marker or enter coordinates. The coordinate fields are a keyboard
   alternative to dragging. Tick the verification box only after checking the
   building. Cancel to discard changes, or **Save pin** to create a new revision.
   Ownership confirmation and pin verification are separate.
6. Open **Edit record** and change a team note. Save and inspect its history.
   If another team member changed the record while the form was open, the save
   must report a conflict. Choose **Reload record**, reopen the form, and review
   the latest values before trying again.
7. Search for an existing property by name or address. Results should open the
   saved record. Saved record search does not yet geocode arbitrary new addresses.
8. Open **Data Sources**. Inspect coverage, provider terms/attribution, privacy,
   and the dates of recorded checks. “Not checked” and “Stale” must remain visible.
   An empty check history must not be presented as healthy.
9. At phone width, use **Open navigation**, Tab through its controls, then Escape.
   Focus should stay in the open menu and return to the menu button on close.
   Dialogs must likewise support keyboard navigation and visible focus.
10. Check **Screen** and **Compare**. Their unavailable explanations are intentional
    until the required data workflows exist. Do not treat them as accepted P0
    functionality. Administrators can additionally inspect recorded job activity.

If tiles fail or WebGL is unavailable, the application must explain the failure
and retain property details/list access. The rings are distance illustrations,
not evidence that demographic or hazard checks have completed. Never interpret
missing data as zero, safe, or a property financial result.

Record the environment/commit, browser, action, and observed result when reporting
an issue. Keep private addresses and notes out of public issue reports. Production
acceptance still requires a real deployed URL, actual source jobs, reference checks,
owner access, backups, and the remaining requirements in docs/07.

Migration operators: follow [WORKSPACE_MIGRATION.md](WORKSPACE_MIGRATION.md) for private export validation, import, and cutover checks. The current local snapshot is verified; migration is deferred by user choice.
