"""
VOLTERRA - API Route: /v1/simulate
==================================
Implements Step 4: Evaluates candidate actions against Digital Twin with parallel branching.
"""

from fastapi import APIRouter
from api.schemas import SimulateRequest, SimulateResponse, SimulatedOutcome, OutcomeMetrics
from engine.simulate import simulate_candidates

router = APIRouter()


@router.post("/simulate", response_model=SimulateResponse)
async def simulate(req: SimulateRequest):
    """
    POST /v1/simulate
    Runs what-if simulation for each candidate against the Digital Twin.
    """
    raw_outcomes = simulate_candidates(
        baseline_state=req.baseline_state,
        candidates=[c.model_dump() for c in req.candidates],
        predicted_state=req.predicted_state,
    )

    outcomes = [
        SimulatedOutcome(
            candidate_id=o.candidate_id,
            projected_state=o.projected_state,
            metrics=OutcomeMetrics(
                peak_demand_kw=o.metrics.get("peak_demand_kw", 0.0),
                cost=o.metrics.get("cost", 0.0),
                battery_reserve_pct=o.metrics.get("battery_reserve_pct", 0.0),
                renewable_utilization_pct=o.metrics.get("renewable_utilization_pct", 0.0),
                degradation_impact_pct=o.metrics.get("degradation_impact_pct", 0.0),
                is_feasible=o.metrics.get("is_feasible", True),
                constraint_notes=o.metrics.get("constraint_notes"),
            ),
        )
        for o in raw_outcomes
    ]

    return SimulateResponse(outcomes=outcomes)
