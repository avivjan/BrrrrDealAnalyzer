import { describe, expect, it } from "vitest";
import { safeHref } from "./safeHref";

describe("safeHref", () => {
  it("passes http and https URLs through unchanged", () => {
    expect(safeHref("https://www.zillow.com/homedetails/1")).toBe("https://www.zillow.com/homedetails/1");
    expect(safeHref("http://example.com/x?y=1")).toBe("http://example.com/x?y=1");
    expect(safeHref("  https://storage.googleapis.com/b/o.pdf ")).toBe("https://storage.googleapis.com/b/o.pdf");
    expect(safeHref("HTTPS://EXAMPLE.COM")).toBe("HTTPS://EXAMPLE.COM");
  });

  it("refuses every other scheme and non-URLs", () => {
    expect(safeHref("javascript:alert(1)")).toBeUndefined();
    expect(safeHref("JavaScript:alert(1)")).toBeUndefined();
    expect(safeHref("data:text/html;base64,PHNjcmlwdD4=")).toBeUndefined();
    expect(safeHref("vbscript:x")).toBeUndefined();
    expect(safeHref("zillow.com/homedetails")).toBeUndefined();
    expect(safeHref("//evil.example")).toBeUndefined();
    expect(safeHref("")).toBeUndefined();
    expect(safeHref(null)).toBeUndefined();
    expect(safeHref(undefined)).toBeUndefined();
  });
});
