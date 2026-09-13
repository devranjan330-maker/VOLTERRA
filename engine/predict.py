"""
VOLTERRA - Engine: Prediction Engine
====================================
Implements Step 2 of the Implementation Document:
Projects key variables (demand, solar/supply) forward across a configurable horizon
and classifies operational risk into normal, at_risk, or critical.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Optional, Tuple, Union

from engine.observe import SystemState


class RiskLevel(str, Enum):
    NORMAL = "normal"
    AT_RISK = "at_risk"
    CRITICAL = "critical"


RiskClassification = RiskLevel


@dataclass
class Forecast:
    """Projected future demand and supply over a specified horizon."""
    horizon_minutes: int
    forecasted_demand_kw: float
    forecasted_supply_kw: float
    risk_classification: RiskLevel
    notes: str
    target_timestamp: Optional[datetime] = None


def classify_risk(forecasted_demand_kw: float, forecasted_supply_kw: float) -> RiskLevel:
    """
    Evaluates system risk based on projected demand vs supply:
    - critical: demand meets or exceeds supply (or supply is 0 and demand > 0)
    - at_risk: demand is within 10% safety margin of supply
    - normal: demand is comfortably below supply
    """
    if forecasted_supply_kw <= 0.0:
        return RiskLevel.CRITICAL if forecasted_demand_kw > 0.0 else RiskLevel.NORMAL

    if forecasted_demand_kw >= forecasted_supply_kw:
        return RiskLevel.CRITICAL

    # Within 10% safety margin of supply
    margin = 0.10 * forecasted_supply_kw
    if forecasted_demand_kw >= (forecasted_supply_kw - margin):
        return RiskLevel.AT_RISK

    return RiskLevel.NORMAL


class ExponentialSmoothingForecaster:
    """Single exponential smoothing with linear trend adjustment."""
    def __init__(self, alpha: float = 0.5, step_minutes: int = 5):
        if not (0 < alpha <= 1):
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = alpha
        self.step_minutes = step_minutes

    def _smooth(self, series: List[float]) -> float:
        if not series:
            raise ValueError("series must not be empty")
        level = series[0]
        for value in series[1:]:
            level = self.alpha * value + (1.0 - self.alpha) * level
        return level

    def _estimate_trend(self, series: List[float]) -> float:
        if len(series) < 2:
            return 0.0
        recent = series[-6:]
        deltas = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
        return sum(deltas) / len(deltas)

    def forecast_series(self, series: List[float], horizon_minutes: int = 30) -> float:
        if not series:
            return 0.0
        if len(series) == 1:
            return series[0]
        level = self._smooth(series)
        trend = self._estimate_trend(series)
        steps_ahead = max(1, round(horizon_minutes / self.step_minutes))
        return max(0.0, float(level + trend * steps_ahead))


class PredictionEngine:
    """Predictive forecasting and risk classification engine."""
    def __init__(self, forecaster: Optional[ExponentialSmoothingForecaster] = None):
        self.forecaster = forecaster or ExponentialSmoothingForecaster()

    def predict(
        self,
        demand_history_kw: List[float],
        supply_history_kw: List[float],
        current_timestamp: Optional[datetime] = None,
        horizon_minutes: int = 30,
    ) -> Forecast:
        now = current_timestamp or datetime.now(timezone.utc)
        target_ts = now + timedelta(minutes=horizon_minutes)

        f_demand = self.forecaster.forecast_series(demand_history_kw, horizon_minutes=horizon_minutes)
        f_supply = self.forecaster.forecast_series(supply_history_kw, horizon_minutes=horizon_minutes)

        f_demand = round(f_demand, 2)
        f_supply = round(f_supply, 2)

        risk = classify_risk(f_demand, f_supply)

        if risk == RiskLevel.CRITICAL:
            notes = (
                f"Predicted demand ({f_demand} kW) meets or exceeds predicted supply ({f_supply} kW). "
                f"Immediate intervention recommended."
            )
        elif risk == RiskLevel.AT_RISK:
            notes = (
                f"Predicted demand ({f_demand} kW) is within 10% safety margin of supply ({f_supply} kW). "
                f"Preventative action advised."
            )
        else:
            notes = (
                f"Predicted demand ({f_demand} kW) is comfortably within supply capacity ({f_supply} kW). "
                f"System operating within normal parameters."
            )

        return Forecast(
            horizon_minutes=horizon_minutes,
            forecasted_demand_kw=f_demand,
            forecasted_supply_kw=f_supply,
            risk_classification=risk,
            notes=notes,
            target_timestamp=target_ts,
        )


def mean_absolute_error(actual: List[float], predicted: List[float]) -> float:
    if not actual or len(actual) != len(predicted):
        return 0.0
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)


def root_mean_squared_error(actual: List[float], predicted: List[float]) -> float:
    if not actual or len(actual) != len(predicted):
        return 0.0
    return math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(actual))
