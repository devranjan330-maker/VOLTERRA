"""
VOLTERRA - API Route: /v1/decide
================================
Implements Step 9: Orchestrated end-to-end execution of the closed-loop decision cycle:
Observe -> Predict -> Generate -> Simulate -> Optimize -> Explain -> Audit Log
"""

from fastapi import APIRouter, HTTPException
from api.schemas import (
    DecideRequest,
    DecideResponse,
    Decision,
    CandidateAction,
    SimulatedOutcome,
    OutcomeMetrics,
    RiskClassification,
)
from engine.observe import normalize_system_state
from engine.predict import PredictionEngine
from engine.generate import generate_candidates
from engine.simulate import simulate_candidates
from engine.optimize import optimize_outcomes, ConstraintViolationError
from engine.explain import explain_decision
from storage.history_store import history_store

router = APIRouter()
predictor = PredictionEngine()


@router.post("/decide", response_model=DecideResponse)
async def decide(req: DecideRequest):
    """
    POST /v1/decide
    Execute complete closed-loop decision cycle in a single call.
    """
    state = normalize_system_state(req.system_state)

    # 1. Predict
    forecast = predictor.predict(
        demand_history_kw=[state.demand_kw],
        supply_history_kw=[state.solar_generation_kw],
        current_timestamp=state.timestamp,
        horizon_minutes=req.horizon_minutes or 30,
    )

    # 2. Generate
    candidates_list = generate_candidates(
        risk_classification=forecast.risk_classification,
        state=state,
        forecast=forecast,
    )

    # 3. Simulate
    sim_outcomes = simulate_candidates(
        baseline_state=state,
        candidates=[c.__dict__ for c in candidates_list],
        horizon_minutes=req.horizon_minutes or 30,
    )

    # 4. Optimize
    try:
        opt_res = optimize_outcomes(
            outcomes=[o.__dict__ for o in sim_outcomes],
            objectives=req.objectives.model_dump() if req.objectives else None,
            constraints=req.constraints.model_dump() if req.constraints else None,
            raise_on_infeasible=True,
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

    # 5. Explain
    rationale = explain_decision(
        selected_candidate_id=opt_res.selected_candidate_id,
        scores=opt_res.scores,
        baseline_demand_kw=state.demand_kw,
    )

    decision_obj = Decision(
        selected_candidate_id=opt_res.selected_candidate_id,
        rationale=rationale,
        score_basis=opt_res.score_basis,
        scores=opt_res.scores,
    )

    candidates_response = [
        CandidateAction(id=c.id, label=c.label, description=c.description)
        for c in candidates_list
    ]

    outcomes_response = [
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
        for o in sim_outcomes
    ]

    # 6. Audit Log (Normalized Relational Database)
    history_store.record_full_cycle(
        observed_state=state.to_dict(),
        forecast_result={
            "timestamp": state.timestamp.isoformat() if hasattr(state.timestamp, "isoformat") else str(state.timestamp),
            "horizon_minutes": forecast.horizon_minutes,
            "forecasted_demand_kw": forecast.forecasted_demand_kw,
            "forecasted_supply_kw": forecast.forecasted_supply_kw,
            "risk_classification": forecast.risk_classification.value,
            "notes": forecast.notes,
        },
        candidates=[{"id": c.id, "label": c.label, "description": c.description} for c in candidates_list],
        sim_outcomes=[
            {
                "candidate_id": o.candidate_id,
                "peak_demand_kw": o.metrics.get("peak_demand_kw", 0.0),
                "cost": o.metrics.get("cost", 0.0),
                "battery_reserve_pct": o.metrics.get("battery_reserve_pct", 0.0),
                "renewable_utilization_pct": o.metrics.get("renewable_utilization_pct", 0.0),
                "projected_state": o.projected_state.to_dict() if hasattr(o.projected_state, "to_dict") else (o.projected_state if isinstance(o.projected_state, dict) else getattr(o.projected_state, "__dict__", {})),
            }
            for o in sim_outcomes
        ],
        optimization_result={
            "selected_candidate_id": opt_res.selected_candidate_id,
            "objectives": req.objectives.model_dump() if req.objectives else {},
            "constraints": req.constraints.model_dump() if req.constraints else {},
            "scores": opt_res.scores,
        },
        rationale=rationale,
        cycle_status="completed",
    )

    return DecideResponse(
        risk_classification=RiskClassification(forecast.risk_classification.value),
        candidates=candidates_response,
        outcomes=outcomes_response,
        decision=decision_obj,
    )
