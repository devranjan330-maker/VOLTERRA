"""
VOLTERRA - API Route: /v1/execute
=================================
Implements Step 7: Virtual (or physical) actuation.
Section 4.7 & Design Principle 2: Stateless request, stateful history.
"""

from fastapi import APIRouter
from api.schemas import ExecuteRequest, ExecuteResponse, SystemState
from engine.execute import execute_action
from storage.history_store import history_store

router = APIRouter()


@router.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest):
    """
    POST /v1/execute
    Apply selected action virtually (or dispatch physically).
    Updates internal cycle execution state for full auditability.
    """
    res = execute_action(
        action_id=req.selected_candidate_id,
        mode=req.mode or "virtual",
    )
    s = res.resulting_state
    resulting_sys_state = SystemState(
        timestamp=s.timestamp.isoformat() if hasattr(s.timestamp, "isoformat") else str(s.timestamp),
        demand_kw=s.demand_kw,
        solar_generation_kw=s.solar_generation_kw,
        battery_level_pct=s.battery_level_pct,
        temperature_c=s.temperature_c,
        occupancy=s.occupancy,
    )

    # Persist execution state to the relational history store
    history_store.update_latest_outcome({
        "status": res.status,
        "mode": res.mode,
        "resulting_state": resulting_sys_state.model_dump(),
    })

    return ExecuteResponse(
        status=res.status,
        mode=res.mode,
        resulting_state=resulting_sys_state,
    )
