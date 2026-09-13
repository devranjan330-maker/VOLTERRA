from fastapi import APIRouter
from app.models import OptimizeRequest, OptimizeResponse
from app.services.optimization_service import optimize_outcomes

router = APIRouter()


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_endpoint(req: OptimizeRequest):
    """
    POST /v1/optimize
    Score simulated outcomes against configured objectives and select best feasible strategy.
    Enforces hard constraints (e.g., minimum battery reserve).
    """
    return optimize_outcomes(
        outcomes=req.outcomes,
        objectives=req.objectives,
        constraints=req.constraints,
    )
