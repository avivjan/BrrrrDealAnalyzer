import { describe, expect, it } from "vitest";

import {
  deviceToday,
  formatLoanDate,
  formatLoanMoney,
  formatLoanMonth,
  loanStatementMonths,
  memberLoanErrorMessage,
  parseLoanAmountTyped,
} from "./memberLoanText";

describe("parseLoanAmountTyped", () => {
  it.each([
    ["1000", "1000.00"],
    ["1000.5", "1000.50"],
    ["1,000.25", "1000.25"],
    ["$31166.01", "31166.01"],
    ["50", "50.00"],
    ["007.10", "7.10"],
  ])("reads %s as exactly %s (no thousands shorthand)", (typed, expected) => {
    expect(parseLoanAmountTyped(typed)).toBe(expected);
  });

  it.each(["", "abc", "10.001", "-5", "1e3", "0", "0.00", "1.2.3", "123456789"])("refuses %s", (typed) => {
    expect(parseLoanAmountTyped(typed)).toBeNull();
  });
});

describe("formatLoanMoney", () => {
  it("groups thousands without turning the text into a number", () => {
    expect(formatLoanMoney("31166.01")).toBe("$31,166.01");
    expect(formatLoanMoney("1234567.80")).toBe("$1,234,567.80");
    expect(formatLoanMoney("0.00")).toBe("$0.00");
    expect(formatLoanMoney("-2000.00")).toBe("-$2,000.00");
    expect(formatLoanMoney(null)).toBe("—");
  });

  it("keeps cents a float would lose", () => {
    expect(formatLoanMoney("9007199254740993.01")).toBe("$9,007,199,254,740,993.01");
  });
});

describe("dates and months", () => {
  it("formats an ISO date as written, whatever the device time zone", () => {
    expect(formatLoanDate("2026-12-15")).toBe("Dec 15, 2026");
    expect(formatLoanDate("2027-01-01T05:00:00+00:00")).toBe("Jan 1, 2027");
  });

  it("gives the device's own date as YYYY-MM-DD", () => {
    expect(deviceToday(new Date(2026, 11, 15, 12, 0))).toBe("2026-12-15");
  });

  it("lists statement months newest first", () => {
    expect(loanStatementMonths("2026-10", "2027-01")).toEqual(["2027-01", "2026-12", "2026-11", "2026-10"]);
    expect(formatLoanMonth("2026-12")).toBe("December 2026");
  });
});

describe("memberLoanErrorMessage", () => {
  it("shows the API's plain-language reason", () => {
    expect(memberLoanErrorMessage({ response: { data: { detail: { message: "The date cannot be in the future.", code: "date_in_future" } } } })).toBe(
      "The date cannot be in the future.",
    );
    expect(memberLoanErrorMessage({ response: { data: { detail: "member_loan_access_denied" } } })).toMatch(/only for the two members/);
    expect(memberLoanErrorMessage({ response: { data: { detail: [{ loc: ["body"] }] } } })).toMatch(/check the form/);
  });
});
