/** Short names for the source catalogue ids (config/sources.yaml), for footnotes. */
export const SOURCE_NAMES: Record<string, string> = {
  "SRC-01": "Census Geocoder",
  "SRC-02": "Nominatim",
  "SRC-03": "Census ACS 5-year",
  "SRC-04": "Census TIGER geography",
  "SRC-05": "Census LODES jobs",
  "SRC-06": "BLS QCEW",
  "SRC-07": "BLS LAUS",
  "SRC-08": "BLS CPI",
  "SRC-09": "Census Building Permits",
  "SRC-10": "FHWA HPMS traffic counts",
  "SRC-11": "FEMA flood maps",
  "SRC-12": "FEMA National Risk Index",
  "SRC-13": "Overture Places",
  "SRC-14": "SEC EDGAR",
  "SRC-15": "Paragon team",
  "SRC-16": "Paragon property listings",
};
/** "SRC-03" → "Census ACS 5-year"; unknown ids pass through. */
export const sourceName = (id: string | null | undefined) => (id ? (SOURCE_NAMES[id] ?? id) : null);
