// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, nextTick } from "vue";
import { mount } from "@vue/test-utils";

import api from "../api";
import { dealReportFilename, useDealReport } from "./useDealReport";

vi.mock("../api", () => ({
  default: { downloadDealReport: vi.fn() },
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const downloadDealReport = vi.mocked(api.downloadDealReport);

/** Mount a throwaway host so the composable's lifecycle hooks have a component to bind to. */
function mountHost() {
  let exposed!: ReturnType<typeof useDealReport>;
  const Host = defineComponent({
    setup() {
      exposed = useDealReport();
      return () => h("div");
    },
  });
  const wrapper = mount(Host);
  return { wrapper, report: exposed };
}

describe("useDealReport", () => {
  beforeEach(() => {
    URL.createObjectURL = vi.fn(() => "blob:preview-1");
    URL.revokeObjectURL = vi.fn();
    downloadDealReport.mockResolvedValue(new Blob(["<!doctype html>"], { type: "text/html" }));
  });
  afterEach(() => vi.clearAllMocks());

  it("names the file after the strategy and the address, safe for any filesystem", () => {
    expect(dealReportFilename("BRRRR", "2286 Laurel Grove Ln W")).toBe("BigWhales_BRRRR_2286_Laurel_Grove_Ln_W.html");
    expect(dealReportFilename("FLIP", "1 Shared/Form St.")).toBe("BigWhales_FLIP_1_Shared_Form_St_.html");
  });

  it("sends the deal whole to the report endpoint for its strategy and opens the preview on the blob", async () => {
    const { report } = mountHost();
    const boughtDeal = { address: "9 Bought Rd", boughtStage: "rehab", purchasePrice: 200, cash_flow: 412 };

    await report.viewDealReport(boughtDeal, "FLIP");

    expect(downloadDealReport).toHaveBeenCalledWith(boughtDeal, "FLIP", "9 Bought Rd", undefined, false);
    expect(report.reportPreview.value).toMatchObject({
      url: "blob:preview-1",
      filename: "BigWhales_FLIP_9_Bought_Rd.html",
      title: "9 Bought Rd",
      dealType: "FLIP",
      canShareReportFile: false,
    });
    const file = report.reportPreview.value!.file;
    expect(file).toBeInstanceOf(File);
    expect(file.name).toBe("BigWhales_FLIP_9_Bought_Rd.html");
    expect(file.type).toBe("text/html");
    expect(report.isPreparingReport.value).toBe(false);
  });

  it("falls back to 'Property' when the deal has no address", async () => {
    const { report } = mountHost();
    await report.viewDealReport({}, "BRRRR");
    expect(downloadDealReport).toHaveBeenCalledWith({}, "BRRRR", "Property", undefined, false);
    expect(report.reportPreview.value?.filename).toBe("BigWhales_BRRRR_Property.html");
  });

  it("passes the results picked in Generate Report through to the endpoint", async () => {
    const { report } = mountHost();
    await report.viewDealReport({ address: "A" }, "BRRRR", ["cash_flow", "dscr"]);
    expect(downloadDealReport).toHaveBeenCalledWith({ address: "A" }, "BRRRR", "A", ["cash_flow", "dscr"], false);
    await report.viewDealReport({ address: "A" }, "BRRRR", ["cash_flow"], true);
    expect(downloadDealReport).toHaveBeenLastCalledWith({ address: "A" }, "BRRRR", "A", ["cash_flow"], true);
  });

  it("revokes the object URL when the preview closes, and again on unmount", async () => {
    const { wrapper, report } = mountHost();
    await report.viewDealReport({ address: "A" }, "BRRRR");
    report.closeReportPreview();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:preview-1");
    expect(report.reportPreview.value).toBeNull();

    await report.viewDealReport({ address: "A" }, "BRRRR");
    wrapper.unmount();
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2);
  });

  it("swallows a failed fetch, logs it, and leaves no preview open", async () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    downloadDealReport.mockRejectedValueOnce(new Error("503"));
    const { report } = mountHost();
    await report.viewDealReport({ address: "A" }, "BRRRR");
    expect(report.reportPreview.value).toBeNull();
    expect(report.isPreparingReport.value).toBe(false);
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
    expect(appended[0]?.getAttribute("download")).toBe("BigWhales_BRRRR_A.html");
    expect(appended[0]?.getAttribute("href")).toBe("blob:preview-1");
    expect(click).toHaveBeenCalledTimes(1);
    click.mockRestore();
    append.mockRestore();
  });

  describe("Share", () => {
    const originalShare = navigator.share;
    const originalCanShare = navigator.canShare;
    afterEach(() => {
      Object.assign(navigator, { share: originalShare, canShare: originalCanShare });
    });

    it("hands the report file to the device's share sheet when the device can share files", async () => {
      const share = vi.fn().mockResolvedValue(undefined);
      const canShare = vi.fn().mockReturnValue(true);
      Object.assign(navigator, { share, canShare });
      const { report } = mountHost();
      await report.viewDealReport({ address: "1 Main St" }, "BRRRR");
      expect(report.reportPreview.value?.canShareReportFile).toBe(true);
      expect(canShare).toHaveBeenCalledWith({ files: [report.reportPreview.value!.file] });

      await report.shareFromPreview();
      expect(share).toHaveBeenCalledWith({ files: [report.reportPreview.value!.file], title: "1 Main St · Big Whales deal report" });
    });

    it("downloads instead where the device cannot share files, or when sharing fails", async () => {
      const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
      Object.assign(navigator, { share: undefined, canShare: undefined });
      const { report } = mountHost();
      await report.viewDealReport({ address: "A" }, "BRRRR");
      await report.shareFromPreview();
      expect(click).toHaveBeenCalledTimes(1);

      Object.assign(navigator, { share: vi.fn().mockRejectedValue(new Error("NotAllowedError")), canShare: () => true });
      await report.viewDealReport({ address: "A" }, "BRRRR");
      await report.shareFromPreview();
      expect(click).toHaveBeenCalledTimes(2);
      click.mockRestore();
    });

    it("treats closing the share sheet as a choice, not a failure", async () => {
      const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
      const abort = Object.assign(new Error("cancelled"), { name: "AbortError" });
      Object.assign(navigator, { share: vi.fn().mockRejectedValue(abort), canShare: () => true });
      const { report } = mountHost();
      await report.viewDealReport({ address: "A" }, "BRRRR");
      await report.shareFromPreview();
      expect(click).not.toHaveBeenCalled();
      click.mockRestore();
    });
  });
});
