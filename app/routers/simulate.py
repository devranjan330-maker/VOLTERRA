from fastapi import APIRouter
from app.models import SimulateRequest, SimulateResponse
from app.services.simulation_service import simulate_candidates

router = APIRouter()


@router.post("/simulate", response_model=SimulateResponse)
async def simulate_endpoint(req: SimulateRequest):
    """
    POST /v1/simulate
    Simulate one or more candidate actions against the Digital Twin.
    """
    outcomes = simulate_candidates(req.baseline_state, req.candidates)
    return SimulateResponse(outcomes=outcomes)
