from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.routes import router as api_router
from backend.config.settings import get_settings
from backend.database.session import session_manager
from backend.logging.setup import configure_logging
from backend.middleware.logging import LoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and clean up runtime resources."""
    configure_logging()
    yield
    await session_manager.dispose()


app = FastAPI(
    title="Altron API",
    version="0.1.0",
    description="Production foundation for the Altron desktop AI assistant",
    lifespan=lifespan,
)

app.add_middleware(LoggingMiddleware)
app.include_router(api_router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Return structured validation errors."""
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors()})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Return structured HTTP errors."""
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Return a safe error response for unexpected failures."""
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Internal Server Error"})


@app.get("/")
async def root() -> dict[str, str]:
    """Return a lightweight root endpoint."""
    settings = get_settings()
    return {"message": f"{settings.app_name} API is running"}


__all__ = ["app"]
