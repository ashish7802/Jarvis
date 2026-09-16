"""Windows auto-start: place/remove a shortcut in the user's Startup folder.

This deliberately avoids Windows Service / admin rights. It creates a
simple `.lnk` in `shell:startup` pointing at the JARVIS executable.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("jarvis.startup")


LINK_NAME = "JARVIS.lnk"


def _startup_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA not set; cannot resolve Startup folder")
    p = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _default_target() -> Path:
    """Best-effort path to the packaged JARVIS.exe."""
    # When packaged with PyInstaller --onedir, this points to dist/JARVIS/JARVIS.exe
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    if os.environ.get("LOCALAPPDATA"):
        installed = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "JARVIS" / "JARVIS.exe"
        if installed.is_file():
            return installed
    project_root = Path(__file__).resolve().parent.parent.parent
    candidate = project_root / "dist" / "JARVIS" / "JARVIS.exe"
    return candidate


def install(target: Path | None = None) -> Path:
    """Create the Startup shortcut. Returns the shortcut path."""
    target = target or _default_target()
    if not target.exists():
        raise FileNotFoundError(
            f"Target executable not found: {target}. Build it first with build.bat."
        )
    shortcut = _startup_dir() / LINK_NAME
    _create_shortcut(target=target, shortcut=shortcut)
    log.info("Installed startup shortcut: %s -> %s", shortcut, target)
    return shortcut


def uninstall() -> Path | None:
    """Remove the Startup shortcut if it exists."""
    shortcut = _startup_dir() / LINK_NAME
    if shortcut.exists():
        try:
            shortcut.unlink()
            log.info("Removed startup shortcut: %s", shortcut)
        except Exception as exc:
            log.exception("Failed to remove shortcut: %s", exc)
            raise
    return shortcut if shortcut.exists() else None


def is_installed() -> bool:
    return (_startup_dir() / LINK_NAME).exists()


def _create_shortcut(target: Path, shortcut: Path) -> None:
    """Create a Windows .lnk pointing at `target`.

    Uses pywin32 if available; otherwise falls back to a tiny PowerShell
    COM script.
    """
    try:
        import win32com.client  # type: ignore

        shell = win32com.client.Dispatch("WScript.Shell")
        s = shell.CreateShortcut(str(shortcut))
        s.Targetpath = str(target)
        s.WorkingDirectory = str(target.parent)
        s.WindowStyle = 1  # normal, visible desktop window on login
        s.IconLocation = str(target)
        s.Description = "JARVIS voice assistant"
        s.save()
        return
    except ImportError:
        pass
    except Exception as exc:
        log.warning("pywin32 shortcut failed (%s) — falling back to PowerShell", exc)

    # PowerShell COM fallback.
    import subprocess

    ps = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut('"
        + str(shortcut).replace("'", "''")
        + "');"
        + "$s.TargetPath = '" + str(target).replace("'", "''") + "';"
        + "$s.WorkingDirectory = '" + str(target.parent).replace("'", "''") + "';"
        + "$s.WindowStyle = 1;"
        + "$s.IconLocation = '" + str(target).replace("'", "''") + "';"
        + "$s.Description = 'JARVIS voice assistant';"
        + "$s.Save();"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    from app.system import autostart

    parser = argparse.ArgumentParser(description="Manage Windows auto-start for JARVIS")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--install", action="store_true", help="Launch at Windows sign-in and unlock")
    g.add_argument("--uninstall", action="store_true", help="Remove JARVIS automatic startup")
    g.add_argument("--run", action="store_true", help="Test the registered Windows startup task now")
    g.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--target", type=Path, default=None, help="Path to JARVIS.exe")
    args = parser.parse_args(argv)

    if args.status:
        print(json.dumps(autostart.status(), indent=2))
        return 0
    if args.run:
        autostart.run_task()
        return 0
    if args.install:
        try:
            info = autostart.install_task(args.target or _default_target())
            # Remove the old sign-in-only shortcut only after registration works.
            uninstall()
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"Installed login/unlock task: {info['name']} -> {info['target']}")
        return 0
    if args.uninstall:
        autostart.uninstall_task()
        sc = uninstall()
        print(f"Removed: {sc}" if sc else "No shortcut to remove")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
