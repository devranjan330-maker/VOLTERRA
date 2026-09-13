from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/health")
async def health_check():
    """Simple health‑check endpoint used by orchestration platforms."""
    return JSONResponse(content={"status": "ok"})
