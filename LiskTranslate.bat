@echo off
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
  echo The app environment is missing.
  echo From this folder, run:
  echo   python -m venv .venv
  echo   .venv\Scripts\python -m pip install -r requirements.txt
  pause
  exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" -m lisktranslate
