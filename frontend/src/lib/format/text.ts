/** "census_interpolated" → "Census Interpolated". */
export const titleCase = (text: string) => text.replaceAll("_", " ").replace(/\b\w/g, (s) => s.toUpperCase());
