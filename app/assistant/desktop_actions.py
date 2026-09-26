"""Explicit, bounded Windows desktop actions.

JARVIS never turns model-generated text into shell commands. App launches are
either fixed Windows utilities or Start Menu shortcuts; websites are limited
to validated HTTP(S) URLs. Screen reading uses the active window's accessible
text only and is invoked separately by an explicit user request.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import os
from pathlib import Path
import re
import subprocess
import unicodedata
import webbrowser
from urllib.parse import urlsplit, urlunsplit


MAX_SCREEN_CHARS = 12_000
MAX_SCREEN_LINES = 180

WEBSITE_ALIASES = {
    "google": ("https://www.google.com", "Google"),
    "youtube": ("https://www.youtube.com", "YouTube"),
    "github": ("https://github.com", "GitHub"),
    "gmail": ("https://mail.google.com", "Gmail"),
    "chatgpt": ("https://chatgpt.com", "ChatGPT"),
    "wikipedia": ("https://www.wikipedia.org", "Wikipedia"),
}

APP_SHORTCUT_ALIASES = {
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "ms edge": "Microsoft Edge",
    "firefox": "Firefox",
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "code": "Visual Studio Code",
}

BUILTIN_APPLICATIONS = {
    "notepad": ("notepad.exe", "Notepad"),
    "calculator": ("calc.exe", "Calculator"),
    "calc": ("calc.exe", "Calculator"),
    "file explorer": ("explorer.exe", "File Explorer"),
    "explorer": ("explorer.exe", "File Explorer"),
    "task manager": ("taskmgr.exe", "Task Manager"),
    "paint": ("mspaint.exe", "Paint"),
    "snipping tool": ("snippingtool.exe", "Snipping Tool"),
    "settings": ("ms-settings:", "Settings"),
    "windows settings": ("ms-settings:", "Settings"),
}


class DesktopActionError(RuntimeError):
    """A safe, user-facing desktop action could not be completed."""


@dataclass(frozen=True)
class DesktopRequest:
    action: str
    target: str = ""


@dataclass(frozen=True)
class ScreenSnapshot:
    title: str
    text: str


def _normalize_phrase(value: str) -> str:
    parts = []
    for char in unicodedata.normalize("NFKC", value).casefold():
        category = unicodedata.category(char)
        parts.append(char if char.isalnum() or category.startswith("M") else " ")
    return " ".join("".join(parts).split())


def _clean_target(value: str) -> str:
    value = value.strip().strip(" \t\r\n\"'`.,!?;:")
    value = re.sub(r"^(?:the|a|an)\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+(?:app|application|program|website|web\s+page|site)$", "", value, flags=re.IGNORECASE)
    return value.strip()


_READ_SCREEN_PHRASES = {
    _normalize_phrase(phrase)
    for phrase in (
        "read screen", "read my screen", "read the screen", "read current screen",
        "what is on my screen", "what's on my screen", "whats on the screen",
        "what is open on my screen", "read the current window", "read active window",
        "screen pe kya hai", "screen par kya hai", "screen pe kya khula hai",
        "screen padh ke batao", "screen padhkar batao", "screen padh kar batao",
        "screen dekh ke batao", "screen dekhkar batao", "screen read karo",
        "jo screen pe hai padh ke batao", "active window padh ke sunao",
        "अभी screen पर क्या है", "screen पढ़कर बताओ", "screen पढ़ के बताओ",
        "screen देख कर बताओ", "मेरी screen पढ़ो", "screen पर क्या है",
        "screen पे क्या है", "स्क्रीन पर क्या है", "स्क्रीन पढ़कर बताओ",
        "मेरी स्क्रीन पढ़ो", "स्क्रीन देख कर बताओ",
    )
}

_OPEN_PREFIX = re.compile(
    r"^(?:open up|open|launch|start|run|visit|go\s+to|"
    r"khol|kholo|khol\s+do|chalao|chala\s+do|open\s+karo|"
    r"खोलो|खोल\s+दो|चालू\s+करो)\s+"
    r"(?:(?:the|a|an)\s+)?"
    r"(?:(website|site|web\s+page|browser|app|application|program)\s+)?(.+)$",
    re.IGNORECASE,
)
_OPEN_SUFFIX = re.compile(
    r"^(.+?)\s+(?:(?:ko)\s+)?"
    r"(?:khol|kholo|khol\s+do|chalao|chala\s+do|start\s+karo|open\s+karo|"
    r"खोलो|खोल\s+दो|चालू\s+करो)$",
    re.IGNORECASE,
)


def parse_desktop_request(text: str) -> DesktopRequest | None:
    """Recognize only short, explicit local open/read requests."""
    value = text.strip()
    value = re.sub(r"^(?:(?:hey\s+)?jarvis)\s*[,!:]?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^(?:please|can you|could you|would you)\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+please[.!?]*$", "", value, flags=re.IGNORECASE).strip()

    normalized = _normalize_phrase(value)
    if normalized in _READ_SCREEN_PHRASES:
        return DesktopRequest("read_screen")
    if normalized in {"open browser", "launch browser", "start browser", "browser kholo"}:
        return DesktopRequest("open_browser")

    match = _OPEN_PREFIX.fullmatch(value)
    category = ""
    target = ""
    if match:
        category, target = match.group(1) or "", match.group(2)
    else:
        match = _OPEN_SUFFIX.fullmatch(value)
        if match:
            target = match.group(1)
    target = _clean_target(target)
    if not target or len(target) > 300:
        return None

    category = category.casefold().strip()
    normalized_target = _normalize_phrase(target)
    if category in {"website", "site", "web page"}:
        return DesktopRequest("open_website", target)
    if category in {"app", "application", "program"}:
        return DesktopRequest("open_app", target)
    if category == "browser" and not normalized_target:
        return DesktopRequest("open_browser")
    if normalized_target in WEBSITE_ALIASES or _looks_like_website(target):
        return DesktopRequest("open_website", target)
    return DesktopRequest("open_app", target)


def _looks_like_website(value: str) -> bool:
    if "://" in value:
        return True
    host = value.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    return "." in host or host.casefold() == "localhost"


def normalize_website_url(value: str) -> str:
    """Accept ordinary HTTP(S) addresses only; reject shell and file schemes."""
    value = value.strip()
    if not value or len(value) > 2_048 or any(ord(char) < 32 or char.isspace() for char in value):
        raise DesktopActionError("Use a normal website address, like example.com.")
    candidate = value if "://" in value else "https://" + value
    try:
        parts = urlsplit(candidate)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise DesktopActionError("Use a normal website address, like example.com.") from exc

    if parts.scheme.casefold() not in {"http", "https"} or not host or parts.username or parts.password:
        raise DesktopActionError("Use a normal website address, like example.com.")
    try:
        host = host.encode("idna").decode("ascii").casefold().rstrip(".")
    except UnicodeError as exc:
        raise DesktopActionError("Use a normal website address, like example.com.") from exc

    try:
        ipaddress.ip_address(host)
        valid_host = True
    except ValueError:
        labels = host.split(".")
        valid_host = (
            (host == "localhost" or len(labels) >= 2)
            and all(
                label and len(label) <= 63 and label[0] != "-" and label[-1] != "-"
                and re.fullmatch(r"[a-z0-9-]+", label)
                for label in labels
            )
        )
    if not valid_host or (port is not None and not 1 <= port <= 65_535):
        raise DesktopActionError("Use a normal website address, like example.com.")

    netloc = f"[{host}]" if ":" in host else host
    if port is not None:
        netloc += f":{port}"
    return urlunsplit((parts.scheme.casefold(), netloc, parts.path or "/", parts.query, parts.fragment))


def _default_start_menu_dirs() -> list[Path]:
    roots: list[Path] = []
    appdata = os.environ.get("APPDATA")
    program_data = os.environ.get("PROGRAMDATA")
    if appdata:
        roots.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    if program_data:
        roots.append(Path(program_data) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    return roots


def find_start_menu_shortcut(name: str, roots: list[Path] | None = None) -> Path | None:
    """Find a unique installed Start Menu shortcut by its displayed name."""
    wanted = _normalize_phrase(name)
    if not wanted:
        return None
    candidates: list[Path] = []
    for root in roots if roots is not None else _default_start_menu_dirs():
        try:
            for path in root.rglob("*.lnk"):
                if _normalize_phrase(path.stem) == wanted:
                    candidates.append(path)
        except OSError:
            continue
    if candidates:
        return sorted(candidates, key=lambda path: str(path).casefold())[0]

    partial: list[Path] = []
    for root in roots if roots is not None else _default_start_menu_dirs():
        try:
            for path in root.rglob("*.lnk"):
                if _normalize_phrase(path.stem).startswith(wanted):
                    partial.append(path)
                    if len(partial) > 1:
                        return None
        except OSError:
            continue
    return partial[0] if len(partial) == 1 else None


class WindowsDesktopActions:
    """Open approved targets and read accessible text from the active window."""

    def __init__(
        self,
        *,
        platform: str | None = None,
        startfile=None,
        launch_process=None,
        browser_open=None,
        menu_dirs: list[Path] | None = None,
        screen_reader=None,
    ):
        self.platform = platform or os.name
        self.startfile = startfile if startfile is not None else getattr(os, "startfile", None)
        self.launch_process = launch_process or subprocess.Popen
        self.browser_open = browser_open or webbrowser.open
        self.menu_dirs = menu_dirs
        self.screen_reader = screen_reader

    def _require_windows(self):
        if self.platform != "nt":
            raise DesktopActionError("Local desktop actions are available in the Windows desktop app only.")

    def open_application(self, target: str) -> str:
        self._require_windows()
        normalized = _normalize_phrase(target)
        if normalized in {"browser", "default browser"}:
            if not self.browser_open("about:blank", new=2):
                raise DesktopActionError("I couldn't open your browser.")
            return "Opening your browser."

        built_in = BUILTIN_APPLICATIONS.get(normalized)
        if built_in:
            executable, label = built_in
            if executable == "ms-settings:":
                if self.startfile is None:
                    raise DesktopActionError("I couldn't open Windows Settings.")
                self.startfile(executable)
            else:
                try:
                    self.launch_process([executable], shell=False)
                except OSError as exc:
                    raise DesktopActionError(f"I couldn't open {label}. Check that it is available.") from exc
            return f"Opening {label}."

        shortcut_name = APP_SHORTCUT_ALIASES.get(normalized, target)
        shortcut = find_start_menu_shortcut(shortcut_name, self.menu_dirs)
        if shortcut is None or self.startfile is None:
            raise DesktopActionError(
                f"I couldn't find an installed app named {target} in the Windows Start menu."
            )
        try:
            self.startfile(str(shortcut))
        except OSError as exc:
            raise DesktopActionError(f"I couldn't open {target}. Check that it is installed.") from exc
        return f"Opening {shortcut.stem}."

    def open_website(self, target: str) -> str:
        self._require_windows()
        normalized = _normalize_phrase(target)
        alias = WEBSITE_ALIASES.get(normalized)
        if alias:
            url, label = alias
        else:
            url = normalize_website_url(target)
            label = urlsplit(url).hostname or target
        if not self.browser_open(url, new=2):
            raise DesktopActionError("I couldn't open that website in your browser.")
        return f"Opening {label} in your browser."

    def read_active_window(self) -> ScreenSnapshot:
        self._require_windows()
        if self.screen_reader is not None:
            snapshot = self.screen_reader()
            if isinstance(snapshot, ScreenSnapshot):
                return snapshot
            title, text = snapshot
            return ScreenSnapshot(str(title), str(text)[:MAX_SCREEN_CHARS])

        try:
            from pywinauto import Desktop
        except ImportError as exc:
            raise DesktopActionError(
                "Screen reading needs the optional Windows accessibility component. "
                "Reinstall Jarvis with the current requirements."
            ) from exc

        try:
            window = Desktop(backend="uia").get_active()
            if window is None:
                raise DesktopActionError(
                    "I couldn't read the active window. Make sure the app is open and visible."
                )
            title = (window.window_text() or "").strip()[:300]
            lines: list[str] = []
            seen: set[str] = set()
            total = 0
            for control in window.descendants():
                if len(lines) >= MAX_SCREEN_LINES or total >= MAX_SCREEN_CHARS:
                    break
                info = control.element_info
                try:
                    if not control.is_visible():
                        continue
                except Exception:
                    pass
                is_password = getattr(info, "is_password", False)
                if callable(is_password):
                    try:
                        is_password = is_password()
                    except Exception:
                        is_password = False
                if is_password:
                    continue
                text = str(getattr(info, "name", "") or "").strip()
                if not text:
                    try:
                        text = str(control.window_text() or "").strip()
                    except Exception:
                        continue
                key = _normalize_phrase(text)
                if not key or key in seen:
                    continue
                seen.add(key)
                remaining = MAX_SCREEN_CHARS - total
                text = text[:remaining]
                lines.append(text)
                total += len(text) + 1
            content = "\n".join(lines).strip()
            if not content:
                raise DesktopActionError(
                    "I couldn't read any text from the active window. Open the app and try again."
                )
            return ScreenSnapshot(title=title or "Active window", text=content)
        except DesktopActionError:
            raise
        except Exception as exc:
            raise DesktopActionError(
                "I couldn't read the active window. Make sure the app is open and visible."
            ) from exc