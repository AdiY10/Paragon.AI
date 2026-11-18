import bootstrap from "../data/bootstrap.json";
export class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}
const statuses = ["owned", "candidate", "archived"],
  types = [
    "retail_center",
    "single_tenant_retail",
    "office",
    "mixed_use",
    "other",
  ];
const publicRecord = (row) => JSON.parse(row.document);
const statement = (db, sql, ...args) => db.prepare(sql).bind(...args);
const page = (results) => ({
  count: results.length,
  next: null,
  previous: null,
  results,
});
const check = (condition, message = "Check the entered values") => {
  if (!condition) throw new HttpError(400, message);
};
const text = (value, max, optional = false) => {
  check(
    typeof value === "string" &&
      value.length <= max &&
      (optional || value.trim().length > 0),
  );
  return value.trim();
};
const strict = (body, allowed) =>
  check(
    body &&
      typeof body === "object" &&
      !Array.isArray(body) &&
      Object.keys(body).every((key) => allowed.includes(key)),
  );
export async function seed(db, owner) {
  if (
    await statement(
      db,
      "SELECT id FROM records WHERE owner_id=? LIMIT 1",
      owner,
    ).first()
  )
    return;
  await db.batch(
    bootstrap.locations.map((item) =>
      statement(
        db,
        "INSERT OR IGNORE INTO records(owner_id,id,version,document) VALUES(?,?,?,?)",
        owner,
        item.id,
        item.version,
        JSON.stringify(item),
      ),
    ),
  );
}
async function get(db, owner, id) {
  const row = await statement(
    db,
    "SELECT document FROM records WHERE owner_id=? AND id=?",
    owner,
    id,
  ).first();
  if (!row) throw new HttpError(404, "Record not found");
  return publicRecord(row);
}
async function mutate(db, owner, id, body, email, kind) {
  const old = await get(db, owner, id);
  check(Number.isInteger(body.expected_version) && body.expected_version > 0);
  if (old.version !== body.expected_version)
    throw new HttpError(409, "This record changed. Reload it before saving.");
  const item = structuredClone(old),
    now = new Date().toISOString(),
    token = crypto.randomUUID();
  let before = {},
    after = {};
  if (kind === "pin_changed") {
    strict(body, ["expected_version", "lat", "lon", "confirmed"]);
    check(
      typeof body.lat === "number" &&
        Number.isFinite(body.lat) &&
        Math.abs(body.lat) <= 90 &&
        typeof body.lon === "number" &&
        Number.isFinite(body.lon) &&
        Math.abs(body.lon) <= 180,
    );
    check(body.confirmed === undefined || typeof body.confirmed === "boolean");
    item.current_revision = {
      id: crypto.randomUUID(),
      number: old.current_revision.number + 1,
      lat: body.lat,
      lon: body.lon,
      method: "manual",
      matched_address: "",
      confirmed: body.confirmed ?? false,
      context: { nature: "User-provided" },
      actor_id: owner,
      created_at: now,
    };
    item.analysis_version++;
    before = { revision: old.current_revision.id };
    after = {
      revision: item.current_revision.id,
      analysis_version: item.analysis_version,
    };
  } else if (kind === "confirmed") {
    strict(body, ["expected_version"]);
    if (old.confirmed) return old;
    item.confirmed = true;
    item.confirmed_at = now;
    before = { confirmed: false };
    after = { confirmed: true };
  } else {
    strict(body, [
      "expected_version",
      "name",
      "status",
      "asset_type",
      "ring_preset",
      "gla_sqft",
      "notes",
    ]);
    check(Object.keys(body).length > 1);
    for (const [key, value] of Object.entries(body)) {
      if (key === "expected_version") continue;
      before[key] = item[key];
      if (key === "name") item[key] = text(value, 200);
      else if (key === "notes") item[key] = text(value, 20000, true);
      else if (key === "status") {
        check(statuses.includes(value));
        item[key] = value;
      } else if (key === "asset_type") {
        check(types.includes(value));
        item[key] = value;
      } else if (key === "ring_preset") {
        check(["1/3/5", "3/5/10"].includes(value));
        item[key] = value;
        if (value !== old.ring_preset) item.analysis_version++;
      } else if (key === "gla_sqft") {
        check(value === null || (Number.isInteger(value) && value > 0));
        item[key] = value;
      }
      after[key] = item[key];
    }
  }
  item.version++;
  item.updated_at = now;
  const audit = {
    id: crypto.randomUUID(),
    action: kind,
    actor: email,
    created_at: now,
    before,
    after,
  };
  const queries = [
    statement(
      db,
      "UPDATE records SET document=?,version=?,token=? WHERE owner_id=? AND id=? AND version=?",
      JSON.stringify(item),
      item.version,
      token,
      owner,
      id,
      old.version,
    ),
    statement(
      db,
      "INSERT INTO audits(owner_id,id,location_id,document) SELECT ?,?,?,? WHERE EXISTS(SELECT 1 FROM records WHERE owner_id=? AND id=? AND token=?)",
      owner,
      audit.id,
      id,
      JSON.stringify(audit),
      owner,
      id,
      token,
    ),
  ];
  if (kind === "pin_changed")
    for (const revision of [old.current_revision, item.current_revision])
      queries.push(
        statement(
          db,
          "INSERT OR IGNORE INTO revisions(owner_id,id,location_id,document) SELECT ?,?,?,? WHERE EXISTS(SELECT 1 FROM records WHERE owner_id=? AND id=? AND token=?)",
          owner,
          revision.id,
          id,
          JSON.stringify(revision),
          owner,
          id,
          token,
        ),
      );
  const result = await db.batch(queries);
  if (result[0].meta.changes !== 1)
    throw new HttpError(409, "This record changed. Reload it before saving.");
  return item;
}
export async function handleAPI(request, env, identity) {
  const url = new URL(request.url),
    path = url.pathname,
    owner = identity.id,
    db = env.DB;
  if (path === "/api/session/" && request.method === "GET")
    return {
      email: identity.email,
      role: "admin",
      csrfToken: "",
      map: { tile_url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" },
      hosting: "temporary-sites",
    };
  if (path === "/api/sources/" && request.method === "GET")
    return bootstrap.sources.map((source) => ({
      ...source,
      status: "Not checked",
      health_scopes: source.health_scopes.map((scope) => ({
        ...scope,
        status: "Not checked",
        needs_alert: false,
      })),
    }));
  if (!db) throw new HttpError(503, "Persistent storage is unavailable");
  if (path === "/api/admin/jobs/")
    throw new HttpError(
      503,
      "Background jobs run in the main application and are unavailable on this temporary Site.",
    );
  await seed(db, owner);
  if (path === "/api/export/" && request.method === "GET") {
    const [records, audits, revisions] = await Promise.all(
      ["records", "audits", "revisions"].map((table) =>
        statement(
          db,
          `SELECT document FROM ${table} WHERE owner_id=?`,
          owner,
        ).all(),
      ),
    );
    return {
      schema_version: 1,
      exported_at: new Date().toISOString(),
      origin: "Paragon Radar temporary Sites workspace",
      source_commit: bootstrap.source_commit,
      locations: records.results.map(publicRecord),
      audits: audits.results.map(publicRecord),
      revisions: revisions.results.map(publicRecord),
      sources: bootstrap.sources,
    };
  }
  if (
    (path === "/api/locations/" && request.method === "GET") ||
    (path === "/api/locations/search/" && request.method === "POST")
  ) {
    const body =
      request.method === "POST"
        ? await request.json()
        : Object.fromEntries(url.searchParams);
    if (request.method === "POST") {
      strict(body, ["q", "state", "status", "asset_type"]);
      text(body.q, 200);
    } else check(!body.q, "Use private POST search");
    const rows = await statement(
      db,
      "SELECT document FROM records WHERE owner_id=?",
      owner,
    ).all();
    const q = (body.q ?? "").toLocaleLowerCase();
    return page(
      rows.results
        .map(publicRecord)
        .filter(
          (item) =>
            (!body.state || item.state === body.state) &&
            (!body.status
              ? item.status !== "archived"
              : body.status === "all" || item.status === body.status) &&
            (!body.asset_type || item.asset_type === body.asset_type) &&
            (!q ||
              [item.name, item.address, item.city, item.state].some((value) =>
                value.toLocaleLowerCase().includes(q),
              )),
        )
        .sort((a, b) => a.name.localeCompare(b.name)),
    );
  }
  if (path === "/api/locations/" && request.method === "POST") {
    const body = await request.json();
    strict(body, ["name", "address", "status", "asset_type", "city", "state"]);
    const now = new Date().toISOString();
    check(!body.status || statuses.includes(body.status));
    check(!body.asset_type || types.includes(body.asset_type));
    check(!body.state || /^[A-Z]{2}$/.test(body.state));
    const item = {
      id: crypto.randomUUID(),
      seed_id: null,
      name: text(body.name, 200),
      address: text(body.address, 500),
      city: text(body.city ?? "", 120, true),
      state: body.state ?? "",
      status: body.status ?? "candidate",
      asset_type: body.asset_type ?? "other",
      ring_preset: "1/3/5",
      gla_sqft: null,
      notes: "",
      confirmed: false,
      confirmed_at: null,
      origin: "user",
      source_url: "",
      source_context: { nature: "User-provided" },
      version: 1,
      analysis_version: 1,
      created_at: now,
      updated_at: now,
      current_revision: {
        id: crypto.randomUUID(),
        number: 1,
        lat: null,
        lon: null,
        method: "unplaced",
        matched_address: "",
        confirmed: false,
        context: {},
        actor_id: owner,
        created_at: now,
      },
    };
    const audit = {
      id: crypto.randomUUID(),
      action: "created",
      actor: identity.email,
      created_at: now,
      before: {},
      after: {
        origin: "user",
        status: item.status,
        revision: item.current_revision.id,
      },
    };
    await db.batch([
      statement(
        db,
        "INSERT INTO records(owner_id,id,version,document) VALUES(?,?,?,?)",
        owner,
        item.id,
        1,
        JSON.stringify(item),
      ),
      statement(
        db,
        "INSERT INTO audits(owner_id,id,location_id,document) VALUES(?,?,?,?)",
        owner,
        audit.id,
        item.id,
        JSON.stringify(audit),
      ),
    ]);
    return item;
  }
  const match = path.match(
    /^\/api\/locations\/([a-f0-9-]+)\/(pin\/|confirm\/|history\/)?$/,
  );
  if (!match) throw new HttpError(404, "Route not found");
  const id = match[1],
    operation = match[2];
  if (!operation && request.method === "GET") return get(db, owner, id);
  if (operation === "history/" && request.method === "GET") {
    await get(db, owner, id);
    const entries = await statement(
      db,
      "SELECT document FROM audits WHERE owner_id=? AND location_id=? ORDER BY rowid DESC",
      owner,
      id,
    ).all();
    return page(entries.results.map(publicRecord));
  }
  if (
    (!operation && request.method === "PATCH") ||
    (operation === "pin/" && request.method === "POST") ||
    (operation === "confirm/" && request.method === "POST")
  )
    return mutate(
      db,
      owner,
      id,
      await request.json(),
      identity.email,
      operation === "pin/"
        ? "pin_changed"
        : operation === "confirm/"
          ? "confirmed"
          : "attributes_changed",
    );
  throw new HttpError(405, "Method not allowed");
}
