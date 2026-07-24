from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs incoming requests and their latency."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], object]) -> Response:
        request_logger = logger.bind(method=request.method, path=request.url.path)
        start_time = time.perf_counter()
        request_logger.info("Request started")
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            request_logger.exception("Request failed", duration_ms=duration_ms)
            raise

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        request_logger.info(
            "Request completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response


__all__ = ["LoggingMiddleware"]
