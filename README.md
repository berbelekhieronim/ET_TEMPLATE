# ET LLM Experiment Application

Aplikacja do eksperymentów eye-tracking z interfejsem LLM wykorzystująca Tobii eye tracker i PsychoPy.

## Funkcje

- Kalibracja eye trackera Tobii
- Prezentacja tekstowych recenzji z bazy danych JSON
- Rejestracja danych eye-tracking w czasie rzeczywistym
- Zapis wyników w formacie binarnym i tekstowym
- Możliwość wcześniejszego zakończenia eksperymentu (klawisz Esc)

## Uruchamianie

### Opcja 1: Skompilowana wersja (Windows) - ZALECANA
1. Pobierz najnowszy release z sekcji "Releases" na GitHub
2. Rozpakuj archiwum do wybranego folderu
3. Upewnij się, że masz podłączony eye tracker Tobii
4. Uruchom `run_experiment.bat` lub bezpośrednio `ET_LLM_Experiment.exe`

### Opcja 2: Z kodu źródłowego
1. Zainstaluj Python 3.9+
2. Zainstaluj zależności: `pip install -r requirements.txt`
3. Uruchom: `python experiment_code.py`

### Opcja 3: Z PsychoPy (jak wcześniej)
1. Zainstaluj PsychoPy w folderze `PsychoPy/`
2. Uruchom `run_experiment.bat`

## Wymagania sprzętowe

- System Windows
- Eye tracker Tobii (kompatybilny z Tobii Research SDK)
- Monitor o rozdzielczości co najmniej 1024x768

## Pliki konfiguracyjne

- `selected_reviews_data.json` - baza danych recenzji do prezentacji
- `IBMPlexMono-Regular.ttf` - czcionka używana w eksperymencie
- `experiment_code.py` - główny kod aplikacji

## Budowanie lokalnie

Aby zbudować plik .exe lokalnie na Windows:

```bash
# Zainstaluj zależności
pip install -r requirements.txt

# Zbuduj używając PyInstaller
pyinstaller experiment_code.spec

# Lub prostsza komenda:
pyinstaller --onefile --windowed --name "ET_LLM_Experiment" --add-data "selected_reviews_data.json;." --add-data "IBMPlexMono-Regular.ttf;." experiment_code.py
```

Skompilowany plik znajdziesz w folderze `dist/`.

## Automatyczne budowanie

Każdy push do gałęzi `main`, `master` lub `for-testing` automatycznie buduje plik .exe za pomocą GitHub Actions.

### Tworzenie nowego release:

1. Utwórz tag: `git tag v1.0.0`
2. Wypchnij tag: `git push origin v1.0.0`
3. GitHub Actions automatycznie utworzy release z plikiem .exe

## Parametry eksperymentu

Główne parametry można modyfikować w górnej części pliku `experiment_code.py`:

- `N_TRIALS` - liczba prób (domyślnie 25)
- `FIX_DUR` - czas fiksacji (0.50s)
- `CALIB_DUR` - czas kalibracji (0.20s)
- `FSIZE` - rozmiar czcionki (34)
- Inne parametry związane z tolerancją i timeoutami

## Struktura logów

Aplikacja zapisuje:
- Plik binarny z danymi eye-tracking (`data*.bin`)
- Logi tekstowe z timestampami zdarzeń
- Metryki kalibracji

## Licencja

[Określ licencję projektu]

## Kontakt

[Twoje dane kontaktowe]