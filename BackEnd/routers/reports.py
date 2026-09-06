"""POST /reports/brrr-pdf, POST /reports/flip-pdf."""

from fastapi import APIRouter
from fastapi.responses import Response

from ReqRes.analyze.analyzeBRRR.analyzeBRRRReq import analyzeBRRRReq
from ReqRes.analyze.analyzeFlip.analyzeFlipReq import analyzeFlipReq
from BL.reports.reportBrrrPdf import report_brrr_pdf as report_brrr_pdf_bl
from BL.reports.reportFlipPdf import report_flip_pdf as report_flip_pdf_bl

router = APIRouter()


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
) -> Response:
    pdf_bytes = report_brrr_pdf_bl(payload, address)
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
) -> Response:
    pdf_bytes = report_flip_pdf_bl(payload, address)
    filename = f"BigWhales_FLIP_{_safe_filename(address)}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{_disposition(disposition)}; filename="{filename}"'},
    )
