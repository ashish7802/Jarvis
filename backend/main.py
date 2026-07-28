from __future__ import annotations

from fastapi import FastAPI

from backend.api.routes import router

app = FastAPI(
    title="Altron Voice Assistant API",
    description="FastAPI Backend for Altron Voice Assistant",
    version="1.0.0",
)

app.include_router(router)
