@echo off
REM Dev mode launcher. Keeps a console window so you can see logs.
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)
if not exist .env (
    copy .env.example .env >nul
    echo Created .env from .env.example. Edit it to set API keys.
)
python -m app.main %*
endlocal
