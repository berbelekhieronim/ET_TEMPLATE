@echo off
REM — get the folder where this .bat lives (with trailing backslash)
setlocal
set "root=%~dp0"

REM — make that the working directory (so any relative imports in your .py still work)
cd /d "%root%"

REM — Check if compiled .exe exists and run it, otherwise fallback to Python
if exist "%root%ET_LLM_Experiment.exe" (
    echo Uruchamianie skompilowanej wersji...
    "%root%ET_LLM_Experiment.exe"
) else if exist "%root%PsychoPy\pythonw.exe" (
    echo Uruchamianie wersji PsychoPy...
    "%root%PsychoPy\pythonw.exe" "%root%experiment_code.py"
) else if exist "%root%experiment_code.py" (
    echo Uruchamianie wersji Python...
    python "%root%experiment_code.py"
) else (
    echo Nie znaleziono pliku wykonywalnego ani skryptu Python!
    pause
)

endlocal

