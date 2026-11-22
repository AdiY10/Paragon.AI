/**
 * Number, rank, index and distance wording. Every function returns null for a missing value so
 * the caller shows "—" (or a reason) instead of a guessed number; missing is never 0.
 */
export const MINUS = "−";
type Num = number | null | undefined;
const isNum = (n: Num): n is number => typeof n === "number" && Number.isFinite(n);

const int = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

/** 84000 → "84,000". */
export const formatInt = (n: Num) => (isNum(n) ? int.format(n) : null);

/** 1284 → "1,284", 12940 → "12.9K", 4_200_000 → "4.2M" (for tiles and axis ends). */
export function formatCompact(n: Num): string | null {
  if (!isNum(n)) return null;
  const abs = Math.abs(n);
  const sign = n < 0 ? MINUS : "";
  const unit = (value: number, suffix: string) => {
    const text = value >= 100 ? Math.round(value).toString() : value.toFixed(1).replace(/\.0$/, "");
    return sign + text + suffix;
  };
  if (abs >= 1e9) return unit(abs / 1e9, "B");
  if (abs >= 1e6) return unit(abs / 1e6, "M");
  if (abs >= 1e4) return unit(abs / 1e3, "K");
  return sign + int.format(abs);
}

/** 183031.9 → "$183,032". */
export const formatUsd = (n: Num) => (isNum(n) ? usd.format(n) : null);

/**
 * Median household income. ACS's top income bracket is "$200,000 or more", so a median in that
 * bracket is reported at its floor: show it as "≥ $200,000", never as an exact figure.
 */
export const ACS_INCOME_TOP = 200_000;
export const formatIncome = (n: Num) =>
  !isNum(n) ? null : n >= ACS_INCOME_TOP ? `≥ ${usd.format(ACS_INCOME_TOP)}` : usd.format(n);

/** 0.5004 → "50.0%" (a share, not a change). */
export const formatShare = (n: Num, digits = 1) => (isNum(n) ? `${(n * 100).toFixed(digits)}%` : null);

/** 0.031 → "+3.1%", −0.098 → "−9.8%", tiny changes → "0.0%". True minus sign. */
export function formatChangePct(n: Num, digits = 1): string | null {
  if (!isNum(n)) return null;
  const pct = n * 100;
  const threshold = 0.5 * 10 ** -digits;
  const sign = pct >= threshold ? "+" : pct <= -threshold ? MINUS : "";
  return `${sign}${Math.abs(pct).toFixed(digits)}%`;
}

/** 4 → "4th". */
export function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  return n + (["th", "st", "nd", "rd"][n % 10] ?? "th");
}

/** rankText(3, 35) → "3 of 35". */
export const rankText = (rank: Num, of: Num) => (isNum(rank) && isNum(of) ? `${rank} of ${of}` : null);

/** "Ranks 3 of 35 owned properties"; a new place "Would rank 3 of 35 owned properties". */
export function rankSentence(rank: Num, of: Num, mode: "property" | "place" = "property"): string | null {
  const text = rankText(rank, of);
  if (!text) return null;
  return `${mode === "place" ? "Would rank" : "Ranks"} ${text} owned properties`;
}

/** Vehicles on the road, never visits: 21000 → "21,000 vehicles/day". */
export const perDay = (n: Num) => (isNum(n) ? `${int.format(n)} vehicles/day` : null);

/** Index where 100 = US average: 112 → "112 · 12% above the US average". */
export function indexText(index: Num): string | null {
  if (!isNum(index)) return null;
  const rounded = Math.round(index);
  const diff = rounded - 100;
  if (diff === 0) return "100 · same as the US average";
  return `${rounded} · ${Math.abs(diff)}% ${diff > 0 ? "above" : "below"} the US average`;
}

/** 0.46 → "0.5 mi", 0.04 → "<0.1 mi", 12.3 → "12 mi". */
export function distanceMi(miles: Num): string | null {
  if (!isNum(miles) || miles < 0) return null;
  if (miles < 0.05) return "<0.1 mi";
  if (miles >= 10) return `${Math.round(miles)} mi`;
  return `${miles.toFixed(1)} mi`;
}

/** List-level flood status (PART C `key_numbers.flood`). */
export function floodShort(flood: "inside" | "near" | "none" | null | undefined): string | null {
  switch (flood) {
    case "inside":
      return "Inside high-risk zone";
    case "near":
      return "Near high-risk zone";
    case "none":
      return "Not in a high-risk zone";
    default:
      return null;
  }
}
