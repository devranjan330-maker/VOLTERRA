from datetime import datetime, timezone
from fastapi import APIRouter
from app.models import ExecuteRequest, ExecuteResponse, SystemState
from app.utils.history_store import history_store

router = APIRouter()


@router.post("/execute", response_model=ExecuteResponse)
async def execute_endpoint(req: ExecuteRequest):
    """
    POST /v1/execute
    Apply the selected decision — virtually (MVP) or via physical IoT integration.
    """
    # Retrieve projected state from the latest cycle if available
    latest = history_store.get_latest()
    resulting_state = None

    if latest and "outcomes" in latest:
        for o in latest["outcomes"]:
            if o.get("candidate_id") == req.selected_candidate_id:
                ps = o.get("projected_state", {})
                resulting_state = SystemState(**ps)
                break

    if not resulting_state:
        # Fallback representative executed state
        resulting_state = SystemState(
            timestamp=datetime.now(timezone.utc).isoformat(),
            demand_kw=7.9,
            solar_generation_kw=8.1,
            battery_level_pct=52.0,
            temperature_c=29.5,
            occupancy="medium",
        )

    # Record execution event in history store
    history_store.update_latest_outcome({
        "status": "executed",
        "mode": req.mode or "virtual",
        "resulting_state": resulting_state.model_dump(),
    })

    return ExecuteResponse(
        status="executed",
        mode=req.mode or "virtual",
        resulting_state=resulting_state,
    )
