from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from api.routers import (
    auth, health, pipeline_management, risk_score,
    anomalies_alerts, forecasts, dashboards, audit
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Dashboard 360° API démarrage...")
    yield
    logger.info("🛑 Dashboard 360° API arrêt.")


app = FastAPI(
    title="Dashboard 360° — Novec",
    description="Système Décisionnel IT Intelligent",
    version="2.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(health.router, tags=["health"])
app.include_router(pipeline_management.router, tags=["pipeline"])
app.include_router(risk_score.router, tags=["risk"])
app.include_router(anomalies_alerts.router, tags=["anomalies"])
app.include_router(forecasts.router, tags=["forecasts"])
app.include_router(dashboards.router, tags=["dashboards"])
app.include_router(audit.router, tags=["audit"])


# FIX: @router.exception_handler → @app.exception_handler
# "router" n'existe pas dans main.py, seul "app" existe ici.
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Gestion uniforme des erreurs de validation Pydantic."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc.body) if hasattr(exc, "body") else None}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Gestion uniforme des erreurs HTTP (401, 403, 404, 500...)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )