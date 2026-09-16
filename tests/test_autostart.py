import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.system.autostart import task_xml, install_task, _quote

NS = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}


def test_login_and_unlock_launch_visible_app_as_only_current_user(tmp_path):
    target = tmp_path / "JARVIS" / "JARVIS.exe"
    sid = "S-1-5-21-1234-1001"
    root = ET.fromstring(task_xml(target, sid))
    login = root.find("t:Triggers/t:LogonTrigger", NS)
    unlock = root.find("t:Triggers/t:SessionStateChangeTrigger", NS)
    assert login.find("t:UserId", NS).text == sid
    assert unlock.find("t:UserId", NS).text == sid
    assert unlock.find("t:StateChange", NS).text == "SessionUnlock"
    assert root.find(".//t:LogonType", NS).text == "InteractiveToken"
    assert root.find(".//t:RunLevel", NS).text == "LeastPrivilege"
    assert root.find(".//t:Command", NS).text == str(target.resolve())
    assert root.find(".//t:WorkingDirectory", NS).text == str(target.resolve().parent)


def test_laptop_startup_has_no_battery_network_or_runtime_limit(tmp_path):
    root = ET.fromstring(task_xml(tmp_path / "JARVIS.exe", "S-1-5-21-1001"))
    for tag in ("DisallowStartIfOnBatteries", "StopIfGoingOnBatteries", "RunOnlyIfNetworkAvailable"):
        assert root.find(f"t:Settings/t:{tag}", NS).text == "false"
    assert root.find("t:Settings/t:ExecutionTimeLimit", NS).text == "PT0S"
    assert root.find("t:Settings/t:Priority", NS).text == "4"
    assert root.find("t:Settings/t:RestartOnFailure/t:Count", NS).text == "3"


def test_xml_and_powershell_paths_preserve_spaces_quotes_and_ampersands(tmp_path):
    target = tmp_path / "Ashish's & Jarvis" / "JARVIS.exe"
    root = ET.fromstring(task_xml(target, "S-1-5-21-1001"))
    assert root.find(".//t:Command", NS).text == str(target.resolve())
    assert _quote("Ashish's & Jarvis") == "'Ashish''s & Jarvis'"


def test_missing_executable_never_registers_a_broken_login_task(tmp_path, monkeypatch):
    monkeypatch.setattr("app.system.autostart._powershell", lambda code: pytest.fail("Windows was changed"))
    with pytest.raises(FileNotFoundError):
        install_task(tmp_path / "missing.exe")
