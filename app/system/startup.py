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
        s.WindowStyle = 7  # minimised / hidden
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
        + "$s.WindowStyle = 7;"
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

    parser = argparse.ArgumentParser(description="Manage Windows auto-start for JARVIS")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--install", action="store_true", help="Install the Startup shortcut")
    g.add_argument("--uninstall", action="store_true", help="Remove the Startup shortcut")
    g.add_argument("--status", action="store_true", help="Show current status")
    parser.add_argument("--target", type=Path, default=None, help="Path to JARVIS.exe")
    args = parser.parse_args(argv)

    if args.status:
        print("installed" if is_installed() else "not installed")
        return 0
    if args.install:
        try:
            sc = install(args.target)
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(f"Installed: {sc}")
        return 0
    if args.uninstall:
        sc = uninstall()
        print(f"Removed: {sc}" if sc else "No shortcut to remove")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
