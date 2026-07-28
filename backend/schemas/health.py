from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "healthy"
    version: str = "1.0.0"


class VersionResponse(BaseModel):
    name: str = "Altron Assistant"
    version: str = "1.0.0"
    environment: str = "production"
