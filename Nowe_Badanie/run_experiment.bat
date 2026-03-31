@echo off
REM ── Uruchamia eksperyment v2 (Nowe_Badanie) ──────────────────────────────
REM Skopiuj cały folder Nowe_Badanie do folderu źródłowego (obok PsychoPy\)
REM i uruchom ten plik. PsychoPy musi być w folderze nadrzędnym.

setlocal
set "root=%~dp0"

REM Przejdź do folderu eksperymentu
cd /d "%root%"

REM Uruchom przez PsychoPy z folderu nadrzędnego
"%root%..\PsychoPy\pythonw.exe" "%root%experiment_code.py"

endlocal
