---
name: perykopa
description: Dodanie nowej perykopy do bazy egzegezy Ewangelii Jana — pełna procedura, struktura danych i kryteria jakości. Użyj zawsze, gdy zadanie brzmi „dodaj perykopę", „opracuj J x,y-z", „kontynuuj egzegezę" albo dotyczy edycji istniejącej perykopy w data/*.json.
---

# Dodanie perykopy

## Zanim napiszesz pierwsze słowo

1. Przeczytaj `CLAUDE.md` (konwencje, uczciwość warsztatowa, pułapki).
2. Obejrzyj wzorzec: `python3 tools/export_pericope.py 1 /tmp/wzor.md` — Prolog
   jest miarą gęstości i tonu. Druga miara, krótsza: perykopa 7 (Kana).
3. Sprawdź, co już jest: `python3 -c "import sqlite3;
   [print(*r) for r in sqlite3.connect('data/egzegeza_jana.sqlite').execute('SELECT siglum,title,status FROM v_spis_perykop')]"`
4. Ustal delimitację perykopy (gdzie się zaczyna i kończy) — kieruj się
   jednostką narracyjną i tradycją lekcjonarzy, nie równą liczbą wersetów.

Uwaga o stanie prac: wszystkie 45 perykop Ewangelii są opracowane. Ten skill
służy dziś przede wszystkim **rewizji istniejącej perykopy**; procedura niżej
opisuje oba wypadki, bo kształt danych jest ten sam.

## Krok 1: gdzie mieszkają dane

Nie dotyka się kodu — dopisuje się dane. Perykopa jest wpisem w tablicy
`pericopes` jednego z plików `data/*.json`. Albo dołączasz ją do pliku
tematycznie bliskiego, albo tworzysz nowy plik i dopisujesz jego nazwę do
listy `PHASES` w `tools/egzegeza_jana_build.py`.

Plik danych ma słownictwo współdzielone i listę perykop:

```jsonc
{
 "books":     [["Am", "Księga Amosa", "ST", 37]],        // tylko NOWE księgi
 "verses":    {"chapter": 2, "items": [[12, "greka NA28", "przekład roboczy"]]},
 "lexemes":   [["ναός", "naos", "rzeczownik", "przybytek — dom samej Obecności"]],
 "semitic":   [],                                        // terminy hbr/aram
 "lexeme_semitic": [], "occurrences": [], "works": [],
 "themes":    [["świątynia — ciało Jezusa", "opis motywu"]],   // tylko NOWE
 "pericopes": [ /* bundle, patrz Krok 2 */ ]
}
```

Pozycje już istniejące pomija `INSERT OR IGNORE` — nie dubluj leksemów
i motywów. Sprawdź przed dopisaniem:
`SELECT lemma FROM lexeme` i `SELECT name FROM theme`.

## Krok 2: bundle perykopy

Klucze obowiązkowe: `pericope`, `intro`, `blocks`, `sections`, `refs`,
`patristic`, `textual`, `theme_links`. Opcjonalne: `struktura`
(renderowana jako podsekcja „Struktura całości" sekcji I), `section_viii`
(wstrzeliwana przed dwie ostatnie sekcje — tak ma Prolog), `citations`,
`revision_note`.

```jsonc
{
 "pericope": {"cs": 2, "vs": 13, "ce": 2, "ve": 22,
              "title": "Oczyszczenie świątyni",
              "motto": "Solvite templum hoc (Zburzcie tę świątynię)",
              "status": "w_opracowaniu", "position": 8},

 "intro": "Akapit wprowadzający do sekcji I — umiejscowienie perykopy w kompozycji księgi i zapowiedź osi interpretacyjnej.",

 "blocks": [                      // sekcja I: tekst + analiza filologiczna
  {"cs": 2, "vs": 13, "ce": 2, "ve": 15,
   "label": "w. 13–15",
   "greek": "pełny tekst grecki bloku (NA28)",
   "transl": "pełny przekład roboczy bloku",
   "units": [                     // [fraza grecka, tłumaczenie, akapit analizy]
    ["τὸ πάσχα τῶν Ἰουδαίων", "Pascha żydowska",
     "Analiza: gramatyka, semantyka, tło semickie, powiązania wewnątrz Ewangelii. Jeden akapit = jedna myśl."]
   ]}
 ],

 // sekcje II–VIII + zakończenie + nota, ZAWSZE w tej kolejności i bez
 // numerów rzymskich w tytule (numery dokłada renderer):
 "sections": [
  {"type": "kontekst",     "title": "Kontekst historyczny, językowy, kulturowy i religijny",
   "body": "…", "children": []},
  {"type": "teologia",     "title": "Obserwacje teologiczne i filozoficzne w duchu tomistycznym",
   "body": "…", "children": []},
  {"type": "autor_ludzki", "title": "Autor ludzki: kim jest i co chce przekazać",
   "body": "…", "children": []},
  {"type": "autor_bozy",   "title": "Autor Boży: co Duch Święty chce przekazać",
   "body": "…", "children": []},
  {"type": "odniesienia",  "title": "Sieć odniesień biblijnych",
   "body": "…", "children": []},
  {"type": "recepcja",     "title": "Znaczenie w historii i liturgii Kościoła",
   "body": null,
   "children": [["Historia dogmatu", "…"], ["Liturgia", "…"]]},   // patrz niżej
  {"type": "patrystyka",   "title": "Komentarze Ojców Kościoła (catena patrum)",
   "body": "Jedno zdanie zapowiadające głosy kateny.", "children": []},
  {"type": "zakonczenie",  "title": "Zakończenie: intencja całości",
   "body": "…", "children": []},
  {"type": "nota",         "title": "Nota warsztatowa", "body": "…", "children": []}
 ],

 // [kotwica, księga, rozdz_od, w_od, rozdz_do, w_do, etykieta, relacja, uwaga]
 // kotwica: ["pericope"] | ["section", tytuł] | ["unit", etykieta_bloku, indeks]
 "refs": [
  [["pericope"], "Za", 14, 21, 14, 21, "Za 14,21", "aluzja", "nie będzie już handlarza w domu Pana"],
  [["unit", "w. 13–15", 0], "Wj", 12, 1, 12, 14, "Wj 12", "tlo", "Pascha — rama chronologiczna Ewangelii"]
 ],

 // [etykieta_bloku, autor, tytuł_dzieła, locus, treść]
 "patristic": [
  ["w. 13–15", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 10",
   "Parafraza myśli Ojca — nie udawany cytat."]
 ],

 // [autor, locus, kotwica, uwaga, tytuł_dzieła]
 "citations": [
  ["św. Tomasz z Akwinu", "Super Io., cap. II", ["section", "Obserwacje teologiczne i filozoficzne w duchu tomistycznym"],
   "Wykład oczyszczenia świątyni.", "Super Evangelium S. Ioannis lectura"]
 ],

 // [nr_wersetu, lemat, typ_problemu, świadkowie, ocena]  (albo 6 elem. z rozdziałem na początku)
 "textual": [[15, "φραγέλλιον", "wariant lekcji", "NA28: … ℵc, A, B …", "ocena"]],

 // [nazwa_motywu, kotwica]  — nazwa musi istnieć w bazie albo w "themes"
 "theme_links": [["świątynia — ciało Jezusa", ["block", "w. 19–22"]]],

 "revision_note": "Data i zakres rewizji — trafia do revision_log."
}
```

**Liturgia nie ma własnego klucza.** Tabelę `liturgical_use` usunięto
w październiku 2026, bo rozjechała się z prozą i zaczęła jej przeczyć.
Recepcja liturgiczna jest **podsekcją sekcji VII** (`recepcja`): ryty, sigla
lekcjonarza, loci Godziny czytań i obrzędy wplatasz w akapit, nie w wiersze
tabeli. Wzorzec: podsekcja „Liturgia" w `data/umycie.json`.

## Krok 3: budowa i kontrola

```bash
make build                                            # baza od zera z data/*.json
python3 tools/export_pericope.py <id> /tmp/kontrola.md   # obejrzyj swoją perykopę
make export                                           # regeneracja egzegeza_jan1.md
```

Walidatora nie ma. Build łapie jedno: rozjazd etykiet bloków kończy się
`KeyError` (`patristic`, `refs` z kotwicą `unit`, `theme_links` z kotwicą
`block` muszą cytować `label` **znak w znak**, z półpauzą). Resztę sprawdź
grepem — półpauza w zakresach i polskie cudzysłowy:

```bash
python3 -c "
import json,glob,re
for f in glob.glob('data/*.json'):
    t = open(f, encoding='utf-8').read()
    for m in re.finditer(r'(?<=\d)-(?=\d)', t):
        print(f, repr(t[m.start()-18:m.end()+10]))" | grep -v '20[0-9][0-9]-'
```

## Kryteria jakości — sprawdź przed commitem

**Sekcja I.** Każdy blok ma grekę NA28 i przekład roboczy. Jednostki
analizy pokrywają frazy niosące ciężar teologiczny — nie każde słowo,
lecz każde ważne. Analiza mówi o gramatyce (czasy, tryby, rodzajniki,
przypadki), semantyce i tle semickim, nie tylko o „przesłaniu".

**Sekcja II.** Konkret historyczny: realia, zwyczaje, archeologia,
judaizm Drugiej Świątyni, targumy, Qumran. Nie ogólniki o „ówczesnych
czasach".

**Sekcja III.** Realna metafizyka Tomasza, nie pobożne uwagi z łacińską
wstawką: akt i możność, istota i istnienie, przyczynowość, uczestnictwo,
łaska i natura. Terminy łacińskie zawsze z tłumaczeniem.

**Sekcja IV** pyta o zamysł literacki i redakcyjny (kompozycja, klamry,
polemika środowiskowa). **Sekcja V** o sens dla Kościoła i czytelnika
dzisiaj — bez kaznodziejstwa, bez drugiej osoby liczby mnogiej.

**Sekcja VI.** Minimum 6–8 odniesień, każde z określoną relacją i uwagą
wyjaśniającą, na czym polega związek. Typologia wymaga wskazania figury
i wypełnienia.

**Sekcja VII.** Historia dogmatu (jeśli perykopa ważyła w sporach),
lekcjonarz, ikonografia, duchowość. Konkretne daty i nazwy. Podsekcja
liturgiczna jest jedynym miejscem recepcji liturgicznej w całej bazie, więc
musi nieść konkret: ryt, okazję i siglum lekcjonarza, a przy obu tradycjach
— rzymską i bizantyjską osobno. Gdzie Wschód czyta perykopę inaczej niż
Zachód, powiedz to wprost; gdzie związek ze świętem jest kalendarzowy albo
kaznodziejski, a nie lekcjonarzowy, też to powiedz — przemilczenie tej
różnicy było źródłem jedynego błędu faktograficznego, jaki ta baza miała
w liturgii.

**Katena.** 3–4 głosy, każdy z innym akcentem — nie trzy warianty tej
samej myśli. Przypisz do bloku, którego realnie dotyczy.

**Aparat.** Noty tekstualne tylko tam, gdzie NA28 notuje realny problem.
Nie wymyślaj wariantów.

## Czego nie robić

- Nie zmieniaj schematu bazy bez wyraźnej potrzeby — jeśli nowa warstwa
  danych nie mieści się w istniejących tabelach, najpierw zapytaj.
- Nie nadawaj statusu `ukonczona`.
- Nie inwestuj w sekcję „Nota warsztatowa": przeglądarka i PDF ją filtrują,
  wchodzi tylko do eksportu Markdown.
- Nie edytuj `data/egzegeza_jana.sqlite` — tylko `data/*.json`, potem `make build`.
- Nie przywracaj tabeli `liturgical_use` ani klucza `liturgy` w bundle'u.
- Nie dubluj leksemów ani motywów, które już są w bazie — sprawdź
  `SELECT lemma FROM lexeme` i `SELECT name FROM theme` przed dopisaniem.
- Nie parafrazuj polskich przekładów objętych prawem autorskim.

## Na koniec

W podsumowaniu podaj: co powstało (liczby: bloki, jednostki, odniesienia,
katena), oś interpretacyjną perykopy, nowe motywy i leksemy — oraz
przypomnienie o weryfikacji loci patrystycznych przy źródłach.
