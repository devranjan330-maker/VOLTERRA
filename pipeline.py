"""
VOLTERRA - Core Architecture Pipeline Orchestrator
==================================================
Implements Section 2, Section 5, and Section 6 of the Technical Architecture Document.

Wired into the sequential, closed-loop pipeline:
    Observe -> Predict -> Generate -> Simulate -> Optimize -> Explain -> Execute -> Measure -> Learning

Combines the two core functions:
- UNDERSTAND: Observe & Predict
- DECIDE: Generate, Simulate, Optimize, Explain
Plus:
- ACT & VERIFY: Execute, Measure, Audit Log
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union
import uuid

from prediction_engine import PredictionEngine, SystemState, Forecast, RiskLevel
from ingestion_layer import IngestionLayer, NormalizedObservation
from decision_engine import DecisionEngine, Decision
from simulation_engine import SimulationEngine, DigitalTwin, TwinConfig, SimulationMetrics
from explanation_layer import ExplanationLayer, Explanation
from execution_layer import (
    BaseExecutor,
    VirtualExecutor,
    ExecutionResult,
    MeasurementLayer,
    MeasurementResult,
    AuditLogger,
    AuditCycleRecord,
)


@dataclass
class PipelineCycleResult:
    """The comprehensive result of executing a complete closed-loop cycle."""
    cycle_id: str
    timestamp: datetime
    raw_observation: NormalizedObservation
    baseline_state: SystemState
    forecast: Forecast
    candidates: List[str]
    simulation_results: List[Dict[str, Any]]
    decision: Decision
    explanation: Explanation
    execution: ExecutionResult
    measurement: MeasurementResult
    audit_record: AuditCycleRecord


class VolterraPipeline:
    """
    The central orchestrator of the VOLTERRA Closed-Loop Decision Engine.
    Adheres strictly to the 5 Design Principles:
        1. Modularity - Predict, Simulate, and Optimize are independently testable and replaceable.
        2. Explainability by default - Every decision carries an optimization-grounded rationale.
        3. Simulate before act - No action is executed without first being validated in the digital twin.
        4. Closed-loop by design - Measures outcomes and logs them for continuous learning.
        5. Core-first engineering - Streamlined, sub-second execution loop.
    """

    def __init__(
        self,
        ingestor: Optional[IngestionLayer] = None,
        predictor: Optional[PredictionEngine] = None,
        decisioner: Optional[DecisionEngine] = None,
        simulator: Optional[SimulationEngine] = None,
        explainer: Optional[ExplanationLayer] = None,
        executor: Optional[BaseExecutor] = None,
        measurer: Optional[MeasurementLayer] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        self.ingestor = ingestor or IngestionLayer()
        self.predictor = predictor or PredictionEngine()
        self.decisioner = decisioner or DecisionEngine()
        self.simulator = simulator or SimulationEngine()
        self.explainer = explainer or ExplanationLayer()
        self.executor = executor or VirtualExecutor(simulator=self.simulator)
        self.measurer = measurer or MeasurementLayer(target_improvement_pct=10.0)
        self.audit_logger = audit_logger or AuditLogger()

    def run_cycle(
        self,
        raw_telemetry: Union[Dict[str, Any], SystemState],
        horizon_minutes: int = 30,
        min_battery_reserve_pct: float = 20.0,
        demand_history: Optional[List[float]] = None,
        supply_history: Optional[List[float]] = None,
    ) -> PipelineCycleResult:
        """
        Execute one complete closed-loop cycle.
        """
        cycle_id = f"cycle_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # 1. OBSERVE (Ingestion Layer)
        # -------------------------------------------------------------
        observation: NormalizedObservation = self.ingestor.ingest_streaming(raw_telemetry)
        baseline_state: SystemState = observation.state

        # -------------------------------------------------------------
        # 2. PREDICT (Prediction Engine)
        # -------------------------------------------------------------
        d_hist = demand_history or [baseline_state.demand_kw]
        s_hist = supply_history or [baseline_state.available_supply_kw()]

        forecast: Forecast = self.predictor.predict(
            demand_history_kw=d_hist,
            supply_history_kw=s_hist,
            current_timestamp=baseline_state.timestamp,
            horizon_minutes=horizon_minutes,
        )

        # -------------------------------------------------------------
        # 3. GENERATE (Decision Space Generator)
        # -------------------------------------------------------------
        candidates = self.decisioner.generate_candidates(forecast=forecast, state=baseline_state)

        # -------------------------------------------------------------
        # 4. SIMULATE (Digital Twin Layer - Parallel "What-If" Branching)
        # -------------------------------------------------------------
        twin = DigitalTwin(TwinConfig(initial_state=baseline_state))
        sim_tuples = []
        sim_outcomes_log = []

        for cand in candidates:
            twin.reset()  # Baseline isolation: start from the same baseline each time
            sim_state = self.simulator.run(twin, cand, horizon=timedelta(minutes=horizon_minutes))
            metrics = twin.last_metrics
            sim_tuples.append((cand, sim_state, metrics))
            sim_outcomes_log.append({
                "candidate": cand,
                "projected_demand_kw": sim_state.demand_kw,
                "projected_battery_pct": sim_state.battery_level_pct,
                "metrics": asdict(metrics) if metrics else {},
            })

        # -------------------------------------------------------------
        # 5. OPTIMIZE (Optimization Engine)
        # -------------------------------------------------------------
        best_action, best_state, scores = self.decisioner.optimize(
            simulation_results=sim_tuples,
            min_battery_reserve_pct=min_battery_reserve_pct,
        )

        decision = Decision(
            action=best_action,
            scores=scores,
            simulated_state=best_state,
        )

        # -------------------------------------------------------------
        # 6. EXPLAIN (Explainability Layer)
        # -------------------------------------------------------------
        explanation: Explanation = self.explainer.explain(
            decision=decision,
            forecast=forecast,
            simulated_state=best_state,
            scores=scores,
        )
        decision.rationale = explanation.text

        # -------------------------------------------------------------
        # 7. EXECUTE (Execution Layer - Virtual or Physical)
        # -------------------------------------------------------------
        exec_result: ExecutionResult = self.executor.execute(
            decision=decision,
            baseline_state=baseline_state,
            twin=twin,
        )

        # -------------------------------------------------------------
        # 8. MEASURE & LEARN (Measurement Layer & Audit Logger)
        # -------------------------------------------------------------
        meas_result: MeasurementResult = self.measurer.measure(
            before=baseline_state,
            after=exec_result.resulting_state,
        )

        audit_record = AuditCycleRecord(
            cycle_id=cycle_id,
            timestamp=now.isoformat(),
            system_state={
                "demand_kw": baseline_state.demand_kw,
                "solar_generation_kw": baseline_state.solar_generation_kw,
                "battery_level_pct": baseline_state.battery_level_pct,
                "temperature_c": baseline_state.temperature_c,
                "occupancy": baseline_state.occupancy,
            },
            prediction={
                "horizon_minutes": forecast.horizon_minutes,
                "forecasted_demand_kw": forecast.forecasted_demand_kw,
                "forecasted_supply_kw": forecast.forecasted_supply_kw,
                "risk_classification": forecast.risk_classification.value,
                "notes": forecast.notes,
            },
            candidates=candidates,
            simulation_outcomes=sim_outcomes_log,
            chosen_action=best_action,
            rationale=explanation.text,
            scores=scores,
            execution={
                "status": exec_result.status,
                "mode": exec_result.mode,
                "details": exec_result.details,
            },
            outcome_metrics=asdict(meas_result),
        )
        self.audit_logger.log_cycle(audit_record)

        return PipelineCycleResult(
            cycle_id=cycle_id,
            timestamp=now,
            raw_observation=observation,
            baseline_state=baseline_state,
            forecast=forecast,
            candidates=candidates,
            simulation_results=sim_outcomes_log,
            decision=decision,
            explanation=explanation,
            execution=exec_result,
            measurement=meas_result,
            audit_record=audit_record,
        )


def _demo() -> None:
    print("================================================================")
    print(" VOLTERRA - Closed-Loop Architecture Pipeline Demonstration    ")
    print("================================================================")
    pipeline = VolterraPipeline()
    raw_telemetry = {
        "demand_kw": 9.4,
        "solar_generation_kw": 5.0,
        "battery_level_pct": 60.0,
        "temperature_c": 29.5,
        "occupancy": "medium",
    }

    print("\n[1. UNDERSTAND - Observe]")
    print(f" Raw Telemetry Ingested: {raw_telemetry}")

    result = pipeline.run_cycle(raw_telemetry, horizon_minutes=30)
    print(f" Normalized SystemState: {result.baseline_state}")

    print("\n[2. UNDERSTAND - Predict (T+30 min)]")
    print(f" Forecast Demand: {result.forecast.forecasted_demand_kw} kW | Supply: {result.forecast.forecasted_supply_kw} kW")
    print(f" Risk Classification: {result.forecast.risk_classification.value.upper()}")
    print(f" Risk Notes: {result.forecast.notes}")

    print("\n[3. DECIDE - Generate (Decision Space)]")
    print(f" Candidate Actions: {result.candidates}")

    print("\n[4. DECIDE - Simulate (Digital Twin What-If Branching)]")
    for sim in result.simulation_results:
        print(f"  Branch '{sim['candidate']}': Projected Demand = {sim['projected_demand_kw']} kW, Battery = {sim['projected_battery_pct']}%")

    print("\n[5. DECIDE - Optimize]")
    print(f" Winning Strategy: {result.decision.action}")
    print(f" Optimization Score Breakdown: {result.decision.scores.get(result.decision.action, {})}")

    print("\n[6. DECIDE - Explain]")
    print(f" Grounded Rationale: {result.explanation.text}")

    print("\n[7. ACT - Execute]")
    print(f" Mode: {result.execution.mode} | Status: {result.execution.status}")
    print(f" Result: {result.execution.details}")

    print("\n[8. VERIFY - Measure & Learn]")
    m = result.measurement
    print(f" Outcome: {m.summary}")
    print(f" Peak Reduction: {m.improvement_pct}% | Target Met: {m.success_metric_met}")
    print(f" Audit Log Record ID: {result.audit_record.cycle_id}")
    print("================================================================")


if __name__ == "__main__":
    _demo()
