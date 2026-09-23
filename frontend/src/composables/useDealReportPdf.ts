/**
 * The branded deal report, as the two card modals use it: fetch the PDF as a blob,
 * hold it in an object URL while the in-app preview is open, download only when the
 * user asks, and revoke the URL on close (and on unmount) so nothing leaks.
 *
 * Lifted out of `views/MyDeals.vue` so `views/BoughtDeals.vue` offers the same
 * "Generate Report" with the same behaviour. The report endpoints take the deal's
 * inputs as the body — no deal id — so a bought deal, serialised whole, works
 * exactly like an active one (the extra stage and result fields are ignored).
 */
import { onBeforeUnmount, ref } from "vue";
import api from "../api";
import type { AnalyzeDealReq } from "../types";

export interface DealReportPdfPreview {
  /** Object URL of the fetched PDF; revoked when the preview closes. */
  url: string;
  filename: string;
  /** The property address, shown in the preview header. */
  title: string;
  dealType: "BRRRR" | "FLIP";
}

/** `BigWhales_BRRRR_2286_Laurel_Grove_Ln_W.pdf` — the name the browser is offered. */
export function dealReportPdfFilename(dealType: "BRRRR" | "FLIP", address: string): string {
  return `BigWhales_${dealType}_${address.replace(/[^A-Za-z0-9]+/g, "_")}.pdf`;
}

export function useDealReportPdf() {
  const isPreparingPdf = ref(false);
  const pdfPreview = ref<DealReportPdfPreview | null>(null);

  const closePdfPreview = () => {
    if (pdfPreview.value) {
      URL.revokeObjectURL(pdfPreview.value.url);
      pdfPreview.value = null;
    }
  };

  /**
   * Generate the report for `deal` and open it in the preview. `selectedResultKeys` are the
   * result tiles picked in "Generate Report" (tile order); left out, the report holds them all.
   */
  const viewDealReport = async (
    deal: { address?: string },
    dealType: "BRRRR" | "FLIP",
    selectedResultKeys?: readonly string[],
  ) => {
    isPreparingPdf.value = true;
    try {
      const address = deal.address || "Property";
      // A plain clone: the modals hand over a reactive proxy, and the API layer
      // should serialise a value, not a proxy.
      const payload = JSON.parse(JSON.stringify(deal)) as AnalyzeDealReq;
      const blob = await api.downloadDealPdf(payload, dealType, address, selectedResultKeys);
      const url = URL.createObjectURL(blob);
      closePdfPreview();
      pdfPreview.value = { url, filename: dealReportPdfFilename(dealType, address), title: address, dealType };
    } catch (err) {
      console.error("Failed to generate deal report", err);
    } finally {
      isPreparingPdf.value = false;
    }
  };

  const downloadFromPreview = () => {
    if (!pdfPreview.value) return;
    const { url, filename } = pdfPreview.value;
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  onBeforeUnmount(closePdfPreview);

  return { isPreparingPdf, pdfPreview, viewDealReport, downloadFromPreview, closePdfPreview };
}
