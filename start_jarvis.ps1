$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$jarvisExe = Join-Path $env:LOCALAPPDATA 'Programs\JARVIS\JARVIS.exe'
if (-not (Test-Path -LiteralPath $jarvisExe)) {
    $jarvisExe = Join-Path $PSScriptRoot 'dist\JARVIS\JARVIS.exe'
}
# The desktop shows initialization progress and recoverable errors itself.
# Do not load the speech models twice or hide the requested application window.
if (Test-Path -LiteralPath $jarvisExe) {
    $jarvisDirectory = Split-Path -Parent $jarvisExe
    $env:JARVIS_ENV_FILE = Join-Path $jarvisDirectory '.env'
    Start-Process -FilePath $jarvisExe -WorkingDirectory $jarvisDirectory
} else {
    $env:JARVIS_ENV_FILE = Join-Path $PSScriptRoot '.env'
    Start-Process -FilePath (Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe') -ArgumentList '-m','app.main' -WorkingDirectory $PSScriptRoot
}
Write-Host 'JARVIS desktop is opening. Say "hey Jarvis" or click the core.'
