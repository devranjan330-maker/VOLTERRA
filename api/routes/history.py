"""
VOLTERRA - API Route: /v1/history
=================================
Implements persistent audit trail querying and Section 6 relational query patterns:
1. Reconstructable Decision Cycle Audit (/v1/history/audit/{cycle_id})
2. Forecast Accuracy Tracking (/v1/history/forecast-accuracy)
3. Historical Improvement Trend (/v1/history/improvement-trend)
4. Candidate Strategy Performance (/v1/history/strategy-performance)
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from api.schemas import (
    HistoryResponse,
    HistoryCycle,
    CycleAuditResponse,
    ForecastAccuracyResponse,
    ImprovementTrendResponse,
    StrategyPerformanceResponse,
)
from storage.history_store import history_store

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


@router.get("/history/audit/{cycle_id}", response_model=CycleAuditResponse)
async def get_cycle_audit(cycle_id: int):
    """
    GET /v1/history/audit/{cycle_id}
    Full relational audit reconstruction joining all 9 entities for a decision cycle.
    """
    audit = history_store.get_full_audit(cycle_id)
    if not audit:
        raise HTTPException(status_code=404, detail=f"Decision cycle {cycle_id} not found")
    return audit


@router.get("/history/forecast-accuracy", response_model=ForecastAccuracyResponse)
async def get_forecast_accuracy():
    """
    GET /v1/history/forecast-accuracy
    Section 6 Pattern 2: Compare predictions against later observed states.
    """
    return history_store.get_forecast_accuracy()


@router.get("/history/improvement-trend", response_model=ImprovementTrendResponse)
async def get_improvement_trend():
    """
    GET /v1/history/improvement-trend
    Section 6 Pattern 3: Aggregate measurements.improvement_pct over time.
    """
    return history_store.get_historical_improvement_trend()


@router.get("/history/strategy-performance", response_model=StrategyPerformanceResponse)
async def get_strategy_performance():
    """
    GET /v1/history/strategy-performance
    Section 6 Pattern 4: Aggregate candidate strategy frequency & associated improvements.
    """
    return history_store.get_candidate_strategy_performance()
