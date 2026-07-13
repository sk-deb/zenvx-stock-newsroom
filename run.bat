@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV_DIR=%~dp0.venv"
set "PY_EXE="

where py >nul 2>&1 && set "PY_EXE=py -3"
if not defined PY_EXE (
  where python >nul 2>&1 && set "PY_EXE=python"
)
if not defined PY_EXE (
  echo [ZenvX Stock] Python 3 not found. Install from https://www.python.org/downloads/
  exit /b 1
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo [ZenvX Stock] Creating virtual environment...
  %PY_EXE% -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo [ZenvX Stock] Failed to create venv.
    exit /b 1
  )
)

echo [ZenvX Stock] Installing / updating dependencies...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip >nul
"%VENV_DIR%\Scripts\python.exe" -m pip install -r "%~dp0backend\requirements.txt"
if errorlevel 1 (
  echo [ZenvX Stock] pip install failed.
  exit /b 1
)

echo.
echo [ZenvX Stock] Starting on http://127.0.0.1:8421
echo [ZenvX Stock] Press Ctrl+C to stop.
echo.
cd /d "%~dp0"
"%VENV_DIR%\Scripts\python.exe" -m uvicorn backend.main:app --host 0.0.0.0 --port 8421
endlocal
