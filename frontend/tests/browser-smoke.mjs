import { chromium } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs/promises";
const base = process.env.UI_BASE_URL;
if (!base || !process.env.UI_SESSION_KEY)
  throw new Error("Run through scripts/verification/ui_smoke.py");
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  headless: true,
});
const context = await browser.newContext();
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
  await page.getByLabel("State", { exact: true }).selectOption("CT");
  const property = page.locator(".property-card").first();
  const name = await property.locator("h3").innerText();
  await property.click();
  await page.getByRole("heading", { name, exact: true }).waitFor();
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
