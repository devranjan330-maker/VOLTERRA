"""
VOLTERRA — Simulation Engine Design Implementation
===================================================
Implements the VOLTERRA Simulation Engine Design Document (Version 1.0, September 2026).

Answers the core question:
    "What happens if we do it?"

Role:
- Sits between Generate (candidate actions) and Optimize (strategy selection).
- Orchestrates "what-if" evaluations of candidate actions against the Digital Twin.
- Produces structured, comparable projections for the Optimization Engine.

5-Step Simulation Flow:
1. Branch creation — one simulation branch per candidate action.
2. State application — candidate action applied to baseline state within branch.
3. Forward projection — Digital Twin advances state across decision horizon.
4. Metric extraction — standardizes values for optimization scoring.
5. Result packaging — packages all outcomes into uniform comparable structure.

Design Principles:
1. One simulation per candidate, no shortcuts.
2. Isolation between branches — simulating B must never alter inputs for C.
3. Parallelizable by design — concurrent execution support for scalability.
4. Consistent output structure — uniform metric contracts for optimization.
5. Full auditability — logs inputs, action, and resulting projection per run.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Union, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import time
import uuid

from engine.observe import SystemState, normalize_system_state
from engine.generate import CandidateAction
from engine.digital_twin import DigitalTwin, TwinConfig, SimulationMetrics


@dataclass
class SimulationRunRecord:
    """
    Audit record for an individual simulation branch execution (Section 8 Principle 5).
    """
    run_id: str
    branch_id: str
    candidate_id: str
    timestamp: str
    decision_horizon_minutes: int
    baseline_state_snapshot: Dict[str, Any]
    predicted_state_snapshot: Optional[Dict[str, Any]]
    action_applied: str
    projected_state: Dict[str, Any]
    metrics: Dict[str, Any]
    latency_ms: float


@dataclass
class SimulatedOutcome:
    """
    Standardized simulation outcome per candidate (Section 4.2).
    """
    candidate_id: str
    projected_state: Dict[str, Any]
    metrics: Dict[str, Any]
    branch_id: Optional[str] = None
    action_label: Optional[str] = None


@dataclass
class SimulationPackage:
    """
    Packaged results of all candidate branches ready for Optimization Engine handoff (Section 5.5).
    """
    outcomes: List[SimulatedOutcome]
    decision_horizon_minutes: int
    baseline_state: Dict[str, Any]
    audit_records: List[SimulationRunRecord] = field(default_factory=list)
    total_execution_ms: float = 0.0


class SimulationEngine:
    """
    The process/orchestration layer that executes, manages, and logs
    what-if branching evaluations against the Digital Twin.
    """

    def __init__(
        self,
        twin_config: Optional[TwinConfig] = None,
        max_workers: int = 4,
    ):
        self.default_twin_config = twin_config
        self.max_workers = max_workers
        self._audit_log: List[SimulationRunRecord] = []

    def get_audit_log(self) -> List[SimulationRunRecord]:
        """Returns historical simulation run audit log."""
        return list(self._audit_log)

    def clear_audit_log(self):
        self._audit_log.clear()

    # -------------------------------------------------------------------------
    # STEP 1: Branch Creation
    # -------------------------------------------------------------------------
    def _create_branch(
        self,
        branch_index: int,
        candidate_id: str,
    ) -> str:
        return f"branch_{branch_index}_{candidate_id}_{uuid.uuid4().hex[:6]}"

    # -------------------------------------------------------------------------
    # STEP 2, 3, & 4: Single Branch Execution (State Application -> Forward Projection -> Metric Extraction)
    # -------------------------------------------------------------------------
    def _execute_branch(
        self,
        branch_id: str,
        cand_id: str,
        baseline_state: SystemState,
        predicted_state: Optional[SystemState],
        horizon_minutes: int,
    ) -> Tuple[SimulatedOutcome, SimulationRunRecord]:
        t0 = time.perf_counter()
        now_ts = datetime.now(timezone.utc).isoformat()

        # Principle 2: Isolation between branches (fresh isolated twin instance)
        twin_cfg = self.default_twin_config or TwinConfig(initial_state=baseline_state)
        # Deepcopy to guarantee side-effect-free execution
        twin_cfg_branch = deepcopy(twin_cfg)
        twin_cfg_branch.initial_state = deepcopy(baseline_state)
        twin = DigitalTwin(twin_cfg_branch)

        # Step 2 & 3: Apply action & Forward project across horizon
        horizon = timedelta(minutes=horizon_minutes)
        sim_state, raw_metrics = twin.transition(
            action_id=cand_id,
            horizon=horizon,
            predicted_state=predicted_state,
        )

        # Step 4: Metric Extraction (Standardized for Optimization Engine handoff)
        peak_demand = raw_metrics.peak_demand_kw
        solar = sim_state.solar_generation_kw
        discharged = raw_metrics.discharged_kw
        batt_reserve = raw_metrics.battery_reserve_pct

        # Derived metrics aligned with Section 7 (the 7 optimization objectives):
        energy_waste = round(max(0.0, (solar + discharged) - peak_demand), 2) if peak_demand > 0 else 0.0
        risk_penalty = round(max(0.0, peak_demand - solar), 2) if solar > 0 else peak_demand
        reliability_margin = round(max(0.0, batt_reserve - 20.0), 2)
        battery_health = round(max(0.0, batt_reserve - (raw_metrics.degradation_impact_pct * 100.0)), 2)

        standardized_metrics = {
            "peak_demand_kw": peak_demand,
            "cost": raw_metrics.cost,
            "battery_reserve_pct": batt_reserve,
            "renewable_utilization_pct": raw_metrics.renewable_utilization_pct,
            "discharged_kw": discharged,
            "shifted_kw": raw_metrics.shifted_kw,
            "degradation_impact_pct": raw_metrics.degradation_impact_pct,
            "energy_waste": energy_waste,
            "risk": risk_penalty,
            "reliability": reliability_margin,
            "battery_health": battery_health,
            "is_feasible": raw_metrics.is_feasible,
            "constraint_notes": raw_metrics.constraint_notes,
        }

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        outcome = SimulatedOutcome(
            candidate_id=cand_id,
            projected_state=sim_state.to_dict(),
            metrics=standardized_metrics,
            branch_id=branch_id,
        )

        audit_rec = SimulationRunRecord(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            branch_id=branch_id,
            candidate_id=cand_id,
            timestamp=now_ts,
            decision_horizon_minutes=horizon_minutes,
            baseline_state_snapshot=baseline_state.to_dict(),
            predicted_state_snapshot=predicted_state.to_dict() if predicted_state else None,
            action_applied=cand_id,
            projected_state=sim_state.to_dict(),
            metrics=standardized_metrics,
            latency_ms=latency_ms,
        )

        return outcome, audit_rec

    # -------------------------------------------------------------------------
    # STEP 5: Result Packaging & Orchestration
    # -------------------------------------------------------------------------
    def run_candidate(
        self,
        baseline_state: Union[Dict[str, Any], SystemState],
        action: Union[str, CandidateAction],
        predicted_state: Optional[Union[Dict[str, Any], SystemState]] = None,
        horizon_minutes: int = 30,
    ) -> SimulatedOutcome:
        """Run simulation for a single candidate action."""
        action_id = action.id if hasattr(action, "id") else str(action)
        norm_baseline = normalize_system_state(baseline_state)
        norm_pred = normalize_system_state(predicted_state) if predicted_state else None

        branch_id = self._create_branch(0, action_id)
        outcome, audit_rec = self._execute_branch(
            branch_id=branch_id,
            cand_id=action_id,
            baseline_state=norm_baseline,
            predicted_state=norm_pred,
            horizon_minutes=horizon_minutes,
        )
        self._audit_log.append(audit_rec)
        return outcome

    def simulate_all(
        self,
        baseline_state: Union[Dict[str, Any], SystemState],
        candidates: List[Union[str, CandidateAction, Dict[str, Any]]],
        predicted_state: Optional[Union[Dict[str, Any], SystemState]] = None,
        horizon_minutes: int = 30,
        parallel: bool = False,
    ) -> List[SimulatedOutcome]:
        """
        Executes parallel branching for each candidate action (Section 5 & 8).
        Ensures baseline isolation and returns standardized comparable outcomes.
        """
        pkg = self.simulate_package(
            baseline_state=baseline_state,
            candidates=candidates,
            predicted_state=predicted_state,
            horizon_minutes=horizon_minutes,
            parallel=parallel,
        )
        return pkg.outcomes

    def simulate_package(
        self,
        baseline_state: Union[Dict[str, Any], SystemState],
        candidates: List[Union[str, CandidateAction, Dict[str, Any]]],
        predicted_state: Optional[Union[Dict[str, Any], SystemState]] = None,
        horizon_minutes: int = 30,
        parallel: bool = False,
    ) -> SimulationPackage:
        """
        Executes the full 5-step simulation process and packages results
        with full audit records ready for optimization handoff.
        """
        t_start = time.perf_counter()
        norm_baseline = normalize_system_state(baseline_state)
        norm_pred = normalize_system_state(predicted_state) if predicted_state else None

        # Principle 1: One simulation per candidate, no shortcuts
        extracted_cands = []
        for idx, cand in enumerate(candidates):
            cid = cand.get("id") if isinstance(cand, dict) else getattr(cand, "id", str(cand))
            extracted_cands.append((idx, cid))

        outcomes: List[SimulatedOutcome] = []
        audit_records: List[SimulationRunRecord] = []

        # Principle 3: Parallelizable by design
        if parallel and len(extracted_cands) > 1:
            with ThreadPoolExecutor(max_workers=min(len(extracted_cands), self.max_workers)) as executor:
                futures = [
                    executor.submit(
                        self._execute_branch,
                        self._create_branch(idx, cid),
                        cid,
                        norm_baseline,
                        norm_pred,
                        horizon_minutes,
                    )
                    for idx, cid in extracted_cands
                ]
                for future in futures:
                    outcome, audit_rec = future.result()
                    outcomes.append(outcome)
                    audit_records.append(audit_rec)
        else:
            for idx, cid in extracted_cands:
                branch_id = self._create_branch(idx, cid)
                outcome, audit_rec = self._execute_branch(
                    branch_id=branch_id,
                    cand_id=cid,
                    baseline_state=norm_baseline,
                    predicted_state=norm_pred,
                    horizon_minutes=horizon_minutes,
                )
                outcomes.append(outcome)
                audit_records.append(audit_rec)

        total_ms = round((time.perf_counter() - t_start) * 1000.0, 2)
        self._audit_log.extend(audit_records)

        # Step 5: Result Packaging
        return SimulationPackage(
            outcomes=outcomes,
            decision_horizon_minutes=horizon_minutes,
            baseline_state=norm_baseline.to_dict(),
            audit_records=audit_records,
            total_execution_ms=total_ms,
        )


def simulate_candidates(
    baseline_state: Union[Dict[str, Any], SystemState],
    candidates: List[Union[str, CandidateAction, Dict[str, Any]]],
    predicted_state: Optional[Union[Dict[str, Any], SystemState]] = None,
    horizon_minutes: int = 30,
    parallel: bool = False,
) -> List[SimulatedOutcome]:
    """Helper function to run simulation on candidates."""
    engine = SimulationEngine()
    return engine.simulate_all(
        baseline_state,
        candidates,
        predicted_state=predicted_state,
        horizon_minutes=horizon_minutes,
        parallel=parallel,
    )
