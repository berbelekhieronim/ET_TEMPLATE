@echo off
echo Budowanie pliku wykonywalnego ET_LLM_Experiment.exe...

REM Sprawdź czy PyInstaller jest zainstalowany
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller nie jest zainstalowany. Instalowanie...
    pip install pyinstaller
)

REM Sprawdź czy pozostałe zależności są zainstalowane
echo Sprawdzanie zależności...
pip install -r requirements.txt

REM Buduj plik .exe
echo Budowanie pliku wykonywalnego...
pyinstaller experiment_code.spec

REM Kopiuj dodatkowe pliki do folderu dist
echo Kopiowanie plików pomocniczych...
if exist dist\ET_LLM_Experiment.exe (
    copy selected_reviews_data.json dist\
    copy IBMPlexMono-Regular.ttf dist\
    copy run_experiment.bat dist\
    
    echo.
    echo ================================
    echo Kompilacja zakończona pomyślnie!
    echo ================================
    echo.
    echo Plik wykonywalny: dist\ET_LLM_Experiment.exe
    echo Wszystkie potrzebne pliki skopiowane do folderu dist\
    echo.
    echo Aby uruchomić aplikację:
    echo 1. Przejdź do folderu dist\
    echo 2. Uruchom ET_LLM_Experiment.exe lub run_experiment.bat
    echo.
) else (
    echo BŁĄD: Kompilacja nie powiodła się!
    echo Sprawdź błędy powyżej.
)

pause