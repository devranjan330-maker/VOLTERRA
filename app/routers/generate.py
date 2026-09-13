from fastapi import APIRouter
from app.models import GenerateRequest, GenerateResponse, CandidateAction

router = APIRouter()

DEFAULT_CANDIDATES = [
    CandidateAction(id="A", label="Do nothing", description="Continue baseline operation without intervention"),
    CandidateAction(id="B", label="Use battery", description="Discharge battery to cover projected shortfall"),
    CandidateAction(id="C", label="Shift flexible loads", description="Defer non-critical electrical loads"),
    CandidateAction(id="D", label="Hybrid response", description="Combined battery discharge and load curtailment"),
]


@router.post("/generate", response_model=GenerateResponse)
async def generate_endpoint(req: GenerateRequest = None):
    """
    POST /v1/generate
    Produce the candidate decision space for a flagged risk condition.
    """
    return GenerateResponse(candidates=DEFAULT_CANDIDATES)
