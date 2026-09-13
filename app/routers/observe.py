from fastapi import APIRouter
from app.models import SystemState, StateResponse
from ingestion_layer import IngestionLayer

router = APIRouter()
ingestor = IngestionLayer()


@router.post("/state", response_model=StateResponse)
async def observe_state(state: SystemState):
    """
    POST /v1/state
    Accept raw or structured sensor/metering input data and normalize into SystemState.
    Uses IngestionLayer to validate and sanitize telemetry feeds.
    """
    obs = ingestor.ingest_streaming(state.model_dump())
    ts_str = (
        obs.state.timestamp.isoformat()
        if hasattr(obs.state.timestamp, "isoformat")
        else str(obs.state.timestamp)
    )

    normalized_state = SystemState(
        timestamp=ts_str,
        demand_kw=obs.state.demand_kw,
        solar_generation_kw=obs.state.solar_generation_kw,
        battery_level_pct=obs.state.battery_level_pct,
        temperature_c=obs.state.temperature_c,
        occupancy=obs.state.occupancy,
    )
    return StateResponse(system_state=normalized_state)
