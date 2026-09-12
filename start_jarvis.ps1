$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:JARVIS_ENV_FILE = Join-Path $PSScriptRoot '.env'
$jarvisPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$jarvisExe = Join-Path $PSScriptRoot 'dist\JARVIS\JARVIS.exe'
if (Test-Path -LiteralPath $jarvisExe) {
    $jarvisCheckLog = Join-Path $env:APPDATA 'JARVIS\logs\jarvis.log'
    $jarvisCheck = Start-Process -FilePath $jarvisExe -ArgumentList '--check' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -Wait -PassThru
    $jarvisCheckCode = $jarvisCheck.ExitCode
} else {
    $jarvisCheckLog = Join-Path $PSScriptRoot 'logs\jarvis.log'
    & $jarvisPython -m app.main --check
    $jarvisCheckCode = $LASTEXITCODE
}
if ($jarvisCheckCode -ne 0) {
    Write-Host "JARVIS could not start. Check .env and $jarvisCheckLog"
    Read-Host 'Press Enter to close'
    exit 1
}
if (Test-Path -LiteralPath $jarvisExe) {
    Start-Process -FilePath $jarvisExe -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
} else {
    Start-Process -FilePath (Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe') -ArgumentList '-m','app.main' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
}
Write-Host 'JARVIS is starting. Say "hey Jarvis" after the greeting. Ctrl+Shift+J stops it.'
