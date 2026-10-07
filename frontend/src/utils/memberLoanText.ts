/**
 * Member Loan text helpers. Amounts stay strings: nothing here converts money
 * to a JavaScript number, so no floating point ever touches a loan figure.
 */

const AMOUNT_TYPED_PATTERN = /^\d{1,8}(\.\d{1,2})?$/;

/**
 * What a member typed into an amount field, as the exact text the API takes,
 * or null when it is not a plain amount. No shorthand: "50" is $50.00, never
 * $50,000 (unlike the deal form's MoneyInput). Commas and a leading "$" are
 * allowed and dropped.
 */
export function parseLoanAmountTyped(raw: string): string | null {
  const cleaned = raw.trim().replace(/^\$/, "").replace(/,/g, "");
  if (!AMOUNT_TYPED_PATTERN.test(cleaned)) return null;
  const [whole, fraction = ""] = cleaned.split(".");
  const wholeWithoutLeadingZeros = whole!.replace(/^0+(?=\d)/, "");
  const amount = `${wholeWithoutLeadingZeros}.${fraction.padEnd(2, "0")}`;
  return amount === "0.00" ? null : amount;
}

/** "31166.01" -> "$31,166.01"; "-2000.00" -> "-$2,000.00". Pure string work. */
export function formatLoanMoney(amount: string | null | undefined): string {
  if (amount === null || amount === undefined || amount === "") return "—";
  const negative = amount.startsWith("-");
  const [whole, fraction = "00"] = amount.replace(/^-/, "").split(".");
  const grouped = whole!.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}$${grouped}.${fraction.padEnd(2, "0").slice(0, 2)}`;
}

/** Today on this device, as YYYY-MM-DD, from the device's own time zone (decision D3). */
export function deviceToday(now: Date = new Date()): string {
  const timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(now);
  const part = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

/** "2026-12-15" -> "Dec 15, 2026", without going through the device's time zone. */
export function formatLoanDate(isoDate: string | null | undefined): string {
  if (!isoDate) return "—";
  const [year, month, day] = isoDate.slice(0, 10).split("-").map((p) => Number.parseInt(p, 10));
  const monthName = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][(month ?? 1) - 1];
  return `${monthName} ${day}, ${year}`;
}

/** "2026-12" -> "December 2026". */
export function formatLoanMonth(yearMonth: string): string {
  const [year, month] = yearMonth.split("-").map((p) => Number.parseInt(p, 10));
  const names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  return `${names[(month ?? 1) - 1]} ${year}`;
}

/** Every month from the loan's first through `lastYearMonth`, newest first. */
export function loanStatementMonths(firstYearMonth: string, lastYearMonth: string): string[] {
  const months: string[] = [];
  let [year, month] = firstYearMonth.split("-").map((p) => Number.parseInt(p, 10)) as [number, number];
  const [lastYear, lastMonth] = lastYearMonth.split("-").map((p) => Number.parseInt(p, 10)) as [number, number];
  while (year < lastYear || (year === lastYear && month <= lastMonth)) {
    months.push(`${year}-${String(month).padStart(2, "0")}`);
    month += 1;
    if (month === 13) {
      month = 1;
      year += 1;
    }
  }
  return months.reverse();
}

export const BUCKET_LABELS: Record<keyof import("../types/memberLoan").MemberLoanBuckets, string> = {
  original_principal: "Principal",
  capitalized_interest: "Capitalized interest",
  total_balance: "Total Balance",
  accrued_interest: "Accrued interest (not yet added)",
  interest_payable: "Interest payable in cash",
  amount_owed: "Amount Owed",
  lender_capital_credited: "Credited to the Lender's capital account",
};

export const PROPOSAL_STATE_LABELS: Record<string, string> = {
  pending: "Waiting for approval",
  approved: "Approved",
  rejected: "Rejected",
  cancelled: "Cancelled",
  expired: "Expired",
};

/** The API's plain-language refusal, or a generic line. */
export function memberLoanErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail;
  if (detail && typeof detail === "object" && typeof detail.message === "string") return detail.message;
  if (detail === "member_loan_access_denied") return "This page is only for the two members of the loan.";
  if (detail === "unauthenticated") return "Please sign in with your passkey.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return "Please check the form: a field is missing or not valid.";
  return error?.message || "Something went wrong.";
}
