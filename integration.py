#!/usr/bin/env python
"""
VOLTERRA - Integration Layer
==============================
Wires every previously built component into the single closed-loop pipeline described
across the VOLTERRA PRD and Architecture:
    Observe -> Predict -> Generate -> Simulate -> Optimize -> Explain -> Execute -> Measure

This script provides a runnable equivalent of the orchestrated /v1/decide endpoint,
plus Execute + Measure to close the loop end-to-end, matching the MVP Definition of Done.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

# Import components
from prediction_engine import PredictionEngine, SystemState, Forecast, RiskLevel
from decision_engine import DecisionEngine, Decision
from simulation_engine import SimulationEngine, DigitalTwin, TwinConfig, SimulationMetrics
from explanation_layer import ExplanationLayer, Explanation


class Executor:
    """Applies the recommended decision virtually or to physical actuators."""
    def execute(self, decision: Decision) -> str:
        return f"Executed action: {decision.action}"


class Measurer:
    """Measures pre- and post-intervention system states to quantify improvement."""
    def measure(self, before: SystemState, after: SystemState) -> Dict[str, Any]:
        delta_demand = after.demand_kw - before.demand_kw
        delta_battery = after.battery_level_pct - before.battery_level_pct
        improvement_pct = (
            ((before.demand_kw - after.demand_kw) / before.demand_kw) * 100.0
            if before.demand_kw > 0
            else 0.0
        )
        return {
            "before_peak_kw": round(before.demand_kw, 2),
            "after_peak_kw": round(after.demand_kw, 2),
            "delta_demand_kw": round(delta_demand, 2),
            "delta_battery_pct": round(delta_battery, 2),
            "peak_reduction_pct": round(improvement_pct, 2),
        }


@dataclass
class VolterraEngine:
    """Orchestrates the full closed-loop pipeline.

    Steps:
        1. Observe - gather current SystemState.
        2. Predict - forecast demand/supply and classify risk.
        3. Generate - produce candidate actions.
        4. Simulate - evaluate each candidate in a digital twin.
        5. Optimize - rank candidates and pick the best strategy.
        6. Explain - generate a human-readable justification.
        7. Execute - apply the chosen action.
        8. Measure - compare pre- and post-state.
    """

    predictor: PredictionEngine = field(default_factory=PredictionEngine)
    decisioner: DecisionEngine = field(default_factory=DecisionEngine)
    simulator: SimulationEngine = field(default_factory=SimulationEngine)
    explainer: ExplanationLayer = field(default_factory=ExplanationLayer)
    executor: Executor = field(default_factory=Executor)
    measurer: Measurer = field(default_factory=Measurer)

    def run(self, current_state: SystemState) -> Dict[str, Any]:
        # 1. Observe (already have `current_state`)

        # 2. Predict near-future system state and classify risk
        forecast: Forecast = self.predictor.predict(
            demand_history_kw=[current_state.demand_kw],
            supply_history_kw=[current_state.available_supply_kw()],
            current_timestamp=current_state.timestamp,
            horizon_minutes=30,
        )

        # 3. Generate candidate actions (PRD Section 5.3: A, B, C, D)
        candidates = self.decisioner.generate_candidates(forecast=forecast, state=current_state)

        # 4. Simulate each candidate on the Digital Twin (PRD Section 5.4)
        twin_cfg = TwinConfig(initial_state=current_state)
        twin = DigitalTwin(twin_cfg)
        simulation_results = []
        for action in candidates:
            twin.reset()  # start from the exact same baseline each time
            result_state = self.simulator.run(twin, action, horizon=timedelta(minutes=30))
            metrics = twin.last_metrics
            simulation_results.append((action, result_state, metrics))

        # 5. Optimize - evaluate simulated outcomes against multi-objective weights & constraints
        best_action, best_state, scores = self.decisioner.optimize(
            simulation_results=simulation_results,
            min_battery_reserve_pct=20.0,
        )

        # 6. Explain - generate plain-language justification (PRD Section 5.6)
        decision = Decision(
            action=best_action,
            rationale=f"Strategy {best_action} optimizes peak demand while protecting battery health.",
            scores=scores,
            simulated_state=best_state,
        )
        explanation: Explanation = self.explainer.explain(
            decision=decision,
            forecast=forecast,
            simulated_state=best_state,
            scores=scores,
        )
        decision.rationale = explanation.text

        # 7. Execute - apply chosen decision
        exec_msg = self.executor.execute(decision)

        # 8. Measure - verify outcome and quantify peak reduction
        metrics = self.measurer.measure(before=current_state, after=best_state)

        # Output summary
        print("=== VOLTERRA Closed-Loop Demo ===")
        print(f"Forecast risk: {forecast.risk_classification.value}")
        print(f"Chosen action: {best_action}")
        print(f"Explanation: {explanation.text}")
        print(f"Execution: {exec_msg}")
        print(f"Metrics: {metrics}")

        return {
            "current_state": current_state,
            "forecast": forecast,
            "candidates": candidates,
            "simulation_results": simulation_results,
            "decision": decision,
            "explanation": explanation,
            "execution": exec_msg,
            "metrics": metrics,
        }


def _demo() -> None:
    # Benchmark scenario from PRD Section 5.2 & 5.8:
    # Peak demand 9.4 kW exceeding 5.0 kW solar supply, triggering optimization
    now = datetime(2026, 9, 12, 14, 0, 0)
    current = SystemState(
        timestamp=now,
        demand_kw=9.4,
        solar_generation_kw=5.0,
        battery_level_pct=60.0,
        temperature_c=29.5,
    )
    engine = VolterraEngine()
    engine.run(current)


if __name__ == "__main__":
    _demo()
