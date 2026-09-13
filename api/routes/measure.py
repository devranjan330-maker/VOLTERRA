"""
VOLTERRA - API Route: /v1/measure
=================================
Implements Step 8: Pre- vs post-intervention comparison and improvement quantification.
"""

from fastapi import APIRouter
from api.schemas import MeasureRequest, MeasureResponse
from engine.measure import measure_improvement

router = APIRouter()


@router.post("/measure", response_model=MeasureResponse)
async def measure(req: MeasureRequest):
    """
    POST /v1/measure
    Compare before and after system states; quantify peak demand reduction.
    """
    res = measure_improvement(req.before_state, req.after_state)
    return MeasureResponse(
        before_peak_kw=res.before_peak_kw,
        after_peak_kw=res.after_peak_kw,
        improvement_pct=res.improvement_pct,
    )
