import {
  ENDPOINT,
  fetchCensus,
  hash,
  locationAddress,
  CensusError,
} from "./census.js";
const sql = (db, query, ...args) => db.prepare(query).bind(...args);
const json = (row) => JSON.parse(row.document);
export function previewPayload(value) {
  const { raw_response, address_hash, ...safe } = value;
  return safe;
}
export async function createPreview({ db, owner, record, version, fail }) {
  if (!Number.isInteger(version) || version !== record.version)
    fail(409, "Record changed; reload before looking up its address.");
  const digest = await hash(locationAddress(record).toLowerCase()),
    now = new Date().toISOString();
  const cache = await sql(
    db,
    "SELECT document FROM geocode_lookups WHERE owner_id=? AND location_id=? AND address_hash=? AND expires_at>? ORDER BY checked_at DESC LIMIT 1",
    owner,
    record.id,
    digest,
    now,
  ).first();
  if (cache) {
    const old = json(cache);
    if (old.expected_version === version) return old;
    const value = {
      ...old,
      id: crypto.randomUUID(),
      expected_version: version,
    };
    await insert(db, owner, value);
    return value;
  }
  let capture;
  try {
    capture = await fetchCensus(locationAddress(record));
  } catch (error) {
    const check = {
      id: crypto.randomUUID(),
      source_id: "SRC-01",
      location_id: record.id,
      completed_at: new Date().toISOString(),
      succeeded: false,
      error_code: error instanceof CensusError ? error.code : "SOURCE_ERROR",
    };
    await sql(
      db,
      "INSERT INTO source_checks(owner_id,id,location_id,checked_at,document) VALUES(?,?,?,?,?)",
      owner,
      check.id,
      record.id,
      check.completed_at,
      JSON.stringify(check),
    ).run();
    fail(503, "Address lookup is temporarily unavailable.");
  }
  const identical = await sql(
    db,
    "SELECT document FROM geocode_lookups WHERE owner_id=? AND location_id=? AND address_hash=? AND json_extract(document,'$.source.sha256')=? ORDER BY checked_at ASC LIMIT 1",
    owner,
    record.id,
    digest,
    capture.sha256,
  ).first();
  const originalCapture = identical
    ? json(identical).retrieved_at
    : capture.checked_at;
  const value = {
    id: crypto.randomUUID(),
    location_id: record.id,
    expected_version: version,
    status: capture.status,
    candidates: capture.candidates,
    benchmark: capture.benchmark,
    vintage: capture.vintage,
    retrieved_at: originalCapture,
    last_checked_at: capture.checked_at,
    expires_at: new Date(
      Date.parse(capture.checked_at) + 30 * 86400000,
    ).toISOString(),
    source: {
      id: "SRC-01",
      name: "U.S. Census Bureau",
      url: ENDPOINT,
      snapshot_id: "census-sha256-" + capture.sha256,
      sha256: capture.sha256,
    },
    notice:
      "Census interpolates along the street. This is not building verification. Review the pin before accepting.",
    address_hash: digest,
    raw_response: capture.raw_response,
  };
  const check = {
    id: crypto.randomUUID(),
    source_id: "SRC-01",
    location_id: record.id,
    completed_at: capture.checked_at,
    succeeded: true,
    error_code: null,
    snapshot_id: value.source.snapshot_id,
  };
  await db.batch([
    insertStatement(db, owner, value),
    sql(
      db,
      "INSERT INTO source_checks(owner_id,id,location_id,checked_at,document) VALUES(?,?,?,?,?)",
      owner,
      check.id,
      record.id,
      check.completed_at,
      JSON.stringify(check),
    ),
  ]);
  return value;
}
function insertStatement(db, owner, value) {
  return sql(
    db,
    "INSERT INTO geocode_lookups(owner_id,id,location_id,address_hash,checked_at,expires_at,document) VALUES(?,?,?,?,?,?,?)",
    owner,
    value.id,
    value.location_id,
    value.address_hash,
    value.last_checked_at,
    value.expires_at,
    JSON.stringify(value),
  );
}
async function insert(db, owner, value) {
  await insertStatement(db, owner, value).run();
}
export async function reviewedCandidate({
  db,
  owner,
  id,
  lookupId,
  body,
  fail,
}) {
  const row = await sql(
    db,
    "SELECT document FROM geocode_lookups WHERE owner_id=? AND location_id=? AND id=?",
    owner,
    id,
    lookupId,
  ).first();
  if (!row) fail(404, "Lookup not found");
  const value = json(row);
  if (
    Object.keys(body).some(
      (k) => !["expected_version", "candidate_index"].includes(k),
    )
  )
    fail(400, "Unsupported fields");
  if (
    !Number.isInteger(body.expected_version) ||
    body.expected_version !== value.expected_version
  )
    fail(409, "Lookup version changed.");
  if (value.expires_at <= new Date().toISOString())
    fail(409, "Lookup expired. Request a new suggestion.");
  if (
    !Number.isInteger(body.candidate_index) ||
    body.candidate_index < 0 ||
    body.candidate_index >= value.candidates.length
  )
    fail(400, "Select a recorded suggestion.");
  const candidate = value.candidates[body.candidate_index];
  return {
    lookup: value,
    candidate,
    context: {
      lookup_id: value.id,
      candidate_index: body.candidate_index,
      source_id: "SRC-01",
      source_url: ENDPOINT,
      snapshot_id: value.source.snapshot_id,
      response_sha256: value.source.sha256,
      retrieved_at: value.retrieved_at,
      last_checked_at: value.last_checked_at,
      benchmark: value.benchmark,
      vintage: value.vintage,
      geographies: candidate.geographies,
      match_quality: "not_reported",
      coordinate_attribution:
        "U.S. Census Bureau · street-interpolated; not building-verified",
    },
  };
}
