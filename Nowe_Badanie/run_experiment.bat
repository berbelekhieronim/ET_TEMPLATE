REM — get the folder where this .bat lives (with trailing backslash)
setlocal
set "root=%~dp0"

REM — make that the working directory (so any relative imports in your .py still work)
cd /d "%root%"

REM — run PsychoPy’s pythonw on the script in the same folder as this .bat
"%root%PsychoPy\pythonw.exe" "%root%experiment_code.py"

endlocal

