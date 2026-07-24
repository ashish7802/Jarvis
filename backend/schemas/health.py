from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(default="ok")
    app_name: str
    environment: str


class VersionResponse(BaseModel):
    """Version response schema."""

    app_name: str
    version: str
