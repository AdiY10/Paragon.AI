# Access and workspace review

Adi's current priority is a regular HTTPS host with named email/password access,
without a ChatGPT account. The password implementation is locally verified; a regular
host URL and private credentials have not yet been issued. See PASSWORD_ACCESS.md.
When deployed, open the supplied URL in a fresh browser, sign in with the separately
delivered account/password, verify portfolio data, sign out, and verify that API
requests no longer return business data. Wrong passwords must reveal no data.

# Reviewing the implemented workspace (about 10 minutes)

**Current status:** this guide covers working UI features. It is not the final
Release 1 acceptance walkthrough. There is no deployed test URL or completed
owner sign-in setup yet. The data calculations, signals, screening, and comparison
workflows remain incomplete; use docs/08 for the full acceptance requirements.

Developers can run the isolated browser review described in USER_INTERFACE.md.
Once a real environment and invited account are available, use the steps below.
No test account, password, or bypass is provided by this guide.

1. Sign in with your invited organization account. Confirm you can see your own
   workspace and sign out. An uninvited account must be denied access.
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
