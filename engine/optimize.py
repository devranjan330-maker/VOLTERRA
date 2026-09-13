"""
VOLTERRA - Engine: Multi-Objective Optimization Engine
=======================================================
Implements Stage 2 (Optimize) of the VOLTERRA Decision Engine Design Document:
- Multi-objective scoring across configurable, weighted objective functions:
    Minimize: energy waste, cost, peak demand, risk
    Maximize: reliability, renewable utilization, battery health
- Explicit hard-constraint filtering (e.g., minimum required battery reserve)
  strictly prior to scoring.
- Transparent and traceable scoring: retains score breakdown per objective for Explainability.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union


class ConstraintViolationError(Exception):
    """Raised when no candidate actions satisfy required hard constraints."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


@dataclass
class ObjectivesConfig:
    """
    Configurable objective functions as specified in Section 5 of the
    Decision Engine Design Document:
        Minimize: energy waste, cost, peak demand, risk
        Maximize: reliability, renewable utilization, battery health
    """
    minimize: List[str] = field(default_factory=lambda: [
        "peak_demand", "cost", "energy_waste", "risk"
    ])
    maximize: List[str] = field(default_factory=lambda: [
        "battery_health", "renewable_utilization", "reliability"
    ])
    weights: Optional[Dict[str, float]] = None


@dataclass
class ConstraintsConfig:
    """Hard operational limits that override objective-score optimization."""
    min_battery_reserve_pct: float = 30.0
    max_allowable_peak_kw: Optional[float] = 15.0


@dataclass
class OptimizationResult:
    selected_candidate_id: str
    scores: Dict[str, Any]
    score_basis: str = ""
    winning_outcome: Optional[Dict[str, Any]] = None


class OptimizationEngine:
    """
    Multi-objective scoring engine with explicit hard constraint enforcement.
    """

    DEFAULT_WEIGHTS = {
        # Minimize (negative weights)
        "peak_demand": -1.0,
        "peak_demand_kw": -1.0,
        "cost": -0.5,
        "energy_waste": -0.4,
        "risk": -0.8,
        # Maximize (positive weights)
        "renewable_utilization": 0.8,
        "renewable_utilization_pct": 0.8,
        "battery_health": 0.5,
        "battery_reserve_pct": 0.3,
        "reliability": 0.7,
    }

    def __init__(
        self,
        default_objectives: Optional[ObjectivesConfig] = None,
        default_constraints: Optional[ConstraintsConfig] = None,
        weights: Optional[Dict[str, float]] = None,
    ):
        self.objectives = default_objectives or ObjectivesConfig()
        self.constraints = default_constraints or ConstraintsConfig()
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)

    def score_outcome(
        self,
        metrics: Dict[str, Any],
        objectives: ObjectivesConfig,
        custom_weights: Optional[Dict[str, float]] = None,
        baseline_demand_kw: Optional[float] = None,
        solar_generation_kw: Optional[float] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculates multi-objective score across the 7 core objectives:
        - peak demand, cost, energy waste, risk (minimize)
        - reliability, renewable utilization, battery health (maximize)
        """
        weights = custom_weights or (objectives.weights if objectives and objectives.weights else self.weights)
        breakdown: Dict[str, float] = {}
        total = 0.0

        peak = float(metrics.get("peak_demand_kw", 0.0))
        cost = float(metrics.get("cost", 0.0))
        batt = float(metrics.get("battery_reserve_pct", 0.0))
        renew = float(metrics.get("renewable_utilization_pct", 0.0))
        solar = float(solar_generation_kw if solar_generation_kw is not None else 0.0)

        # 1. Peak Demand (Minimize)
        w_peak = weights.get("peak_demand", weights.get("peak_demand_kw", -1.0))
        s_peak = w_peak * peak
        breakdown["peak_score"] = round(s_peak, 2)
        total += s_peak

        # 2. Cost (Minimize)
        w_cost = weights.get("cost", -0.5)
        s_cost = w_cost * cost
        breakdown["cost_score"] = round(s_cost, 2)
        total += s_cost

        # 3. Energy Waste (Minimize)
        # Unutilized or lost energy
        discharged = float(metrics.get("discharged_kw", 0.0))
        energy_waste = max(0.0, (solar + discharged) - peak) if peak > 0 else 0.0
        w_waste = weights.get("energy_waste", -0.4)
        s_waste = w_waste * energy_waste
        breakdown["energy_waste_score"] = round(s_waste, 2)
        total += s_waste

        # 4. Risk (Minimize)
        # Operational deficit risk: demand exceeding on-site generation
        risk_penalty = max(0.0, peak - solar) if solar > 0 else peak
        w_risk = weights.get("risk", -0.8)
        s_risk = w_risk * (risk_penalty / 10.0)
        breakdown["risk_score"] = round(s_risk, 2)
        total += s_risk

        # 5. Renewable Utilization (Maximize)
        w_renew = weights.get("renewable_utilization", weights.get("renewable_utilization_pct", 0.8))
        s_renew = w_renew * (renew / 10.0)
        breakdown["renewable_score"] = round(s_renew, 2)
        total += s_renew

        # 6. Battery Health (Maximize)
        # Remaining reserve minus degradation impact
        degradation = float(metrics.get("degradation_impact_pct", 0.0))
        health_metric = max(0.0, batt - (degradation * 100.0))
        w_batt = weights.get("battery_health", weights.get("battery_reserve_pct", 0.3))
        s_batt = w_batt * (health_metric / 10.0)
        breakdown["battery_score"] = round(s_batt, 2)
        total += s_batt

        # 7. Reliability (Maximize)
        # Reserve safety buffer
        reliability_margin = max(0.0, batt - 20.0)
        w_rel = weights.get("reliability", 0.7)
        s_rel = w_rel * (reliability_margin / 20.0)
        breakdown["reliability_score"] = round(s_rel, 2)
        total += s_rel

        return round(total, 2), breakdown

    def optimize(
        self,
        outcomes: List[Any],
        objectives: Optional[Union[ObjectivesConfig, Dict[str, Any]]] = None,
        constraints: Optional[Union[ConstraintsConfig, Dict[str, Any]]] = None,
        raise_on_infeasible: bool = True,
        baseline_demand_kw: Optional[float] = None,
    ) -> OptimizationResult:
        """
        1. Filters outcomes against hard operational constraints.
        2. Computes multi-objective score for all feasible strategies.
        3. Identifies optimal action and returns score basis.
        """
        # Parse configs
        if isinstance(objectives, dict):
            obj_cfg = ObjectivesConfig(
                minimize=objectives.get("minimize", ["peak_demand", "cost", "energy_waste", "risk"]),
                maximize=objectives.get("maximize", ["battery_health", "renewable_utilization", "reliability"]),
                weights=objectives.get("weights"),
            )
        elif isinstance(objectives, ObjectivesConfig):
            obj_cfg = objectives
        else:
            obj_cfg = self.objectives

        if isinstance(constraints, dict):
            min_batt = float(constraints.get("min_battery_reserve_pct", 30.0))
            max_peak = constraints.get("max_allowable_peak_kw")
            const_cfg = ConstraintsConfig(
                min_battery_reserve_pct=min_batt,
                max_allowable_peak_kw=float(max_peak) if max_peak is not None else None,
            )
        elif isinstance(constraints, ConstraintsConfig):
            const_cfg = constraints
        else:
            const_cfg = self.constraints

        scores: Dict[str, Any] = {}
        feasible_candidates: List[Tuple[str, float, Any, Dict[str, Any]]] = []

        for o in outcomes:
            cid = getattr(o, "candidate_id", None) or (o.get("candidate_id") if isinstance(o, dict) else "unknown")
            metrics = getattr(o, "metrics", None) or (o.get("metrics", {}) if isinstance(o, dict) else {})
            if hasattr(metrics, "to_dict"):
                metrics = metrics.to_dict()

            batt_reserve = float(metrics.get("battery_reserve_pct", 0.0))
            peak_demand = float(metrics.get("peak_demand_kw", 0.0))

            # Hard constraint check 1: minimum battery reserve
            is_feasible = batt_reserve >= const_cfg.min_battery_reserve_pct

            # Hard constraint check 2: maximum allowable peak kW (if configured)
            if const_cfg.max_allowable_peak_kw is not None and peak_demand > const_cfg.max_allowable_peak_kw:
                is_feasible = False

            total_score, breakdown = self.score_outcome(
                metrics,
                obj_cfg,
                baseline_demand_kw=baseline_demand_kw,
            )

            scores[cid] = {
                "total_score": total_score,
                "feasible": is_feasible,
                "peak_demand_kw": peak_demand,
                "battery_reserve_pct": batt_reserve,
                "cost": metrics.get("cost"),
                "renewable_utilization_pct": metrics.get("renewable_utilization_pct"),
                "degradation_impact_pct": metrics.get("degradation_impact_pct", 0.0),
                "breakdown": breakdown,
            }

            if is_feasible:
                feasible_candidates.append((cid, total_score, o, metrics))

        if not feasible_candidates:
            if raise_on_infeasible:
                raise ConstraintViolationError(
                    f"All candidate actions violate hard constraints (min_battery_reserve_pct >= {const_cfg.min_battery_reserve_pct}%).",
                    details={"min_battery_reserve_pct": const_cfg.min_battery_reserve_pct, "scores": scores},
                )
            # Fallback
            fallback = max(scores.items(), key=lambda item: item[1]["battery_reserve_pct"])
            return OptimizationResult(
                selected_candidate_id=fallback[0],
                scores=scores,
                score_basis="Fallback to candidate closest to battery constraint",
                winning_outcome=None,
            )

        # Select highest-scoring feasible candidate
        winning_cid, winning_score, winning_outcome, winning_metrics = max(feasible_candidates, key=lambda x: x[1])

        # Formulate score basis per Section 5 example:
        # "Reduces predicted peak demand while preserving required battery reserve"
        score_basis = (
            f"Reduces predicted peak demand to {winning_metrics.get('peak_demand_kw')} kW "
            f"while preserving required battery reserve at {winning_metrics.get('battery_reserve_pct')}%"
        )

        return OptimizationResult(
            selected_candidate_id=winning_cid,
            scores=scores,
            score_basis=score_basis,
            winning_outcome=winning_outcome if isinstance(winning_outcome, dict) else (winning_outcome.__dict__ if hasattr(winning_outcome, "__dict__") else None),
        )


def optimize_outcomes(
    outcomes: List[Any],
    objectives: Optional[Any] = None,
    constraints: Optional[Any] = None,
    raise_on_infeasible: bool = True,
    baseline_demand_kw: Optional[float] = None,
) -> OptimizationResult:
    opt = OptimizationEngine()
    return opt.optimize(
        outcomes,
        objectives,
        constraints,
        raise_on_infeasible=raise_on_infeasible,
        baseline_demand_kw=baseline_demand_kw,
    )
