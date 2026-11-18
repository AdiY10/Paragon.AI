export const ENDPOINT =
  "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress";
export const MAX_BYTES = 1048576;
export class CensusError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}
const bad = () => {
  throw new CensusError("SCHEMA_ERROR");
};
const label = (value, max) => {
  if (typeof value !== "string" || !value.trim() || value.length > max) bad();
  return value;
};
export function normalizeAddress(value) {
  if (
    typeof value !== "string" ||
    value.length > 500 ||
    /[\x00-\x1f]/.test(value) ||
    !value.trim()
  )
    throw new CensusError("INPUT_ERROR");
  return value.trim().replace(/\s+/g, " ");
}
export function parseCensus(raw) {
  try {
    if (
      typeof raw !== "string" ||
      new TextEncoder().encode(raw).byteLength > MAX_BYTES
    )
      bad();
    const result = JSON.parse(raw).result,
      input = result.input;
    const version = (value, key, name) => {
      if (
        value?.[key] !== name ||
        typeof value.id !== "string" ||
        !/^\d{1,16}$/.test(value.id)
      )
        bad();
      return { id: value.id, name };
    };
    const benchmark = version(
        input.benchmark,
        "benchmarkName",
        "Public_AR_Current",
      ),
      vintage = version(input.vintage, "vintageName", "Current_Current");
    if (
      !Array.isArray(result.addressMatches) ||
      result.addressMatches.length > 20
    )
      bad();
    const candidates = result.addressMatches.map((match) => {
      const lat = match.coordinates.y,
        lon = match.coordinates.x;
      if (
        typeof lat !== "number" ||
        typeof lon !== "number" ||
        !Number.isFinite(lat) ||
        !Number.isFinite(lon) ||
        Math.abs(lat) > 90 ||
        Math.abs(lon) > 180
      )
        bad();
      if (
        !match.geographies ||
        typeof match.geographies !== "object" ||
        Array.isArray(match.geographies)
      )
        bad();
      const geographies = {};
      for (const [key, kind, length, geoVintage] of [
        ["States", "state", 2, "Current_Current"],
        ["Counties", "county", 5, "Current_Current"],
        ["Census Tracts", "tract", 11, "Current_Current"],
        ["Census Block Groups", "block_group", 12, "Current_Current"],
        ["2020 Census Blocks", "block", 15, "Census2020"],
      ]) {
        const rows = match.geographies[key] ?? [];
        if (!Array.isArray(rows) || rows.length > 1) bad();
        if (!rows.length) continue;
        const entry = rows[0];
        if (
          typeof entry.GEOID !== "string" ||
          !new RegExp("^[0-9]{" + length + "}$").test(entry.GEOID)
        )
          bad();
        geographies[kind] = {
          geoid: entry.GEOID,
          name: label(entry.NAME, 500),
          geography_vintage: geoVintage,
        };
      }
      return {
        lat,
        lon,
        matched_address: label(match.matchedAddress, 500),
        method: "census_interpolated",
        match_quality: "not_reported",
        geographies,
      };
    });
    return {
      status:
        candidates.length === 0
          ? "no_match"
          : candidates.length === 1
            ? "matched"
            : "ambiguous",
      candidates,
      benchmark,
      vintage,
    };
  } catch (error) {
    if (error instanceof CensusError) throw error;
    throw new CensusError("SCHEMA_ERROR");
  }
}
export async function hash(value) {
  const bytes = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return [...new Uint8Array(bytes)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
export function locationAddress(record) {
  let value = record.address;
  for (const extra of [record.city, record.state]) {
    const escaped = extra?.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (extra && !new RegExp("(^|\\W)" + escaped + "($|\\W)", "i").test(value))
      value += ", " + extra;
  }
  return normalizeAddress(value);
}
export async function fetchCensus(address) {
  address = normalizeAddress(address);
  const controller = new AbortController(),
    timer = setTimeout(() => controller.abort(), 10000);
  try {
    const url =
      ENDPOINT +
      "?" +
      new URLSearchParams({
        address,
        benchmark: "Public_AR_Current",
        vintage: "Current_Current",
        layers: "all",
        format: "json",
      });
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
        "User-Agent":
          "ParagonRadar/0.1 (+https://github.com/AdiY10/Paragon.AI)",
      },
      redirect: "manual",
      signal: controller.signal,
    });
    if (!response.ok) throw new CensusError("HTTP_ERROR");
    if (
      !(response.headers.get("Content-Type") ?? "")
        .toLowerCase()
        .startsWith("application/json")
    )
      bad();
    const reader = response.body.getReader(),
      chunks = [];
    let total = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_BYTES) {
        await reader.cancel();
        bad();
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.length;
    }
    const raw = new TextDecoder("utf-8", { fatal: true }).decode(bytes),
      parsed = parseCensus(raw);
    if (
      normalizeAddress(
        JSON.parse(raw).result.input.address.address,
      ).toLowerCase() !== address.toLowerCase()
    )
      bad();
    return {
      ...parsed,
      raw_response: raw,
      sha256: await hash(raw),
      checked_at: new Date().toISOString(),
    };
  } catch (error) {
    if (error instanceof CensusError) throw error;
    throw new CensusError(
      controller.signal.aborted ? "TIMEOUT" : "SOURCE_ERROR",
    );
  } finally {
    clearTimeout(timer);
  }
}
