from ReqRes.common.analyze_inputs import analyzeBRRRReq
from BL.common.deal_validation import validate_brrr_inputs
from BL.common.deal_analysis import calculate_brrr_results
from BL.reports.common.deal_pdf import build_deal_pdf


def report_brrr_pdf(payload: analyzeBRRRReq, address: str) -> bytes:
    validate_brrr_inputs(payload)
    result = calculate_brrr_results(payload)
    return build_deal_pdf(
        address=address,
        deal_type="BRRRR",
        result=result.model_dump(),
    )
