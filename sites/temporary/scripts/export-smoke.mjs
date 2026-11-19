// Disposable D1/Worker migration contract check; no production data is modified.
import { Miniflare } from "miniflare";
import fs from "node:fs/promises";
import assert from "node:assert/strict";
const mf = new Miniflare({
  modules: true,
  scriptPath: "dist/server/index.js",
  compatibilityDate: "2026-05-15",
  d1Databases: { DB: "export-qa" },
  port: 0,
});
try {
  const db = await mf.getD1Database("DB");
  for (const file of (await fs.readdir("drizzle"))
    .filter((file) => file.endsWith(".sql"))
    .sort()) {
    await db.exec(
      (await fs.readFile("drizzle/" + file, "utf8"))
        .replaceAll("--> statement-breakpoint", "")
        .replaceAll("\n", " "),
    );
  }
  const owner = "isolated-export-test-owner";
  async function request(path, method = "GET", body, identity = owner) {
    const response = await mf.dispatchFetch("https://site.test" + path, {
      method,
      headers: {
        "oai-authenticated-user-id": identity,
        "oai-authenticated-user-email": "export-test@example.invalid",
        Origin: "https://site.test",
        "Content-Type": "application/json",
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    assert.equal(response.status, 200);
    return response.json();
  }
  assert.equal(
    (await mf.dispatchFetch("https://site.test/api/export/")).status,
    401,
  );
  const portfolio = await request("/api/locations/");
  const record = portfolio.results.find((row) => row.seed_id === "P03");
  const path = "/api/locations/" + record.id + "/";
  const edited = await request(path, "PATCH", {
    expected_version: record.version,
    notes: "Isolated migration contract note",
  });
  await request(path + "pin/", "POST", {
    expected_version: edited.version,
    lat: 41.1266,
    lon: -73.3882,
    confirmed: true,
  });
  const exported = await request("/api/export/");
  assert.equal(exported.schema_version, 3);
  assert.equal(exported.workspace_id, owner);
  assert.equal(exported.locations.length, 36);
  assert.equal(exported.audits.length, 2);
  assert.equal(exported.revisions.length, 2);
  for (const row of [...exported.audits, ...exported.revisions])
    assert.equal(row.location_id, record.id);
  const current = exported.locations.find((row) => row.id === record.id);
  assert.equal(current.notes, "Isolated migration contract note");
  assert.equal(current.current_revision.number, 2);
  const other = await request(
    "/api/export/",
    "GET",
    null,
    "isolated-other-owner",
  );
  assert.equal(other.audits.length, 0);
  assert.equal(other.revisions.length, 0);
  assert.equal(other.locations.find((row) => row.id === record.id).notes, "");
  if (process.env.QA_EXPORT_PATH)
    await fs.writeFile(process.env.QA_EXPORT_PATH, JSON.stringify(exported), {
      mode: 0o600,
    });
  console.log(
    JSON.stringify({
      verified: true,
      schema: 3,
      locations: 36,
      audits: 2,
      revisions: 2,
      ownerIsolation: true,
    }),
  );
} finally {
  await mf.dispose();
}
