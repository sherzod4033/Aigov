from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import setup_logging, get_logger

# Setup logging
setup_logging(level="DEBUG" if settings.ENVIRONMENT == "development" else "INFO")
logger = get_logger(__name__)
from app.api.endpoints import (
    auth,
    documents,
    sources,
    notebooks,
    notes,
    insights,
    chat,
    ask,
    logs,
    analytics,
    settings as runtime_settings,
)

app = FastAPI(
    title=f"{settings.PROJECT_NAME} API",
    description="Backend for a grounded knowledge assistant over uploaded sources",
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# CORS Middleware
# In production, set CORS_ORIGINS to specific domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
# Compatibility alias for clients expecting /api/auth/*
app.include_router(auth.router, prefix="/api/auth", tags=["auth-compat"])
app.include_router(
    documents.router, prefix=f"{settings.API_V1_STR}/documents", tags=["documents"]
)
app.include_router(
    sources.router, prefix=f"{settings.API_V1_STR}/sources", tags=["sources"]
)
app.include_router(
    notebooks.router, prefix=f"{settings.API_V1_STR}/notebooks", tags=["notebooks"]
)
app.include_router(notes.router, prefix=f"{settings.API_V1_STR}/notes", tags=["notes"])
app.include_router(
    insights.router, prefix=f"{settings.API_V1_STR}/insights", tags=["insights"]
)
app.include_router(chat.router, prefix=f"{settings.API_V1_STR}/chat", tags=["chat"])
app.include_router(ask.router, prefix=f"{settings.API_V1_STR}/ask", tags=["ask"])
app.include_router(logs.router, prefix=f"{settings.API_V1_STR}/logs", tags=["logs"])
app.include_router(
    analytics.router, prefix=f"{settings.API_V1_STR}/analytics", tags=["analytics"]
)
app.include_router(
    runtime_settings.router, prefix=f"{settings.API_V1_STR}/settings", tags=["settings"]
)


@app.exception_handler(ExternalServiceError)
async def external_service_error_handler(
    request: Request, exc: ExternalServiceError
) -> JSONResponse:
    cause_text = f"; cause={exc.cause}" if exc.cause else ""
    logger.warning(
        "External service error on %s %s: %s%s",
        request.method,
        request.url.path,
        exc.message,
        cause_text,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "service": exc.service},
    )


@app.get("/", tags=["root"])
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} API", "version": "0.1.0"}


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.
    Returns 200 OK if the service is running.
    """
    return {
        "status": "healthy",
        "service": f"{settings.PROJECT_NAME.lower()}-api",
        "version": "0.1.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/ready", tags=["health"])
async def readiness_check():
    """
    Readiness check endpoint for Kubernetes.
    Verifies database and external service connections.
    """
    from app.core.database import engine
    from app.modules.rag.service import RAGService

    checks = {
        "database": False,
        "chromadb": False,
    }

    # Check database connection
    try:
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        checks["database_error"] = str(e)
        logger.error(f"Database health check failed: {e}")

    # Check ChromaDB
    try:
        rag = RAGService()
        if rag.collection is not None:
            checks["chromadb"] = True
    except Exception as e:
        checks["chromadb_error"] = str(e)

    all_healthy = all(checks.values())

    return JSONResponse(
        status_code=status.HTTP_200_OK
        if all_healthy
        else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ready" if all_healthy else "not_ready", "checks": checks},
    )
