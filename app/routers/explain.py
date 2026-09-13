from fastapi import APIRouter
from app.models import ExplainRequest, ExplainResponse
from app.services.explain_service import generate_explanation

router = APIRouter()


@router.post("/explain", response_model=ExplainResponse)
async def explain_endpoint(req: ExplainRequest):
    """
    POST /v1/explain
    Generate a human-readable, grounded rationale for the selected decision.
    """
    rationale = generate_explanation(
        selected_candidate_id=req.selected_candidate_id,
        scores=req.scores,
    )
    return ExplainResponse(rationale=rationale)
