"""
VOLTERRA - API Route: /v1/generate
==================================
Implements Step 3: Returns candidate action space (>= 2 candidates).
"""

from fastapi import APIRouter
from api.schemas import GenerateRequest, GenerateResponse, CandidateAction
from engine.generate import generate_candidates

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
async def generate_actions(req: GenerateRequest):
    """
    POST /v1/generate
    Generates candidate decision space (e.g., A: Do nothing, B: Use battery,
    C: Shift loads, D: Hybrid response).
    """
    risk = req.risk_classification.value if req.risk_classification else None
    cands = generate_candidates(risk_classification=risk, state=req.forecasted_state)

    return GenerateResponse(
        candidates=[
            CandidateAction(id=c.id, label=c.label, description=c.description)
            for c in cands
        ]
    )
