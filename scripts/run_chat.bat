@echo off
cd /d "%~dp0\.."
echo Starting Universal LLM Router Chat...
python -m src.llm_router.cli --chat
if %errorlevel% neq 0 (
    echo Retrying with 'py'...
    py -m src.llm_router.cli --chat
)
pause
