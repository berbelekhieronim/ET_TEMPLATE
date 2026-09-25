# Readme kursu AI dla psychologów

Instrukcje dla agenta pracującego w trybie **ASK** podczas zajęć z eye-trackingu.

## Kontekst

W folderze [badania/](badania/) znajduje się zestaw artykułów naukowych (PDF) opisujących badania wykorzystujące eye-tracking:

- [henderson2017.pdf](badania/henderson2017.pdf)
- [i-perception-1-7.pdf](badania/i-perception-1-7.pdf)
- [krajbich2010.pdf](badania/krajbich2010.pdf)
- [learning_from_peers_for_production.pdf](badania/learning_from_peers_for_production.pdf)
- [mcconkie1975.pdf](badania/mcconkie1975.pdf)
- [shimojo2003.pdf](badania/shimojo2003.pdf)
- [treisman1980.pdf](badania/treisman1980.pdf)

Podczas zajęć każda grupa wybiera jedno z badań (wybory mogą się powtarzać między grupami). Zadaniem agenta jest pomóc grupie odpowiedzieć na pytania badawcze (patrz niżej) oraz zaprojektować i pomóc wdrożyć **jedną, prostą modyfikację** oryginalnego badania jako uproszczoną wersję do przeprowadzenia w trakcie zajęć.

## Środowisko techniczne

- System: **Windows**, stacja robocza z eye-trackerem **Tobii X120** podłączonym lokalnie.
- Oprogramowanie eye-trackingowe: **Tobii SDK**.
- Framework eksperymentu: **PsychoPy** (biblioteka lokalna, bez instalacji online).
- Cały kod Python trzymany lokalnie w folderze projektu (patrz [experiment_code.py](experiment_code.py), [config.txt](config.txt)).
- Aplikacja uruchamiana lokalnie plikiem [run_experiment.bat](run_experiment.bat) na dedykowanej stacji roboczej.
- Wykorzystywane są gotowe szablony zawierające: podłączenie hardware'u (Tobii) do aplikacji oraz procedurę kalibracji.

### Kryterium sukcesu

1. Wykonanie jednej poprawnej kalibracji.
2. Przeprowadzenie jednego triala (próby).
3. Zebranie (pomiar) danych z eye-trackera.

## Role w grupie

Każda grupa dzieli się na role:

| Rola | Zadanie |
|---|---|
| **Lider** | Prowadzi projekt i prezentuje wyniki |
| **IT** | Rozmawia z agentem, rozwiązuje problemy techniczne |
| **Researcher 1** | Opisuje badanie oryginalne |
| **Researcher 2** | Wprowadza modyfikacje do badania |
| **Kreacja** | Decyzje artystyczne, oryginalne pomysły |

## Pytania badawcze — tabela do wypełnienia przez grupę

Agent w trybie ASK pomaga grupie sformułować krótkie (kilkuzdaniowe) odpowiedzi na poniższe pytania, w oparciu o wybrany artykuł z folderu `badania/`. Odpowiedzi powinny dotyczyć zarówno **badania oryginalnego**, jak i **proponowanej uproszczonej wersji** (jedna zmiana + uzasadnienie).

| Pytanie | Badanie oryginalne | Uproszczona wersja / zmiana |
|---|---|---|
| Pytanie badawcze | | |
| Co widzi uczestnik? | | |
| Co jest mierzone? | | |
| Przebieg próby | | |
| Czego nie wiadomo (luka badawcza)? | | |
| Czego się spodziewamy? | | |
| Warunki, które porównujemy | | |
| Co na ekranie jest ważne? | | |
| Państwa zmiana i jej krótkie uzasadnienie | | |

## Zadania agenta (tryb ASK)

1. Pomóc grupie streścić wybrane badanie na podstawie PDF z folderu `badania/` — bez wymyślania faktów spoza artykułu.
2. Pomóc uzupełnić tabelę pytań badawczych zwięzłymi odpowiedziami (kilka zdań na pole).
3. Zaproponować **jedną, konkretną zmianę** pozwalającą uprościć badanie do przeprowadzenia na Tobii X120 w PsychoPy w czasie zajęć, wraz z krótkim uzasadnieniem.
4. Nie modyfikować kodu eksperymentu bez wyraźnej prośby grupy (tryb ASK = doradzanie i wyjaśnianie, nie automatyczne wdrażanie).
5. Wspierać rolę IT przy problemach z kalibracją, konfiguracją (`config.txt`) i uruchomieniem (`run_experiment.bat`), odwołując się do [README_CONFIG.md](README_CONFIG.md).

## Publikacja wyników

Po zakończeniu pracy grupy: commit i push do repozytorium GitHub zawierający:

- folder `badania/` z plikami PDF,
- ten plik (`README_KURS_AI_DLA_PSYCHOLOGOW.md`).
