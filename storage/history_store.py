"""
VOLTERRA - Storage Layer: History Store
=======================================
Persists decision cycles for auditability, post-intervention measurement,
and continuous learning as specified in Step 8 and Section 3/4 of the
Implementation Document, backed by the normalized 9-table relational
architecture defined in the Database Design Document (Version 1.0, September 2026).

Supports both in-memory store and SQLite database persistence.
"""

from pathlib import Path
from threading import Lock
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from storage.database import DatabaseManager


class HistoryStore:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self.db = DatabaseManager(db_path=db_path)
        self._seed_if_empty()

    def _seed_if_empty(self):
        """Seed the relational database with canonical initial audit trail if empty."""
        existing = self.db.query_history_summary(limit=1)
        if len(existing) == 0:
            self._seed_initial_data()

    def _seed_initial_data(self):
        seed_observed = {
            "timestamp": "2026-09-09T14:30:00Z",
            "demand_kw": 7.2,
            "solar_generation_kw": 5.1,
            "battery_level_pct": 62.0,
            "temperature_c": 29.5,
            "occupancy": "medium",
        }
        seed_forecast = {
            "timestamp": "2026-09-09T15:00:00Z",
            "horizon_minutes": 30,
            "forecasted_demand_kw": 9.4,
            "forecasted_supply_kw": 5.0,
            "risk_classification": "critical",
            "notes": "Predicted demand (9.4 kW) exceeds renewable supply threshold.",
        }
        candidates = [
            {"id": "A", "label": "Do nothing", "description": "Maintain baseline operations"},
            {"id": "B", "label": "Use battery", "description": "Dispatch battery storage"},
            {"id": "C", "label": "Shift load", "description": "Curtail deferrable HVAC load"},
            {"id": "D", "label": "Hybrid response", "description": "Coordinate battery discharge and HVAC load shifting"},
        ]
        sim_outcomes = [
            {
                "candidate_id": "A",
                "peak_demand_kw": 9.4,
                "cost": 2.82,
                "battery_reserve_pct": 62.0,
                "renewable_utilization_pct": 53.2,
                "projected_state": {"demand_kw": 9.4, "battery_level_pct": 62.0},
            },
            {
                "candidate_id": "B",
                "peak_demand_kw": 8.1,
                "cost": 2.43,
                "battery_reserve_pct": 48.0,
                "renewable_utilization_pct": 61.7,
                "projected_state": {"demand_kw": 8.1, "battery_level_pct": 48.0},
            },
            {
                "candidate_id": "C",
                "peak_demand_kw": 8.6,
                "cost": 2.58,
                "battery_reserve_pct": 62.0,
                "renewable_utilization_pct": 58.1,
                "projected_state": {"demand_kw": 8.6, "battery_level_pct": 62.0},
            },
            {
                "candidate_id": "D",
                "peak_demand_kw": 7.9,
                "cost": 2.37,
                "battery_reserve_pct": 51.0,
                "renewable_utilization_pct": 63.3,
                "projected_state": {"demand_kw": 7.9, "battery_level_pct": 51.0},
            },
        ]
        optimization_result = {
            "selected_candidate_id": "D",
            "objectives": {"peak_demand_weight": 0.4, "cost_weight": 0.3, "battery_weight": 0.2, "renewable_weight": 0.1},
            "constraints": {"min_battery_reserve_pct": 30.0},
            "scores": {
                "A": {"total_score": -12.4, "feasible": True},
                "B": {"total_score": -3.2, "feasible": True},
                "C": {"total_score": -4.8, "feasible": True},
                "D": {"total_score": 2.1, "feasible": True},
            },
        }
        rationale = (
            "Strategy D (Hybrid response) is preferred because it reduces the predicted peak "
            "to 7.9 kW while maintaining the required battery reserve at 51.0%."
        )
        execution = {
            "mode": "virtual",
            "status": "executed",
            "resulting_state": {
                "timestamp": "2026-09-09T14:31:00Z",
                "demand_kw": 7.9,
                "battery_level_pct": 51.0,
                "temperature_c": 29.5,
                "occupancy": "medium",
            },
        }
        measurement = {
            "before_peak_kw": 9.4,
            "after_peak_kw": 7.9,
            "improvement_pct": 15.96,
        }

        # Record seed to matching 9-table schema
        self.db.record_full_cycle(
            observed_state=seed_observed,
            forecast_result=seed_forecast,
            candidates=candidates,
            sim_outcomes=sim_outcomes,
            optimization_result=optimization_result,
            rationale=rationale,
            execution=execution,
            measurement=measurement,
            cycle_status="completed",
        )

    def record_full_cycle(
        self,
        observed_state: Dict[str, Any],
        forecast_result: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        sim_outcomes: List[Dict[str, Any]],
        optimization_result: Dict[str, Any],
        rationale: str,
        execution: Optional[Dict[str, Any]] = None,
        measurement: Optional[Dict[str, Any]] = None,
        cycle_status: str = "completed",
    ) -> int:
        """Atomically records a complete cycle into the 9 normalized tables."""
        return self.db.record_full_cycle(
            observed_state=observed_state,
            forecast_result=forecast_result,
            candidates=candidates,
            sim_outcomes=sim_outcomes,
            optimization_result=optimization_result,
            rationale=rationale,
            execution=execution,
            measurement=measurement,
            cycle_status=cycle_status,
        )

    def add(self, record: Dict[str, Any]) -> int:
        """
        Append a completed decision cycle, gracefully converting legacy dicts
        into normalized relational records.
        """
        # Check if record has full relational components
        if "candidates" in record and "sim_outcomes" in record:
            return self.db.record_full_cycle(
                observed_state=record.get("system_state", {}),
                forecast_result=record.get("forecast", {
                    "risk_classification": record.get("risk_classification", "normal"),
                    "notes": "Decide pipeline evaluation",
                }),
                candidates=record.get("candidates", []),
                sim_outcomes=record.get("sim_outcomes", []),
                optimization_result=record.get("optimization_result", record.get("decision", {})),
                rationale=record.get("decision", {}).get("rationale", ""),
                execution=record.get("execution"),
                measurement=record.get("measurement"),
            )

        # Legacy dict fallback: convert into relational entries
        sys_state = record.get("system_state", {})
        ts = record.get("timestamp") or sys_state.get("timestamp") or datetime.now(timezone.utc).isoformat()
        sys_state["timestamp"] = ts

        decision = record.get("decision", {})
        selected_id = decision.get("selected_candidate_id", "A")
        rationale = decision.get("rationale", "Automated system decision")
        scores = decision.get("scores", {selected_id: {"total_score": 0.0, "feasible": True}})

        outcome = record.get("outcome") or {}
        before_kw = outcome.get("before_peak_kw", sys_state.get("demand_kw", 0.0))
        after_kw = outcome.get("after_peak_kw", before_kw)
        imp_pct = outcome.get("improvement_pct", 0.0)

        candidates = [
            {"id": "A", "label": "Candidate A", "description": "Candidate option A"},
            {"id": selected_id, "label": f"Candidate {selected_id}", "description": f"Strategy {selected_id}"},
        ]
        if selected_id == "A":
            candidates = [{"id": "A", "label": "Candidate A", "description": "Baseline action"}]

        sim_outcomes = [
            {
                "candidate_id": selected_id,
                "peak_demand_kw": after_kw,
                "cost": round(after_kw * 0.3, 2),
                "battery_reserve_pct": sys_state.get("battery_level_pct", 50.0),
                "renewable_utilization_pct": 50.0,
                "projected_state": sys_state,
            }
        ]

        exec_data = None
        meas_data = None
        if outcome:
            exec_data = {
                "mode": outcome.get("mode", "virtual"),
                "status": outcome.get("status", "executed"),
                "resulting_state": sys_state,
            }
            meas_data = {
                "before_peak_kw": before_kw,
                "after_peak_kw": after_kw,
                "improvement_pct": imp_pct,
            }

        return self.db.record_full_cycle(
            observed_state=sys_state,
            forecast_result={
                "timestamp": ts,
                "horizon_minutes": 30,
                "forecasted_demand_kw": sys_state.get("demand_kw", 0.0),
                "forecasted_supply_kw": sys_state.get("solar_generation_kw", 0.0),
                "risk_classification": record.get("risk_classification", "normal"),
                "notes": "Decision cycle recorded",
            },
            candidates=candidates,
            sim_outcomes=sim_outcomes,
            optimization_result={
                "selected_candidate_id": selected_id,
                "scores": scores,
            },
            rationale=rationale,
            execution=exec_data,
            measurement=meas_data,
        )

    def get_latest(self) -> Optional[Dict[str, Any]]:
        """Retrieve latest cycle in summary format."""
        cycles = self.db.query_history_summary(limit=1)
        return cycles[-1] if cycles else None

    def update_latest_outcome(self, outcome_data: Dict[str, Any]):
        """Update outcome of the most recent cycle after execution/measurement."""
        exec_data = None
        if "mode" in outcome_data or "resulting_state" in outcome_data or outcome_data.get("status") == "executed":
            exec_data = {
                "mode": outcome_data.get("mode", "virtual"),
                "status": outcome_data.get("status", "executed"),
                "resulting_state": outcome_data.get("resulting_state", {}),
            }

        meas_data = None
        if "improvement_pct" in outcome_data or "before_peak_kw" in outcome_data:
            meas_data = {
                "before_peak_kw": outcome_data.get("before_peak_kw", 0.0),
                "after_peak_kw": outcome_data.get("after_peak_kw", 0.0),
                "improvement_pct": outcome_data.get("improvement_pct", 0.0),
            }

        self.db.update_latest_execution_and_measurement(
            cycle_id=None,
            execution_data=exec_data,
            measurement_data=meas_data,
        )

    def query(
        self,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        limit: Optional[int] = 50,
    ) -> List[Dict[str, Any]]:
        """Query past decision cycles filtered by time range and limit."""
        return self.db.query_history_summary(from_time=from_time, to_time=to_time, limit=limit)

    def get_full_audit(self, cycle_id: int) -> Optional[Dict[str, Any]]:
        """Section 6 Pattern 1: Full audit join across 9 tables."""
        return self.db.get_full_audit(cycle_id)

    def get_forecast_accuracy(self) -> Dict[str, Any]:
        """Section 6 Pattern 2: Forecast accuracy tracking."""
        return self.db.get_forecast_accuracy()

    def get_historical_improvement_trend(self) -> Dict[str, Any]:
        """Section 6 Pattern 3: Historical improvement trend."""
        return self.db.get_historical_improvement_trend()

    def get_candidate_strategy_performance(self) -> Dict[str, Any]:
        """Section 6 Pattern 4: Candidate strategy performance."""
        return self.db.get_candidate_strategy_performance()


# Global canonical singleton instance
history_store = HistoryStore()
