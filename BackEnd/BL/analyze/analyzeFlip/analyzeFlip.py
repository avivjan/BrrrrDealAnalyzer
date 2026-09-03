from ReqRes.common.analyze_inputs import analyzeFlipReq
from ReqRes.common.analyze_results import analyzeFlipRes
from BL.common.deal_validation import validate_flip_inputs
from BL.common.deal_analysis import calculate_flip_results


def analyze_flip(payload: analyzeFlipReq) -> analyzeFlipRes:
    validate_flip_inputs(payload)
    return calculate_flip_results(payload)
