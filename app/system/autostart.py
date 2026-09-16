"""Visible per-user launches at sign-in and unlock, using Windows Task Scheduler.

InteractiveToken keeps the GUI on the user's desktop without storing a password.
https://learn.microsoft.com/en-us/windows/win32/taskschd/sessionstatechangetrigger
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET


def _powershell(code):
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new(); " + code],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if completed.returncode:
        raise RuntimeError("Windows startup registration failed: " + completed.stderr.strip())
    return completed.stdout.strip()


def _quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def current_sid():
    if os.name != "nt":
        raise RuntimeError("Windows auto-start is only available on Windows")
    return _powershell("[Security.Principal.WindowsIdentity]::GetCurrent().User.Value")


def task_name(sid):
    return "JARVIS Desktop - " + sid


def task_xml(target, sid):
    target = Path(target).resolve()
    root = ET.Element("Task", version="1.2", xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task")
    def child(parent, tag, text=None, **attributes):
        element = ET.SubElement(parent, tag, attributes)
        element.text = text
        return element
    info = child(root, "RegistrationInfo")
    child(info, "Description", "Open the JARVIS voice assistant at sign-in and when this user unlocks Windows.")
    triggers = child(root, "Triggers")
    login = child(triggers, "LogonTrigger")
    child(login, "Enabled", "true")
    child(login, "Delay", "PT10S")
    child(login, "UserId", sid)
    unlock = child(triggers, "SessionStateChangeTrigger")
    child(unlock, "Enabled", "true")
    child(unlock, "Delay", "PT3S")
    child(unlock, "UserId", sid)
    child(unlock, "StateChange", "SessionUnlock")
    principals = child(root, "Principals")
    principal = child(principals, "Principal", id="CurrentUser")
    child(principal, "UserId", sid)
    child(principal, "LogonType", "InteractiveToken")
    child(principal, "RunLevel", "LeastPrivilege")
    settings = child(root, "Settings")
    for key, value in {
        "MultipleInstancesPolicy": "IgnoreNew", "DisallowStartIfOnBatteries": "false",
        "StopIfGoingOnBatteries": "false", "StartWhenAvailable": "true",
        "RunOnlyIfNetworkAvailable": "false", "AllowStartOnDemand": "true",
        # Task Scheduler defaults to background CPU/I/O/memory priority.
        # A voice UI needs the normal priority of an interactive desktop app.
        "Enabled": "true", "ExecutionTimeLimit": "PT0S", "Priority": "4",
    }.items():
        child(settings, key, value)
    restart = child(settings, "RestartOnFailure")
    child(restart, "Interval", "PT1M")
    child(restart, "Count", "3")
    actions = child(root, "Actions", Context="CurrentUser")
    action = child(actions, "Exec")
    child(action, "Command", str(target))
    child(action, "Arguments", "--autostart")
    child(action, "WorkingDirectory", str(target.parent))
    return ET.tostring(root, encoding="unicode")


def install_task(target):
    target = Path(target).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"JARVIS executable not found: {target}")
    sid = current_sid()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", encoding="utf-8", delete=False) as file:
        file.write(task_xml(target, sid))
        xml_path = Path(file.name)
    try:
        _powershell(
            "$service=New-Object -ComObject Schedule.Service; $service.Connect(); "
            "$folder=$service.GetFolder('\\'); "
            f"$xml=[IO.File]::ReadAllText({_quote(xml_path)}); "
            f"$null=$folder.RegisterTask({_quote(task_name(sid))}, $xml, 6, {_quote(sid)}, $null, 3, $null)"
        )
    finally:
        xml_path.unlink(missing_ok=True)
    return status(sid)


def status(sid=None):
    name = task_name(sid or current_sid())
    output = _powershell(
        "$service=New-Object -ComObject Schedule.Service; $service.Connect(); "
        f"$task=@($service.GetFolder('\\').GetTasks(1) | Where-Object {{$_.Name -eq {_quote(name)}}}); "
        "if ($task.Count -eq 0) { '{\"installed\":false}' } else { "
        "$task=$task[0]; [pscustomobject]@{installed=$true; name=$task.Name; enabled=$task.Enabled; "
        "state=$task.State; last_result=$task.LastTaskResult; last_run=$task.LastRunTime.ToString('s'); "
        "target=$task.Definition.Actions.Item(1).Path; arguments=$task.Definition.Actions.Item(1).Arguments; "
        "xml=$task.Xml} | ConvertTo-Json -Compress }"
    )
    return json.loads(output)


def uninstall_task():
    info = status()
    if info.get("installed"):
        _powershell("$service=New-Object -ComObject Schedule.Service; $service.Connect(); "
                    f"$service.GetFolder('\\').DeleteTask({_quote(info['name'])},0)")


def run_task():
    name = task_name(current_sid())
    _powershell("$service=New-Object -ComObject Schedule.Service; $service.Connect(); "
                f"$null=$service.GetFolder('\\').GetTask({_quote(name)}).Run($null)")
