from typing import Optional
from fastapi import APIRouter, Query
from app.models import HistoryResponse, HistoryCycle
from app.utils.history_store import history_store

router = APIRouter()


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    from_time: Optional[str] = Query(None, alias="from"),
    to_time: Optional[str] = Query(None, alias="to"),
    limit: Optional[int] = Query(50, ge=1, le=500),
):
    """
    GET /v1/history
    Retrieve past decision cycles for auditability and continuous learning.
    """
    raw_cycles = history_store.query(from_time=from_time, to_time=to_time, limit=limit)
    cycles = [
        HistoryCycle(
            timestamp=c.get("timestamp", ""),
            system_state=c.get("system_state", {}),
            risk_classification=c.get("risk_classification", "normal"),
            decision=c.get("decision", {}),
            outcome=c.get("outcome"),
        )
        for c in raw_cycles
    ]
    return HistoryResponse(cycles=cycles)
