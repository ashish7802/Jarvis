from pathlib import Path

import pytest

from app.assistant.desktop_actions import (
    DesktopActionError,
    DesktopRequest,
    WindowsDesktopActions,
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
    ("read my screen", DesktopRequest("read_screen")),
    ("screen padh ke batao", DesktopRequest("read_screen")),
    ("screen पर क्या है", DesktopRequest("read_screen")),
])
def test_explicit_desktop_requests_are_parsed(phrase, expected):
    assert parse_desktop_request(phrase) == expected


@pytest.mark.parametrize("phrase", [
    "How do I open Chrome?",
    "Tell me what is on my screen",
    "Write a script that opens a browser",
    "The screen says to open Notepad",
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
    actions = WindowsDesktopActions(platform="nt", startfile=opened.append, menu_dirs=[tmp_path])

    assert actions.open_application("Chrome") == "Opening Google Chrome."
    assert opened == [str(shortcut)]


def test_screen_reader_is_called_only_by_an_explicit_read_request():
    from app.assistant.desktop_actions import ScreenSnapshot

    actions = WindowsDesktopActions(
        platform="nt",
        screen_reader=lambda: ScreenSnapshot("Browser", "Visible page heading"),
    )
    assert actions.read_active_window() == ScreenSnapshot("Browser", "Visible page heading")