---
name: perykopa
description: Dodanie nowej perykopy do bazy egzegezy Ewangelii Jana — pełna procedura, struktura danych i kryteria jakości. Użyj zawsze, gdy zadanie brzmi „dodaj perykopę", „opracuj J x,y-z", „kontynuuj egzegezę" albo dotyczy edycji istniejącej perykopy w data/*.json.
---

# Dodanie perykopy

## Zanim napiszesz pierwsze słowo

1. Przeczytaj `CLAUDE.md` (konwencje, uczciwość warsztatowa, pułapki)
   oraz `humanizer.md` — standard redakcyjny obowiązuje od pierwszego zdania,
   a nie dopiero przy korekcie.
2. Obejrzyj wzorzec: `python3 tools/export_pericope.py 1 /tmp/wzor.md` — Prolog
   jest miarą gęstości i tonu. Druga miara, krótsza: perykopa 7 (Kana).
3. Sprawdź, co już jest: `python3 -c "import sqlite3;
   [print(*r) for r in sqlite3.connect('data/egzegeza_jana.sqlite').execute('SELECT siglum,title,status FROM v_spis_perykop')]"`
4. Ustal delimitację perykopy (gdzie się zaczyna i kończy) — kieruj się
   jednostką narracyjną i tradycją lekcjonarzy, nie równą liczbą wersetów.

Uwaga o stanie prac: wszystkie 45 perykop Ewangelii są opracowane. Ten skill
służy dziś przede wszystkim **rewizji istniejącej perykopy**; procedura niżej
opisuje oba wypadki, bo kształt danych jest ten sam. Jeśli zadanie dotyczy
innej księgi Pisma niż Jan, kształt pracy zostaje ten sam, ale repozytorium
stawia się wedle `NOWA_KSIEGA.md`.

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

## Zapis greki i typografia

**Grekę pisz w formie złożonej (NFC).** Przydech ani akcent nie mogą stać
osobno przed literą. Kolumna grecka sekcji „Tekst perykopy" idzie krojem
ligaturowym RGreekL (`tools/rgreekl.py`), a enkoder normalizuje wejście do NFD
i samodzielny znak rozkłada mu się na spację z markami, **bez litery bazowej**
— przydech i cyrkumfleks przepadają. Pisz `Ἦν` (U+1F2E), nie `῏Ην`
(U+1FCF + Η). Dotyczy to `verses.items[*][1]`, `blocks[*].greek`
i `units[*][0]`.

Dług historyczny: w danych stoi dziś 15 takich miejsc w 11 plikach.
`browser/app.py` składa je w locie (`_zloz_marki`), więc nic nie jest zepsute,
ale nowych nie dokładaj. Samodzielne `᾽` (koronis) i `᾿` (psili) jako znak
elizji — `δ᾽`, `ἀλλ᾽` — są poprawne i zostają; problemem jest wyłącznie znak
stojący **przed literą**.

**Nawiasy edytorskie NA28** (`[ ]`, `( )`) zostają w tekście, ale pamiętaj,
że ten font mapuje `( )` na przydechy, a `[ ]` na litery, więc werset idzie
do API w odcinkach i nawiasy lądują poza krojem ligaturowym. To obsłużone
w kodzie; nie obchodź tego, zmieniając dane.

**Cudzysłowy.** Otwierający to `„` (U+201E), zamykający to **zwykły ASCII `"`**
(U+0022) — nie `”`. W korpusie: `„` 4986×, `"` 4986×, `”` 0×, `’` 0×. Zachowaj
tę równowagę; niedomknięty cudzysłów to błąd danych, którego build nie złapie.

**Pauzy.** Em-pauza `—` dla wtrąceń (11 909 w korpusie), półpauza `–`
w zakresach (3954). Dywiz ze spacjami: 0 wystąpień — nie wprowadzaj go.
Jedyne dywizy między cyframi to daty ISO w notach rewizji.

**Przytoczenia są nienaruszalne.** Fragment w `„…"` dłuższy niż kilka słów to
przytoczony werset, formuła liturgiczna albo zdanie Ojca. Przepisuj go co do
słowa, razem z wielkością liter — zmiana `„na trzeci dzień…"` na
`„Na trzeci dzień…"` przy przebudowie zdania jest już przekłamaniem źródła.

**Zapis plików danych.** `json.dumps(obj, ensure_ascii=False, indent=1)` —
dokładnie to formatowanie, inaczej diff obejmie cały plik zamiast zmienionego
łańcucha. `data/lazarz.json` i `data/pilat.json` nie mają kończącej nowej linii;
zachowaj ten stan.

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

Sprawdź też zapis greki i cudzysłowy. W surowym JSON-ie cudzysłów zamykający
stoi jako `\\"`, więc liczy się jego, nie goły znak:

```bash
python3 - <<'PY'
import glob, re
for f in sorted(glob.glob('data/*.json')):
    t = open(f, encoding='utf-8').read()
    for m in re.finditer(r'[\u1FBD\u1FBF\u1FCF](?=[^\W\d_])', t):
        print('greka niezlozona:', f, repr(t[m.start()-20:m.end()+12]))
    otw, zam = t.count('\u201e'), t.count(r'\"')
    if otw != zam:
        print('cudzyslowy niezbilansowane:', f, otw, '->', zam)
    for z, n in (('\u201d', 'obcy cudzyslow \u201d'), ('\u2019', 'obcy apostrof \u2019')):
        if z in t:
            print(n + ':', f)
PY
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

## Standard redakcyjny: wzorce pisania AI

Procedura stoi w `humanizer.md`; tu jest to, co wyszło z przebiegu po całej
Ewangelii i czego nie widać, pisząc jedną perykopę.

**Najgroźniejszy jest szablon powtórzony między perykopami.** Sekcję
zamykającą **22 perykop** otwierało to samo zdanie („Jeśli zebrać wszystko
w jedno zdanie:"). Pojedynczo brzmi nieszkodliwie, w książce jest to główna
oznaka maszyny. Jeśli łapiesz się na stałym otwarciu sekcji, zmień je.

**Ten sam aforyzm nie może stać w trzech sekcjach.** W Kanie „najlepsze
u Boga nie jest za nami" wracało w sekcji IV, VII i VIII w trzech wariantach,
a sekwencja „brak — słowo — posłuszeństwo — przemiana — chwała — wiara" trzy
razy. Zostaw jedno wystąpienie, w sekcji, do której należy.

**Nie zapowiadaj, że przejdziesz do sedna — przejdź.** Wypadły: „Warto
zauważyć, że…" i dwukropki zapowiadające własną kategorię („Epistemologia
sceny jest precyzyjna:"). Zdanie, które mówi tylko „to, co teraz powiem, jest
ważne", nie wnosi faktu.

**Antytezę „nie X, lecz Y" zostaw tam, gdzie koryguje błędne przekonanie.**
W korpusie jest jej ponad 600 i celowo nie została przerzedzona — „Jan nie
mówi, że Słowo stało się na początku, lecz że było" to rozstrzygnięcie
merytoryczne. Tylko nie używaj jej jako rytmu w każdym akapicie.

**Powtórzenie wersetu kluczowego jest zamierzone.** „JA JESTEM
zmartwychwstaniem i życiem" w intro, strukturze i zakończeniu to nie wzorzec
AI, lecz klamra. Nie ruszaj przytoczeń Pisma przy redakcji stylu.

Przy redakcji po fakcie chroń bezwzględnie: wyrażenia w pismach niełacińskich,
przytoczenia w `„…"` dłuższe niż kilka słów, kursywę (łacina i tytuły dzieł)
oraz sigla i liczby. Tekst po redakcji ma być **krótszy**, nie dłuższy.

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
- Nie dokładaj greki z samodzielnym przydechem przed literą (`῏Ην`) — enkoder
  ligatur gubi literę bazową. Pisz formę złożoną (`Ἦν`).
- Nie otwieraj sekcji zamykającej stałą formułą i nie powtarzaj tej samej
  puenty w kilku sekcjach.
- Nie puszczaj lokalnego modelu po korpusie „dla poprawy stylu". Próbowano
  tego w październiku 2026: przebieg spłaszczał autorską dykcję
  (`licytuje się z Barabaszem o poklask` → `konkuruje o popularność`),
  rozdymał tekst o 6%, podnosił liczbę oznak AI i w leksemach **wymyślał
  grekę** (`οὗτος` → `ὃς οὗτος`). Narzędzie zostało usunięte z repozytorium.

## Na koniec

W podsumowaniu podaj: co powstało (liczby: bloki, jednostki, odniesienia,
katena), oś interpretacyjną perykopy, nowe motywy i leksemy — oraz
przypomnienie o weryfikacji loci patrystycznych przy źródłach.
