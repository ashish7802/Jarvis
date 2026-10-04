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
import platform
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unicodedata
import webbrowser
from urllib.parse import parse_qs, urlsplit, urlunsplit
import hashlib


MAX_SCREEN_CHARS = 12_000
MAX_SCREEN_LINES = 180
MAX_FILE_SEARCH_RESULTS = 5
MAX_FILE_SEARCH_DIRS = 2500
FILE_SEARCH_SECONDS = 2.0
MAX_EDIT_FILE_BYTES = 64 * 1024
EDITABLE_FILE_SUFFIXES = {
    ".c", ".cc", ".cpp", ".cs", ".css", ".csv", ".go", ".h", ".hpp", ".html",
    ".ini", ".java", ".js", ".json", ".jsx", ".kt", ".log", ".md", ".php",
    ".py", ".pyi", ".rb", ".rs", ".scss", ".sql", ".svg", ".swift", ".toml",
    ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}
EXECUTABLE_FILE_SUFFIXES = {
    ".bat", ".cmd", ".com", ".cpl", ".dll", ".docm", ".exe", ".hta", ".inf",
    ".jar", ".js", ".jse", ".lnk", ".msi", ".msp", ".potm", ".ppam", ".pptm",
    ".ps1", ".psm1", ".py", ".pyw", ".reg", ".scr", ".url", ".vbe", ".vbs",
    ".wsf", ".wsh", ".xlam", ".xlsm", ".xltm", ".dotm",
}

WEBSITE_ALIASES = {
    "google": ("https://www.google.com", "Google"),
    "youtube": ("https://www.youtube.com", "YouTube"),
    "github": ("https://github.com", "GitHub"),
    "gmail": ("https://mail.google.com", "Gmail"),
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


@dataclass(frozen=True)
class FileDraftRequest:
    path: Path
    instructions: str


@dataclass(frozen=True)
class FileDraft:
    path: Path
    original_content: str
    expected_sha256: str | None


_FILE_DRAFT = re.compile(
    r"^(?:please\s+)?(?:create|write|edit|update)\s+(?:a\s+)?"
    r"(?:text\s+|code\s+)?file\s+"
    r"(?:\"([^\"]+)\"|'([^']+)'|(.+?))\s+"
    r"(?:with|containing|that says)\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_RESEARCH = re.compile(
    r"^(?:research\s+karo|search\s+karo|web\s+par\s+search\s+karo|"
    r"internet\s+par\s+(?:search|research|dhoondo)\s+karo|"
    r"research(?:\s+about)?|search(?:\s+the)?\s+web\s+for|"
    r"look\s+up|find\s+current\s+information\s+about)\s+(.+)$",
    re.IGNORECASE,
)


def parse_file_draft_request(text: str) -> FileDraftRequest | None:
    match = _FILE_DRAFT.fullmatch(text.strip())
    if not match:
        return None
    path = next((part for part in match.groups()[:3] if part is not None), "").strip()
    instructions = match.group(4).strip()
    if not path or not instructions:
        return None
    return FileDraftRequest(Path(path).expanduser(), instructions)


def parse_research_request(text: str) -> str | None:
    match = _RESEARCH.fullmatch(text.strip())
    if not match:
        return None
    query = match.group(1).strip()
    if not query or len(query) > 300 or any(ord(char) < 32 for char in query):
        return None
    return query


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
_FIND_FILE = re.compile(
    r"^(?:find|search for|locate|dhoondo|dhundho|ढूंढो|ढूँढो|खोजो)\s+"
    r"(?:(?:the|my|a)\s+)?(?:file\s+)?(.+)$",
    re.IGNORECASE,
)
_FIND_FILE_HINGLISH = re.compile(
    r"^(?:mere|my)\s+(?:laptop|computer|pc)(?:\s+(?:me|mein|on))?\s+"
    r"(.+?)\s+(?:dhoondo|dhundho|ढूंढो|ढूँढो|खोजो)$",
    re.IGNORECASE,
)
_FILE_OPEN = re.compile(
    r"^(?:open|launch|khol|kholo|खोलो|खोल\s+दो)\s+"
    r"(?:the\s+)?file\s+(.+)$",
    re.IGNORECASE,
)
_FILE_OPEN_SUFFIX = re.compile(
    r"^file\s+(.+?)\s+(?:khol|kholo|खोलो|खोल\s+दो)$",
    re.IGNORECASE,
)
_LOCAL_STATUS_PHRASES = {
    "system status", "show system status", "show system info", "system information",
    "laptop status", "how is my laptop", "check my laptop", "mera laptop kaisa hai",
    "laptop ki halat batao", "system ki halat batao", "मेरे लैपटॉप का हाल बताओ",
    "लैपटॉप की स्थिति बताओ", "सिस्टम की जानकारी दो",
}
_POWER_ACTIONS = {
    "shutdown_windows": (
        "shutdown", "shut down", "shut down my laptop", "shutdown my computer",
        "turn off my laptop", "turn off my computer", "laptop band karo",
        "laptop band kar do", "computer band karo", "pc band kar do",
        "लैपटॉप बंद करो", "कंप्यूटर बंद करो",
    ),
    "restart_windows": (
        "restart", "restart my laptop", "restart my computer", "reboot my laptop",
        "laptop restart karo", "computer restart karo", "laptop dobara chalao",
        "लैपटॉप रीस्टार्ट करो", "कंप्यूटर रीस्टार्ट करो",
    ),
    "cancel_shutdown": (
        "cancel shutdown", "abort shutdown", "shutdown cancel karo",
        "shutdown rok do", "शटडाउन रोक दो", "शटडाउन रद्द करो",
    ),
}


def parse_desktop_request(text: str) -> DesktopRequest | None:
    """Recognize only short, explicit local system requests."""
    value = text.strip()
    value = re.sub(r"^(?:(?:hey\s+)?jarvis)\s*[,!:]?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^(?:please|can you|could you|would you)\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+please[.!?]*$", "", value, flags=re.IGNORECASE).strip()

    normalized = _normalize_phrase(value)
    if parse_research_request(value) is not None:
        return DesktopRequest("research", parse_research_request(value) or "")
    if normalized in _READ_SCREEN_PHRASES:
        return DesktopRequest("read_screen")
    if normalized in {_normalize_phrase(item) for item in _LOCAL_STATUS_PHRASES}:
        return DesktopRequest("system_status")
    for action, phrases in _POWER_ACTIONS.items():
        if normalized in {_normalize_phrase(item) for item in phrases}:
            return DesktopRequest(action)
    if normalized in {"open browser", "launch browser", "start browser", "browser kholo"}:
        return DesktopRequest("open_browser")

    match = _FILE_OPEN.fullmatch(value) or _FILE_OPEN_SUFFIX.fullmatch(value)
    if match:
        target = _clean_target(match.group(1))
        return DesktopRequest("open_file", target) if target else None

    match = _FIND_FILE.fullmatch(value) or _FIND_FILE_HINGLISH.fullmatch(value)
    if match:
        target = _clean_target(match.group(1))
        if target and len(target) <= 180:
            return DesktopRequest("find_file", target)

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
    """Perform bounded local actions and read opt-in text from the active window."""

    def __init__(
        self,
        *,
        platform: str | None = None,
        startfile=None,
        launch_process=None,
        run_process=None,
        browser_open=None,
        menu_dirs: list[Path] | None = None,
        screen_reader=None,
        file_opener=None,
        home_dir: Path | None = None,
        project_root: Path | None = None,
        browser_paths: dict[str, Path] | None = None,
    ):
        self.platform = platform or os.name
        self.startfile = startfile if startfile is not None else getattr(os, "startfile", None)
        self.launch_process = launch_process or subprocess.Popen
        self.run_process = run_process or subprocess.run
        self.browser_open = browser_open or webbrowser.open
        self.menu_dirs = menu_dirs
        self.screen_reader = screen_reader
        self.file_opener = file_opener if file_opener is not None else self.startfile
        self.home_dir = Path(home_dir) if home_dir is not None else Path.home()
        self.project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )
        self.browser_paths = browser_paths

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

        browser_alias = {
            "chrome": "chrome", "google chrome": "chrome",
            "edge": "edge", "microsoft edge": "edge", "ms edge": "edge",
            "firefox": "firefox", "mozilla firefox": "firefox",
            "brave": "brave", "brave browser": "brave",
            "opera": "opera", "opera gx": "opera",
            "vivaldi": "vivaldi", "chromium": "chromium",
        }.get(normalized)
        if browser_alias:
            executable = self._find_browser(browser_alias)
            if executable is not None:
                try:
                    self.launch_process([str(executable)], shell=False)
                except OSError as exc:
                    raise DesktopActionError(
                        f"I couldn't open {target}. Check that it is installed."
                    ) from exc
                browser_label = {
                    "chrome": "Google Chrome",
                    "edge": "Microsoft Edge",
                    "firefox": "Firefox",
                    "brave": "Brave",
                    "opera": "Opera",
                    "vivaldi": "Vivaldi",
                    "chromium": "Chromium",
                }[browser_alias]
                return f"Opening {browser_label}."

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

    def _find_browser(self, browser: str) -> Path | None:
        if self.browser_paths is not None:
            candidate = self.browser_paths.get(browser)
            return candidate if candidate is not None and candidate.is_file() else None
        executable_names = {
            "chrome": "chrome.exe",
            "edge": "msedge.exe",
            "firefox": "firefox.exe",
            "brave": "brave.exe",
            "opera": "opera.exe",
            "vivaldi": "vivaldi.exe",
            "chromium": "chrome.exe",
        }
        app_path = (
            None if browser == "chromium"
            else self._registered_app_path(executable_names[browser])
        )
        if app_path is not None and app_path.is_file():
            return app_path
        roots = [
            Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")),
            Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")),
            Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))),
        ]
        relative_paths = {
            "chrome": (Path("Google/Chrome/Application/chrome.exe"),),
            "edge": (Path("Microsoft/Edge/Application/msedge.exe"),),
            "firefox": (Path("Mozilla Firefox/firefox.exe"),),
            "brave": (Path("BraveSoftware/Brave-Browser/Application/brave.exe"),),
            "opera": (Path("Programs/Opera/launcher.exe"), Path("Programs/Opera/opera.exe")),
            "vivaldi": (Path("Vivaldi/Application/vivaldi.exe"),),
            "chromium": (Path("Chromium/Application/chrome.exe"),),
        }
        for root in roots:
            for relative in relative_paths[browser]:
                candidate = root / relative
                if candidate.is_file():
                    return candidate
        return None

    @staticmethod
    def _registered_app_path(executable: str) -> Path | None:
        if os.name != "nt":
            return None
        import winreg

        key_path = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{executable}"
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    value, _ = winreg.QueryValueEx(key, None)
                return Path(value.strip('"'))
            except OSError:
                continue
        return None

    def prepare_file_draft(self, target: str | Path) -> FileDraft:
        self._require_windows()
        path = self._validate_editable_path(target)
        if not path.parent.is_dir():
            raise DesktopActionError("The folder doesn't exist. I won't create folders without a separate request.")
        if not path.exists():
            return FileDraft(path, "", None)
        if not path.is_file() or path.is_symlink():
            raise DesktopActionError("I can only draft edits for a regular text file, not a link or folder.")
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise DesktopActionError(f"I couldn't read that file: {exc}") from exc
        if len(raw) > MAX_EDIT_FILE_BYTES:
            raise DesktopActionError("That file is over 64 KB. I won't send its contents for an AI edit.")
        if b"\0" in raw:
            raise DesktopActionError("That file appears to contain binary data; I won't edit it as text.")
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise DesktopActionError("That file isn't valid UTF-8 text; I won't rewrite it.") from exc
        return FileDraft(path, content, hashlib.sha256(raw).hexdigest())

    def write_file_draft(
        self,
        target: str | Path,
        content: str,
        expected_sha256: str | None,
    ) -> str:
        self._require_windows()
        path = self._validate_editable_path(target)
        if not path.parent.is_dir():
            raise DesktopActionError("The destination folder no longer exists.")
        if len(content.encode("utf-8")) > MAX_EDIT_FILE_BYTES or "\0" in content:
            raise DesktopActionError("The proposed text is too large or contains invalid binary data.")
        if path.exists():
            if not path.is_file() or path.is_symlink():
                raise DesktopActionError("The destination is no longer a regular file.")
            try:
                current = path.read_bytes()
            except OSError as exc:
                raise DesktopActionError(f"I couldn't verify the current file: {exc}") from exc
            if expected_sha256 is None or hashlib.sha256(current).hexdigest() != expected_sha256:
                raise DesktopActionError("That file changed after the preview. Draft it again before saving.")
        elif expected_sha256 is not None:
            raise DesktopActionError("That file was removed after the preview. Draft it again before saving.")

        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".jarvis-", suffix=".tmp", dir=path.parent, delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(content.encode("utf-8"))
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, path)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise DesktopActionError(f"I couldn't save the approved draft: {exc}") from exc
        return f"Saved the approved draft to {path}."

    def _validate_editable_path(self, target: str | Path) -> Path:
        value = str(target).strip()
        if not value or len(value) > 1024 or any(ord(char) < 32 for char in value):
            raise DesktopActionError("Give me one valid text-file path.")
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = self.project_root / candidate
        if candidate.is_symlink():
            raise DesktopActionError("I won't edit a symbolic link.")
        try:
            path = candidate.resolve(strict=False)
        except OSError as exc:
            raise DesktopActionError("I couldn't resolve that destination path.") from exc
        name = path.name.casefold()
        if (name.startswith(".env") or any(word in name for word in ("secret", "credential", "password", "private_key"))
                or name in {"id_rsa", "id_ed25519", "known_hosts"}):
            raise DesktopActionError("That filename looks like a secret or credential file; I won't read or edit it.")
        if path.suffix.casefold() not in EDITABLE_FILE_SUFFIXES:
            raise DesktopActionError("I can only draft plain-text and source-code file types.")
        if path.exists() and path.is_symlink():
            raise DesktopActionError("I won't edit a symbolic link.")
        return path

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

    def _file_roots(self) -> list[Path]:
        roots = []
        for name in ("Desktop", "Documents", "Downloads"):
            root = self.home_dir / name
            if root.is_dir():
                roots.append(root.resolve())
        return roots

    def _find_files(self, query: str, *, exact: bool = False) -> list[Path]:
        wanted = query.strip().strip("\"'").casefold()
        if not wanted or len(wanted) > 180 or any(char in wanted for char in "\\/:*?<>|"):
            raise DesktopActionError("Give me a file name, not a path or wildcard.")
        roots = self._file_roots()
        if not roots:
            raise DesktopActionError("I couldn't find your Desktop, Documents, or Downloads folders.")

        found: list[Path] = []
        visited = 0
        deadline = time.monotonic() + FILE_SEARCH_SECONDS
        for root in roots:
            for current, directories, files in os.walk(root, followlinks=False):
                visited += 1
                if visited > MAX_FILE_SEARCH_DIRS or time.monotonic() > deadline:
                    return found
                directories[:] = [
                    name for name in directories
                    if not name.startswith(".") and name.casefold() not in {
                        "node_modules", "__pycache__", "$recycle.bin"
                    }
                ]
                for name in files:
                    candidate = name.casefold()
                    matches = candidate == wanted if exact else wanted in candidate
                    if matches:
                        found.append(Path(current) / name)
                        if len(found) >= MAX_FILE_SEARCH_RESULTS:
                            return found
        return found

    def find_file(self, query: str) -> str:
        self._require_windows()
        files = self._find_files(query)
        if not files:
            return f"I couldn't find a file matching {query!r} in Desktop, Documents, or Downloads."
        locations = "; ".join(str(path) for path in files)
        suffix = f" Showing up to {MAX_FILE_SEARCH_RESULTS} results." if len(files) == MAX_FILE_SEARCH_RESULTS else ""
        return f"I found {len(files)} matching file(s): {locations}.{suffix}"

    def open_file(self, query: str) -> str:
        self._require_windows()
        self._validate_file_query(query)
        candidate = Path(query.strip().strip("\"'")).expanduser()
        roots = self._file_roots()
        if candidate.is_absolute():
            try:
                resolved = candidate.resolve(strict=True)
            except OSError as exc:
                raise DesktopActionError("I couldn't find that file.") from exc
            if not any(resolved.is_relative_to(root) for root in roots):
                raise DesktopActionError(
                    "For safety, I can only open files in Desktop, Documents, or Downloads."
                )
            if not resolved.is_file():
                raise DesktopActionError("That path isn't a file.")
            matches = [resolved]
        else:
            matches = self._find_files(query, exact=True)
            matches = [
                path.resolve(strict=True)
                for path in matches
                if path.is_file() and any(path.resolve().is_relative_to(root) for root in roots)
            ]
        if not matches:
            raise DesktopActionError(
                f"I couldn't find {query!r} in Desktop, Documents, or Downloads."
            )
        if len(matches) > 1:
            choices = "; ".join(str(path) for path in matches[:3])
            raise DesktopActionError(
                f"I found more than one matching file. Please say a more specific name: {choices}."
            )
        if matches[0].suffix.casefold() in EXECUTABLE_FILE_SUFFIXES:
            raise DesktopActionError(
                "That file can run software, scripts, or macros. I won't launch it as a document. "
                "Open an installed app by its name instead."
            )
        if self.file_opener is None:
            raise DesktopActionError("Opening local files is available in the Windows desktop app only.")
        self.file_opener(str(matches[0]))
        return f"Opening {matches[0].name}."

    @staticmethod
    def _validate_file_query(query: str) -> None:
        if (not query.strip() or len(query) > 260
                or any(ord(char) < 32 for char in query)):
            raise DesktopActionError("Give me one clear file name or a path under Desktop, Documents, or Downloads.")

    def system_status(self) -> str:
        self._require_windows()
        home_usage = shutil.disk_usage(self.home_dir)
        free_gb = home_usage.free / (1024 ** 3)
        total_gb = home_usage.total / (1024 ** 3)
        status = (
            f"Your system is running {platform.system()} {platform.release()} "
            f"on {os.cpu_count() or 'an unknown number of'} logical CPU cores. "
            f"The system drive has {free_gb:.1f} GB free out of {total_gb:.1f} GB."
        )
        try:
            import ctypes
            from ctypes import wintypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            memory = MemoryStatus()
            memory.dwLength = ctypes.sizeof(memory)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
                available = memory.ullAvailPhys / (1024 ** 3)
                total = memory.ullTotalPhys / (1024 ** 3)
                status += f" {available:.1f} GB of {total:.1f} GB RAM is available."
        except (AttributeError, OSError):
            pass
        return status

    def run_confirmed_system_action(self, action: str) -> str:
        self._require_windows()
        commands = {
            "shutdown_windows": ["shutdown.exe", "/s", "/t", "60"],
            "restart_windows": ["shutdown.exe", "/r", "/t", "60"],
            "cancel_shutdown": ["shutdown.exe", "/a"],
        }
        command = commands.get(action)
        if command is None:
            raise DesktopActionError("That system action is not available.")
        if action == "cancel_shutdown":
            try:
                self.run_process(
                    command, check=True, shell=False, capture_output=True,
                    text=True, timeout=10,
                )
            except subprocess.CalledProcessError as exc:
                raise DesktopActionError(
                    "Windows did not report a pending shutdown or restart to cancel."
                ) from exc
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise DesktopActionError("Windows could not cancel the pending shutdown.") from exc
            return "I asked Windows to cancel the pending shutdown or restart."
        try:
            self.launch_process(command, shell=False)
        except OSError as exc:
            raise DesktopActionError(
                f"Windows could not start the requested system action: {exc}"
            ) from exc
        if action == "shutdown_windows":
            return "Windows shutdown is scheduled in 60 seconds. Say cancel shutdown to stop it."
        return "Windows restart is scheduled in 60 seconds. Say cancel shutdown to stop it."

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