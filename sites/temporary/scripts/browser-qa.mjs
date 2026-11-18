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
  const allRecords = (
    await (
      await context.request.get(base + "/api/locations/?status=all")
    ).json()
  ).results;
  for (const [seedId, expected] of [
    ["P03", "matched"],
    ["P21", "ambiguous"],
    ["P20", "no_match"],
  ]) {
    const record = allRecords.find((item) => item.seed_id === seedId);
    const before = await (
      await context.request.get(`${base}/api/locations/${record.id}/`)
    ).json();
    await page.goto(`${base}/#/locations/${record.id}`);
    await page
      .getByRole("button", { name: "Find address pin", exact: true })
      .click();
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
      assert.equal(after.current_revision.id, before.current_revision.id);
      assert.equal(after.version, before.version);
      await page.keyboard.press("Escape");
      continue;
    }
    await dialog.getByRole("radio").first().waitFor();
    if (expected === "ambiguous") {
      assert.equal(await dialog.getByRole("radio").count(), 2);
      assert.equal(
        await dialog
          .getByRole("radio")
          .evaluateAll((inputs) => inputs.some((input) => input.checked)),
        false,
      );
      assert.equal(
        await dialog
          .getByRole("button", { name: "Use selected Census pin" })
          .isDisabled(),
        true,
      );
      await dialog.getByRole("radio").nth(1).check();
    }
    await dialog.locator(".location-map[data-ready=true]").waitFor();
    await dialog
      .getByRole("button", { name: "Use selected Census pin", exact: true })
      .click();
    await dialog.waitFor({ state: "hidden" });
    const after = await (
      await context.request.get(`${base}/api/locations/${record.id}/`)
    ).json();
    assert.equal(after.current_revision.method, "census_interpolated");
    assert.equal(after.current_revision.confirmed, false);
    assert.equal(after.confirmed, false);
    assert.ok(after.current_revision.context.response_sha256);
  }
  const finalExport = await (
    await context.request.get(base + "/api/export/")
  ).json();
  assert.equal(finalExport.schema_version, 2);
  assert.equal(finalExport.geocode_lookups.length, 3);
  assert.equal(finalExport.source_checks.length, 3);
  for (const lookup of finalExport.geocode_lookups)
    assert.ok(lookup.raw_response && lookup.source.sha256);
  const sourceCatalog = await (
    await context.request.get(base + "/api/sources/")
  ).json();
  assert.equal(
    sourceCatalog.find((source) => source.id === "SRC-01").status,
    "OK",
  );
  assert.equal(
    sourceCatalog.find((source) => source.id === "SRC-01").health_scopes.length,
    3,
  );
  const acceptedLookup = finalExport.geocode_lookups.find(
    (lookup) =>
      lookup.location_id ===
      allRecords.find((record) => record.seed_id === "P03").id,
  );
  const acceptedRecord = await (
    await context.request.get(
      `${base}/api/locations/${acceptedLookup.location_id}/`,
    )
  ).json();
  const apiHeaders = { Origin: base, "Content-Type": "application/json" };
  const replay = await context.request.post(
    `${base}/api/locations/${acceptedLookup.location_id}/geocode/${acceptedLookup.id}/accept/`,
    {
      headers: apiHeaders,
      data: {
        expected_version: acceptedLookup.expected_version,
        candidate_index: 0,
      },
    },
  );
  assert.equal(replay.status(), 200);
  assert.equal(
    (await replay.json()).current_revision.id,
    acceptedRecord.current_revision.id,
  );
  const cached = await context.request.post(
    `${base}/api/locations/${acceptedLookup.location_id}/geocode/`,
    { headers: apiHeaders, data: { expected_version: acceptedRecord.version } },
  );
  assert.equal(cached.status(), 200);
  const cachedBody = await cached.json();
  assert.equal(cachedBody.last_checked_at, acceptedLookup.last_checked_at);
  assert.equal(cachedBody.retrieved_at, acceptedLookup.retrieved_at);
  assert.equal(
    (await (await context.request.get(base + "/api/export/")).json())
      .source_checks.length,
    3,
  );
  const forged = await context.request.post(
    `${base}/api/locations/${acceptedLookup.location_id}/geocode/${cachedBody.id}/accept/`,
    {
      headers: apiHeaders,
      data: {
        expected_version: acceptedRecord.version,
        candidate_index: 0,
        lat: 0,
      },
    },
  );
  assert.equal(forged.status(), 400);
  const otherAccept = await mf.dispatchFetch(
    "https://site.test/api/locations/" +
      acceptedLookup.location_id +
      "/geocode/" +
      acceptedLookup.id +
      "/accept/",
    {
      method: "POST",
      headers: {
        "oai-authenticated-user-id": "different-qa-owner",
        "oai-authenticated-user-email": "other@example.invalid",
        Origin: "https://site.test",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        expected_version: acceptedLookup.expected_version,
        candidate_index: 0,
      }),
    },
  );
  assert.equal(otherAccept.status, 404);
  assert.deepEqual(failures, []);
  console.log(
    "Sites QA passed: real D1 SQL, private identity, CSRF, concurrent CAS/audit, owner isolation, 375/768/1280 WCAG/overflow, real map worker/pins, persisted edits, pin revisions, migration export, and live Census match/ambiguity/no-match acceptance.",
  );
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
  await mf.dispose();
}
