"""
VOLTERRA - API Route: /v1/optimize
==================================
Implements Step 5: Multi-objective scoring and hard-constraint filtering.
Returns 409 Constraint Violation if all candidates violate constraints.
"""

from fastapi import APIRouter, HTTPException
from api.schemas import OptimizeRequest, OptimizeResponse
from engine.optimize import optimize_outcomes, ConstraintViolationError

router = APIRouter()


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize(req: OptimizeRequest):
    """
    POST /v1/optimize
    Score simulated outcomes across multi-objectives subject to constraints.
    """
    try:
        opt_res = optimize_outcomes(
            outcomes=[o.model_dump() for o in req.outcomes],
            objectives=req.objectives.model_dump() if req.objectives else None,
            constraints=req.constraints.model_dump() if req.constraints else None,
            raise_on_infeasible=True,
        )
        return OptimizeResponse(
            selected_candidate_id=opt_res.selected_candidate_id,
            scores=opt_res.scores,
        )
    except ConstraintViolationError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "constraint_violation",
                "message": str(e),
                "details": e.details,
            },
        )
