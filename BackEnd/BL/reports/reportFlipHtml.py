from ReqRes.common.analyze_inputs import analyzeFlipReq
from BL.analyze.common.validation import validate_flip_inputs
from BL.analyze.analyzeFlip import calculate_flip_results
from BL.reports.common.deal_html_report import build_deal_html_report


def report_flip_html(payload: analyzeFlipReq, address: str, selected_result_keys: list[str] | None = None,
                     include_deal_inputs: bool = False) -> str:
    validate_flip_inputs(payload)
    result = calculate_flip_results(payload)
    return build_deal_html_report(
        address=address,
        deal_type="FLIP",
        result=result.model_dump(),
        selected_result_keys=selected_result_keys,
        # The inputs as the form sends them (aliases), for the optional Deal Inputs section.
        deal_inputs=payload.model_dump(by_alias=True) if include_deal_inputs else None,
    )
