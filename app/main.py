"""
VOLTERRA - Main API Application Entrypoint
==========================================
Exposes the canonical FastAPI application defined in api.main.
"""

from api.main import app, FRONTEND_DIR, STATIC_DIR

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
