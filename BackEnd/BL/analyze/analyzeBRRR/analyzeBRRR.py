from ReqRes.common.analyze_inputs import analyzeBRRRReq
from ReqRes.common.analyze_results import analyzeBRRRRes
from BL.common.deal_validation import validate_brrr_inputs
from BL.common.deal_analysis import calculate_brrr_results


def analyze_brrr(payload: analyzeBRRRReq) -> analyzeBRRRRes:
    validate_brrr_inputs(payload)
    return calculate_brrr_results(payload)
