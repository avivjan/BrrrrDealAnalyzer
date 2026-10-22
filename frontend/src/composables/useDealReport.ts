/**
 * The interactive deal report, as the two card modals use it: fetch the report (one
 * self-contained HTML file that works like the breakdown popups) as a blob, hold it in an
 * object URL while the in-app preview is open, and on request download it or hand it to the
 * device's own share sheet (WhatsApp, Gmail, Messages, AirDrop...). The URL is revoked on
 * close and on unmount so nothing leaks.
 *
 * Shared by `views/MyDeals.vue` and `views/BoughtDeals.vue`. The report endpoints take the
 * deal's inputs as the body — no deal id — so a bought deal, serialised whole, works exactly
 * like an active one (the extra stage and result fields are ignored).
 */
import { onBeforeUnmount, ref } from "vue";
import api from "../api";
import type { AnalyzeDealReq } from "../types";

export interface DealReportPreview {
  /** Object URL of the fetched report; revoked when the preview closes. */
  url: string;
  /** The report as a file, ready for the share sheet. */
  file: File;
  filename: string;
  /** The property address, shown in the preview header. */
  title: string;
  dealType: "BRRRR" | "FLIP";
  /** Whether this device can hand the file to its share sheet (most phones, Safari, Edge). */
  canShareReportFile: boolean;
}

/** `BigWhales_BRRRR_2286_Laurel_Grove_Ln_W.html` — the name the file is offered and shared under. */
export function dealReportFilename(dealType: "BRRRR" | "FLIP", address: string): string {
  return `BigWhales_${dealType}_${address.replace(/[^A-Za-z0-9]+/g, "_")}.html`;
}

function deviceCanShareFile(file: File): boolean {
  if (typeof navigator === "undefined" || typeof navigator.canShare !== "function" || typeof navigator.share !== "function") {
    return false;
  }
  try {
    return navigator.canShare({ files: [file] });
  } catch {
    return false;
  }
}

export function useDealReport() {
  const isPreparingReport = ref(false);
  const reportPreview = ref<DealReportPreview | null>(null);

  const closeReportPreview = () => {
    if (reportPreview.value) {
      URL.revokeObjectURL(reportPreview.value.url);
      reportPreview.value = null;
    }
  };

  /**
   * Generate the report for `deal` and open it in the preview. `selectedResultKeys` are the
   * result tiles picked in "Generate Report" (tile order); left out, the report holds them all.
   * `includeDealInputs` adds the collapsed "Deal Inputs" section (every input, by stage).
   */
  const viewDealReport = async (
    deal: { address?: string },
    dealType: "BRRRR" | "FLIP",
    selectedResultKeys?: readonly string[],
    includeDealInputs = false,
  ) => {
    isPreparingReport.value = true;
    try {
      const address = deal.address || "Property";
      // A plain clone: the modals hand over a reactive proxy, and the API layer
      // should serialise a value, not a proxy.
      const payload = JSON.parse(JSON.stringify(deal)) as AnalyzeDealReq;
      const blob = await api.downloadDealReport(payload, dealType, address, selectedResultKeys, includeDealInputs);
      const filename = dealReportFilename(dealType, address);
      const file = new File([blob], filename, { type: "text/html" });
      const url = URL.createObjectURL(file);
      closeReportPreview();
      reportPreview.value = { url, file, filename, title: address, dealType, canShareReportFile: deviceCanShareFile(file) };
    } catch (err) {
      console.error("Failed to generate deal report", err);
    } finally {
      isPreparingReport.value = false;
    }
  };

  const downloadFromPreview = () => {
    if (!reportPreview.value) return;
    const { url, filename } = reportPreview.value;
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  /** Open the device's share sheet with the report file; where that is not possible, download it. */
  const shareFromPreview = async () => {
    if (!reportPreview.value) return;
    const { file, title, canShareReportFile } = reportPreview.value;
    if (!canShareReportFile) {
      downloadFromPreview();
      return;
    }
    try {
      await navigator.share({ files: [file], title: `${title} · Big Whales deal report` });
    } catch (err) {
      // Closing the share sheet is not an error; anything else falls back to the download.
      if ((err as { name?: string } | null)?.name !== "AbortError") downloadFromPreview();
    }
  };

  onBeforeUnmount(closeReportPreview);

  return { isPreparingReport, reportPreview, viewDealReport, downloadFromPreview, shareFromPreview, closeReportPreview };
}
