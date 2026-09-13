"""
VOLTERRA - Core Engine Package
==============================
Exposes all pipeline stages:
1. Observe (Ingestion & Normalization)
2. Predict (Forecasting & Risk Classification)
3. Generate (Candidate Action Space)
4. Digital Twin & Simulate (Branching Simulation)
5. Optimize (Objective Scoring & Constraints)
6. Explain (Grounded Rationale Generation)
7. Execute (Virtual & Physical Actuation)
8. Measure (Outcome Verification & Logging)
"""

from engine.observe import SystemState, IngestionEngine, normalize_system_state
from engine.predict import PredictionEngine, Forecast, RiskLevel, RiskClassification, classify_risk
from engine.generate import CandidateGenerator, CandidateAction, generate_candidates
from engine.digital_twin import DigitalTwin, TwinConfig, SimulationMetrics
from engine.simulate import SimulationEngine, SimulatedOutcome, simulate_candidates
from engine.optimize import (
    OptimizationEngine,
    ObjectivesConfig,
    ConstraintsConfig,
    OptimizationResult,
    ConstraintViolationError,
    optimize_outcomes,
)
from engine.explain import ExplanationEngine, explain_decision
from engine.execute import BaseExecutor, VirtualExecutor, PhysicalExecutor, ExecutionResult, execute_action
from engine.measure import MeasurementEngine, MeasurementResult, measure_improvement

__all__ = [
    "SystemState",
    "IngestionEngine",
    "normalize_system_state",
    "PredictionEngine",
    "Forecast",
    "RiskLevel",
    "RiskClassification",
    "classify_risk",
    "CandidateGenerator",
    "CandidateAction",
    "generate_candidates",
    "DigitalTwin",
    "TwinConfig",
    "SimulationMetrics",
    "SimulationEngine",
    "SimulatedOutcome",
    "simulate_candidates",
    "OptimizationEngine",
    "ObjectivesConfig",
    "ConstraintsConfig",
    "OptimizationResult",
    "ConstraintViolationError",
    "optimize_outcomes",
    "ExplanationEngine",
    "explain_decision",
    "BaseExecutor",
    "VirtualExecutor",
    "PhysicalExecutor",
    "ExecutionResult",
    "execute_action",
    "MeasurementEngine",
    "MeasurementResult",
    "measure_improvement",
]
