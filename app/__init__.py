"""JARVIS package."""
import os
from pathlib import Path

# Optional app-local VC++ runtime for machines without the system runtime.
# Keep the handle alive so native speech libraries can resolve their DLLs.
_runtime_dir = Path(__file__).resolve().parent.parent / ".cache" / "runtime"
_runtime_handle = (
    os.add_dll_directory(str(_runtime_dir))
    if os.name == "nt" and _runtime_dir.is_dir()
    else None
)

__version__ = "0.1.0"
