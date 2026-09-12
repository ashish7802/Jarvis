$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$jarvisPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $jarvisPython)) {
    throw 'Create the .venv and install requirements first (see README.md).'
}
if (Test-Path -LiteralPath '.cache\runtime') {
    # PyInstaller uses isolated Python subprocesses to inspect native packages.
    # Give those processes the same DLL search directory as app/__init__.py.
    Set-Content -LiteralPath '.venv\Lib\site-packages\jarvis_runtime.pth' -Value 'import os, sys; sys._jarvis_runtime_dlls = os.add_dll_directory(os.path.abspath(os.path.join(sys.prefix, "..", ".cache", "runtime")))'
}
& $jarvisPython -m app.setup_models
if ($LASTEXITCODE -ne 0) { throw 'Speech model setup failed.' }
$jarvisBuildArgs = @(
    '--noconfirm', '--noconsole', '--name', 'JARVIS', '--paths', '.',
    '--collect-all', 'faster_whisper', '--collect-all', 'ctranslate2',
    '--collect-all', 'edge_tts', '--collect-all', 'sounddevice',
    '--collect-all', 'soundfile', '--collect-all', 'openwakeword',
    '--collect-all', 'onnxruntime', '--collect-all', 'google.genai',
    '--copy-metadata', 'google-genai', '--hidden-import', 'keyboard',
    '--add-data', '.cache\whisper;.cache\whisper'
)
# Build into a fresh folder. PyInstaller's in-place cleanup can fail on
# OneDrive's read-only directories and would leave a half-deleted installation.
$jarvisStage = Join-Path $PSScriptRoot ('build\package-' + [guid]::NewGuid().ToString('N'))
$jarvisBuildArgs += @('--distpath', $jarvisStage)
if (Test-Path -LiteralPath '.cache\runtime') {
    $jarvisBuildArgs += @('--add-binary', '.cache\runtime\*.dll;.cache\runtime')
}
$jarvisBuildArgs += 'app\main.py'
$jarvisPackagedEnv = if (Test-Path -LiteralPath 'dist\JARVIS\.env') {
    [System.IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'dist\JARVIS\.env'))
} else { $null }
& $jarvisPython -c 'import app; import PyInstaller.__main__; PyInstaller.__main__.run()' @jarvisBuildArgs
if ($LASTEXITCODE -ne 0) { throw 'JARVIS build failed.' }
$jarvisStagedApp = Join-Path $jarvisStage 'JARVIS'
$jarvisDestination = Join-Path $PSScriptRoot 'dist\JARVIS'
$jarvisPrevious = Join-Path $PSScriptRoot ('.cache\previous-build-' + [guid]::NewGuid().ToString('N'))
$jarvisWorkspacePrefix = [System.IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\') + '\'
foreach ($jarvisMovePath in @($jarvisStagedApp, $jarvisDestination, $jarvisPrevious)) {
    if (-not [System.IO.Path]::GetFullPath($jarvisMovePath).StartsWith($jarvisWorkspacePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Package path must stay within the JARVIS workspace.'
    }
}
if (-not (Test-Path -LiteralPath (Join-Path $jarvisStagedApp 'JARVIS.exe'))) {
    throw 'Build did not produce JARVIS.exe.'
}
if (Test-Path -LiteralPath $jarvisDestination) {
    Move-Item -LiteralPath $jarvisDestination -Destination $jarvisPrevious
}
try {
    New-Item -ItemType Directory -Force (Join-Path $PSScriptRoot 'dist') | Out-Null
    Move-Item -LiteralPath $jarvisStagedApp -Destination $jarvisDestination
} catch {
    if ((Test-Path -LiteralPath $jarvisPrevious) -and -not (Test-Path -LiteralPath $jarvisDestination)) {
        Move-Item -LiteralPath $jarvisPrevious -Destination $jarvisDestination
    }
    throw
}
# Keep credentials external and preserve any existing packaged configuration.
if ($null -ne $jarvisPackagedEnv) {
    [System.IO.File]::WriteAllBytes((Join-Path $PSScriptRoot 'dist\JARVIS\.env'), [byte[]]$jarvisPackagedEnv)
} elseif (-not (Test-Path -LiteralPath 'dist\JARVIS\.env')) {
    $jarvisEnvSource = if (Test-Path -LiteralPath '.env') { '.env' } else { '.env.example' }
    Copy-Item -LiteralPath $jarvisEnvSource -Destination 'dist\JARVIS\.env'
}
Write-Output "Built: $PSScriptRoot\dist\JARVIS\JARVIS.exe"
