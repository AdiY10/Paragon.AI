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
      .getByRole("heading", { name: "Your portfolio, in focus." })
      .waitFor();
    await page.getByText("36", { exact: true }).first().waitFor();
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )
    )
      throw new Error(`Horizontal overflow at ${width}`);
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
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
    if (output)
      await page.screenshot({
        path: `${output}/dashboard-${width}.png`,
        fullPage: true,
      });
  }
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto(`${base}/#/portfolio`);
  await page.getByRole("heading", { name: "The portfolio." }).waitFor();
  await page.locator(".location-map[data-ready=true]").waitFor();
  await page.locator(".map-marker").first().waitFor();
  if (await page.locator(".map-status").count())
    throw new Error("Live map did not load normally");
  const mapA11y = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
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
  if ((await page.locator(".map-marker").count()) !== 35)
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
  await page.getByLabel("State", { exact: true }).selectOption("CT");
  const property = page.locator(".property-card").first();
  const name = await property.locator("h3").innerText();
  await property.click();
  await page.getByRole("heading", { name, exact: true }).waitFor();
  await page.locator(".location-map[data-ready=true]").waitFor();
  await page.locator(".map-marker").first().waitFor();
  await page.locator(".location-map[data-rings='3']").waitFor();
  if (output)
    await page.screenshot({
      path: `${output}/property-map-1280.png`,
      fullPage: true,
    });
  await page.getByRole("button", { name: "View provenance" }).click();
  await page
    .getByRole("heading", { name: "Property record evidence" })
    .waitFor();
  await page.getByRole("heading", { name: "Change history" }).waitFor();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Edit record" }).click();
  await page
    .getByLabel("Team notes")
    .fill("Browser verification note — isolated test database only.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await page
    .getByText("Browser verification note — isolated test database only.", {
      exact: true,
    })
    .waitFor();
  await page
    .getByRole("button", { name: "Confirm record", exact: true })
    .click();
  await page.getByText("Record confirmed.", { exact: true }).waitFor();
  if (output)
    await page.screenshot({
      path: `${output}/property-1280.png`,
      fullPage: true,
    });
  await page.goto(`${base}/#/sources`);
  await page
    .getByRole("heading", { name: "The evidence, explained." })
    .waitFor();
  if ((await page.locator(".source-card").count()) !== 16)
    throw new Error("Expected 16 real catalog sources");
  if (output)
    await page.screenshot({
      path: `${output}/sources-1280.png`,
      fullPage: true,
    });
  await page.goto(base);
  const search = page.getByRole("textbox", {
    name: "Search portfolio by name or address",
  });
  await search.fill(name);
  await search.press("Enter");
  await page.locator(".search-results").getByRole("link").first().waitFor();
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.abort(),
  );
  await page.goto(`${base}/#/portfolio`);
  await page
    .getByText("Basemap tiles unavailable.", { exact: false })
    .waitFor();
  if ((await page.locator(".map-marker").count()) !== 35)
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
    "UI browser smoke passed: 375/768/1280 layouts, WCAG AA, private APIs, filters, provenance, real edits, confirmation, sources, and POST search.",
  );
} finally {
  await browser.close();
}
