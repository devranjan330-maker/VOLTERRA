"""
VOLTERRA - API Route: /v1/explain
=================================
Implements Step 6: Generates grounded natural-language rationales tied to real scoring data.
"""

from fastapi import APIRouter
from api.schemas import ExplainRequest, ExplainResponse
from engine.explain import explain_decision

router = APIRouter()


@router.post("/explain", response_model=ExplainResponse)
async def explain(req: ExplainRequest):
    """
    POST /v1/explain
    Generate optimization-grounded rationale for the selected candidate.
    """
    rationale = explain_decision(
        selected_candidate_id=req.selected_candidate_id,
        scores=req.scores,
    )
    return ExplainResponse(rationale=rationale)
