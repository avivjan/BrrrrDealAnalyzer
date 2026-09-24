from ReqRes.common.analyze_inputs import analyzeFlipReq
from BL.analyze.common.validation import validate_flip_inputs
from BL.analyze.analyzeFlip import calculate_flip_results
from BL.reports.common.deal_pdf import build_deal_pdf


def report_flip_pdf(payload: analyzeFlipReq, address: str, selected_result_keys: list[str] | None = None) -> bytes:
    validate_flip_inputs(payload)
    result = calculate_flip_results(payload)
    return build_deal_pdf(
        address=address,
        deal_type="FLIP",
        result=result.model_dump(),
        selected_result_keys=selected_result_keys,
    )
