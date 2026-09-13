"""
VOLTERRA - API Route: /v1/state
===============================
Implements Step 1: Ingests raw input telemetry and returns normalized SystemState.
"""

from fastapi import APIRouter
from api.schemas import SystemState, StateResponse
from engine.observe import normalize_system_state

router = APIRouter()


@router.post("/state", response_model=StateResponse)
async def observe_state(state: SystemState):
    """
    POST /v1/state
    Accept raw or structured sensor/metering input data and normalize into SystemState.
    """
    normalized = normalize_system_state(state)
    return StateResponse(
        system_state=SystemState(
            timestamp=normalized.timestamp.isoformat() if hasattr(normalized.timestamp, "isoformat") else str(normalized.timestamp),
            demand_kw=normalized.demand_kw,
            solar_generation_kw=normalized.solar_generation_kw,
            battery_level_pct=normalized.battery_level_pct,
            temperature_c=normalized.temperature_c,
            occupancy=normalized.occupancy,
        )
    )
