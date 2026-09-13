"""
VOLTERRA - Engine: Measurement & Verification Layer
===================================================
Implements Step 8 of the Implementation Document:
Compares pre-intervention (before) and post-intervention (after) system states,
calculates quantified improvement metrics (peak reduction kW, improvement percentage),
and logs the full decision cycle to the history store.
"""

from dataclasses import dataclass
from typing import Dict, Any, Union, Optional
from datetime import datetime, timezone

from engine.observe import SystemState, normalize_system_state
from storage.history_store import history_store


@dataclass
class MeasurementResult:
    before_peak_kw: float
    after_peak_kw: float
    delta_demand_kw: float
    improvement_pct: float
    delta_battery_pct: float
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "before_peak_kw": self.before_peak_kw,
            "after_peak_kw": self.after_peak_kw,
            "delta_demand_kw": self.delta_demand_kw,
            "improvement_pct": self.improvement_pct,
            "delta_battery_pct": self.delta_battery_pct,
            "summary": self.summary,
        }


class MeasurementEngine:
    """Calculates before/after outcome metrics and logs completed cycles."""

    def measure(
        self,
        before_state: Union[Dict[str, Any], SystemState],
        after_state: Union[Dict[str, Any], SystemState],
    ) -> MeasurementResult:
        b = normalize_system_state(before_state)
        a = normalize_system_state(after_state)

        before_peak = b.demand_kw
        after_peak = a.demand_kw
        delta_kw = round(after_peak - before_peak, 2)
        delta_battery = round(a.battery_level_pct - b.battery_level_pct, 2)

        if before_peak > 0.0:
            improvement_pct = round(((before_peak - after_peak) / before_peak) * 100.0, 2)
        else:
            improvement_pct = 0.0

        summary = (
            f"Peak demand reduced from {before_peak} kW to {after_peak} kW "
            f"({improvement_pct}% improvement). Battery delta: {delta_battery}%."
        )

        result = MeasurementResult(
            before_peak_kw=before_peak,
            after_peak_kw=after_peak,
            delta_demand_kw=delta_kw,
            improvement_pct=improvement_pct,
            delta_battery_pct=delta_battery,
            summary=summary,
        )

        # Update latest record in history store with verified outcome
        history_store.update_latest_outcome({
            "status": "executed",
            "before_peak_kw": before_peak,
            "after_peak_kw": after_peak,
            "improvement_pct": improvement_pct,
            "delta_battery_pct": delta_battery,
        })

        return result


def measure_improvement(
    before_state: Union[Dict[str, Any], SystemState],
    after_state: Union[Dict[str, Any], SystemState],
) -> MeasurementResult:
    measurer = MeasurementEngine()
    return measurer.measure(before_state, after_state)
