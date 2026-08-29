from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path


_INITIALIZED = False


class _SecretFilter(logging.Filter):
    """Best-effort filter that scrubs obvious secret-looking substrings."""

    _SENSITIVE_KEYS = (
        "api_key",
        "apikey",
        "token",
        "secret",
        "password",
        "access_key",
    )

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        try:
            msg = record.getMessage()
        except Exception:
            return True
        lowered = msg.lower()
        for key in self._SENSITIVE_KEYS:
            if key in lowered and "=" in msg:
                msg = _redact_kv(msg, key)
        record.msg = msg
        record.args = ()
        return True


def _redact_kv(text: str, key: str) -> str:
    """Replace values of *key*=... occurrences with <redacted>.

    The value is the longest run of non-whitespace, non-comma, non-}}
    characters following the equals sign. This is robust to values that
    contain letters, digits, dashes and underscores.
    """
    import re

    pattern = re.compile(
        r"(" + re.escape(key) + r"\s*=\s*)([^\s,}]+)",
        re.IGNORECASE,
    )
    return pattern.sub(r"\1<redacted>", text)


def setup_logging(logs_dir: Path, level: str = "INFO") -> logging.Logger:
    """Configure root logger. Safe to call multiple times."""
    global _INITIALIZED

    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "jarvis.log"

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear any pre-existing handlers (e.g. from PyInstaller/bootstrap).
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(_SecretFilter())
    root.addHandler(file_handler)

    # Console only when stderr is a real tty (i.e. dev mode).
    if sys.stderr is not None and getattr(sys.stderr, "isatty", lambda: False)():
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(fmt)
        stream.addFilter(_SecretFilter())
        root.addHandler(stream)

    # Tame chatty third-party loggers.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sounddevice").setLevel(logging.WARNING)

    _INITIALIZED = True
    return logging.getLogger("jarvis")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
