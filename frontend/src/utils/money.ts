/**
 * Parsing and formatting for the deal form's money fields.
 *
 * ---------------------------------------------------------------------------
 * Why this exists
 * ---------------------------------------------------------------------------
 * Money on a deal is *stored* in thousands (`purchasePrice: 200` means
 * $200,000) because that is the unit the backend calc and the DB columns use.
 * It used to be *typed* in thousands too, which made a $50,500 purchase price
 * impossible to enter — the field rounded to whole thousands.
 *
 * Now the field shows and accepts real dollars, and `MoneyInput` divides by
 * 1000 on the way back out. Typing the full seven digits for every deal would
 * be a regression in speed, so a bare number under 1,000 is read as thousands
 * — that keeps the fast path ("50" -> $50,000) while making every exact amount
 * reachable. `k` / `m` suffixes and an explicit `$` cover the rest, and
 * `MoneyInput` always renders the parsed result under the field so the
 * interpretation is never a surprise.
 */

/** Result of interpreting what someone typed into a money field. */
export interface ParsedMoney {
  /** Dollars, or `null` for an empty/unparseable entry. */
  dollars: number | null;
  /** True when a `k`/`m` suffix or the <1000 rule scaled the typed number. */
  scaled: boolean;
}

const EMPTY: ParsedMoney = { dollars: null, scaled: false };

/**
 * Interpret a money field's raw text as dollars.
 *
 * `shorthand` enables the thousands conveniences, and is on only for fields
 * stored in thousands. Rent, taxes, insurance, HOA and utilities pass `false`:
 * a $50 monthly HOA must stay $50, not become $50,000.
 *
 * | typed     | shorthand: true | shorthand: false |
 * |-----------|-----------------|------------------|
 * | `50`      | 50_000          | 50               |
 * | `50.5`    | 50_500          | 50.5             |
 * | `50500`   | 50_500          | 50_500           |
 * | `50,500`  | 50_500          | 50_500           |
 * | `50k`     | 50_000          | 50_000           |
 * | `1.2m`    | 1_200_000       | 1_200_000        |
 * | `$800`    | 800             | 800              |
 */
export function parseMoney(raw: string, shorthand: boolean): ParsedMoney {
  const text = raw.trim();
  if (text === "") return EMPTY;

  // An explicit dollar sign, wherever the user put it, means "this exact
  // amount" — the escape hatch for a genuinely small figure in a field that
  // would otherwise read it as thousands.
  const explicitDollars = text.includes("$");
  // A thousands separator means they typed the amount out in full.
  const hasSeparator = text.includes(",");

  const suffixMatch = /([km])\s*$/i.exec(text.replace(/\$/g, "").trim());
  const suffix = suffixMatch?.[1]?.toLowerCase();

  const digits = text.replace(/[$,\s]/g, "").replace(/[km]$/i, "");
  if (digits === "" || !/^-?\d*\.?\d*$/.test(digits)) return EMPTY;

  const value = Number(digits);
  if (!Number.isFinite(value)) return EMPTY;

  if (suffix === "k") return { dollars: round2(value * 1_000), scaled: true };
  if (suffix === "m") return { dollars: round2(value * 1_000_000), scaled: true };

  const readAsThousands =
    shorthand &&
    !explicitDollars &&
    !hasSeparator &&
    Math.abs(value) > 0 &&
    Math.abs(value) < 1_000;

  return readAsThousands
    ? { dollars: round2(value * 1_000), scaled: true }
    : { dollars: round2(value), scaled: false };
}

/** Guard against float dust from the ×1000 (e.g. 50.505 * 1000). */
function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/** `50500` -> `"$50,500"`. Cents are shown only when the amount has them. */
export function formatMoney(dollars: number | null | undefined): string {
  if (dollars == null || !Number.isFinite(dollars)) return "";
  const hasCents = Math.round(dollars * 100) % 100 !== 0;
  return dollars.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: hasCents ? 2 : 0,
    maximumFractionDigits: hasCents ? 2 : 0,
  });
}

/**
 * The editable text shown when a money field takes focus: plain digits, no `$`
 * and no separators, so the caret can move without fighting a format mask.
 */
export function toEditableText(dollars: number | null | undefined): string {
  if (dollars == null || !Number.isFinite(dollars)) return "";
  return String(dollars);
}
