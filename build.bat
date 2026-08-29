@echo off
REM Build a no-console JARVIS.exe using PyInstaller.
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install --upgrade pip
) else (
    call .venv\Scripts\activate.bat
)

echo Installing requirements + pyinstaller...
pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements.
    exit /b 1
)
pip install pyinstaller
if errorlevel 1 (
    echo Failed to install pyinstaller.
    exit /b 1
)

REM Pre-fetch openwakeword assets so PyInstaller can bundle them.
REM openwakeword v0.6.0 ships the model paths but no resources/ tree;
REM the assets are downloaded from the openwakeword GitHub release on
REM first Model() init, so we trigger that here before freezing.
echo Pre-fetching openwakeword models ...
python -c "from openwakeword.utils import download_models; download_models(model_names=['hey_jarvis_v0.1'])" >nul
if errorlevel 1 (
    echo WARNING: failed to pre-fetch openwakeword models.
    echo          The packaged EXE will try to fetch them on first run.
)

if not exist .env (
    copy .env.example .env >nul
    echo Created .env from .env.example. Set API keys before deploying.
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Building JARVIS.exe ...
pyinstaller --noconfirm ^
    --noconsole ^
    --name JARVIS ^
    --paths . ^
    --collect-all faster_whisper ^
    --collect-all edge_tts ^
    --collect-all sounddevice ^
    --collect-all soundfile ^
    --collect-all numpy ^
    --collect-all openwakeword ^
    --collect-all onnxruntime ^
    --hidden-import sounddevice ^
    --hidden-import soundfile ^
    --hidden-import faster_whisper ^
    --hidden-import edge_tts ^
    --hidden-import keyboard ^
    --hidden-import openwakeword ^
    --hidden-import onnxruntime ^
    app\main.py

if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

if not exist dist\JARVIS\JARVIS.exe (
    echo Build did not produce dist\JARVIS\JARVIS.exe
    exit /b 1
)

echo.
echo Built: %CD%\dist\JARVIS\JARVIS.exe
echo.
echo To install Windows auto-start:
echo     dist\JARVIS\JARVIS.exe --check
echo     python -m app.system.startup --install
echo.
endlocal
