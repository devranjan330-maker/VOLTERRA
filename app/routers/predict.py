from fastapi import APIRouter
from app.models import PredictRequest, PredictResponse
from app.services.predict_service import predict_future

router = APIRouter()


@router.post("/predict", response_model=PredictResponse)
async def predict_endpoint(req: PredictRequest):
    """
    POST /v1/predict
    Generate a forecast and risk classification from a given SystemState.
    """
    return predict_future(
        state=req.system_state,
        horizon_minutes=req.horizon_minutes or 30,
        demand_history=req.demand_history_kw,
        supply_history=req.supply_history_kw,
    )
