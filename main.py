"""
─────────────────────────────────────────────────────────────────────────────
File        : main.py
Purpose     : Application entry point for the CityCare Clinic FastAPI backend.

Responsibilities:
    - Create and configure the FastAPI application instance
    - Manage the application lifespan (database connect/disconnect)
    - Configure CORS middleware
    - Register the API router
    - Set Swagger UI and ReDoc metadata

Flow:
    uvicorn starts the ASGI application
        ↓
    Lifespan: connect_to_database() runs on startup
        ↓
    Requests routed through api_router → routes → controllers → cruds → MongoDB
        ↓
    Lifespan: close_database_connection() runs on shutdown

Usage:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Swagger UI:
    http://localhost:8000/docs

ReDoc:
    http://localhost:8000/redoc
─────────────────────────────────────────────────────────────────────────────
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from common.config import get_cors_origins, load_project_env, validate_config
from common.logger import get_logger
from core.apis.api import api_router
from core.database.database import close_database_connection, connect_to_database, get_engine
from core.database.seed import seed_initial_users

# ─── Load Environment Variables ───────────────────────────────────────────────

load_project_env()

# ─── Logger ───────────────────────────────────────────────────────────────────

logger = get_logger(__name__)


# ─── Application Lifespan ─────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(application: FastAPI):
    """
    Manage startup and shutdown events for the FastAPI application.

    On startup  : Validates production configuration, establishes MongoDB connection,
                  and optionally seeds default accounts if explicitly enabled.
    On shutdown : Gracefully closes the Motor client connection.

    Args:
        application (FastAPI): The FastAPI application instance.
    """
    logger.info("CityCare Clinic API starting up...")
    validate_config()
    await connect_to_database()
    await seed_initial_users()
    logger.info("CityCare Clinic API is ready to accept requests.")

    yield

    logger.info("CityCare Clinic API shutting down...")
    await close_database_connection()
    logger.info("CityCare Clinic API shut down complete.")


# ─── Application Instance ─────────────────────────────────────────────────────

app = FastAPI(
    title="CityCare Clinic API",
    description=(
        "## CityCare Clinic — Appointment Booking System\n\n"
        "**Doctor**: Dr. Meera Kulkarni — General Physician\n\n"
        "This API powers the complete appointment booking system for CityCare Clinic. "
        "It supports patient registration, JWT-based authentication, slot availability, "
        "appointment booking with four validation gates, and a doctor dashboard.\n\n"
        "### Authentication\n"
        "All protected endpoints require a Bearer token in the `Authorization` header:\n"
        "```\nAuthorization: Bearer <your_token>\n```\n\n"
        "Obtain a token via `POST /api/v1/login`.\n\n"
        "### Roles\n"
        "- **patient** — can book, view, and cancel their own appointments\n"
        "- **doctor**  — can view the full schedule and clinic statistics\n"
    ),
    version="1.0.0",
    contact={
        "name": "CityCare Clinic Engineering",
        "email": "engineering@citycare.com",
    },
    license_info={
        "name": "Private",
    },
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS Middleware ──────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

# ─── API Router ───────────────────────────────────────────────────────────────

app.include_router(api_router)

# ─── Health & Probes ──────────────────────────────────────────────────────────


@app.get("/", tags=["Health"], summary="Health check", include_in_schema=True)
async def health_check() -> dict:
    """
    Confirm the API is running and reachable.

    Returns:
        dict: Status message and API version.
    """
    return {
        "status": "healthy",
        "service": "CityCare Clinic API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health/liveness", tags=["Health"], summary="Liveness probe", include_in_schema=True)
async def liveness_probe() -> dict:
    """
    Lightweight liveness probe that returns HTTP 200 without checking external services.
    """
    return {"status": "alive"}


@app.get("/health/readiness", tags=["Health"], summary="Readiness probe", include_in_schema=True)
async def readiness_probe() -> dict:
    """
    Readiness probe verifying MongoDB client/engine and performing a bounded database ping.
    Returns HTTP 503 if the database is unavailable.
    """
    try:
        engine = get_engine()
        if engine is None or engine.client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"status": "not_ready", "database": "disconnected"},
            )
        await asyncio.wait_for(engine.client.admin.command("ping"), timeout=2.0)
        return {"status": "ready", "database": "connected"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "database": "disconnected"},
        )
