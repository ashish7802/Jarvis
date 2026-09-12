"""Emergency-stop global hotkey.

Binds a configurable hotkey (default Ctrl+Shift+J) that triggers an
immediate, clean shutdown of the assistant. This is essential because
the production JARVIS has no visible UI.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

log = logging.getLogger("jarvis.hotkey")


class EmergencyHotkey:
    """Owns a global hotkey hook (Windows, via the `keyboard` package).

    The hook runs on its own thread. When the configured hotkey is
    pressed, the registered callback fires exactly once.
    """

    def __init__(self, hotkey: str = "Ctrl+Shift+J") -> None:
        self.hotkey = hotkey
        self._handle = None
        self._callback: Optional[Callable[[], None]] = None
        self._fired = threading.Event()

    def set_callback(self, cb: Callable[[], None]) -> None:
        self._callback = cb

    def start(self) -> bool:
        if self._handle is not None:
            return True
        try:
            import keyboard  # type: ignore
        except ImportError as e:
            log.error("`keyboard` package not installed: %s", e)
            return False
        try:
            self._fired.clear()
            self._handle = keyboard.add_hotkey(
                self.hotkey, self._on_press, suppress=False
            )
            log.info("Emergency hotkey registered: %s", self.hotkey)
            return True
        except Exception as exc:
            log.exception("Failed to register hotkey %s: %s", self.hotkey, exc)
            self._handle = None
            return False

    def stop(self) -> None:
        if self._handle is not None:
            try:
                import keyboard  # type: ignore

                keyboard.remove_hotkey(self._handle)
            except Exception:
                pass
            self._handle = None
        log.info("Emergency hotkey unregistered")

    def _on_press(self) -> None:
        if self._fired.is_set():
            return
        self._fired.set()
        log.warning("EMERGENCY HOTKEY pressed: %s", self.hotkey)
        if self._callback is not None:
            try:
                self._callback()
            except Exception as exc:
                log.exception("hotkey callback error: %s", exc)
