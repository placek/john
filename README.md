# Egzegeza Ewangelii według św. Jana — baza SQLite

Baza `egzegeza_jana.sqlite` przechowuje pełną egzegezę perykopa po perykopie.
Zawartość: **J 1,1–9,41** w dwudziestu trzech perykopach — Prolog (zmigrowany z dokumentu roboczego) oraz dwadzieścia dwie perykopy J 1,15–9,41; wszystkie doprowadzone do pełnej egzegezy (status: ukończona).

## Układ repozytorium

Dane są oddzielone od narzędzi — pliki `.json` przechowują całą treść, a
skrypty w `tools/` są **wyłącznie** narzędziami, które z nich budują bazę.

```
data/                     ← źródła (pod kontrolą wersji)
  schema.sql              schemat bazy (DDL)
  prolog.json            Prolog J 1,1-14 + katena Ojców
  continuation.json      J 1,15-51 (pięć perykop)
  kana.json              J 2,1-11 (Wesele w Kanie)
  swiatynia.json         J 2,12-25 (Oczyszczenie świątyni)
  nikodem.json           J 3,1-21 (Rozmowa z Nikodemem)
  oblubieniec.json       J 3,22-36 (Przyjaciel Oblubieńca)
  samarytanka.json       J 4,1-42 (Samarytanka)
  dworzanin.json         J 4,43-54 (Syn dworzanina)
  betesda.json           J 5,1-18 (Uzdrowienie nad Betesdą)
  mowa.json              J 5,19-47 (Mowa o Synu i świadectwach)
  chleb.json             J 6,1-21 (Rozmnożenie chleba i przejście przez morze)
  eucharystia.json       J 6,22-71 (Mowa eucharystyczna o chlebie życia)
  bracia.json            J 7,1-13 (Niewiara braci i wejście na Święto Namiotów)
  swieto.json            J 7,14-36 (Nauczanie w połowie święta)
  woda.json              J 7,37-52 (Rzeki wody żywej)
  adultera.json          J 7,53-8,11 (Kobieta cudzołożna)
  swiatlosc.json         J 8,12-30 (Światłość świata)
  abraham.json           J 8,31-59 (Prawda, wolność i Abraham)
  niewidomy.json         J 9,1-41 (Uzdrowienie niewidomego od urodzenia)
  egzegeza_jana.sqlite    baza generowana (make build; poza gitem)
tools/
  egzegeza_jana_build.py  buduje data/egzegeza_jana.sqlite z data/*.json
  export_pericope.py      regeneruje Markdown perykopy z bazy
browser/
  app.py                  backend (serwer + API, biblioteka standardowa)
  index.html              interfejs przeglądarki
Makefile                  make build | serve | export | clean
```

## Źródło tekstu: `db.sqlite`

W korzeniu repozytorium leży `db.sqlite` — **źródło prawdy dla samego tekstu**
Ewangelii (Jan ma w nim numer księgi `500`):

| tabela | zawartość |
|---|---|
| `words` | interlinia grecko-polska słowo po słowie: `text` (greka NA28 wraz ze znakami aparatu), `translation` (polski odpowiednik), `strong`, `morphology`, `footnote` oraz **`red`** — znacznik słów Jezusa (*verba Christi*) |
| `commentaries` | aparat krytyczny NA28, powiązany ze znakami (`marker`) wplecionymi w tekst grecki |
| `latin_verses` | Wulgata łacińska, werset po wersecie — trzecia kolumna tekstu paralelnego |

Baza egzegetyczna (`data/egzegeza_jana.sqlite`) pozostaje magazynem **komentarza**
— analiz, kateny, aparatu autorskiego i odniesień; tekst do prezentacji bierzemy
z `db.sqlite`. W sekcji „Analiza wers po wersie" przeglądarka wykorzystuje
wszystkie trzy warstwy `words` oraz `commentaries`:

- **interlinia** — greka nad polskim odpowiednikiem, słowa Jezusa czerwienią;
- **Strong i morfologia** — kliknięcie (lub Enter na zaznaczonym) słowa otwiera
  okienko z formą grecką, znaczeniem, numerem Stronga (odsyłacz do konkordancji)
  i **rozwiniętym po polsku** kodem morfologicznym: `v--papnsm-` czyta się jako
  „czasownik · praesens · strona czynna · imiesłów · mianownik · liczba
  pojedyncza · rodzaj męski";
- **aparat NA28** — wpisy z `commentaries` przypięte do wersetów bloku; znaki
  aparatu (`°`, `⸀`, `⸂`…) są podświetlone również wewnątrz greki interlinii, więc
  widać, do którego słowa odnosi się dana nota.

Każdy plik `data/*.json` ma tę samą strukturę: słownictwo współdzielone
(`books`, `verses`, `lexemes`, `semitic`, `occurrences`, `works`, `themes`)
oraz listę samodzielnych perykop (`pericopes`). `make build` (czyli
`python3 tools/egzegeza_jana_build.py`) buduje bazę od zera, w kolejności
`prolog → continuation → kana → swiatynia → nikodem → oblubieniec → samarytanka →
dworzanin → betesda → mowa → chleb → eucharystia → bracia → swieto → woda → adultera → swiatlosc → abraham → niewidomy`.

## Warstwy schematu

1. **Kanon**: `book`, `verse` (tekst grecki NA28 + przekład roboczy per werset)
2. **Perykopa**: `pericope` (zakres, tytuł, motto, status opracowania)
3. **Komentarz**: `section` (drzewo sekcji I–VII), `commentary_block` (zakres
   wersetów, np. „w. 6–8"), `analysis_unit` (fraza grecka + akapit analizy —
   najmniejszy klocek egzegezy)
4. **Słowniki wielokrotnego użytku**: `lexeme` (λόγος, σάρξ…), `semitic_term`
   (dawar, Szechina…), `lexeme_semitic` (podwójne dno grecko-semickie),
   `lexeme_occurrence` (mapa wystąpień słów-kluczy)
5. **Aparat**: `scripture_ref` (odniesienia z typem relacji), `textual_note`
   (warianty i interpunkcja), `work` + `citation` (autorzy i dzieła)
6. **Katena patrystyczna**: `patristic_comment` — komentarz Ojca Kościoła
   (work + locus + treść) przypięty do bloku wersetowego; widok `v_catena`;
   sekcja VIII w eksporcie składa się z tej tabeli automatycznie
7. **Recepcja**: `liturgical_use`
8. **Przekroje**: `theme` + `theme_link` (nici tematyczne przez całą księgę)
9. **Warsztat**: `meta`, `revision_log`, triggery `updated_at`, FTS5

## Otwieranie

- CLI: `sqlite3 data/egzegeza_jana.sqlite` (na tym środowisku: `python3 -c "import sqlite3..."`)
- GUI: DBeaver, DB Browser for SQLite, Datasette (`datasette data/egzegeza_jana.sqlite`)

## Wyszukiwanie pełnotekstowe

```sql
SELECT entity, entity_id, snippet(fts_tresc, 0, '[', ']', '…', 12)
FROM fts_tresc WHERE fts_tresc MATCH 'Szechina';
```

Uwaga: `remove_diacritics` w FTS5 zdejmuje tylko diakrytykę łacińską (ó, é…).
Grekę, hebrajski i polskie „ł" wyszukuj w pełnym zapisie: `MATCH 'λόγος'`,
`MATCH 'światłość'`. Triggery synchronizują FTS automatycznie przy każdej
zmianie w `analysis_unit`, `section`, `commentary_block`, `lexeme`.

## Przykładowe zapytania

```sql
-- spis perykop z licznikami
SELECT * FROM v_spis_perykop;

-- pełna analiza w. 14: frazy i treść
SELECT u.phrase_greek, u.body_md
FROM analysis_unit u JOIN commentary_block b ON b.id = u.block_id
WHERE b.label = 'w. 14' ORDER BY u.position;

-- mapa semantyczna słowa-klucza
SELECT * FROM v_leksykon WHERE lemma = 'φῶς';

-- wszystkie typologie ST dla perykopy
SELECT target_label, note_md FROM scripture_ref
WHERE pericope_id = 1 AND relation = 'typologia';
```

## Dodawanie kolejnej perykopy

Nie dotyka się już kodu — dopisuje się dane.

1. Dodaj perykopę jako kolejny wpis w tablicy `pericopes` w odpowiednim
   pliku `data/*.json` (albo utwórz nowy plik danych i dopisz go do listy
   `PHASES` w `tools/egzegeza_jana_build.py`). Uzupełnij `verses` i — w razie
   potrzeby — słownictwo (`lexemes`, `semitic`, `works`, `themes`); leksemy
   już istniejące zostaną pominięte (`INSERT OR IGNORE`).
2. `make build` — przebuduj bazę od zera z `data/*.json`.
3. `python3 tools/export_pericope.py 2 kana_export.md` — kontrola.

Struktura pojedynczej perykopy (`bundle`): `pericope`, `intro` (sekcja I),
`blocks` (z `units`), `sections` (II…), `refs`, `patristic`, `liturgy`,
`textual`, `theme_links`; opcjonalnie `struktura`, `section_viii`,
`citations`, `revision_note`.

Status perykopy (`szkic` → `w_opracowaniu` → `ukonczona` → `do_rewizji`)
i `revision_log` służą do prowadzenia pracy na lata.

## Katena — przykładowe zapytania

```sql
-- wszyscy Ojcowie komentujący w. 14
SELECT autor, locus, body_md FROM v_catena WHERE blok = 'w. 14';

-- wszystkie komentarze Augustyna w całej bazie
SELECT blok, locus, body_md FROM v_catena WHERE autor = 'św. Augustyn';

-- pełnotekstowo po katenie
SELECT snippet(fts_tresc,0,'[',']','…',12) FROM fts_tresc
WHERE fts_tresc MATCH 'przebóstwieni' AND entity = 'patristic_comment';
```

## Perykopy

| Siglum | Tytuł | Status |
|---|---|---|
| J 1,1–14 | Prolog | ukończona |
| J 1,15–18 | Dopełnienie Prologu | ukończona |
| J 1,19–28 | Świadectwo Jana Chrzciciela | ukończona |
| J 1,29–34 | Baranek Boży | ukończona |
| J 1,35–42 | Pierwsi uczniowie | ukończona |
| J 1,43–51 | Powołanie Filipa i Natanaela | ukończona |
| J 2,1–11 | Wesele w Kanie Galilejskiej | ukończona |
| J 2,12–25 | Oczyszczenie świątyni | ukończona |
| J 3,1–21 | Rozmowa z Nikodemem | ukończona |
| J 3,22–36 | Przyjaciel Oblubieńca | ukończona |
| J 4,1–42 | Samarytanka | ukończona |
| J 4,43–54 | Syn dworzanina | ukończona |
| J 5,1–18 | Uzdrowienie nad Betesdą | ukończona |
| J 5,19–47 | Mowa o Synu i świadectwach | ukończona |
| J 6,1–21 | Rozmnożenie chleba i przejście przez morze | ukończona |
| J 6,22–71 | Mowa eucharystyczna o chlebie życia | ukończona |
| J 7,1–13 | Niewiara braci i wejście na Święto Namiotów | ukończona |
| J 7,14–36 | Nauczanie w połowie święta | ukończona |
| J 7,37–52 | Rzeki wody żywej | ukończona |
| J 7,53–8,11 | Kobieta cudzołożna | ukończona |
| J 8,12–30 | Światłość świata | ukończona |
| J 8,31–59 | Prawda, wolność i Abraham | ukończona |
| J 9,1–41 | Uzdrowienie niewidomego od urodzenia | ukończona |

Eksport pojedynczej perykopy: `make export PID=4` (lub
`python3 tools/export_pericope.py 4 baranek.md`); całości: `make export`.

## Aplikacja webowa

```bash
make serve              # startuje na http://localhost:8000
make serve PORT=9000    # inny port
# równoważnie: PORT=9000 python3 browser/app.py
```

Bez zależności zewnętrznych — tylko biblioteka standardowa Pythona; baza
otwierana w trybie tylko do odczytu (`mode=ro`), więc przeglądanie nie może
uszkodzić danych. Zatrzymanie: Ctrl+C. Port ustawia zmienna `PORT`
(domyślnie 8000). Jeśli baza nie istnieje, uruchom najpierw `make build`.

**Co jest w interfejsie**

Perykopa jest jednym ciągłym dokumentem (bez zakładek), ułożonym tak, jak się ją
czyta — od tekstu do szczegółu:

1. **Tekst perykopy** — trzy kolumny *paralelnie*, werset przy wersecie:
   greka NA28, przekład roboczy i **Wulgata** (z `latin_verses`), z numeracją
   na marginesie (perykopy przekraczające granicę rozdziałów dostają znaczniki
   rozdziału i numery w postaci `8,12`). Kolumnę łacińską można schować
   przyciskiem; wybór pamięta się między perykopami
2. **Komentarz** — „Struktura całości" oraz sekcje II–VII z podsekcjami,
   zakończenie i nota warsztatowa
3. **Ojcowie Kościoła** — katena z autorem, dziełem, miejscem (locus) i blokiem
   wersetowym, którego dotyczy
4. **Liturgia** — recepcja liturgiczna: ryt, okazja, perykopa lekcjonarza, opis
5. **Analiza wers po wersie** — blok po bloku: **interlinia** grecko-polska
   z `db.sqlite` (nad każdym słowem greka, pod nim polski odpowiednik; słowa
   Jezusa na czerwono, kliknięcie słowa otwiera Stronga i morfologię po
   polsku), pod nią przekład ciągły, jednostki analizy frazowej, *leksykon*
   słów-kluczy tego bloku, *aparat NA28* z `commentaries` oraz autorskie
   *noty tekstualne* przypisane do jego wersetów
6. **Odniesienia i motywy** — tabela odniesień biblijnych i motywy przekrojowe

Do tego: lewa kolumna z listą perykop, przyklejony spis części (podświetla
sekcję, którą właśnie czytasz), górne przyciski *Leksykon* i *Motywy*, tryb
ciemny wedle ustawień systemu, układ responsywny (na wąskim ekranie greka staje
nad przekładem) i arkusz do druku. Wyszukiwarka u góry działa pełnotekstowo po
FTS5 (analizy, sekcje, katena, leksykon); kliknięcie wyniku otwiera perykopę.
Grekę i „ł" wpisuj w pełnym zapisie.

**Punkty API** (przydatne przy własnych narzędziach):
`/api/pericopes`, `/api/pericope?id=N`, `/api/search?q=…`, `/api/lexicon`, `/api/themes`
— wszystkie zwracają JSON.

## GitHub Pages (wersja statyczna)

GitHub Pages nie uruchomi Pythona, więc przeglądarkę publikuje się w wersji
statycznej: `make site` woła `tools/export_site.py`, który importuje
`browser/app.py` i zamienia każdy endpoint API w plik JSON w `site/api/`
(perykopy, leksykon, motywy oraz `szukaj.json` — indeks dla wyszukiwarki
działającej wtedy po stronie przeglądarki, bez FTS5). Kopiowany
`index.html` dostaje atrybut `data-static` i sam przełącza się na pliki.

Publikacją zajmuje się workflow `.github/workflows/pages.yml`: przy każdym
pushu na `master` buduje bazę, generuje `site/` i wdraża na Pages.
Jednorazowo trzeba włączyć w repozytorium:
**Settings → Pages → Build and deployment → Source: „GitHub Actions"**.

Podgląd lokalny wersji statycznej: `make site && python3 -m http.server -d site 8001`.
