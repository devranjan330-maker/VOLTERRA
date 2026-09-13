from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Optional
from prediction_engine import PredictionEngine, ExponentialSmoothingForecaster, RiskLevel, classify_risk as core_classify_risk
from app.models import SystemState, RiskClassification, PredictResponse

engine = PredictionEngine(ExponentialSmoothingForecaster(alpha=0.5, step_minutes=5))

def predict_future(
    state: SystemState,
    horizon_minutes: int = 30,
    demand_history: Optional[List[float]] = None,
    supply_history: Optional[List[float]] = None,
) -> PredictResponse:
    """
    Produce forecast and risk classification using VOLTERRA Prediction Engine.
    """
    # Parse timestamp or default to now
    try:
        ts = datetime.fromisoformat(state.timestamp.replace("Z", "+00:00"))
    except Exception:
        ts = datetime.now(timezone.utc)

    # Build or use historical series
    if not demand_history or len(demand_history) < 2:
        # Generate representative 5-step history trending toward current state
        step = state.demand_kw * 0.05
        demand_history = [
            round(state.demand_kw - (4 - i) * step, 2)
            for i in range(5)
        ]
    if not supply_history or len(supply_history) < 2:
        step = state.solar_generation_kw * 0.02
        supply_history = [
            round(state.solar_generation_kw - (4 - i) * step, 2)
            for i in range(5)
        ]

    forecast = engine.predict(
        demand_history_kw=demand_history,
        supply_history_kw=supply_history,
        current_timestamp=ts,
        horizon_minutes=horizon_minutes,
    )

    future_ts = ts + timedelta(minutes=horizon_minutes)

    forecasted_state = SystemState(
        timestamp=future_ts.isoformat(),
        demand_kw=forecast.forecasted_demand_kw,
        solar_generation_kw=forecast.forecasted_supply_kw,
        battery_level_pct=state.battery_level_pct,
        temperature_c=state.temperature_c,
        occupancy=state.occupancy,
    )

    return PredictResponse(
        forecasted_state=forecasted_state,
        risk_classification=RiskClassification(forecast.risk_classification.value),
        notes=forecast.notes,
    )
