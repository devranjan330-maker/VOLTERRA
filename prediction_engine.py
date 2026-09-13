"""
VOLTERRA - AI/ML Prediction Engine
===================================
Implements the forecasting + risk
classification logic described in
VOLTERRA_AI_ML.md and
VOLTERRA_Prediction.md.

This module is intentionally self-contained
(no external ML dependencies
beyond the Python standard library) so it
can run in a hackathon
environment without extra setup. It can be
swapped later for a more
sophisticated model (regression / gradient-boosted
trees / LSTM) behind
the same interface, per the "model-agnostic
interface" design principle.

Core responsibilities:
    1. Forecast future values of key system
variables (demand, supply).
    2. Classify risk (normal / at_risk /
critical) based on the forecast.
    3. Provide evaluation metrics (MAE,
RMSE) for validating forecast
       accuracy against historical/held-out
data.

Usage:
    python prediction_engine.py
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional
import math

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class SystemState:
    """A structured snapshot of the system at a point in time."""
    timestamp: datetime
    demand_kw: float
    solar_generation_kw: float
    battery_level_pct: float
    temperature_c: float
    occupancy: str = "medium"

    def available_supply_kw(self) -> float:
        """Simple supply model: solar generation is the primary supply source."""
        return self.solar_generation_kw


class RiskLevel(str, Enum):
    NORMAL = "normal"
    AT_RISK = "at_risk"
    CRITICAL = "critical"


@dataclass
class Forecast:
    """Output of the Prediction Engine for a single horizon."""
    based_on_timestamp: datetime
    horizon_minutes: int
    forecasted_demand_kw: float
    forecasted_supply_kw: float
    risk_classification: RiskLevel
    notes: str


# ---------------------------------------------------------------------------
# Risk Classification Thresholds
# ---------------------------------------------------------------------------

# Margin (as a fraction of supply) below which we consider the system
# "at_risk" even though demand hasn't yet exceeded supply.
AT_RISK_MARGIN_PCT = 0.10  # e.g., demand within 10% of supply


def classify_risk(forecasted_demand_kw: float, forecasted_supply_kw: float) -> RiskLevel:
    """
    Classify risk by comparing forecasted demand against forecasted supply.
    - CRITICAL: forecasted demand meets or exceeds forecasted supply.
    - AT_RISK:  forecasted demand is within AT_RISK_MARGIN_PCT of supply.
    - NORMAL:   forecasted demand is comfortably below supply.
    """
    if forecasted_supply_kw <= 0:
        # No supply available at all -> treat any demand as critical.
        return RiskLevel.CRITICAL if forecasted_demand_kw > 0 else RiskLevel.NORMAL

    margin = (forecasted_supply_kw - forecasted_demand_kw) / forecasted_supply_kw

    if forecasted_demand_kw >= forecasted_supply_kw:
        return RiskLevel.CRITICAL
    elif margin <= AT_RISK_MARGIN_PCT:
        return RiskLevel.AT_RISK
    else:
        return RiskLevel.NORMAL


# ---------------------------------------------------------------------------
# Forecasting Models
# ---------------------------------------------------------------------------

class ExponentialSmoothingForecaster:
    """
    Simple exponential smoothing forecaster.

    Recommended as the MVP baseline (see VOLTERRA_AI_ML.md, Section 3.2):
    fast, interpretable, requires no training beyond recent history.

    Forecast is computed as:
        smoothed_level + trend * horizon_steps
    where `trend` is estimated from the recent rate of change in the
    historical series.
    """

    def __init__(self, alpha: float = 0.5, step_minutes: int = 5):
        """
        Args:
            alpha: smoothing factor (0 < alpha <= 1). Higher = more weight
                   on recent observations.
            step_minutes: the time interval, in minutes, between
                          consecutive historical observations.
        """
        if not (0 < alpha <= 1):
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = alpha
        self.step_minutes = step_minutes

    def _smooth(self, series: List[float]) -> float:
        """Return the exponentially smoothed level of a series."""
        if not series:
            raise ValueError("series must not be empty")
        level = series[0]
        for value in series[1:]:
            level = self.alpha * value + (1 - self.alpha) * level
        return level

    def _estimate_trend(self, series: List[float]) -> float:
        """Estimate a simple per-step trend from the last few observations."""
        if len(series) < 2:
            return 0.0
        # Average of recent step-to-step deltas (last up to 5 steps).
        recent = series[-6:]
        deltas = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
        return sum(deltas) / len(deltas)

    def forecast_series(self, series: List[float], horizon_minutes: int) -> float:
        """Forecast a single value `horizon_minutes` ahead of the last observation."""
        level = self._smooth(series)
        trend = self._estimate_trend(series)
        steps_ahead = max(1, round(horizon_minutes / self.step_minutes))
        return level + trend * steps_ahead


class PredictionEngine:
    """
    The Prediction Engine: forecasts near-future system state and
    classifies risk, per VOLTERRA_Prediction.md.
    """

    def __init__(self, forecaster: Optional[ExponentialSmoothingForecaster] = None):
        self.forecaster = forecaster or ExponentialSmoothingForecaster()

    def predict(
        self,
        demand_history_kw: List[float],
        supply_history_kw: List[float],
        current_timestamp: datetime,
        horizon_minutes: int = 30,
    ) -> Forecast:
        """
        Forecast demand and supply at `horizon_minutes` ahead, and classify risk.

        Args:
            demand_history_kw: recent historical demand values, oldest first.
            supply_history_kw: recent historical supply values, oldest first.
            current_timestamp: timestamp of the most recent observation.
            horizon_minutes: how far ahead to forecast.
        """
        forecasted_demand = self.forecaster.forecast_series(demand_history_kw, horizon_minutes)
        forecasted_supply = self.forecaster.forecast_series(supply_history_kw, horizon_minutes)

        risk = classify_risk(forecasted_demand, forecasted_supply)

        if risk == RiskLevel.CRITICAL:
            notes = (
                f"Predicted demand ({forecasted_demand:.1f} kW) meets or exceeds "
                f"predicted supply ({forecasted_supply:.1f} kW)."
            )
        elif risk == RiskLevel.AT_RISK:
            notes = (
                f"Predicted demand ({forecasted_demand:.1f} kW) is approaching "
                f"predicted supply ({forecasted_supply:.1f} kW)."
            )
        else:
            notes = (
                f"Predicted demand ({forecasted_demand:.1f} kW) is comfortably "
                f"within predicted supply ({forecasted_supply:.1f} kW)."
            )

        return Forecast(
            based_on_timestamp=current_timestamp,
            horizon_minutes=horizon_minutes,
            forecasted_demand_kw=round(forecasted_demand, 2),
            forecasted_supply_kw=round(forecasted_supply, 2),
            risk_classification=risk,
            notes=notes,
        )


# ---------------------------------------------------------------------------
# Evaluation Metrics (for validating forecast accuracy)
# ---------------------------------------------------------------------------

def mean_absolute_error(actual: List[float], predicted: List[float]) -> float:
    if len(actual) != len(predicted) or not actual:
        raise ValueError("actual and predicted must be non-empty and equal length")
    return sum(abs(a - p) for a, p in zip(actual, predicted)) / len(actual)


def root_mean_squared_error(actual: List[float], predicted: List[float]) -> float:
    if len(actual) != len(predicted) or not actual:
        raise ValueError("actual and predicted must be non-empty and equal length")
    return math.sqrt(sum((a - p) ** 2 for a, p in zip(actual, predicted)) / len(actual))


# ---------------------------------------------------------------------------
# Example / Manual Test Run
# ---------------------------------------------------------------------------

def _demo():
    """
    Runs the primary demo scenario from VOLTERRA_DEMO.md:
    rising demand approaching supply limit.
    """
    now = datetime(2026, 9, 12, 14, 0, 0)

    # Simulated recent history (5-minute intervals), demand trending upward.
    demand_history = [6.0, 6.3, 6.6, 6.9, 7.2]
    supply_history = [8.3, 8.2, 8.2, 8.1, 8.1]

    engine = PredictionEngine()
    forecast = engine.predict(
        demand_history_kw=demand_history,
        supply_history_kw=supply_history,
        current_timestamp=now,
        horizon_minutes=30,
    )

    print("=== VOLTERRA Prediction Engine - Demo ===")
    print(f"Based on:           {forecast.based_on_timestamp}")
    print(f"Horizon:            {forecast.horizon_minutes} minutes")
    print(f"Forecasted demand:  {forecast.forecasted_demand_kw} kW")
    print(f"Forecasted supply:  {forecast.forecasted_supply_kw} kW")
    print(f"Risk classification: {forecast.risk_classification.value}")
    print(f"Notes:              {forecast.notes}")

    # --- Evaluation metrics example ---
    print("\n=== Forecast Accuracy Evaluation (example) ===")
    actual = [9.1, 9.3, 9.0, 9.4, 9.2]
    predicted = [9.0, 9.2, 9.1, 9.3, 9.3]
    print(f"MAE:  {mean_absolute_error(actual, predicted):.3f}")
    print(f"RMSE: {root_mean_squared_error(actual, predicted):.3f}")


if __name__ == "__main__":
    _demo()
