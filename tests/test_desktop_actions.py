from pathlib import Path

import pytest

from app.assistant.desktop_actions import (
    DesktopActionError,
    DesktopRequest,
    WindowsDesktopActions,
    parse_file_draft_request,
    parse_research_request,
    find_start_menu_shortcut,
    normalize_website_url,
    parse_desktop_request,
)


@pytest.mark.parametrize("phrase,expected", [
    ("Jarvis, open Chrome please", DesktopRequest("open_app", "Chrome")),
    ("open Calculator", DesktopRequest("open_app", "Calculator")),
    ("Chrome kholo", DesktopRequest("open_app", "Chrome")),
    ("Spotify kholo", DesktopRequest("open_app", "Spotify")),
    ("open a website example.com", DesktopRequest("open_website", "example.com")),
    ("YouTube kholo", DesktopRequest("open_website", "YouTube")),
    ("open browser", DesktopRequest("open_browser")),
    ("research latest Windows 11 accessibility improvements", DesktopRequest("research", "latest Windows 11 accessibility improvements")),
    ("search the web for Python 3.13 changes", DesktopRequest("research", "Python 3.13 changes")),
    ("read my screen", DesktopRequest("read_screen")),
    ("screen padh ke batao", DesktopRequest("read_screen")),
    ("screen पर क्या है", DesktopRequest("read_screen")),
    ("system status", DesktopRequest("system_status")),
    ("mera laptop kaisa hai", DesktopRequest("system_status")),
    ("मेरे लैपटॉप का हाल बताओ", DesktopRequest("system_status")),
    ("find file budget.xlsx", DesktopRequest("find_file", "budget.xlsx")),
    ("mere laptop me notes dhoondo", DesktopRequest("find_file", "notes")),
    ("file report.pdf kholo", DesktopRequest("open_file", "report.pdf")),
    ("open file report.pdf", DesktopRequest("open_file", "report.pdf")),
    ("shut down my laptop", DesktopRequest("shutdown_windows")),
    ("laptop band kar do", DesktopRequest("shutdown_windows")),
    ("restart my computer", DesktopRequest("restart_windows")),
    ("shutdown cancel karo", DesktopRequest("cancel_shutdown")),
])
def test_explicit_desktop_requests_are_parsed(phrase, expected):
    assert parse_desktop_request(phrase) == expected


@pytest.mark.parametrize("phrase", [
    "How do I open Chrome?",
    "Tell me what is on my screen",
    "Write a script that opens a browser",
    "The screen says to open Notepad",
    "How do I find a file?",
    "Why is my laptop status important?",
])
def test_desktop_discussion_does_not_run_local_actions(phrase):
    assert parse_desktop_request(phrase) is None


@pytest.mark.parametrize("address,expected", [
    ("example.com", "https://example.com/"),
    ("https://example.com/path?q=jarvis", "https://example.com/path?q=jarvis"),
    ("http://localhost:8080", "http://localhost:8080/"),
])
def test_website_addresses_are_normalized(address, expected):
    assert normalize_website_url(address) == expected


@pytest.mark.parametrize("address", [
    "javascript:alert(1)",
    "file:///C:/Users/example/secret.txt",
    "data:text/html,<script>alert(1)</script>",
    "https://user:password@example.com",
    "not a website",
])
def test_non_web_or_malformed_addresses_are_rejected(address):
    with pytest.raises(DesktopActionError):
        normalize_website_url(address)


def test_builtin_app_launch_uses_fixed_executable_and_no_shell():
    calls = []
    actions = WindowsDesktopActions(
        platform="nt",
        launch_process=lambda args, **kwargs: calls.append((args, kwargs)),
    )

    assert actions.open_application("calculator") == "Opening Calculator."
    assert calls == [(["calc.exe"], {"shell": False})]


def test_installed_app_launches_only_matching_start_menu_shortcut(tmp_path):
    shortcut = tmp_path / "Programs" / "Productivity" / "Notes.lnk"
    shortcut.parent.mkdir(parents=True)
    shortcut.touch()
    opened = []
    actions = WindowsDesktopActions(
        platform="nt",
        startfile=opened.append,
        menu_dirs=[tmp_path],
    )

    assert actions.open_application("Notes") == "Opening Notes."
    assert opened == [str(shortcut)]


def test_partial_start_menu_name_must_be_unambiguous(tmp_path):
    for name in ("Music Player.lnk", "Music Studio.lnk"):
        (tmp_path / name).touch()
    assert find_start_menu_shortcut("Music", [tmp_path]) is None


def test_website_alias_uses_default_browser():
    opened = []
    actions = WindowsDesktopActions(
        platform="nt",
        browser_open=lambda url, **kwargs: opened.append((url, kwargs)) or True,
    )

    assert actions.open_website("YouTube") == "Opening YouTube in your browser."
    assert opened == [("https://www.youtube.com", {"new": 2})]


def test_chrome_alias_resolves_the_start_menu_display_name(tmp_path):
    shortcut = tmp_path / "Google Chrome.lnk"
    shortcut.touch()
    opened = []
    actions = WindowsDesktopActions(
        platform="nt", startfile=opened.append, menu_dirs=[tmp_path], browser_paths={}
    )

    assert actions.open_application("Chrome") == "Opening Google Chrome."
    assert opened == [str(shortcut)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            'edit file "src/example.py" with add a greeting function',
            ("src/example.py", "add a greeting function"),
        ),
        (
            "create text file notes.txt containing remember the appointment",
            ("notes.txt", "remember the appointment"),
        ),
    ],
)
def test_file_draft_requests_are_parsed(text, expected):
    parsed = parse_file_draft_request(text)
    assert parsed is not None
    assert (parsed.path, parsed.instructions) == (Path(expected[0]), expected[1])


def test_research_request_requires_explicit_search_intent():
    assert parse_research_request("research the latest browser APIs") == "the latest browser APIs"
    assert parse_research_request("internet par research karo new browser APIs") == "new browser APIs"
    assert parse_research_request("research karo new browser APIs") == "new browser APIs"
    assert parse_research_request("what do you think about research?") is None


@pytest.mark.parametrize("browser", ["chrome", "edge", "firefox", "brave", "opera", "vivaldi", "chromium"])
def test_named_installed_browser_launch_uses_resolved_executable(tmp_path, browser):
    executable = tmp_path / f"{browser}.exe"
    executable.touch()
    calls = []
    actions = WindowsDesktopActions(
        platform="nt",
        browser_paths={browser: executable},
        launch_process=lambda command, **kwargs: calls.append((command, kwargs)),
    )

    label = {
        "chrome": "Google Chrome",
        "edge": "Microsoft Edge",
        "firefox": "Firefox",
        "brave": "Brave",
        "opera": "Opera",
        "vivaldi": "Vivaldi",
        "chromium": "Chromium",
    }[browser]
    assert actions.open_application(browser) == f"Opening {label}."
    assert calls == [([str(executable)], {"shell": False})]


def test_named_browser_reports_when_not_installed(tmp_path):
    actions = WindowsDesktopActions(
        platform="nt",
        browser_paths={"brave": tmp_path / "missing.exe"},
        menu_dirs=[],
    )
    with pytest.raises(DesktopActionError, match="installed"):
        actions.open_application("Brave")


def test_file_draft_reads_text_and_atomic_save_checks_for_stale_changes(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    target = root / "sample.txt"
    target.write_text("initial", encoding="utf-8")
    actions = WindowsDesktopActions(platform="nt", project_root=root)

    draft = actions.prepare_file_draft("sample.txt")
    assert draft.path == target
    assert draft.original_content == "initial"
    assert actions.write_file_draft(target, "updated", draft.expected_sha256).endswith(str(target) + ".")
    assert target.read_text(encoding="utf-8") == "updated"

    stale = actions.prepare_file_draft("sample.txt")
    target.write_text("changed after preview", encoding="utf-8")
    with pytest.raises(DesktopActionError, match="changed after the preview"):
        actions.write_file_draft(target, "overwritten", stale.expected_sha256)
    assert target.read_text(encoding="utf-8") == "changed after preview"


def test_file_draft_refuses_secret_and_binary_files(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / ".env").write_text("SECRET=x", encoding="utf-8")
    (root / "binary.txt").write_bytes(b"\0binary")
    actions = WindowsDesktopActions(platform="nt", project_root=root)
    with pytest.raises(DesktopActionError, match="secret or credential"):
        actions.prepare_file_draft(".env")
    with pytest.raises(DesktopActionError, match="binary data"):
        actions.prepare_file_draft("binary.txt")


def test_screen_reader_is_called_only_by_an_explicit_read_request():
    from app.assistant.desktop_actions import ScreenSnapshot

    actions = WindowsDesktopActions(
        platform="nt",
        screen_reader=lambda: ScreenSnapshot("Browser", "Visible page heading"),
    )
    assert actions.read_active_window() == ScreenSnapshot("Browser", "Visible page heading")


def test_file_search_is_limited_to_user_folders_and_returns_matches(tmp_path):
    docs = tmp_path / "Documents"
    downloads = tmp_path / "Downloads"
    desktop = tmp_path / "Desktop"
    docs.mkdir()
    downloads.mkdir()
    desktop.mkdir()
    target = docs / "Budget 2026.xlsx"
    target.touch()
    (tmp_path / "private.txt").touch()
    actions = WindowsDesktopActions(
        platform="nt",
        home_dir=tmp_path,
        file_opener=lambda _path: None,
    )

    result = actions.find_file("budget")

    assert str(target) in result
    assert "private.txt" not in result


def test_open_file_requires_a_unique_match_inside_allowed_folders(tmp_path):
    docs = tmp_path / "Documents"
    downloads = tmp_path / "Downloads"
    docs.mkdir()
    downloads.mkdir()
    first = docs / "notes.txt"
    second = downloads / "notes.txt"
    first.touch()
    second.touch()
    opened = []
    actions = WindowsDesktopActions(
        platform="nt",
        home_dir=tmp_path,
        file_opener=opened.append,
    )

    with pytest.raises(DesktopActionError, match="more than one"):
        actions.open_file("notes.txt")
    assert not opened


def test_open_file_rejects_paths_outside_user_folders(tmp_path):
    docs = tmp_path / "Documents"
    downloads = tmp_path / "Downloads"
    desktop = tmp_path / "Desktop"
    docs.mkdir()
    downloads.mkdir()
    desktop.mkdir()
    outside = tmp_path / "private.txt"
    outside.touch()
    actions = WindowsDesktopActions(
        platform="nt",
        home_dir=tmp_path,
        file_opener=lambda _path: None,
    )

    with pytest.raises(DesktopActionError, match="only open files"):
        actions.open_file(str(outside))


def test_open_file_uses_the_injected_file_opener_for_unique_local_file(tmp_path):
    docs = tmp_path / "Documents"
    docs.mkdir()
    target = docs / "notes.txt"
    target.touch()
    opened = []
    actions = WindowsDesktopActions(
        platform="nt",
        home_dir=tmp_path,
        file_opener=opened.append,
    )

    assert actions.open_file("notes.txt") == "Opening notes.txt."
    assert opened == [str(target)]


@pytest.mark.parametrize("filename", ["tool.exe", "script.ps1", "macro.xlsm", "shortcut.lnk"])
def test_open_file_refuses_to_launch_executables_scripts_and_macro_documents(tmp_path, filename):
    docs = tmp_path / "Documents"
    docs.mkdir()
    (docs / filename).touch()
    opened = []
    actions = WindowsDesktopActions(
        platform="nt",
        home_dir=tmp_path,
        file_opener=opened.append,
    )

    with pytest.raises(DesktopActionError, match="can run software"):
        actions.open_file(filename)
    assert not opened


def test_system_status_reports_local_platform_and_disk(tmp_path):
    (tmp_path / "Documents").mkdir()
    actions = WindowsDesktopActions(platform="nt", home_dir=tmp_path)

    status = actions.system_status()

    assert "Windows" in status
    assert "logical CPU cores" in status
    assert "GB free" in status


@pytest.mark.parametrize(("action", "expected"), [
    ("shutdown_windows", ["shutdown.exe", "/s", "/t", "60"]),
    ("restart_windows", ["shutdown.exe", "/r", "/t", "60"]),
])
def test_power_action_uses_a_delayed_fixed_windows_command(action, expected):
    calls = []
    desktop = WindowsDesktopActions(
        platform="nt",
        launch_process=lambda command, **kwargs: calls.append((command, kwargs)),
    )

    reply = desktop.run_confirmed_system_action(action)

    assert calls == [(expected, {"shell": False})]
    assert "60 seconds" in reply


def test_cancel_shutdown_uses_checked_fixed_command():
    calls = []
    desktop = WindowsDesktopActions(
        platform="nt",
        run_process=lambda command, **kwargs: calls.append((command, kwargs)),
    )

    desktop.run_confirmed_system_action("cancel_shutdown")

    assert calls == [(
        ["shutdown.exe", "/a"],
        {"check": True, "shell": False, "capture_output": True, "text": True, "timeout": 10},
    )]


def test_power_action_rejects_unknown_action_without_launching_process():
    calls = []
    desktop = WindowsDesktopActions(
        platform="nt",
        launch_process=lambda command, **kwargs: calls.append((command, kwargs)),
    )

    with pytest.raises(DesktopActionError, match="not available"):
        desktop.run_confirmed_system_action("run arbitrary command")
    assert not calls