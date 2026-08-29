from __future__ import annotations

import os
from pathlib import Path

from app.system import startup


def test_default_target_points_into_dist(tmp_path, monkeypatch):
    target = startup._default_target()  # noqa: SLF001
    # Either the project hasn't been built yet (path doesn't exist) or
    # the build directory is where the spec puts it.
    assert target.name == "JARVIS.exe"
    assert target.parent.name == "JARVIS"


def test_install_uninstall_roundtrip(tmp_path, monkeypatch):
    fake_target = tmp_path / "JARVIS.exe"
    fake_target.write_bytes(b"MZ")
    fake_startup = tmp_path / "Startup"
    fake_startup.mkdir()
    monkeypatch.setenv("APPDATA", str(tmp_path))
    # Patch the helper to return our fake startup dir.
    monkeypatch.setattr(startup, "_startup_dir", lambda: fake_startup)
    # Patch _create_shortcut to just touch a file (we can't create a
    # real .lnk without Windows shell).
    def fake_create(target, shortcut):
        shortcut.write_text(f"target={target}")
    monkeypatch.setattr(startup, "_create_shortcut", fake_create)

    sc = startup.install(fake_target)
    assert sc.exists()
    assert "JARVIS.exe" in sc.read_text()
    assert startup.is_installed() is True

    sc2 = startup.uninstall()
    assert sc2 is None or not sc2.exists()
    assert startup.is_installed() is False
