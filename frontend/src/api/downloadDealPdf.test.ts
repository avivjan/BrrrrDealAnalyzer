// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import api, { apiClient } from "./index";

afterEach(() => vi.restoreAllMocks());

/** The query string axios really sends for a captured request config. */
function sentQueryString(config: Parameters<typeof apiClient.getUri>[0]): string {
  return decodeURIComponent(apiClient.getUri(config).split("?")[1] ?? "");
}

describe("api.downloadDealPdf", () => {
  it("sends each picked result as its own selected_result_keys parameter, as FastAPI reads a list", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ status: 200, data: new Blob(["%PDF"]) });
    await api.downloadDealPdf({ address: "1 Main St" } as never, "BRRRR", "1 Main St", ["cash_flow", "dscr"]);
    const [url, , config] = post.mock.calls[0]!;
    expect(url).toBe("/reports/brrr-pdf");
    expect(config!.responseType).toBe("blob");
    expect(sentQueryString({ url, params: config!.params, paramsSerializer: config!.paramsSerializer })).toBe(
      "address=1+Main+St&selected_result_keys=cash_flow&selected_result_keys=dscr",
    );
  });

  it("leaves the parameter out when every result is wanted", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({ status: 200, data: new Blob(["%PDF"]) });
    await api.downloadDealPdf({} as never, "FLIP", "2 Oak Ave");
    const [url, , config] = post.mock.calls[0]!;
    expect(url).toBe("/reports/flip-pdf");
    expect(sentQueryString({ url, params: config!.params, paramsSerializer: config!.paramsSerializer })).toBe("address=2+Oak+Ave");
  });
});
