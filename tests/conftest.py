"""Shared pytest fixtures."""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    """Each test gets a fresh .env-free environment in a temp dir."""
    # Don't load any pre-existing .env in the project root.
    monkeypatch.setenv("JARVIS_ENV_FILE", str(tmp_path / "no.env"))
    # Avoid clobbering user logs
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    yield


@pytest.fixture
def tmp_logs(tmp_path):
    return tmp_path / "logs"


@pytest.fixture
def tmp_tts_cache(tmp_path):
    return tmp_path / "tts_cache"
