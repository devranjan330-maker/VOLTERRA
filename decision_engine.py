"""
VOLTERRA — Decision Engine
==========================
Implements the VOLTERRA Decision Engine Design Document (Version 1.0, September 2026).

Answers the system's second core question:
    "What should we do?"

Covers three tightly coupled stages:
1. Stage 1 — Generate: Decision Space Creation (creates multiple viable candidates).
2. Stage 2 — Optimize: Multi-objective Strategy Selection (scores simulated outcomes
   across cost, peak demand, risk, energy waste, reliability, renewables, and battery health
   subject to hard constraints).
3. Stage 3 — Explain: Grounded Rationale Generation (communicates why the selected
   strategy was chosen over alternatives using real scoring data).

Guiding principle:
    "Never commit to a single action immediately. Alternatives are always explored,
    simulated, and compared before a decision is finalized."
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, Any, List, Optional, Tuple, Union

from prediction_engine import PredictionEngine, SystemState, Forecast, RiskLevel
from simulation_engine import SimulationEngine, DigitalTwin, TwinConfig, SimulationMetrics


@dataclass
class Decision:
    """Represents the selected action with supporting score basis, justification, and scores."""
    action: str
    rationale: str = ""
    score_basis: str = ""
    scores: Dict[str, Any] = field(default_factory=dict)
    simulated_state: Optional[SystemState] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateOption:
    """A candidate intervention strategy with human-readable description."""
    id: str
    action_key: str
    label: str
    description: str


# Predefined candidate strategies (Section 4)
DEFAULT_CANDIDATE_OPTIONS = [
    CandidateOption(
        id="A",
        action_key="do_nothing",
        label="Strategy A — Do nothing",
        description="Maintain baseline operations without intervention.",
    ),
    CandidateOption(
        id="B",
        action_key="use_battery",
        label="Strategy B — Use battery",
        description="Discharge on-site battery storage to shave the anticipated peak.",
    ),
    CandidateOption(
        id="C",
        action_key="shift_load",
        label="Strategy C — Shift flexible loads",
        description="Defer non-critical deferrable equipment/HVAC loads.",
    ),
    CandidateOption(
        id="D",
        action_key="hybrid",
        label="Strategy D — Hybrid response",
        description="Combine moderate load shifting with conservative battery discharge.",
    ),
]


class DecisionEngine:
    """
    The Decision Engine coordinates the Generate -> Simulate -> Optimize -> Explain loop.
    """

    DEFAULT_WEIGHTS = {
        # Minimize (negative weights)
        "peak_demand_kw": -1.0,
        "peak_demand": -1.0,
        "cost": -0.5,
        "energy_waste": -0.4,
        "risk": -0.8,
        # Maximize (positive weights)
        "renewable_utilization_pct": 0.8,
        "renewable_utilization": 0.8,
        "battery_reserve_pct": 0.3,
        "battery_health": 0.5,
        "reliability": 0.7,
    }

    def __init__(
        self,
        min_battery_reserve_pct: float = 20.0,
        weights: Optional[Dict[str, float]] = None,
        simulator: Optional[SimulationEngine] = None,
    ):
        self.min_battery_reserve_pct = min_battery_reserve_pct
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)
        self.simulator = simulator or SimulationEngine()

    # -------------------------------------------------------------------------
    # STAGE 1: GENERATE (Decision Space Creation)
    # -------------------------------------------------------------------------
    def generate_candidates(
        self,
        forecast: Optional[Forecast] = None,
        state: Optional[SystemState] = None,
    ) -> List[str]:
        """
        Generates candidate response space (Section 4).
        Never defaults to a single action; explores alternatives.
        """
        # Under normal conditions without risk, preserve battery or do nothing
        if forecast and forecast.risk_classification == RiskLevel.NORMAL:
            return ["do_nothing", "use_battery", "shift_load"]
        return ["do_nothing", "use_battery", "shift_load", "hybrid"]

    def get_candidate_options(self) -> List[CandidateOption]:
        """Return structured candidate metadata."""
        return list(DEFAULT_CANDIDATE_OPTIONS)

    # -------------------------------------------------------------------------
    # STAGE 2: OPTIMIZE (Strategy Selection)
    # -------------------------------------------------------------------------
    def optimize(
        self,
        simulation_results: List[Tuple[str, SystemState, Optional[SimulationMetrics]]],
        min_battery_reserve_pct: Optional[float] = None,
        custom_weights: Optional[Dict[str, float]] = None,
        max_allowable_peak_kw: Optional[float] = None,
    ) -> Tuple[str, SystemState, Dict[str, Any]]:
        """
        Compares simulated outcomes of candidate actions across the 7 objective functions
        subject to hard operational constraints (Section 5).

        Returns:
            Tuple of (winning_action, winning_state, detailed_scores_dict)
        """
        threshold = (
            min_battery_reserve_pct
            if min_battery_reserve_pct is not None
            else self.min_battery_reserve_pct
        )
        weights = custom_weights or self.weights

        scores: Dict[str, Any] = {}
        feasible_candidates: List[Tuple[str, SystemState, float, Dict[str, Any]]] = []

        for item in simulation_results:
            action = item[0]
            sim_state = item[1]
            metrics = item[2]

            peak_demand = sim_state.demand_kw
            battery_reserve = sim_state.battery_level_pct
            cost = metrics.cost if metrics else round(peak_demand * 0.5, 2)
            solar = sim_state.solar_generation_kw
            renewable_util = (
                metrics.renewable_utilization_pct
                if metrics
                else min(100.0, max(0.0, (solar / max(0.1, peak_demand)) * 100.0))
            )
            discharged = metrics.discharged_kw if metrics else 0.0

            # 1. Hard Constraints (Section 5)
            # Minimum battery reserve
            is_feasible = battery_reserve >= threshold
            if max_allowable_peak_kw is not None and peak_demand > max_allowable_peak_kw:
                is_feasible = False

            # 2. Multi-Objective Scoring (Section 5)
            # Minimize: peak demand, cost, energy waste, risk
            score_peak = weights.get("peak_demand_kw", -1.0) * peak_demand
            score_cost = weights.get("cost", -0.5) * cost
            energy_waste = max(0.0, (solar + discharged) - peak_demand) if peak_demand > 0 else 0.0
            score_waste = weights.get("energy_waste", -0.4) * energy_waste
            risk_penalty = max(0.0, peak_demand - solar) if solar > 0 else peak_demand
            score_risk = weights.get("risk", -0.8) * (risk_penalty / 10.0)

            # Maximize: renewable utilization, battery health, reliability
            score_renew = weights.get("renewable_utilization_pct", 0.8) * (renewable_util / 10.0)
            score_batt = weights.get("battery_reserve_pct", 0.3) * (battery_reserve / 10.0)
            reliability_margin = max(0.0, battery_reserve - 20.0)
            score_rel = weights.get("reliability", 0.7) * (reliability_margin / 20.0)

            total_score = round(
                score_peak + score_cost + score_waste + score_risk + score_renew + score_batt + score_rel,
                2,
            )

            scores[action] = {
                "total_score": total_score,
                "feasible": is_feasible,
                "peak_demand_kw": peak_demand,
                "battery_reserve_pct": battery_reserve,
                "cost": cost,
                "renewable_utilization_pct": renewable_util,
                "breakdown": {
                    "peak_score": round(score_peak, 2),
                    "cost_score": round(score_cost, 2),
                    "energy_waste_score": round(score_waste, 2),
                    "risk_score": round(score_risk, 2),
                    "renewable_score": round(score_renew, 2),
                    "battery_score": round(score_batt, 2),
                    "reliability_score": round(score_rel, 2),
                },
            }

            if is_feasible:
                feasible_candidates.append((action, sim_state, total_score, scores[action]))

        if not feasible_candidates:
            # Fallback to least-violating candidate
            best_action, best_state, _ = max(
                [(item[0], item[1], item[1].battery_level_pct) for item in simulation_results],
                key=lambda x: x[2],
            )
            return best_action, best_state, scores

        # Select highest scoring feasible candidate
        best_action, best_state, _, _ = max(feasible_candidates, key=lambda x: x[2])
        return best_action, best_state, scores

    # -------------------------------------------------------------------------
    # STAGE 3: EXPLAIN (Explainable Decision Intelligence)
    # -------------------------------------------------------------------------
    def explain(
        self,
        selected_action: str,
        scores: Dict[str, Any],
        baseline_demand_kw: Optional[float] = None,
    ) -> Tuple[str, str]:
        """
        Communicates why the selected strategy was chosen (Section 6).
        Returns:
            (rationale, score_basis)
        """
        cand_score = scores.get(selected_action, {})
        peak = cand_score.get("peak_demand_kw")
        batt = cand_score.get("battery_reserve_pct")

        label_map = {
            "do_nothing": "Strategy A (Do nothing)",
            "use_battery": "Strategy B (Use battery)",
            "shift_load": "Strategy C (Shift flexible loads)",
            "hybrid": "Strategy D (Hybrid response)",
            "A": "Strategy A (Do nothing)",
            "B": "Strategy B (Use battery)",
            "C": "Strategy C (Shift flexible loads)",
            "D": "Strategy D (Hybrid response)",
        }
        label = label_map.get(selected_action, f"Strategy {selected_action}")

        # Score basis (Section 5 example)
        if peak is not None and batt is not None:
            score_basis = f"Reduces predicted peak demand while preserving required battery reserve"
        else:
            score_basis = "Maximizes multi-objective score while respecting operational constraints"

        # Correct pattern (Section 6)
        if peak is not None and batt is not None:
            rationale = (
                f"{label} is preferred because it reduces the predicted peak to {peak} kW "
                f"while maintaining the required battery reserve at {batt}%."
            )
        else:
            rationale = f"{label} is preferred based on multi-objective scoring evaluation."

        return rationale, score_basis

    # -------------------------------------------------------------------------
    # FULL DECISION CYCLE
    # -------------------------------------------------------------------------
    def decide(
        self,
        current_state: SystemState,
        horizon_minutes: int = 30,
        min_battery_reserve_pct: Optional[float] = None,
        forecast: Optional[Forecast] = None,
    ) -> Decision:
        """
        Executes Generate -> Simulate -> Optimize -> Explain.
        """
        # 1. Generate (Stage 1)
        candidates = self.generate_candidates(forecast=forecast, state=current_state)

        # 2. Simulate (Digital Twin branching)
        twin = DigitalTwin(TwinConfig(initial_state=current_state))
        sim_results = []
        for cand in candidates:
            twin.reset()
            sim_state = self.simulator.run(twin, cand, horizon=timedelta(minutes=horizon_minutes))
            sim_results.append((cand, sim_state, twin.last_metrics))

        # 3. Optimize (Stage 2)
        best_action, best_state, scores = self.optimize(
            sim_results,
            min_battery_reserve_pct=min_battery_reserve_pct,
        )

        # 4. Explain (Stage 3)
        rationale, score_basis = self.explain(
            selected_action=best_action,
            scores=scores,
            baseline_demand_kw=current_state.demand_kw,
        )

        winning_metrics = scores.get(best_action, {})

        return Decision(
            action=best_action,
            rationale=rationale,
            score_basis=score_basis,
            scores=scores,
            simulated_state=best_state,
            metrics=winning_metrics,
        )
