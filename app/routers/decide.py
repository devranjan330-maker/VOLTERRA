from fastapi import APIRouter
from app.models import (
    DecideRequest,
    DecideResponse,
    Decision,
    CandidateAction,
)
from app.services.predict_service import predict_future
from app.services.simulation_service import simulate_candidates
from app.services.optimization_service import optimize_outcomes
from app.services.explain_service import generate_explanation
from app.routers.generate import DEFAULT_CANDIDATES
from app.utils.history_store import history_store

router = APIRouter()


@router.post("/decide", response_model=DecideResponse)
async def decide_endpoint(req: DecideRequest):
    """
    POST /v1/decide
    Run the full closed-loop pipeline:
    Predict -> Generate -> Simulate -> Optimize -> Explain
    """
    # 1. Predict future state & classify risk
    pred = predict_future(state=req.system_state, horizon_minutes=req.horizon_minutes or 30)

    # 2. Generate candidate actions
    candidates = DEFAULT_CANDIDATES

    # 3. Simulate candidates against Digital Twin
    outcomes = simulate_candidates(pred.forecasted_state, candidates)

    # 4. Optimize and rank candidates
    opt_resp = optimize_outcomes(
        outcomes=outcomes,
        objectives=req.objectives,
        constraints=req.constraints,
    )

    # 5. Explain winning rationale
    rationale = generate_explanation(
        selected_candidate_id=opt_resp.selected_candidate_id,
        scores=opt_resp.scores,
    )

    decision = Decision(
        selected_candidate_id=opt_resp.selected_candidate_id,
        rationale=rationale,
        scores=opt_resp.scores,
    )

    response = DecideResponse(
        risk_classification=pred.risk_classification,
        candidates=candidates,
        outcomes=outcomes,
        decision=decision,
    )

    # Persist decision cycle to history for closed-loop learning and auditability
    history_store.add({
        "timestamp": req.system_state.timestamp,
        "system_state": req.system_state.model_dump(),
        "risk_classification": pred.risk_classification.value,
        "candidates": [c.model_dump() for c in candidates],
        "outcomes": [o.model_dump() for o in outcomes],
        "decision": decision.model_dump(),
        "outcome": None,
    })

    return response
