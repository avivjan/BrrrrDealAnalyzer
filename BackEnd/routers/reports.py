"""POST /reports/brrr-pdf, POST /reports/flip-pdf."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from ReqRes.analyze.analyzeBRRR.analyzeBRRRReq import analyzeBRRRReq
from ReqRes.analyze.analyzeFlip.analyzeFlipReq import analyzeFlipReq
from BL.reports.reportBrrrPdf import report_brrr_pdf as report_brrr_pdf_bl
from BL.reports.reportFlipPdf import report_flip_pdf as report_flip_pdf_bl
from BL.reports.common.report_result_tiles import UnknownReportResultKeys, select_report_result_tiles

router = APIRouter()

SELECTED_RESULT_KEYS_DESCRIPTION = (
    "The result tiles to include, one query parameter per key, in any order (the report keeps tile "
    "order). Omit for every tile. BRRRR keys: cash_flow, cash_out, cash_out_routi, cash_on_cash, dscr, "
    "equity, roi, net_profit, total_cash_needed_for_deal, cash_to_close_buy, cash_out_routi_conservative, "
    "stolen_money. FLIP keys: net_profit, roi, annualized_roi, total_cash_needed, "
    "total_cash_needed_with_buffer, total_holding_costs, total_hml_interest. An unknown key or an empty "
    "selection is a 422."
)


def _validated_selected_result_keys(deal_type: str, selected_result_keys: list[str] | None) -> list[str] | None:
    """Reject an unknown key or an empty selection before any calculation runs."""
    try:
        tiles = select_report_result_tiles(deal_type, selected_result_keys)
    except UnknownReportResultKeys as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return None if selected_result_keys is None else [tile.result_key for tile in tiles]


def _safe_filename(address: str) -> str:
    cleaned = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in (address or "deal"))
    return cleaned.strip("_") or "deal"


def _disposition(value: str) -> str:
    """Normalize the optional `disposition` query param.
    `inline` (default) → preview in the browser; `attachment` → force download."""
    return "attachment" if (value or "").lower() == "attachment" else "inline"


@router.post("/reports/brrr-pdf")
def report_brrr_pdf(
    payload: analyzeBRRRReq,
    address: str = "Property",
    disposition: str = "inline",
    selected_result_keys: list[str] | None = Query(None, description=SELECTED_RESULT_KEYS_DESCRIPTION),
) -> Response:
    validated_selected_result_keys = _validated_selected_result_keys("BRRRR", selected_result_keys)
    pdf_bytes = report_brrr_pdf_bl(payload, address, validated_selected_result_keys)
    filename = f"BigWhales_BRRRR_{_safe_filename(address)}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{_disposition(disposition)}; filename="{filename}"'},
    )


@router.post("/reports/flip-pdf")
def report_flip_pdf(
    payload: analyzeFlipReq,
    address: str = "Property",
    disposition: str = "inline",
    selected_result_keys: list[str] | None = Query(None, description=SELECTED_RESULT_KEYS_DESCRIPTION),
) -> Response:
    validated_selected_result_keys = _validated_selected_result_keys("FLIP", selected_result_keys)
    pdf_bytes = report_flip_pdf_bl(payload, address, validated_selected_result_keys)
    filename = f"BigWhales_FLIP_{_safe_filename(address)}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{_disposition(disposition)}; filename="{filename}"'},
    )
