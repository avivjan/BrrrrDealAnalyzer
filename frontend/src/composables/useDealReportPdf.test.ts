// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, nextTick } from "vue";
import { mount } from "@vue/test-utils";

import api from "../api";
import { dealReportPdfFilename, useDealReportPdf } from "./useDealReportPdf";

vi.mock("../api", () => ({
  default: { downloadDealPdf: vi.fn() },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const downloadDealPdf = vi.mocked(api.downloadDealPdf);

/** Mount a throwaway host so the composable's lifecycle hooks have a component to bind to. */
function mountHost() {
  let exposed!: ReturnType<typeof useDealReportPdf>;
  const Host = defineComponent({
    setup() {
      exposed = useDealReportPdf();
      return () => h("div");
    },
  });
  const wrapper = mount(Host);
  return { wrapper, report: exposed };
}

describe("useDealReportPdf", () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => "blob:preview-1");
    URL.revokeObjectURL = vi.fn();
    downloadDealPdf.mockResolvedValue(new Blob(["%PDF"], { type: "application/pdf" }));
  });
  afterEach(() => vi.clearAllMocks());

  it("names the file after the strategy and the address, safe for any filesystem", () => {
    expect(dealReportPdfFilename("BRRRR", "2286 Laurel Grove Ln W")).toBe("BigWhales_BRRRR_2286_Laurel_Grove_Ln_W.pdf");
    expect(dealReportPdfFilename("FLIP", "1 Shared/Form St.")).toBe("BigWhales_FLIP_1_Shared_Form_St_.pdf");
  });

  it("sends the deal whole to the report endpoint for its strategy and opens the preview on the blob", async () => {
    const { report } = mountHost();
    const boughtDeal = { address: "9 Bought Rd", boughtStage: "rehab", purchasePrice: 200, cash_flow: 412 };

    await report.viewDealReport(boughtDeal, "FLIP");

    expect(downloadDealPdf).toHaveBeenCalledWith(boughtDeal, "FLIP", "9 Bought Rd", undefined);
    expect(report.pdfPreview.value).toEqual({
      url: "blob:preview-1",
      filename: "BigWhales_FLIP_9_Bought_Rd.pdf",
      title: "9 Bought Rd",
      dealType: "FLIP",
    });
    expect(report.isPreparingPdf.value).toBe(false);
  });

  it("falls back to 'Property' when the deal has no address", async () => {
    const { report } = mountHost();
    await report.viewDealReport({}, "BRRRR");
    expect(downloadDealPdf).toHaveBeenCalledWith({}, "BRRRR", "Property", undefined);
    expect(report.pdfPreview.value?.filename).toBe("BigWhales_BRRRR_Property.pdf");
  });

  it("passes the results picked in Generate Report through to the endpoint", async () => {
    const { report } = mountHost();
    await report.viewDealReport({ address: "A" }, "BRRRR", ["cash_flow", "dscr"]);
    expect(downloadDealPdf).toHaveBeenCalledWith({ address: "A" }, "BRRRR", "A", ["cash_flow", "dscr"]);
  });

  it("revokes the object URL when the preview closes, and again on unmount", async () => {
    const { wrapper, report } = mountHost();
    await report.viewDealReport({ address: "A" }, "BRRRR");
    report.closePdfPreview();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview-1");
    expect(report.pdfPreview.value).toBeNull();

    await report.viewDealReport({ address: "A" }, "BRRRR");
    wrapper.unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2);
  });

  it("swallows a failed fetch, logs it, and leaves no preview open", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    downloadDealPdf.mockRejectedValueOnce(new Error("503"));
    const { report } = mountHost();
    await report.viewDealReport({ address: "A" }, "BRRRR");
    expect(report.pdfPreview.value).toBeNull();
    expect(report.isPreparingPdf.value).toBe(false);
    expect(error).toHaveBeenCalled();
    error.mockRestore();
  });

  it("downloads through a temporary anchor named after the preview", async () => {
    const { report } = mountHost();
    await report.viewDealReport({ address: "A" }, "BRRRR");
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const appended: HTMLAnchorElement[] = [];
    const append = vi.spyOn(document.body, "appendChild").mockImplementation((node) => {
      appended.push(node as HTMLAnchorElement);
      return node;
    });
    report.downloadFromPreview();
    await nextTick();
    expect(appended[0]?.getAttribute("download")).toBe("BigWhales_BRRRR_A.pdf");
    expect(appended[0]?.getAttribute("href")).toBe("blob:preview-1");
    expect(click).toHaveBeenCalledTimes(1);
    click.mockRestore();
    append.mockRestore();
  });
});
