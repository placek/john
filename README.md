# Egzegeza Ewangelii według św. Jana — baza SQLite

Baza `egzegeza_jana.sqlite` przechowuje pełną egzegezę perykopa po perykopie.
Zawartość: **J 1,1–2,11** w siedmiu perykopach — Prolog (zmigrowany z dokumentu roboczego) oraz sześć perykop J 1,15–2,11; wszystkie doprowadzone do pełnej egzegezy (status: ukończona).

## Układ repozytorium

Dane są oddzielone od narzędzi — pliki `.json` przechowują całą treść, a
skrypty w `tools/` są **wyłącznie** narzędziami, które z nich budują bazę.

```
data/                     ← źródła (pod kontrolą wersji)
  schema.sql              schemat bazy (DDL)
  prolog.json            Prolog J 1,1-14 + katena Ojców
  continuation.json      J 1,15-51 (pięć perykop)
  kana.json              J 2,1-11 (Wesele w Kanie)
  egzegeza_jana.sqlite    baza generowana (make build; poza gitem)
tools/
  egzegeza_jana_build.py  buduje data/egzegeza_jana.sqlite z data/*.json
  export_pericope.py      regeneruje Markdown perykopy z bazy
browser/
  app.py                  backend (serwer + API, biblioteka standardowa)
  index.html              interfejs przeglądarki
Makefile                  make build | serve | export | clean
```

Każdy plik `data/*.json` ma tę samą strukturę: słownictwo współdzielone
(`books`, `verses`, `lexemes`, `semitic`, `occurrences`, `works`, `themes`)
oraz listę samodzielnych perykop (`pericopes`). `make build` (czyli
`python3 tools/egzegeza_jana_build.py`) buduje bazę od zera, w kolejności
`prolog → continuation → kana`.

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

- lewa kolumna: lista perykop z siglum
- zakładka *Tekst i analiza*: bloki wersetowe — greka NA28, przekład roboczy,
  pod nimi jednostki analizy (fraza grecka + akapit)
- zakładka *Komentarz*: sekcje II–VII wraz z podsekcjami
- zakładka *Ojcowie*: katena patrystyczna z autorem, dziełem i miejscem (locus)
- zakładka *Odniesienia*: tabela z typem relacji i miejscem zaczepienia
- zakładka *Aparat i liturgia*: noty krytyki tekstu, recepcja liturgiczna, motywy
- górne przyciski: *Leksykon* (słowa-klucze z mapą wystąpień) i *Motywy*
- wyszukiwarka u góry: pełnotekstowo po FTS5 (analizy, sekcje, katena, leksykon);
  kliknięcie wyniku otwiera perykopę. Grekę i „ł" wpisuj w pełnym zapisie.

**Punkty API** (przydatne przy własnych narzędziach):
`/api/pericopes`, `/api/pericope?id=N`, `/api/search?q=…`, `/api/lexicon`, `/api/themes`
— wszystkie zwracają JSON.
