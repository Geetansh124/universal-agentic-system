@echo off
cd /d "%~dp0\.."
echo ======================================================================
echo  STARTING UNIVERSAL AGENTIC PLATFORM (CLAUDE DESKTOP STYLE)
echo ======================================================================
echo Launching local server at http://127.0.0.1:8000 ...
start "" "http://127.0.0.1:8000"
python -m uvicorn src.web.server:app --host 127.0.0.1 --port 8000
if %errorlevel% neq 0 (
    echo Retrying with py...
    py -m uvicorn src.web.server:app --host 127.0.0.1 --port 8000
)
pause
