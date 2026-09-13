from typing import List, Dict, Any, Tuple
from fastapi import HTTPException
from app.models import SimulatedOutcome, ObjectivesConfig, ConstraintsConfig, OptimizeResponse


def optimize_outcomes(
    outcomes: List[SimulatedOutcome],
    objectives: ObjectivesConfig = None,
    constraints: ConstraintsConfig = None,
) -> OptimizeResponse:
    """
    Score simulated outcomes against configured objectives and hard constraints.
    Returns the winning candidate_id and detailed scores.
    """
    if not outcomes:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_input", "message": "No simulated outcomes provided to optimize"},
        )

    if objectives is None:
        objectives = ObjectivesConfig()
    if constraints is None:
        constraints = ConstraintsConfig()

    min_reserve = constraints.min_battery_reserve_pct if constraints.min_battery_reserve_pct is not None else 0.0

    scores: Dict[str, Any] = {}
    feasible_candidates = []

    for outcome in outcomes:
        cid = outcome.candidate_id
        m = outcome.metrics

        # Constraint check: hard constraint on battery reserve
        is_feasible = m.battery_reserve_pct >= min_reserve

        # Objective scoring:
        # Negative terms for minimize, positive terms for maximize
        score_breakdown = {}
        total_score = 0.0

        for min_metric in objectives.minimize or []:
            val = getattr(m, min_metric, 0.0)
            weight = -1.0
            contrib = weight * val
            score_breakdown[f"min_{min_metric}"] = round(contrib, 2)
            total_score += contrib

        for max_metric in objectives.maximize or []:
            val = getattr(m, max_metric, 0.0)
            weight = 0.5  # scaling weight for percentage values
            contrib = weight * val
            score_breakdown[f"max_{max_metric}"] = round(contrib, 2)
            total_score += contrib

        total_score = round(total_score, 2)

        scores[cid] = {
            "total_score": total_score,
            "breakdown": score_breakdown,
            "feasible": is_feasible,
            "peak_demand_kw": m.peak_demand_kw,
            "cost": m.cost,
            "battery_reserve_pct": m.battery_reserve_pct,
            "renewable_utilization_pct": m.renewable_utilization_pct,
        }

        if is_feasible:
            feasible_candidates.append((cid, total_score))

    if not feasible_candidates:
        # 409 Constraint violation per Document 3 Section 5
        raise HTTPException(
            status_code=409,
            detail={
                "code": "constraint_violation",
                "message": f"No candidate strategy satisfies the minimum battery reserve constraint ({min_reserve}%).",
            },
        )

    # Select highest total_score among feasible candidates
    best_candidate_id, _ = max(feasible_candidates, key=lambda x: x[1])

    return OptimizeResponse(
        selected_candidate_id=best_candidate_id,
        scores=scores,
    )
