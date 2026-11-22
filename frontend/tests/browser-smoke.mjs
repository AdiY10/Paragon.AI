import { chromium } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs/promises";
const base = process.env.UI_BASE_URL;
if (!base || !process.env.UI_SESSION_KEY)
  throw new Error("Run through scripts/verification/ui_smoke.py");
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  headless: true,
  args: ["--enable-webgl", "--use-angle=swiftshader-webgl"],
});
const context = await browser.newContext({ ignoreHTTPSErrors: true });
await context.addCookies([
  {
    name: "sessionid",
    value: process.env.UI_SESSION_KEY,
    url: base,
    httpOnly: true,
    sameSite: "Lax",
  },
]);
const page = await context.newPage();
const errors = [];
if (process.env.UI_DEBUG_NETWORK) {
  page.on("console", (message) => console.log("Browser:", message.text()));
  page.on("requestfailed", (request) => {
    if (request.url().startsWith("https://tile.openstreetmap.org/"))
      console.log("Tile request failed:", request.failure()?.errorText);
  });
  page.on("response", (response) => {
    if (
      response.url().startsWith("https://tile.openstreetmap.org/") &&
      response.status() >= 400
    )
      console.log("Tile HTTP status:", response.status());
  });
}

page.on("pageerror", (error) => errors.push(error.message));
const output = process.env.UI_SCREENSHOT_DIR;
if (output) await fs.mkdir(output, { recursive: true });
try {
  for (const width of [1280, 768, 375]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(base);
    await page
      .getByRole("heading", { level: 1 })
      .first()
      .waitFor();
    await page.getByRole("heading", { name: "Properties", level: 1 }).waitFor();
    // WI-1 shell: top navigation and account menu.
    if (width > 640) {
      const mainNav = page.getByRole("navigation", { name: "Main", exact: true });
      for (const label of ["Properties", "Analyze", "Alerts", "Compare"])
        await mainNav.getByRole("link", { name: label, exact: true }).waitFor();
      if ((await mainNav.getByRole("link", { name: "Properties", exact: true }).getAttribute("aria-current")) !== "page")
        throw new Error("Properties is not the current page");
      await page.getByRole("button", { name: "Account menu", exact: true }).click();
      for (const label of ["Data sources", "Admin"])
        await page.getByRole("link", { name: label, exact: true }).waitFor();
      await page.getByRole("button", { name: "Sign out", exact: true }).waitFor();
      await page.keyboard.press("Escape");
      if ((await page.evaluate(() => document.activeElement?.getAttribute("aria-label"))) !== "Account menu")
        throw new Error("Account menu did not return focus");
    }
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw new Error(`Horizontal overflow at ${width}`);
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze();
    if (result.violations.length)
      throw new Error(
        JSON.stringify(
          result.violations.map((v) => ({
            id: v.id,
            nodes: v.nodes.map((n) => n.target),
          })),
        ),
      );
    if (width === 375) {
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
      const navigation = page.getByRole("dialog", {
        name: "Workspace navigation",
      });
      await navigation.waitFor();
      for (let tab = 0; tab < 12; tab++) {
        await page.keyboard.press("Tab");
        if (
          !(await navigation.evaluate((element) =>
            element.contains(document.activeElement),
          ))
        )
          throw new Error("Mobile navigation lost its focus trap");
      }
      await page.keyboard.press("Escape");
      // Focus returns to the trigger once the dialog has unmounted (next animation frame).
      await page
        .waitForFunction(() => document.activeElement?.getAttribute("aria-label") === "Open navigation", null, { timeout: 2000 })
        .catch(() => {
          throw new Error("Mobile navigation did not restore focus");
        });
    }
    if (output)
      await page.screenshot({
        path: `${output}/dashboard-${width}.png`,
        fullPage: true,
      });
  }
  await page.setViewportSize({ width: 1280, height: 1000 });
  // Old routes redirect (WI-1): #/portfolio → #/, #/screen → #/analyze, #/setup → #/.
  for (const [from, to] of [["#/screen", "#/analyze"], ["#/setup", "#/"], ["#/portfolio", "#/"]]) {
    await page.goto(`${base}/${from}`);
    await page.waitForFunction((hash) => location.hash === hash, to);
  }
  await page.getByRole("heading", { name: "Properties", level: 1 }).waitFor();
  // WI-3 portfolio map: HTML pins + screen-space clusters; data-pins counts every pinned record.
  await page.locator('.location-map[data-ready=true][data-pins="35"]').waitFor();
  await page.locator(".portfolio-pin:not([hidden])").first().waitFor();
  if (await page.locator(".map-status").count())
    throw new Error("Live map did not load normally");
  const clusterLabel = await page.locator(".map-cluster").first().getAttribute("aria-label");
  if (!/^\d+ properties.*Zoom in$/.test(clusterLabel ?? ""))
    throw new Error(`Unexpected cluster label: ${clusterLabel}`);
  await page.locator(".portfolio-pin:not([hidden])").first().hover();
  await page.locator(".hover-card").getByText("Open analysis").waitFor();
  await page.mouse.move(5, 5);
  const mapA11y = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  if (mapA11y.violations.length)
    throw new Error(
      JSON.stringify(
        mapA11y.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => n.target),
        })),
      ),
    );
  if ((await page.locator(".portfolio-pin").count()) !== 35)
    throw new Error("Expected 35 real portfolio reference pins");
  if (output)
    await page.screenshot({
      path: `${output}/portfolio-map-1280.png`,
      fullPage: false,
    });
  for (const width of [768, 375]) {
    await page.setViewportSize({ width, height: 1000 });
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw new Error(`Map overflows at ${width}`);
  }
  await page.setViewportSize({ width: 1280, height: 1000 });
  // WI-4 Properties table: 36 owned rows, sortable headers, filters and compare selection in the URL.
  const ownedTable = page.getByRole("table", { name: "Owned properties" });
  if ((await ownedTable.locator("tbody tr").count()) !== 36)
    throw new Error("Expected 36 owned property rows");
  await ownedTable.getByRole("button", { name: "People within 3 mi" }).click();
  if ((await ownedTable.locator("th[aria-sort]").getAttribute("aria-sort")) !== "descending")
    throw new Error("Sorting did not set aria-sort");
  if (!page.url().includes("sort=population"))
    throw new Error("Sort is not in the URL");
  await page.getByLabel("State", { exact: true }).selectOption("CT");
  await page.waitForFunction(() => location.hash.includes("state=CT"));
  if ((await ownedTable.locator("tbody tr td:nth-child(3)").allInnerTexts()).some((state) => state !== "CT"))
    throw new Error("State filter left other states in the table");
  const compareBoxes = ownedTable.getByRole("checkbox", { name: /^Compare / });
  await compareBoxes.nth(0).check();
  await compareBoxes.nth(1).check();
  const tray = page.getByRole("complementary", { name: "Compare selection" });
  await tray.getByRole("link", { name: "Compare 2 properties" }).click();
  await page.waitForFunction(() => location.hash.startsWith("#/compare?ids="));
  // WI-8 Compare: both chosen properties are columns of the side-by-side table.
  await page.getByRole("heading", { name: "Compare", level: 1 }).waitFor();
  await page.getByRole("table", { name: "Side-by-side comparison" }).waitFor();
  if ((await page.getByRole("table", { name: "Side-by-side comparison" }).locator("thead th").count()) !== 4)
    throw new Error("Compare should show two properties plus the measure and portfolio columns");
  await page.goBack();
  await page.getByRole("table", { name: "Owned properties" }).waitFor();
  await page.getByRole("button", { name: "Clear", exact: true }).click();
  const property = ownedTable.locator("tbody tr").first().getByRole("rowheader").getByRole("link");
  const name = await property.innerText();
  const propertyHref = await property.getAttribute("href");
  await page.goto(`${base}/${propertyHref.replace("#/p/", "#/locations/")}`);
  await page.waitForFunction((hash) => location.hash === hash, propertyHref);
  if ((await page.getByRole("navigation", { name: "Main", exact: true }).getByRole("link", { name: "Properties", exact: true }).getAttribute("aria-current")) !== "page")
    throw new Error("Properties is not current on a property analysis");
  await page.getByRole("heading", { name, exact: true }).waitFor();
  // WI-6 analysis page: fixed section menu, takeaways or progress, and no buttons that run an analysis.
  const sectionNav = page.getByRole("navigation", { name: "Analysis sections" });
  await sectionNav.waitFor();
  if ((await sectionNav.getByRole("link").count()) !== 10) throw new Error("Expected 10 analysis sections");
  await page.getByText(/^(Key takeaways|Analysis progress)$/).first().waitFor();
  if (await page.getByRole("button", { name: /calculate|check area data|confirm/i }).count())
    throw new Error("Analysis page still shows a run/confirm button");
  await sectionNav.getByRole("link", { name: "Risk" }).click();
  await page.waitForFunction(() => location.hash.includes("section=risk"));
  if ((await page.evaluate(() => document.activeElement?.id)) !== "risk-title")
    throw new Error("Section link did not move focus to the section heading");
  // Property pages at phone width: no overflow and no WCAG 2.2 AA violations (R2.23).
  await page.setViewportSize({ width: 375, height: 1000 });
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
    throw new Error("Property page overflows at 375");
  const propertyA11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
  if (propertyA11y.violations.length)
    throw new Error(`Property page a11y at 375: ${propertyA11y.violations.map((v) => v.id).join(", ")}`);
  await page.setViewportSize({ width: 1280, height: 1000 });
  // Overview map: subject pin and the three radius rings.
  await page.locator("#overview .location-map[data-ready=true][data-rings='3']").waitFor();
  await page.locator("#overview .map-marker").first().waitFor();
  const propertyActions = async (item) => {
    await page.getByRole("button", { name: "Property actions", exact: true }).click();
    await page.getByRole("button", { name: item, exact: true }).click();
  };
  if (output)
    await page.screenshot({
      path: `${output}/property-map-1280.png`,
      fullPage: true,
    });
  await propertyActions("Record & history");
  await page.getByRole("dialog", { name: "Record & history" }).waitFor();
  await page
    .getByRole("heading", { name: "Property record evidence" })
    .waitFor();
  await page.getByRole("heading", { name: "Change history" }).waitFor();
  await page.keyboard.press("Escape");
  await page
    .waitForFunction(() => document.activeElement?.getAttribute("aria-label") === "Property actions", null, { timeout: 2000 })
    .catch(() => {
      throw new Error("Closing a Property actions dialog did not return focus to the menu");
    });
  await propertyActions("Edit details");
  await page
    .getByLabel("Team notes")
    .fill("Browser verification note — isolated test database only.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await page
    .getByText("Browser verification note — isolated test database only.", {
      exact: true,
    })
    .waitFor();
  await propertyActions("Correct pin");
  const pinDialog = page.getByRole("dialog", {
    name: "Review the property pin",
  });
  await pinDialog.locator(".location-map[data-ready=true]").waitFor();
  const beforeDrag = await pinDialog
    .getByLabel("Longitude", { exact: true })
    .inputValue();
  const dragPin = await pinDialog.locator(".map-marker").boundingBox();
  if (!dragPin) throw new Error("Missing draggable preview pin");
  await page.mouse.move(
    dragPin.x + dragPin.width / 2,
    dragPin.y + dragPin.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    dragPin.x + dragPin.width / 2 + 30,
    dragPin.y + dragPin.height / 2,
    { steps: 8 },
  );
  await page.mouse.up();
  await page.waitForFunction(
    (before) =>
      document.querySelector("input[name=longitude]")?.value !== before,
    beforeDrag,
  );
  await pinDialog.getByLabel("Latitude", { exact: true }).fill("41.138370");
  await pinDialog.getByLabel("Longitude", { exact: true }).fill("-73.300803");
  await page.setViewportSize({ width: 375, height: 1000 });
  if (
    await pinDialog.evaluate(
      (element) => element.scrollWidth > element.clientWidth,
    )
  )
    throw new Error("Pin dialog overflows on phone");
  if (output)
    await page.screenshot({
      path: `${output}/pin-editor-375.png`,
      fullPage: false,
    });
  await page.setViewportSize({ width: 1280, height: 1000 });
  await pinDialog
    .getByLabel("I checked that this pin is on the property building.")
    .check();
  await pinDialog
    .getByRole("button", { name: "Save pin", exact: true })
    .click();
  await pinDialog.waitFor({ state: "hidden" });
  const savedPin = await page.evaluate(async () => {
    const path =
      location.hash.slice(1).split("?")[0].replace("/p/", "/api/locations/") + "/";
    return (await fetch(path)).json();
  });
  if (
    savedPin.current_revision.number !== 2 ||
    savedPin.current_revision.method !== "manual" ||
    !savedPin.current_revision.confirmed ||
    savedPin.analysis_version !== 2
  )
    throw new Error(
      "Pin save did not preserve revision and analysis semantics",
    );
  await propertyActions("Edit details");
  const editDialog = page.getByRole("dialog", { name: "Edit property record" });
  await editDialog
    .getByLabel("Team notes")
    .fill("Stale form must not overwrite the newer record.");
  await page.evaluate(async () => {
    const path =
      location.hash.slice(1).split("?")[0].replace("/p/", "/api/locations/") + "/";
    const record = await (await fetch(path)).json();
    const csrf = document.querySelector('meta[name="csrf-token"]').content;
    const response = await fetch(path, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify({
        expected_version: record.version,
        notes: "Concurrent browser test update — isolated database only.",
      }),
    });
    if (!response.ok) throw new Error("Concurrent test update failed");
    window.dispatchEvent(new Event("visibilitychange"));
  });
  await page.waitForFunction(
    () =>
      document.querySelector(".notes p")?.textContent ===
      "Concurrent browser test update — isolated database only.",
  );
  await editDialog.getByRole("button", { name: "Save changes" }).click();
  await editDialog
    .getByRole("alert")
    .filter({ hasText: /record changed|location changed/i })
    .waitFor();
  await editDialog.getByRole("button", { name: "Reload record" }).click();
  await page
    .getByText("Concurrent browser test update — isolated database only.", {
      exact: true,
    })
    .waitFor();
  if (output)
    await page.screenshot({
      path: `${output}/property-1280.png`,
      fullPage: true,
    });
  // WI-8 Alerts: High and Watch are on by default, FYI is opt-in.
  await page.goto(`${base}/#/alerts`);
  await page.getByRole("heading", { name: "Alerts", level: 1 }).waitFor();
  if (
    !(await page.getByRole("checkbox", { name: "High", exact: true }).isChecked()) ||
    !(await page.getByRole("checkbox", { name: "Watch", exact: true }).isChecked()) ||
    (await page.getByRole("checkbox", { name: "FYI", exact: true }).isChecked())
  )
    throw new Error("Alerts should default to High and Watch");
  await page.getByText(/No High or Watch alerts\.|alerts?$/).first().waitFor();
  for (const width of [768, 375]) {
    await page.setViewportSize({ width, height: 1000 });
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
      throw new Error(`Alerts page overflows at ${width}`);
    const alertsA11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    if (alertsA11y.violations.length)
      throw new Error(`Alerts page a11y at ${width}: ${alertsA11y.violations.map((v) => v.id).join(", ")}`);
  }
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto(`${base}/#/sources`);
  await page.getByRole("heading", { name: "Data sources", level: 1 }).waitFor();
  const sourceList = page.getByRole("list", { name: "Sources" });
  await sourceList.waitFor();
  if ((await sourceList.locator(":scope > li").count()) !== 16)
    throw new Error("Expected 16 real catalog sources");
  if (output)
    await page.screenshot({
      path: `${output}/sources-1280.png`,
      fullPage: true,
    });
  // WI-7 Analyze a place: a map click offers "Analyze this point", which opens the new place's analysis.
  await page.goto(`${base}/#/analyze`);
  await page.getByRole("heading", { name: "Analyze a place", level: 1 }).waitFor();
  await page.getByRole("heading", { name: "Recent analyses" }).waitFor();
  const pickMap = page.locator(".location-map[data-ready=true]");
  await pickMap.waitFor();
  for (const width of [768, 375]) {
    await page.setViewportSize({ width, height: 1000 });
    if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
      throw new Error(`Analyze page overflows at ${width}`);
    const analyzeA11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"]).analyze();
    if (analyzeA11y.violations.length)
      throw new Error(`Analyze page a11y at ${width}: ${analyzeA11y.violations.map((v) => v.id).join(", ")}`);
  }
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.waitForTimeout(500);
  const pickBox = await pickMap.boundingBox();
  await page.mouse.click(pickBox.x + pickBox.width * 0.5, pickBox.y + pickBox.height * 0.5);
  await page.getByRole("button", { name: "Analyze this point", exact: true }).click();
  await page.waitForFunction(() => /^#\/analyze\/[0-9a-f-]{36}/.test(location.hash), null, { timeout: 30000 });
  await page.getByRole("heading", { level: 1 }).waitFor();
  if ((await page.getByRole("navigation", { name: "Analysis sections" }).getByRole("link").count()) !== 9)
    throw new Error("A new place should have 9 analysis sections (no tenants)");
  await page.getByRole("button", { name: "Star", exact: true }).click();
  await page.waitForFunction(() =>
    [...document.querySelectorAll(".analysis-actions button[aria-pressed]")].some(
      (b) => b.textContent.includes("Starred") && b.getAttribute("aria-pressed") === "true",
    ),
  );
  await page.goto(`${base}/#/analyze`);
  await page.locator(".recent-list .star-button[aria-pressed=true]").first().waitFor();
  await page.goto(base);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  const searchDialog = page.getByRole("dialog", { name: "Search properties" });
  const search = searchDialog.getByRole("textbox", { name: "Search by name or address" });
  await search.fill(name);
  await search.press("Enter");
  await searchDialog.getByRole("list", { name: "Search results" }).getByRole("link").first().waitFor();
  await searchDialog.getByRole("button", { name: "Analyze this address" }).waitFor();
  if (page.url().includes(encodeURIComponent(name)) || page.url().includes(name))
    throw new Error("Search text leaked into the URL");
  await page.keyboard.press("Escape");
  const records = (
    await (
      await context.request.get(base + "/api/locations/?status=all")
    ).json()
  ).results;
  for (const [seedId, expected] of [
    ["P03", "matched"],
    ["P21", "ambiguous"],
    ["P20", "no_match"],
  ]) {
    const record = records.find((item) => item.seed_id === seedId);
    const before = await (
      await context.request.get(`${base}/api/locations/${record.id}/`)
    ).json();
    await page.goto(`${base}/#/p/${record.id}`);
    await page.getByRole("heading", { level: 1 }).waitFor();
    await propertyActions("Find address pin");
    const dialog = page.getByRole("dialog", {
      name: "Find a Census address pin",
    });
    await dialog
      .getByRole("button", { name: "Find suggestions", exact: true })
      .click();
    if (expected === "no_match") {
      await dialog
        .getByRole("status")
        .filter({ hasText: "No Census match." })
        .waitFor();
      const after = await (
        await context.request.get(`${base}/api/locations/${record.id}/`)
      ).json();
      if (
        after.version !== before.version ||
        after.current_revision.id !== before.current_revision.id
      )
        throw new Error("No-match changed the saved pin");
      await page.keyboard.press("Escape");
      continue;
    }
    await dialog.getByRole("radio").first().waitFor();
    if (expected === "ambiguous") {
      if ((await dialog.getByRole("radio").count()) !== 2)
        throw new Error("Expected actual ambiguous Mount Kisco alternatives");
      if (
        await dialog
          .getByRole("radio")
          .evaluateAll((inputs) => inputs.some((input) => input.checked))
      )
        throw new Error("Ambiguity was preselected");
      if (
        !(await dialog
          .getByRole("button", { name: "Use selected Census pin" })
          .isDisabled())
      )
        throw new Error("Ambiguous accept was enabled before selection");
      await dialog.getByRole("radio").nth(1).check();
    }
    await dialog.locator(".location-map[data-ready=true]").waitFor();
    if (seedId === "P03") {
      await page.setViewportSize({ width: 375, height: 1000 });
      if (
        await dialog.evaluate(
          (element) => element.scrollWidth > element.clientWidth,
        )
      )
        throw new Error("Census dialog overflows on phone");
      if(output)await page.screenshot({path:`${output}/census-review-375.png`,fullPage:false});
      const scan = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze();
      if (scan.violations.length)
        throw new Error(
          JSON.stringify(
            scan.violations.map((v) => ({
              id: v.id,
              nodes: v.nodes.map((n) => n.target),
            })),
          ),
        );
      if (output)
        await page.screenshot({
          path: `${output}/census-review-375.png`,
          fullPage: false,
        });
      await page.setViewportSize({ width: 1280, height: 1000 });
    }
    await dialog
      .getByRole("button", { name: "Use selected Census pin", exact: true })
      .click();
    await dialog.waitFor({ state: "hidden" });
    const after = await (
      await context.request.get(`${base}/api/locations/${record.id}/`)
    ).json();
    if (
      after.current_revision.confirmed ||
      after.confirmed ||
      after.version !== before.version + 1 ||
      !after.current_revision.context.snapshot_id
    )
      throw new Error(
        "Census acceptance lost evidence or fabricated verification",
      );
  }
  const finalRecords=await(await context.request.get(base+'/api/locations/?status=all')).json();
  const expectedPinned=finalRecords.results.filter(item=>item.current_revision.lat!==null).length;
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
  await page.goto(`${base}/#/`);
  await page
    .getByText("Basemap tiles unavailable.", { exact: false })
    .waitFor();
  await page.locator(`.location-map[data-ready=true][data-pins="${expectedPinned}"]`).waitFor();
  if ((await page.locator(".portfolio-pin").count()) !== expectedPinned)
    throw new Error("Tile failure lost the saved pins");
  await page.unroute("https://tile.openstreetmap.org/**");
  const anonymous = await browser.newContext();
  const anonymousPage = await anonymous.newPage();
  const response = await anonymousPage.goto(`${base}/api/locations/`);
  if (response.status() !== 403)
    throw new Error("Anonymous API was not denied");
  await anonymous.close();
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(
    "UI browser smoke passed: Properties map/table/sort/filters/compare tray, Compare table, Alerts defaults, Sources list, analysis page sections/menu/Property actions, Analyze map point + star, top navigation, account menu, legacy redirects, 375/768/1280 layouts, WCAG AA, private APIs, filters, provenance, real edits, confirmation, sources, POST search, pin dragging/revisions, concurrent-edit conflicts, mobile keyboard focus, and live Census match/ambiguity/no-match review.",
  );
} finally {
  await browser.close();
}
