from ReqRes.common.analyze_inputs import analyzeFlipReq
from BL.common.deal_validation import validate_flip_inputs
from BL.common.deal_analysis import calculate_flip_results
from BL.reports.common.deal_pdf import build_deal_pdf


def report_flip_pdf(payload: analyzeFlipReq, address: str) -> bytes:
    validate_flip_inputs(payload)
    result = calculate_flip_results(payload)
    return build_deal_pdf(
        address=address,
        deal_type="FLIP",
        result=result.model_dump(),
    )
