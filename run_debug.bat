@echo off
REM Debug script for eye tracker connection diagnostics
REM This script helps identify why the eye tracker connection might be failing

setlocal
set "root=%~dp0"

REM Make the script directory the working directory
cd /d "%root%"

echo.
echo ======================================================================
echo Running Eye Tracker Connection Diagnostics
echo ======================================================================
echo.

REM Try to find Python executable (prefer python.exe over pythonw.exe for console output)
if exist "%root%PsychoPy\python.exe" (
    echo Using: %root%PsychoPy\python.exe
    echo.
    "%root%PsychoPy\python.exe" "%root%debug_import.py"
) else if exist "%root%PsychoPy\pythonw.exe" (
    echo Using: %root%PsychoPy\pythonw.exe
    echo WARNING: Using pythonw.exe - output may not be visible
    echo.
    "%root%PsychoPy\pythonw.exe" "%root%debug_import.py"
) else (
    echo ERROR: Cannot find Python in %root%PsychoPy\
    echo Please check if PsychoPy folder exists.
    echo.
    echo Trying system Python instead...
    python "%root%debug_import.py"
)

REM Pause to see results
echo.
echo.
echo ======================================================================
echo Diagnostics complete. Press any key to close this window...
echo ======================================================================
pause >nul

endlocal
