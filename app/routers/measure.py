from fastapi import APIRouter
from app.models import MeasureRequest, MeasureResponse
from app.utils.history_store import history_store

router = APIRouter()


@router.post("/measure", response_model=MeasureResponse)
async def measure_endpoint(req: MeasureRequest):
    """
    POST /v1/measure
    Compare pre- and post-execution states and quantify improvement.
    """
    before_peak = req.before_state.demand_kw
    after_peak = req.after_state.demand_kw

    if before_peak > 0:
        improvement = ((before_peak - after_peak) / before_peak) * 100.0
    else:
        improvement = 0.0

    resp = MeasureResponse(
        before_peak_kw=round(before_peak, 2),
        after_peak_kw=round(after_peak, 2),
        improvement_pct=round(improvement, 2),
    )

    # Persist measurement to history store for learning loop
    history_store.update_latest_outcome({
        "before_peak_kw": resp.before_peak_kw,
        "after_peak_kw": resp.after_peak_kw,
        "improvement_pct": resp.improvement_pct,
    })

    return resp
