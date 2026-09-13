"""
VOLTERRA - API Entrypoint (FastAPI Application)
==============================================
Implements Step 10 of the Implementation Document:
Exposes all individual endpoints plus /v1/decide and /v1/history, with
comprehensive error handling (400 / 409 / 422 / 500).
"""

from pathlib import Path
import uvicorn
from fastapi import Depends
from app.auth import api_key_dependency
from app.metrics import router as metrics_router
from app.health import router as health_router
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.routes import (
    state,
    predict,
    generate,
    simulate,
    optimize,
    explain,
    execute,
    measure,
    decide,
    history,
)

app = FastAPI(
    title="VOLTERRA Decision Intelligence Engine",
    description="Closed-loop decision engine: Observe -> Predict -> Generate -> Simulate -> Optimize -> Explain -> Execute -> Measure",
    version="1.0.0",
    dependencies=[Depends(api_key_dependency)],
    title="VOLTERRA Decision Intelligence Engine",
    description="Closed-loop decision engine: Observe -> Predict -> Generate -> Simulate -> Optimize -> Explain -> Execute -> Measure",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Error Handling per Specification (400 / 409 / 422 / 500)
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
        )
    if exc.status_code == 409:
        code = "constraint_violation"
    elif exc.status_code == 422:
        code = "unprocessable_entity"
    elif exc.status_code == 400:
        code = "malformed_request"
    elif exc.status_code == 404:
        code = "not_found"
    else:
        code = "error"

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": str(exc.detail),
            }
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first_error = exc.errors()[0] if exc.errors() else {}
    msg = first_error.get("msg", "Malformed or incomplete request body")
    loc = " -> ".join(str(l) for l in first_error.get("loc", []))
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "malformed_request",
                "message": f"{msg} at {loc}" if loc else msg,
            }
        },
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": f"Internal server error: {str(exc)}",
            }
        },
    )

# Static file paths (frontend / static)
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def root(request: Request):
    accept_header = request.headers.get("accept", "")
    index_file = (FRONTEND_DIR / "index.html") if (FRONTEND_DIR / "index.html").exists() else (STATIC_DIR / "index.html")
    if "text/html" in accept_header and "application/json" not in accept_header and index_file.exists():
        return FileResponse(index_file)
    return {
        "engine": "VOLTERRA",
        "status": "online",
        "version": "1.0.0",
        "documentation": "/docs",
        "dashboard": "/dashboard",
        "pipeline": [
            "POST /v1/state",
            "POST /v1/predict",
            "POST /v1/generate",
            "POST /v1/simulate",
            "POST /v1/optimize",
            "POST /v1/explain",
            "POST /v1/execute",
            "POST /v1/measure",
            "POST /v1/decide",
            "GET /v1/history",
        ],
        "database_audit_patterns": [
            "GET /v1/history/audit/{cycle_id}",
            "GET /v1/history/forecast-accuracy",
            "GET /v1/history/improvement-trend",
            "GET /v1/history/strategy-performance",
        ],
    }

@app.get("/dashboard")
async def dashboard():
    index_file = (FRONTEND_DIR / "index.html") if (FRONTEND_DIR / "index.html").exists() else (STATIC_DIR / "index.html")
    if index_file.exists():
        return FileResponse(index_file)
    return JSONResponse({"status": "dashboard not found"}, status_code=404)

# Mount routes to /v1
app.include_router(state.router, prefix="/v1", tags=["1. Observe"])
app.include_router(predict.router, prefix="/v1", tags=["2. Predict"])
app.include_router(generate.router, prefix="/v1", tags=["3. Generate"])
app.include_router(simulate.router, prefix="/v1", tags=["4. Simulate"])
app.include_router(optimize.router, prefix="/v1", tags=["5. Optimize"])
app.include_router(explain.router, prefix="/v1", tags=["6. Explain"])
app.include_router(execute.router, prefix="/v1", tags=["7. Execute"])
app.include_router(measure.router, prefix="/v1", tags=["8. Measure"])
app.include_router(decide.router, prefix="/v1", tags=["9. Decide (End-to-End)"])
app.include_router(history.router, prefix="/v1", tags=["10. History"])

app.include_router(metrics_router, prefix="/metrics", tags=["Metrics"])
app.include_router(health_router, prefix="/health", tags=["Health"])

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
