import { Miniflare } from "miniflare";
import { chromium } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import fs from "node:fs/promises";
import http from "node:http";
import assert from "node:assert/strict";
const mf = new Miniflare({
  modules: true,
  scriptPath: "dist/server/index.js",
  compatibilityDate: "2026-05-15",
  d1Databases: { DB: "paragon-qa" },
  port: 0,
});
const db = await mf.getD1Database("DB");
for (const file of (await fs.readdir("drizzle"))
  .filter((f) => f.endsWith(".sql"))
  .sort())
  await db.exec(
    (await fs.readFile("drizzle/" + file, "utf8"))
      .replaceAll("--> statement-breakpoint", "")
      .replaceAll("\n", " "),
  );
const headers = {
  "oai-authenticated-user-id": "qa-only-owner",
  "oai-authenticated-user-email": "qa@example.invalid",
};
const request = (path, options = {}) =>
  mf.dispatchFetch("https://site.test" + path, {
    ...options,
    headers: { ...headers, ...options.headers },
  });
assert.equal(
  (await mf.dispatchFetch("https://site.test/api/locations/")).status,
  401,
);
assert.equal(
  (
    await request("/api/locations/", {
      method: "POST",
      headers: {
        Origin: "https://evil.test",
        "Content-Type": "application/json",
      },
      body: "{}",
    })
  ).status,
  403,
);
const initial = await (await request("/api/locations/?status=all")).json();
assert.equal(initial.count, 36);
const id = initial.results[0].id,
  version = initial.results[0].version;
const update = (notes) =>
  request("/api/locations/" + id + "/", {
    method: "PATCH",
    headers: {
      Origin: "https://site.test",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ expected_version: version, notes }),
  });
const races = await Promise.all([
  update("Concurrent QA A"),
  update("Concurrent QA B"),
]);
assert.deepEqual(races.map((r) => r.status).sort(), [200, 409]);
const other = await mf.dispatchFetch(
  "https://site.test/api/locations/" + id + "/",
  {
    headers: {
      "oai-authenticated-user-id": "different-qa-owner",
      "oai-authenticated-user-email": "other@example.invalid",
    },
  },
);
assert.equal((await other.json()).notes, "");
const server = http.createServer(async (req, res) => {
  try {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const incomingHeaders = new Headers(req.headers);
    incomingHeaders.set(
      "oai-authenticated-user-id",
      headers["oai-authenticated-user-id"],
    );
    incomingHeaders.set(
      "oai-authenticated-user-email",
      headers["oai-authenticated-user-email"],
    );
    const response = await mf.dispatchFetch(
      "http://127.0.0.1:" + server.address().port + req.url,
      {
        method: req.method,
        headers: incomingHeaders,
        ...(!["GET", "HEAD"].includes(req.method)
          ? { body: Buffer.concat(chunks) }
          : {}),
      },
    );
    res.writeHead(response.status, Object.fromEntries(response.headers));
    res.end(Buffer.from(await response.arrayBuffer()));
  } catch {
    res.writeHead(500);
    res.end("Local test gateway error");
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  headless: true,
  args: ["--enable-webgl", "--use-angle=swiftshader-webgl"],
});
try {
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await context.newPage();
  const failures = [];
  page.on("pageerror", (error) => failures.push(error.message));
  const base = "http://127.0.0.1:" + server.address().port;
  for (const width of [1280, 768, 375]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(base);
    await page
      .getByRole("heading", { name: "Your portfolio, in focus." })
      .waitFor();
    await page.getByText("36", { exact: true }).first().waitFor();
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
    );
    const a11y = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    assert.deepEqual(
      a11y.violations.map((v) => v.id),
      [],
    );
    if (process.env.UI_SCREENSHOT_DIR) {
      await fs.mkdir(process.env.UI_SCREENSHOT_DIR, { recursive: true });
      await page.screenshot({
        path: process.env.UI_SCREENSHOT_DIR + `/sites-dashboard-${width}.png`,
        fullPage: true,
      });
    }
  }
  await page.setViewportSize({ width: 1280, height: 1000 });
  await page.goto(base + "/#/portfolio");
  await page.locator(".location-map[data-ready=true]").waitFor();
  assert.equal(await page.locator(".map-marker").count(), 35);
  await page.locator(".property-card").first().click();
  await page.getByRole("button", { name: "Edit record" }).click();
  await page
    .getByLabel("Team notes")
    .fill("Ephemeral Sites browser verification only.");
  await page.getByRole("button", { name: "Save changes" }).click();
  await page
    .getByText("Ephemeral Sites browser verification only.", { exact: true })
    .waitFor();
  await page.reload();
  await page
    .getByText("Ephemeral Sites browser verification only.", { exact: true })
    .waitFor();
  await page.getByRole("button", { name: "Correct / confirm pin" }).click();
  const dialog = page.getByRole("dialog", { name: "Review the property pin" });
  await dialog
    .getByLabel("I checked that this pin is on the property building.")
    .check();
  await dialog.getByRole("button", { name: "Save pin", exact: true }).click();
  await page
    .getByText("Pin confirmed by a team member.", { exact: true })
    .waitFor();
  const exported = await (
    await context.request.get(base + "/api/export/")
  ).json();
  assert.equal(exported.locations.length, 36);
  assert.equal(exported.revisions.length, 2);
  assert.ok(exported.audits.length >= 3);
  assert.ok(
    exported.locations.some(
      (item) => item.notes === "Ephemeral Sites browser verification only.",
    ),
  );
  assert.deepEqual(failures, []);
  console.log(
    "Sites QA passed: real D1 SQL, private identity, CSRF, concurrent CAS/audit, owner isolation, 375/768/1280 WCAG/overflow, real map worker/pins, persisted edits, pin revisions, and migration export.",
  );
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
  await mf.dispose();
}
