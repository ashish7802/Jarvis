param([string]$PackagePath = (Join-Path $PSScriptRoot 'dist\JARVIS'))
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$jarvisSource = (Resolve-Path -LiteralPath $PackagePath).Path
if (-not (Test-Path -LiteralPath (Join-Path $jarvisSource 'JARVIS.exe'))) { throw 'Build JARVIS first.' }
$jarvisPrograms = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs'))
$jarvisInstall = Join-Path $jarvisPrograms 'JARVIS'
$jarvisStage = Join-Path $jarvisPrograms ('JARVIS-update-' + [guid]::NewGuid().ToString('N'))
$jarvisPrevious = Join-Path $jarvisPrograms ('JARVIS-previous-' + [guid]::NewGuid().ToString('N'))
foreach ($jarvisCheckedPath in @($jarvisInstall, $jarvisStage, $jarvisPrevious)) {
    if (-not [IO.Path]::GetFullPath($jarvisCheckedPath).StartsWith($jarvisPrograms.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Installation paths must stay within this user''s local Programs folder.'
    }
}
$jarvisRunning = Get-Process JARVIS -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq (Join-Path $jarvisInstall 'JARVIS.exe') }
if ($jarvisRunning) { throw 'Close the installed JARVIS window before updating it.' }
New-Item -ItemType Directory -Path $jarvisPrograms -Force | Out-Null
Copy-Item -LiteralPath $jarvisSource -Destination $jarvisStage -Recurse
# Include speech models downloaded after the last executable build as well.
$jarvisModelCache = Join-Path $PSScriptRoot '.cache\whisper'
if (Test-Path -LiteralPath $jarvisModelCache) {
    $jarvisInstalledModels = Join-Path $jarvisStage '_internal\.cache\whisper'
    New-Item -ItemType Directory -Path $jarvisInstalledModels -Force | Out-Null
    Get-ChildItem -LiteralPath $jarvisModelCache -Directory -Filter 'models--*' | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $jarvisInstalledModels -Recurse -Force
    }
}
if (Test-Path -LiteralPath (Join-Path $jarvisInstall '.env')) {
    Copy-Item -LiteralPath (Join-Path $jarvisInstall '.env') -Destination (Join-Path $jarvisStage '.env') -Force
}
if (Test-Path -LiteralPath $jarvisInstall) { Move-Item -LiteralPath $jarvisInstall -Destination $jarvisPrevious }
try {
    Move-Item -LiteralPath $jarvisStage -Destination $jarvisInstall
} catch {
    if ((Test-Path -LiteralPath $jarvisPrevious) -and -not (Test-Path -LiteralPath $jarvisInstall)) {
        Move-Item -LiteralPath $jarvisPrevious -Destination $jarvisInstall
    }
    throw
}
$jarvisPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $jarvisPython -m app.system.startup --install --target (Join-Path $jarvisInstall 'JARVIS.exe')
if ($LASTEXITCODE -ne 0) { throw 'The app was copied, but Windows startup registration failed.' }
$jarvisMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\JARVIS.lnk'
$jarvisMenuLink = (New-Object -ComObject WScript.Shell).CreateShortcut($jarvisMenu)
$jarvisMenuLink.TargetPath = Join-Path $jarvisInstall 'JARVIS.exe'
$jarvisMenuLink.WorkingDirectory = $jarvisInstall
$jarvisMenuLink.WindowStyle = 1
$jarvisMenuLink.IconLocation = $jarvisMenuLink.TargetPath
$jarvisMenuLink.Save()
Write-Output "Installed: $jarvisInstall\JARVIS.exe"
