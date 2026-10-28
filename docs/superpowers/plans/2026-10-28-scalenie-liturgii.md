# Scalenie liturgii — plan wykonawczy

> **Dla wykonawców agentowych:** WYMAGANY SUB-SKILL: `superpowers:subagent-driven-development` (zalecany) albo `superpowers:executing-plans`. Kroki mają składnię checkboxów (`- [ ]`).

**Cel:** Zlać materię liturgiczną 45 perykop z dwóch warstw schematu w jedną — prozę podsekcji liturgicznej sekcji VII — i usunąć `liturgical_use` wraz z obsługującym go kodem.

**Architektura:** Robota idzie w trzech fazach. Faza redakcyjna (zadania 2–10) wchłania 162 rekordy `liturgy` w prozę, perykopa po perykopie, zostawiając `"liturgy": []` jako widoczny znacznik postępu. Faza techniczna (zadanie 11) usuwa opróżniony klucz, tabelę ze schematu i oba renderery. Faza domykająca (zadanie 12) aktualizuje dokumentację i dziennik recenzji. Kolejność jest wymuszona: `tools/egzegeza_jana_build.py:163` indeksuje `bundle["liturgy"]` twardo, więc klucz musi dożyć końca fazy redakcyjnej.

**Stos:** Python 3 (biblioteka standardowa), SQLite ≥ 3.37 (STRICT), Typst do PDF. Zero zależności zewnętrznych.

**Specyfikacja:** `docs/superpowers/specs/2026-10-28-liturgia-scalenie-design.md` — plan argumentuje z niej i bez niej nie jest wykonalny. Czytaj oba.

## Ograniczenia globalne

- Język wszystkich treści: **polski**.
- Cudzysłowy polskie `„…"`. Nigdy `"…"` w prozie.
- Półpauza w zakresach: `J 1,1–14`, `w. 6–8`. Nigdy dywiz.
- Każde wyrażenie greckie, łacińskie, hebrajskie i aramejskie dostaje polskie tłumaczenie w nawiasie bezpośrednio po nim — **zawsze**, także przy powtórzeniu w tej samej perykopie: *ultimum Evangelium* (ostatnia Ewangelia), *Missa in die* (Msza w dzień).
- Ton oznajmujący, gęsty, bez egzaltacji i kaznodziejstwa. Wzorzec: podsekcja „Liturgia" w `prolog.json`.
- Zapis plików danych: `json.dumps(obj, ensure_ascii=False, indent=1)`. `data/lazarz.json` i `data/pilat.json` nie mają kończącego `\n` — zachować ten stan.
- Statusy perykop zostają `ukonczona`. Decyzja Pawła; nie ruszać.
- **Tytuły podsekcji zostają**, także złożone („Liturgia i duchowość", „Liturgia: Agnus Dei", „Adwent i święta Chrzciciela"). Niosą treść. Tytuł zmieniamy tylko wtedy, gdy po scaleniu przestał opisywać zawartość — wtedy `zapisz(..., tytul=...)`.
- **Podsekcji zrośniętych nie rozcinamy** domyślnie. Rekordy wchłania część liturgiczna akapitu; materii nieliturgicznej (duchowość, ikonografia, kalendarz) nie ruszamy i nie wynosimy. Rozcięcie na dwie podsekcje jest dozwolone wyłącznie wtedy, gdy po wchłonięciu rekordów akapit przestaje się czytać jako jedna myśl.
- Nie dopisywać faktów liturgicznych, których nie ma w żadnym z dwóch scalanych źródeł.
- Projekt nie ma testów automatycznych ani walidatora (`validate.py` z `CLAUDE.md` nie istnieje). W miejsce cyklu TDD każde zadanie domyka **cykl weryfikacyjny**: poprawność JSON → `make build` → grepy konwencji → commit.

## Na co patrzeć w recenzji

Pięć klas wejścia, które specyfikacja zakłada, a których żaden krok nie sprawdza sam z siebie — każda ma przypisany test w zadaniu, które ją posiada:

1. **Łacina z rekordów wchodzi do prozy bez polskiej glosy.** 12 ze 162 rekordów nosi w treści obce wyrażenia (*Missa in die*, *Agnus Dei*, *ultimum Evangelium*) i **żaden ich nie tłumaczy** — rekordy nie podlegały tej konwencji, proza podlega. Mechaniczne przeniesienie łamie regułę naczelną `CLAUDE.md`. Test: grep konwencji w cyklu każdej partii (procedura P, krok 5).
2. **Dywiz zamiast półpauzy w siglach wniesionych z rekordów.** Rekordy mają sigla poprawne (`J 5,17–30`), ale siglum przepisane z pamięci w nowym zdaniu łatwo dostaje `-`. Test: grep `J [0-9]+,[0-9]+-` w cyklu partii.
3. **Prosty cudzysłów w nowej prozie.** Test: grep `"` w zmienionych podsekcjach w cyklu partii.
4. **Zapis pliku gubi kończący `\n` albo go dodaje.** Dotyczy `lazarz.json` i `pilat.json`. Test: funkcja `zapisz()` z zadania 1 zachowuje stan wejściowy; kontrola `git diff --stat` w cyklu partii nie pokazuje zmian na końcu pliku.
5. **Treść wyparowuje przy scaleniu.** Rekord zaklasyfikowany jako powtórzenie, choć wnosił siglum. Test: `scal.py stan` porównuje objętość prozy z punktem odniesienia z zadania 1; zadanie 12 domyka kontrolą całości.

---

## Zadanie 1: Punkt odniesienia i narzędzie audytu

**Pliki:**
- Zbuduj: `data/egzegeza_jana.sqlite` (nieaktualna — z 31 lipca, przy danych z 28 października)
- Utwórz: `$SCRATCH/scal.py` (narzędzie jednorazowe, nie wchodzi do repo)
- Utwórz: `$SCRATCH/bazowy.json`, `$SCRATCH/baza-przed.sqlite`

`$SCRATCH` = katalog roboczy sesji poza repozytorium.

**Interfejsy — produkuje (używane przez zadania 2–12):**
- `scal.py stan` — tabela: plik, indeks perykopy, siglum, tytuł podsekcji liturgicznej, znaki prozy, liczba rekordów; na końcu sumy i liczba perykop z niepustym `liturgy`
- `scal.py poka <plik>` — dla każdej perykopy: tytuł i pełna proza podsekcji liturgicznej, wszystkie rekordy, wiersz `data/REVIEW_LOG.md` dla tego pliku
- `scal.py bazowy` — zapisuje `$SCRATCH/bazowy.json`: `{plik: {idx: znaki_prozy}}`
- `scal.py roznica` — proza teraz kontra `bazowy.json`, per perykopa, z saldem
- funkcja `zapisz(plik, idx, proza, tytul=None)` — podmienia `children[i][1]` podsekcji liturgicznej, ustawia `liturgy = []`, zapisuje plik zachowując formatowanie i stan kończącego `\n`

- [ ] **Krok 1: Zbuduj świeżą bazę i odłóż kopię na punkt odniesienia**

```bash
make build && cp data/egzegeza_jana.sqlite $SCRATCH/baza-przed.sqlite
```

- [ ] **Krok 2: Napisz `$SCRATCH/scal.py`**

Rozpoznawanie podsekcji liturgicznej: sekcja VII to element `sections` z `type == "recepcja"`; podsekcja liturgiczna to pierwsze `children[i]`, którego `[0]` zawiera „Liturgia" (dopasowanie bez względu na wielkość liter). Dla `continuation.json` perykopa 2 („Adwent i święta Chrzciciela") automat nie trafi — `scal.py` musi trzymać jawną mapę wyjątków `{("continuation.json", 1): 0}` i przy braku trafienia **podnosić wyjątek, nie zgadywać**.

- [ ] **Krok 3: Zweryfikuj, że narzędzie widzi cały materiał**

```bash
python3 $SCRATCH/scal.py stan
```
Oczekiwane: 45 wierszy, 45 perykop z niepustym `liturgy`, suma rekordów **162**, każdy wiersz z niepustym tytułem i niezerową liczbą znaków prozy. Zero wyjątków.

- [ ] **Krok 4: Sprawdź, że `zapisz()` nie rusza formatowania**

Na kopii: wywołaj `zapisz()` z prozą identyczną z obecną na `data/lazarz.json` (bez `\n` na końcu) i `data/abraham.json` (z `\n`), potem `git diff --stat`.
Oczekiwane: `liturgy` wyczyszczone, poza tym zero zmian formatowania; żadnej zmiany na ostatniej linii. Następnie `git checkout data/lazarz.json data/abraham.json`.

- [ ] **Krok 5: Zapisz punkt odniesienia**

```bash
python3 $SCRATCH/scal.py bazowy
```

- [ ] **Krok 6: Wpuść dokumenty do repo i commituj**

`.gitignore:3` ignoruje `*.md` z zasady (Markdown to generowane eksporty) i whitelistuje tylko `README.md` oraz `data/REVIEW_LOG.md`. Dokument projektowy i plan są utrzymywane ręcznie, jak dziennik recenzji, więc dostają wpis w tej samej konwencji — a nie `git add -f`, które za rok nikomu nic nie powie:

```
!docs/superpowers/**/*.md
```

Kontrola, że wpis wpuszcza dokumenty i nie wpuszcza eksportów:

```bash
git check-ignore -v docs/superpowers/plans/2026-10-28-scalenie-liturgii.md   # ma trafić w regułę !docs/…
git check-ignore -v egzegeza_jan1.md                                         # ma nadal trafiać w *.md
```

Narzędzie `scal.py` żyje poza repo i nie jest commitowane.

```bash
git add .gitignore docs/
git commit -m "docs: projekt i plan scalenia liturgii"
```

Uwaga dla wykonawcy: `.gitignore` może już nieść niezwiązany z tą robotą wpis `/graft/` (lokalny cache grafu, dodany przez narzędzia). Jeśli tak — wydziel go do osobnego commita przed tym krokiem, żeby ten commit niósł jedną zmianę.

---

## Procedura P — cykl jednej partii

Zadania 3–10 wykonują tę procedurę na swojej liście plików. Zadanie 2 też, z dodatkową bramką.

1. **Czytaj oba źródła naraz:** `python3 $SCRATCH/scal.py poka <plik>`. Wyjście podaje prozę, rekordy i wiersz recenzji dla tego pliku.
2. **Klasyfikuj każdy rekord** wobec prozy — kategorie (a)–(d) z sekcji „Zasada redakcyjna" specyfikacji.
3. **Rozstrzygnij sprzeczności (d):** najpierw wiersz `REVIEW_LOG.md` z wyjścia kroku 1, przy milczeniu dziennika — rekord. Sprzeczność nieuzasadnioną przez rekord zapisz do listy do weryfikacji przy źródłach (trafi do podsumowania zadania 12).
4. **Przeredaguj prozę** i zapisz: `zapisz(plik, idx, nowa_proza)`. Wplatać (b) i (c) w wywód; (a) pomijać. Nie dopisywać wyliczenia na końcu akapitu.
5. **Cykl weryfikacyjny:**

```bash
python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('data/*.json')]"
make build
git diff -U0 data/ | grep -nE '^\+.*("|J [0-9]+,[0-9]+-|w\. [0-9]+-[0-9]+)' || echo "konwencje OK"
git diff --stat data/
python3 $SCRATCH/scal.py roznica
```
Oczekiwane: JSON się wczytuje, `make build` kończy się bez `KeyError`, grep konwencji milczy (prosty cudzysłów i dywiz w zakresach), `git diff --stat` pokazuje tylko pliki tej partii, `roznica` nie pokazuje salda ujemnego bez uzasadnienia w notatce.

6. **Kontrola obcych wyrażeń:** przejrzyj dodane linie `git diff data/` i potwierdź, że każde wyrażenie łacińskie, greckie, hebrajskie i aramejskie ma polską glosę w nawiasie bezpośrednio po sobie. Tego nie złapie grep — to lektura.
7. **Commit** z komunikatem wzoru: `refactor(dane): scal liturgię — <pliki partii>`.

---

## Zadanie 2: Perykopa wzorcowa — `prolog.json`

Sześć rekordów, najwięcej w bazie, i to Prolog jest wzorcem tonu całego projektu. Proza ma dziś pięć akapitów z pogrubionymi lidami; rekordy wnoszą ryt bizantyjski (Pascha, `J 1,1–17`), którego proza nie ma w ogóle — kategoria (c) w czystej postaci.

**Pliki:** Modyfikuj: `data/prolog.json` (perykopa 0, podsekcja „Liturgia")

- [ ] **Krok 1: Wykonaj procedurę P na `data/prolog.json`**
- [ ] **Krok 2: Pokaż Pawłowi scaloną podsekcję i zatrzymaj robotę**

Przyjęty wzorzec ustala próg redakcyjny dla pozostałych 44 perykop. Bez jego akceptacji zadania 3–10 nie startują: poprawianie tonu po 45 plikach kosztuje tyle, ile napisanie ich od nowa.

---

## Zadania 3–10: Partie redakcyjne

Każde zadanie: procedura P na swoich plikach, jeden commit. Alfabetycznie.

- [ ] **Zadanie 3:** `abraham` `adultera` `betesda` `bilans` `bracia` `chleb` (6 perykop)

- [ ] **Zadanie 4:** `continuation` (**5 perykop w jednym pliku** — J 1,15–18; 1,19–28; 1,29–34; 1,35–42; 1,43–51)

Najcięższa partia i jedyna z własnymi pułapkami, wszystkie wymienione, bo wykonawca ich nie odgadnie:
- Cztery z siedmiu podsekcji zrośniętych są tutaj: „Liturgia: Agnus Dei", „Liturgia i Andrzej Protokletos", „Liturgia i kalendarz" oraz „Adwent i święta Chrzciciela" (ta ostatnia bez słowa „liturgia" w tytule — `scal.py` bierze ją z mapy wyjątków).
- **Znana sprzeczność do rozstrzygnięcia:** perykopa J 1,19–28. Proza wiąże ją z uroczystością Narodzenia św. Jana Chrzciciela (24 VI); rekord mówi, że 24 VI Ewangelią jest Łk 1,57–66.80, a J 1,19–28 czyta się 2 stycznia. `REVIEW_LOG.md:51` (recenzja z 2026-08-29) potwierdza rekord: „recepcję liturgiczną J 1,19–28 (2 I, nie 24 VI)". Rekord wygrywa, a jego polemika wchodzi do prozy — symetria przesileń z J 3,30 zostaje jako materiał kaznodziejski, nie jako twierdzenie o lekcjonarzu.
- Ten sam wiersz recenzji notuje drugą poprawkę liturgiczną: J 1,35–42 — „30 XI rzymskie czyta Mt 4,18–22". Sprawdź prozę perykopy J 1,35–42 pod tym kątem.

- [ ] **Zadanie 5:** `duch` `dworzanin` `epilog` `eucharystia` `golgota` `kajfasz` (6 perykop)

`epilog` i `golgota` mają w recenzjach poprawki liturgiczne (`REVIEW_LOG.md:12` — J 21,20–25 w sobotę VII tygodnia wielkanocnego, nie 27 XII; wiersz `golgota` wymienia liturgię wśród obszarów poprawek). Czytaj dziennik przed rozstrzyganiem.

- [ ] **Zadanie 6:** `kana` `krzew` `lazarz` `mieszkania` `modlitwa` `mowa` (6 perykop)

Dwie zrośnięte podsekcje: „Liturgia: Epifania i lekcjonarz" (`kana`), „Liturgia i duchowość" (`mowa`). W `mowa` proza ma ryt bizantyjski (Niedziela Paralityka), którego rekordy nie mają, a rekordy mają siglum `J 5,24–29` dla mszy za zmarłych, którego proza nie ma — scalenie idzie w obie strony. `kana.json` dostanie przy zapisie dodatkową jednoliniową poprawkę wcięcia nawiasu (błąd formatowania w pliku; round-trip go naprawia) — to oczekiwane, nie przypadkowe. `lazarz.json` bez kończącego `\n`.

- [ ] **Zadanie 7:** `namaszczenie` `nienawisc` `niewidomy` `nikodem` `oblubieniec` `paraklet` (6 perykop)

- [ ] **Zadanie 8:** `pasterz` `pilat` `pojmanie` `poswiecenie` `radosc` `samarytanka` (6 perykop)

Zrośnięta: „Liturgia: wielka katecheza chrzcielna" (`samarytanka`). `pilat.json` bez kończącego `\n`.

- [ ] **Zadanie 9:** `swiatlosc` `swiatynia` `swieto` `umycie` `wjazd` `woda` (6 perykop)

- [ ] **Zadanie 10:** `zdrada` `ziarno` `zmartwychwstanie` (3 perykopy)

Po tym zadaniu: `python3 $SCRATCH/scal.py stan` musi pokazać **zero** perykop z niepustym `liturgy` i sumę rekordów 0.

---

## Zadanie 11: Usunięcie klucza, tabeli i rendererów

Startuje dopiero gdy `scal.py stan` pokazuje zero niepustych `liturgy`. Wcześniejszy start maskuje nieprzescalone rekordy, zamiast je ujawnić.

**Pliki:**
- Modyfikuj: `data/*.json` — usuń klucz `"liturgy"` z każdego bundle'a (45 wystąpień, wszystkie `[]`)
- Modyfikuj: `data/schema.sql:239-246` (tabela), `data/schema.sql:3-11` (numeracja warstw w komentarzu)
- Modyfikuj: `tools/egzegeza_jana_build.py:80` (`TABLES`), `:163-165` (pętla `INSERT`)
- Modyfikuj: `browser/app.py:200-201` (zapytanie), `:266` (klucz odpowiedzi API)
- Modyfikuj: `browser/index.html:257-269` i `:473-474` (CSS `.liturgia-poz`), `:811-825` (`czescLiturgia()`), `:1040` (wpis spisu części)
- Modyfikuj: `tools/export_typst.py:319-331` (`liturgia()`), `:422` (krotka części), `:456` (kontrola warstw)
- Modyfikuj: `README.md:117` (warstwa 7 „Recepcja"), `:271` (punkt 4 opisu interfejsu), lista kluczy bundle'a — w trzech miejscach przenumeruj to, co po usunięciu pozycji zostaje

Bez zmian: `tools/export_pericope.py` (nigdy nie znał klucza), `tools/export_site.py` i `.github/workflows/pages.yml` (zrzucają endpointy `browser/app.py` w ciemno).

- [ ] **Krok 1: Usuń klucz `liturgy` ze wszystkich bundle'ów**

Skryptem przez `zapisz()`-owy tryb zapisu (to samo formatowanie), nie ręcznie.

- [ ] **Krok 2: Potwierdź, że klucza nie ma, a prozy nie ubyło**

```bash
grep -c '"liturgy"' data/*.json | grep -v ':0' || echo "klucz usuniety wszedzie"
```
Oczekiwane: komunikat o usunięciu. **Nie** używaj do tej kontroli grepa na `liturg` w `data/*.json` — słowo „liturgia" występuje w prozie legalnie i ma występować.

- [ ] **Krok 3: Usuń tabelę ze schematu i obsługę z build.py, przebuduj**

```bash
make build
```
Oczekiwane: build przechodzi. Gdyby `KeyError: 'liturgy'` — krok 1 pominął plik.

- [ ] **Krok 4: Usuń renderery i API, zaktualizuj README**

- [ ] **Krok 5: Sprawdź wszystkie cztery wyjścia i czystość kodu**

```bash
make export && make typst && make site
grep -rn 'liturg' --include='*.py' --include='*.sql' --include='*.html' . | grep -v REVIEW_LOG || echo "kod czysty"
grep -n 'Liturgia' egzegeza_jan1.md | head
```
Oczekiwane: trzy eksporty przechodzą; grep po kodzie milczy; `egzegeza_jan1.md` zawiera „Liturgia" **jako nagłówek podsekcji sekcji VII** — to dowód, że eksport Markdown zyskał treść, której wcześniej nie miał.

- [ ] **Krok 6: Commit**

```bash
git add data/ tools/ browser/ README.md
git commit -m "refactor: usun liturgical_use — liturgia zyje w prozie sekcji VII"
```

---

## Zadanie 12: Dziennik i domknięcie

**Pliki:** Modyfikuj: `data/REVIEW_LOG.md` (nowy wiersz nad obecnym pierwszym — tabela jest ułożona od najnowszych)

- [ ] **Krok 1: Kontrola końcowa objętości wobec punktu odniesienia**

```bash
python3 $SCRATCH/scal.py roznica
```
Oczekiwane: saldo per perykopa dodatnie albo zerowe. Każde ujemne musi mieć uzasadnienie w notatkach z procedury P krok 3 (usunięte powtórzenie) — inaczej treść wyparowała i trzeba wrócić do tej perykopy.

- [ ] **Krok 2: Dopisz wiersz do `data/REVIEW_LOG.md`**

Format jak pozostałe wiersze: `| data (UTC) | plik | poprawki | podsumowanie |`. W polu pliku: `*.json (45 perykop)`. W podsumowaniu: zakres scalenia, liczba wchłoniętych rekordów (162), liczba rozstrzygniętych sprzeczności proza/rekord i te rozstrzygnięte wbrew prozie wymienione z siglami.

- [ ] **Krok 3: Commit**

```bash
git add data/REVIEW_LOG.md
git commit -m "docs(dane): odnotuj scalenie liturgii w dzienniku recenzji"
```

- [ ] **Krok 4: Podsumuj Pawłowi**

Obowiązek z `CLAUDE.md` — podsumowanie zawiera: listę rozstrzygniętych sprzeczności proza/rekord z informacją, co wybrano; listę sprzeczności nieuzasadnionych przez rekord, do weryfikacji przy źródłach w pierwszej kolejności (lekcjonarz rzymski, typikon bizantyjski); przypomnienie, że sigla wniesione z rekordów dziedziczą wiarygodność recenzji, która je wprowadziła, a nie lektury źródła.

Dodatkowo — zgłoszenie zaległości wykrytej przy tej robocie, poza jej zakresem (specyfikacja, „Czego nie robimy"): `CLAUDE.md` jest nieaktualny. Opisuje nieistniejący `validate.py` i układ repozytorium sprzed przeniesienia plików do `tools/`, `data/` i `browser/`, a jego tabela stanu prac wymienia 7 perykop ze statusem `w_opracowaniu` przy 45 perykopach `ukonczona` w danych. To osobna robota do zlecenia.
