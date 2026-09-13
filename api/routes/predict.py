"""
VOLTERRA - API Route: /v1/predict
=================================
Implements Step 2: Forecasts future demand and supply and classifies operational risk.
"""

from fastapi import APIRouter
from api.schemas import PredictRequest, PredictResponse, SystemState, RiskClassification
from engine.predict import PredictionEngine
from engine.observe import normalize_system_state

router = APIRouter()
engine = PredictionEngine()


@router.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    """
    POST /v1/predict
    Forecast near-future demand and supply; output risk classification.
    """
    state = normalize_system_state(req.system_state)
    d_history = req.demand_history_kw or [state.demand_kw]
    s_history = req.supply_history_kw or [state.solar_generation_kw]

    forecast = engine.predict(
        demand_history_kw=d_history,
        supply_history_kw=s_history,
        current_timestamp=state.timestamp,
        horizon_minutes=req.horizon_minutes or 30,
    )

    forecasted_state = SystemState(
        timestamp=forecast.target_timestamp.isoformat() if forecast.target_timestamp else state.timestamp.isoformat(),
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
