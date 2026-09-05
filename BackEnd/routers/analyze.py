"""POST /analyze/brrr, POST /analyze/flip."""

from fastapi import APIRouter

from ReqRes.analyze.analyzeBRRR.analyzeBRRRReq import analyzeBRRRReq
from ReqRes.analyze.analyzeBRRR.analyzeBRRRRes import analyzeBRRRRes
from ReqRes.analyze.analyzeFlip.analyzeFlipReq import analyzeFlipReq
from ReqRes.analyze.analyzeFlip.analyzeFlipRes import analyzeFlipRes
from BL.analyze.analyzeBRRR import analyze_brrr as analyze_brrr_bl
from BL.analyze.analyzeFlip import analyze_flip as analyze_flip_bl

router = APIRouter()


@router.post("/analyze/brrr", response_model=analyzeBRRRRes)
def analyze_brrr(payload: analyzeBRRRReq) -> analyzeBRRRRes:
    return analyze_brrr_bl(payload)

@router.post("/analyze/flip", response_model=analyzeFlipRes)
def analyze_flip(payload: analyzeFlipReq) -> analyzeFlipRes:
    return analyze_flip_bl(payload)
