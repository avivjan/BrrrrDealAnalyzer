from ReqRes.common.analyze_inputs import analyzeBRRRReq
from BL.analyze.common.validation import validate_brrr_inputs
from BL.analyze.analyzeBRRR import calculate_brrr_results
from BL.reports.common.deal_html_report import build_deal_html_report


def report_brrr_html(payload: analyzeBRRRReq, address: str, selected_result_keys: list[str] | None = None,
                     include_deal_inputs: bool = False) -> str:
    validate_brrr_inputs(payload)
    result = calculate_brrr_results(payload)
    return build_deal_html_report(
        address=address,
        deal_type="BRRRR",
        result=result.model_dump(),
        selected_result_keys=selected_result_keys,
        # The inputs as the form sends them (aliases), for the optional Deal Inputs section.
        deal_inputs=payload.model_dump(by_alias=True) if include_deal_inputs else None,
    )
