# 01 · Research and Discovery

**Purpose:** Explain what we know about Paragon Realty Group, what we are assuming, what John still needs to answer, and why the first release focuses where it does.
**Research date:** 2026-11-17. All web sources were accessed on that date unless noted.

Every statement below carries one of three labels:

- **[Fact]** Verified from a public source, which is cited.
- **[Assumption]** A working assumption used so the work can proceed. It must be validated with John. Each one has an ID (A-xx) that other documents refer to.
- **[Question]** Needs John's input. Each one has an ID (Q-xx) and is listed in §5.

---

## 1. The business

### 1.1 Verified facts

| # | Fact | Source |
|---|---|---|
| F1 | Paragon Realty Group LLC is a private real estate development and management company based at 276 Post Road West, Suite 201, Westport, CT 06880. | [paragonct.com](https://paragonct.com/), [Contact](https://paragonct.com/contact/) |
| F2 | Its portfolio is "approximately 2,000,000 square feet" (also described as "in excess of two million") of investment commercial real estate. | [Home](https://paragonct.com/), [About](https://paragonct.com/about/) |
| F3 | Paragon and its affiliates have invested for over 35 years, "primarily shopping centers in the Northeast, Mid-Atlantic, and Southeast," with some office and mixed-use properties. | [About](https://paragonct.com/about/) |
| F4 | John Nelson founded Paragon in 1986 and is its Founder and CEO. He previously practiced real estate law at Paul, Weiss and holds a BA/BS, JD and Wharton MBA from Penn. He lives in Bridgehampton, NY. | [Executive Team](https://paragonct.com/executive-team/) |
| F5 | The executive team includes David Wright, CPM (President; property management, leasing, brokerage), Daniel Weinreb (Managing Principal; acquisitions, development, financing, leasing), Jennifer Conroy, CPA (CFO, joined 2025) and Adam Nelson (Principal, Acquisitions; joined 2020; sourcing, underwriting, leasing, dispositions, financing; formerly a Cushman & Wakefield broker). | [Executive Team](https://paragonct.com/executive-team/) |
| F6 | **Acquisition criteria:** Northeast, Mid-Atlantic and Southeast; neighborhood, community and regional shopping centers, in-fill retail strips and CBD retail condos; prefers dominant grocery-anchored centers but has bought shadow-anchored, junior-anchored and unanchored centers; $7M–$30M focus, up to $50M for one property and higher for portfolios; free-standing or in-fill strips considered under $3M; 50,000+ SF preferred; value-add through renovation, lease-up, anchor replacement, tenant-mix upgrades, outparcel development and adjacent land; "high barriers to entry." | [Acquisition Criteria](https://paragonct.com/acquisition-criteria/) |
| F7 | Paragon "responds quickly to submissions; performs due diligence, management and leasing analysis in-house." | [Acquisition Criteria](https://paragonct.com/acquisition-criteria/) |
| F8 | The public property page lists **36 properties in 12 states**: CT 13, PA 7, NY 5, OH 3, and one each in FL, MD, MA, NV, NJ, NC, ND and VT. Most are retail; a few are office or mixed-use. | [Properties](https://paragonct.com/properties/); full list in [`data/seed/paragon_public_properties.csv`](../data/seed/paragon_public_properties.csv) |
| F9 | Property pages present each site through **1/3/5-mile rings** (3/5/10-mile for less dense sites) showing population and average household income labelled **"Esri 2021 Demographics"**, plus traffic counts (vehicles per day), tenant lists, "area retailers" and current availabilities. | Property pages, e.g. [Kingston Marketplace](https://paragonct.com/properties/kingston-marketplace/), [Barrington Plaza](https://paragonct.com/properties/barrington-plaza/) |
| F10 | Recent transaction activity: the website news page lists "Disposition of 44 Main Street" (Westport), dated 2026-10-05, headlined "Rye realty company buys posh Westport building for $23.4M." A Paragon affiliate, with Clarion Partners, bought 44 Main St in 2015 for $22.5M. | [News](https://paragonct.com/news/); [NEREJ (2015)](https://nerej.com/keefe-lindland-and-fellah-of-hk-group-sell-44-main-street-22-5-million) |
| F11 | Paragon bought the 131,000 SF Barrington Plaza (Great Barrington, MA) from a Kimco Realty affiliate (reported January 2018). Trade press also reports a 2007 Norwalk acquisition (490/508 Westport Ave) and a 2016 Kingston, NY acquisition ("Kings Mall," about $19.6M). | [Shopping Center Business](https://shoppingcenterbusiness.com/paragon-realty-group-acquires-131-000-square-foot-shopping-center-in-massachusetts/), [GlobeSt 2007](https://www.globest.com/amp/2007/10/18/paragon-gets-norwalk-retail-office-property/), CoStar headline (paywalled; seen only in search results) |
| F12 | Some public listing content is out of date. Southside Shopping Center (Scranton) lists Rite Aid as an anchor, and Rite Aid's parent filed an SEC 8-K with Item 1.03 (bankruptcy) on 2023-10-16. Cottman Plaza lists Sprint, a brand that no longer exists after its merger into T-Mobile. The listings use 2021 demographics. | Property pages; [EDGAR submissions API, CIK 84129](https://data.sec.gov/submissions/CIK0000084129.json) (verified 2026-11-17) |

### 1.2 What these facts imply (inferences, not facts)

- **The core asset is the neighborhood and community shopping center.** Its value depends on the **trade area** (households, income, growth), **co-tenancy** (anchors and the nearby retailers that draw traffic), **access and visibility** (traffic counts) and **tenant credit** (whether anchors and national tenants stay solvent and keep their stores open). Paragon's own listings present exactly these items (F9).
- **Paragon's current market evidence is static and dated.** Listing demographics are from 2021, traffic counts are older than the current federal data, and tenant lists are not maintained. A platform that keeps this evidence **current, sourced and comparable** directly upgrades how Paragon already describes its properties.
- **Acquisition speed matters (F7).** A credible first-pass read of any submitted address in minutes, compared with properties Paragon already owns, fits how the firm works.
- **The geography is national, not just Connecticut** (F8). Core data sources must therefore cover the whole US. State-only datasets (for example Connecticut's open data) can only be enhancements.
- The portfolio is managed **in-house** (F5, F7), so leasing and management staff could become secondary users.

## 2. Users

| User | Role (verified) | Likely use (assumption) |
|---|---|---|
| **John Nelson**, primary | Founder and CEO (F4) | **[A-01]** Reviews a weekly digest of what changed around owned properties, opens evidence when something looks material, and compares acquisition locations before approving underwriting time. Busy and non-technical in his tool use. Expects executive-level clarity. |
| **Adam Nelson**, secondary | Principal, Acquisitions (F5) | **[A-02]** Runs first-pass screens on submitted deals and builds comparisons for John. Also responsible for leasing, so he cares about co-tenancy and nearby retailer changes. |
| David Wright / Daniel Weinreb, secondary | President / Managing Principal (F5) | **[A-02]** Occasional users for property-level context (management and leasing). |

**[A-03]** Up to 10 named users. No external or tenant-facing access.
**[A-04]** Desktop or laptop is the primary device. The weekly digest and property summaries must also work well on a phone.

## 3. Candidate workflows and prioritization

We scored each candidate workflow from 1 to 5 on **frequency**, **decision value**, **data feasibility with legitimate free or public data**, and **effort**. A higher effort score means less effort.

| ID | Workflow | Freq. | Value | Data feasibility | Effort | Decision |
|---|---|---|---|---|---|---|
| W1 | **Property trade-area profile**: a current, sourced picture of one location (rings, economy, retail landscape, access, hazards) | 4 | 4 | 5 (national public data, verified) | 4 | **Release 1 (foundation)** |
| W2 | **Portfolio watch and weekly brief**: what changed around owned properties that could affect tenant demand or vacancy risk | 5 | 4 | 4 (most sources update monthly to annually; SEC filings daily) | 3 | **Release 1** |
| W3 | **Acquisition first-pass screen**: any US address to a profile, plus an evidence summary measured against Paragon's own portfolio | 3 | 5 | 5 | 4 | **Release 1** |
| W4 | **Side-by-side comparison** of 2–4 locations plus a portfolio benchmark | 3 | 4 | 5 | 4 | **Release 1** |
| W5 | **Tenant credit watch**: SEC filings (bankruptcy, exit/closure items) for public-company tenants | 4 | 5 | 4 (public companies only, verified) | 4 | **Release 1 (limited to public companies)** |
| W6 | Market rents, comps, availability and vacancy | 4 | 5 | **1**: CoStar, LoopNet and Crexi are paid or restricted and offer no permitted free API | 2 | **Excluded** (can be entered by hand in later releases) |
| W7 | Deal sourcing (finding properties for sale) | 3 | 4 | **1**: listings platforms are paid or restricted | 2 | **Excluded** |
| W8 | Underwriting, pro formas, valuation | 3 | 5 | n/a (internal data, done in Excel) | 1 | **Excluded** |
| W9 | Foot-traffic analytics | 3 | 4 | **1**: paid (e.g. Placer.ai) | 3 | **Excluded** (future integration if Paragon subscribes) |
| W10 | Zoning, entitlement and redevelopment feasibility | 2 | 4 | **1**: municipal and fragmented | 1 | **Excluded** |
| W11 | Leasing prospecting (retailers expanding nearby) | 2 | 3 | 3 (could use Overture brand appearances) | 3 | Deferred to a later release |
| W12 | Connecticut sale comps from state open data | 2 | 3 | 4 (verified, but CT only) | 4 | Deferred to Release 1.1 |

**Why this release scope.** W1 is the foundation for W2–W4. W2 answers John's "what deserves my attention this week" question. W3 and W4 answer "how do potential acquisition locations compare" and "what evidence supports investigating further." W5 addresses the biggest vacancy risk for a shopping-center owner, an anchor or national tenant failing, using a free, authoritative, daily source. Workflows that depend on proprietary market data (W6, W7, W9) are excluded, not faked.

## 4. Working assumptions (validate with John)

| ID | Assumption | Why it is reasonable | Effect if wrong |
|---|---|---|---|
| A-01 | John is the primary user; his core loops are a weekly review and ad-hoc comparisons. | Matches his question list and his role. | The home screen emphasis may shift toward acquisitions. |
| A-02 | Adam (acquisitions and leasing) is the main secondary user. | Matches his role in F5. | Minor. |
| A-03 | Up to 10 invited users; no public or tenant access. | Private firm, small team. | Auth model is unchanged. |
| A-04 | Desktop first; brief and summaries must be phone-friendly. | Executive usage pattern. | Layout priorities change. |
| A-05 | **The owned portfolio equals the 36 public listings, marked "unconfirmed," until John confirms it.** Users can add, edit or archive properties. | Only public source available; the website may include sold properties (see F10) and omit unlisted ones. | None. The app treats the portfolio as user-maintained. |
| A-06 | Publicly listed tenants are a starting tenant roster, marked "unconfirmed / from public listing." | Same as A-05. | Tenant watch accuracy depends on John or Adam confirming. |
| A-07 | Ring-based trade areas (1/3/5 mi by default; 3/5/10 mi for less dense sites) are the right lens. Drive-time areas are not needed in Release 1. | Paragon's own listings use rings (F9). | Drive-time areas would need a paid or self-hosted routing service. |
| A-08 | The weekly brief arrives on **Monday, 7:00 a.m. US Eastern**, in the app. Email delivery is an optional P1 item. | Common executive cadence. | Change a schedule setting. |
| A-09 | Release 1 uses only free or public data and user input. Ongoing running cost stays under about $50/month. | No paid subscriptions confirmed. | Paid sources can be added later (see doc 03 §4). |
| A-10 | No rent rolls, leases, sales reports or financial data in Release 1. | Sensitive internal data and higher security burden; not needed for the chosen workflows. | A later release adds secure upload. |
| A-11 | Default materiality thresholds (doc 04 §5) are reasonable starting points. | Based on common practice and data noise levels. | Thresholds are configuration, not code. |
| A-12 | Release 1 covers US addresses only, in English. | Paragon invests only in the US (F6, F8). | None. |

## 5. Open questions for John

None of these block the build. Each has a default assumption.

| ID | Question | Default until answered |
|---|---|---|
| Q-01 | Which of the 36 listed properties do you still own, and are there unlisted ones? | A-05 |
| Q-02 | Who else at Paragon should have access? | A-02, A-03 |
| Q-03 | Which matters more right now: monitoring the portfolio or screening acquisitions? | Both, with the brief as the home screen |
| Q-04 | Does Paragon subscribe to CoStar, Esri Business Analyst, Placer.ai or similar? If so, we could integrate under that licence in a later release. | No subscriptions |
| Q-05 | Which tenants matter most (anchors, national credit tenants)? Can you confirm current tenant lists? | A-06 |
| Q-06 | What counts as "material" to you (for example, how much population decline, or which kinds of nearby closures)? | A-11 thresholds |
| Q-07 | When and how do you want the weekly brief (day, time, email or app)? | A-08 |
| Q-08 | Which markets or metros are you actively targeting for acquisitions? | Any US address |
| Q-09 | Do you have 2–4 recent or live deal addresses we can use as realistic test cases? | Use public listings as test cases |
| Q-10 | Should each property use 1/3/5-mile or 3/5/10-mile rings? | 1/3/5 by default; the website's choice where it differs |
| Q-11 | Any confidentiality requirements for candidate (deal) addresses beyond "private to the Paragon team"? | Candidate locations visible only to signed-in users; never shared with third parties beyond required data lookups (doc 06 §2) |
| Q-12 | Is John's main device a laptop, an iPad or a phone? | A-04 |

## 6. Discovery not done (and not invented)

- No interviews with John or his team. Every user need above is inferred from public information and Adi's brief.
- No access to Paragon's internal portfolio data, leases or financials.
- The current ownership status of each listed property was not verified.

These gaps are handled by assumptions A-01 to A-12, by making the portfolio and tenants user-editable, and by a feedback mechanism in the product (FR-34 in doc 02).
