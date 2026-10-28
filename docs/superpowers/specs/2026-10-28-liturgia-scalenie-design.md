# Scalenie liturgii: jedno miejsce zamiast dwóch

Projekt redakcyjno-techniczny. Data: 2026-10-28. Decyzje: Paweł Placzyński.

## Dlaczego

Materia liturgiczna każdej perykopy mieszka dziś w dwóch rozdzielnych
warstwach schematu, które nigdy się nie widzą:

- **warstwa 3** — podsekcja „Liturgia" w sekcji VII („Znaczenie w historii
  i liturgii Kościoła"), proza, składana generycznym rendererem sekcji;
- **warstwa 6** — rekordy `liturgical_use` (`rite`, `occasion`, `passage`,
  `description_md`), składane jako osobna sekcja przez `czescLiturgia()`
  (`browser/index.html:812`) i `liturgia()` (`tools/export_typst.py:319`).

Dwa źródła tej samej prawdy, dwa niezależne renderery i żadnej kontroli
spójności między nimi. Skutek jest dokładnie taki, jakiego należało się
spodziewać: proza i rekordy rozjechały się, a w części perykop **są wprost
sprzeczne**. Wzorcowy przypadek to `continuation.json` (J 1,19–28), gdzie
proza wiąże perykopę z uroczystością Narodzenia św. Jana Chrzciciela
(24 VI), a rekord stwierdza wprost, że 24 VI Ewangelią jest Łk 1,57–66.80,
a J 1,19–28 czyta się 2 stycznia. Rekord ma rację — poprawkę wniosła
recenzja naukowa odnotowana w `data/REVIEW_LOG.md`, ale wniosła ją tylko
do rekordu, bo recenzent poprawiał to, co miał pod ręką. Proza została
z błędem, który renderuje się do dziś w PDF i w przeglądarce.

Scalenie nie jest więc kosmetyką układu. Jest ściągnięciem liturgii do
jednego miejsca, w którym da się ją utrzymać poprawną — i jednorazowym
uzgodnieniem wszystkich 45 perykop z ustaleniami recenzji.

## Co zostało zdecydowane

Dwie decyzje Pawła, podjęte w rozmowie poprzedzającej ten dokument:

**Miejsce: wariant A — wewnątrz sekcji VII.** Scalona liturgia zostaje tam,
gdzie dziś jest proza: jako podsekcja sekcji VII. Tytuł sekcji VII pozostaje
bez zmian („Znaczenie w historii i liturgii Kościoła") i pozostaje uczciwy,
bo liturgia dalej w niej mieszka. Odrzucony wariant B wynosił liturgię do
osobnej sekcji i wymagał przemianowania sekcji VII w 45 plikach.

**Forma: wariant 2 — rekordy znikają.** Rezygnujemy z formy tabelarycznej na
rzecz opisu i odniesienia w prozie. `liturgical_use` wypada ze schematu,
`liturgy` z bundle'a, oba renderery liturgii z kodu. Jedno źródło prawdy,
zero możliwości rozjazdu. Odrzucony wariant 1 zostawiał rekordy w bazie jako
niewidoczny indeks maszynowy — za cenę utrzymywania zgodności prozy
z rekordami przez 45 perykop na lata, czyli za cenę powtórzenia dokładnie
tego mechanizmu, który wygenerował obecne błędy.

Cena wariantu 2, przyjęta świadomie: znika jedyny strukturalny przekrój
liturgiczny bazy. Pytanie „pokaż wszystkie perykopy czytane w Wielkim
Tygodniu" przestaje być sortowaniem po kolumnie `occasion` i staje się
wyszukiwaniem pełnotekstowym po prozie.

Dwie okoliczności istotnie zmniejszają tę cenę i warto je znać, bo nie są
oczywiste:

1. **Proza jest indeksowana w FTS5, rekordy nigdy nie były.** Triggery
   `trg_fts_section_*` wrzucają `section.body_md` do `fts_tresc`;
   `liturgical_use` nie ma żadnego triggera FTS (`data/schema.sql`). Po
   scaleniu liturgia staje się więc *lepiej* przeszukiwalna niż dziś —
   zyskuje indeks, którego jako tabela nie miała.
2. **Eksport Markdown nigdy liturgii nie renderował.** `export_pericope.py`
   nie zna klucza `liturgy` w ogóle. Treść rekordów nie trafiała do
   `egzegeza_jan1.md` — po scaleniu trafi tam jako proza sekcji VII, czyli
   eksport Markdown na scaleniu zyskuje.

## Cele

- Jedno miejsce w książce i w przeglądarce, w którym czytelnik znajduje
  liturgiczną recepcję perykopy: podsekcja liturgiczna sekcji VII.
- Zero utraty treści. Wszystko, co rekordy wnosiły ponad prozę — a wnosiły
  realnie: ryt bizantyjski, sigla lekcjonarza, sakramentalia — jest w prozie
  po scaleniu.
- Rozstrzygnięcie każdej sprzeczności proza/rekord na korzyść ustaleń
  recenzji naukowej.
- Zero rekordów `liturgical_use` i zero kodu je obsługującego po robocie.
- `make build`, `make export`, `make typst` i `make site` przechodzą.

## Czego nie robimy

- Nie przenosimy podsekcji liturgicznej poza sekcję VII i nie zmieniamy
  tytułu sekcji VII.
- Nie piszemy liturgii od nowa i nie dociekamy przy źródłach nowych faktów
  liturgicznych. Scalamy to, co jest; rozstrzygamy sprzeczności na korzyść
  rekordu, bo rekord przeszedł recenzję.
- Nie ruszamy pozostałych podsekcji sekcji VII („Historia dogmatu",
  „Recepcja teologiczna" i pokrewne) — poza wypadkiem opisanym niżej, gdy
  materia liturgiczna jest z nimi zrośnięta.
- Nie zmieniamy statusów perykop. Wszystkie 45 mają `ukonczona`; scalenie
  redakcyjne tego nie unieważnia, bo nie wnosi nowych twierdzeń.
- Nie naprawiamy niezależnych nieaktualności w `CLAUDE.md` (opisuje
  nieistniejący `validate.py` i zdezaktualizowany układ repozytorium). To
  osobna robota — zgłoszona, nie wykonana tutaj.

## Czego nie wolno

- **Rozjazd nie może przeżyć w drugą stronę.** Gdyby po robocie został
  gdziekolwiek rekord `liturgical_use` albo martwy renderer liturgii,
  dostalibyśmy to samo co dziś, tylko z pustą tabelą — gorzej niż przed
  zmianą, bo bez treści i bez widoczności.
- **Scalenie nie może być zlepkiem.** Doklejenie wierszy rekordów na koniec
  prozy jako wyliczenia spełnia literę zadania i niszczy jego sens: łamie
  zasadę naczelną projektu („gęstość, nie objętość") i daje czytelnikowi
  tabelę przebraną w akapit. Proza musi zostać prozą.
- **Nie wolno zgubić faktu, bo się nie mieścił w zdaniu.** Jeśli rekord
  wnosi siglum albo ryt, którego proza nie ma, siglum i ryt muszą w niej być
  po scaleniu — nawet jeśli wymaga to przebudowania akapitu.
- **Nie wolno zmyślić nic po drodze.** Scalenie dwóch istniejących źródeł
  nie jest okazją do uzupełniania luk z pamięci. Czego nie ma w żadnym
  z dwóch źródeł, tego nie dopisujemy.

## Zasada redakcyjna — rdzeń roboty

Dla każdej perykopy: podsekcja liturgiczna sekcji VII wchłania wszystkie
rekordy `liturgy` tej perykopy i zostaje jedynym miejscem liturgii.

Kształt danych, żeby nie szukać: w bundle'u `sections` sekcja VII to obiekt
`{type: "recepcja", title: …, body: null, children: [...]}`, a każde
`children[i]` jest dwuelementową listą `[tytuł, proza_md]`. Redakcja dotyka
wyłącznie elementu `[1]` podsekcji liturgicznej. Rekordy to `liturgy`:
lista list `[rite, occasion, passage, description_md]`.

Krok po kroku, per perykopa:

1. **Zestaw oba źródła.** Wypisz prozę podsekcji liturgicznej i wszystkie
   rekordy (1–6 wierszy, mediana 4).
2. **Zaklasyfikuj każdy rekord** wobec prozy: (a) proza już to mówi równie
   dokładnie — rekord nie wnosi nic, (b) proza mówi to mniej dokładnie —
   rekord wnosi siglum, datę, nazwę rytu, (c) proza tego nie ma — rekord
   wnosi fakt nowy, (d) proza mówi inaczej — **sprzeczność**.
3. **Rozstrzygnij sprzeczności na korzyść rekordu — ale najpierw zajrzyj
   do dziennika.** Przed rozstrzygnięciem przeczytaj wpis recenzji dla tego
   pliku w `data/REVIEW_LOG.md`: często nazywa poprawkę wprost i wtedy nie
   ma czego zgadywać. Wzorcowo `REVIEW_LOG.md:51` (recenzja
   `continuation.json`, 2026-08-29) notuje „recepcję liturgiczną J 1,19–28
   (2 I, nie 24 VI)" — czyli dokładnie tę sprzeczność, z rozstrzygnięciem.
   Gdy dziennik milczy, wybierz rekord: rekordy przeszły recenzję, proza
   w tych miejscach nie.
   Gdy rekord jest wprost polemiczny wobec prozy — jak przytoczony wypadek
   24 VI, gdzie rekord sam tłumaczy, dlaczego potoczne skojarzenie jest
   błędne — polemika wchodzi do prozy, bo ma wartość dydaktyczną.
   Przy sprzeczności, której rekord nie uzasadnia, zapisz ją w podsumowaniu
   do weryfikacji przy źródłach i wybierz rekord.
4. **Przeredaguj akapit, nie dopisuj go.** Wpleć (b) i (c) w istniejący
   wywód tam, gdzie należą merytorycznie. Pomiń (a) — to są powtórzenia,
   a powtórzenie jest tu jedynym realnym ryzykiem rozdęcia tekstu.
5. **Utrzymaj konwencje treści** z `CLAUDE.md`: polskie „…", półpauza
   w zakresach (`J 1,1–14`, nie `J 1,1-14`), każde wyrażenie obce
   z tłumaczeniem w nawiasie bezpośrednio po nim (*ultimum Evangelium* —
   ostatnia Ewangelia), ton oznajmujący, bez kaznodziejstwa. Wzorzec:
   podsekcja „Liturgia" w `prolog.json`.
6. **Objętość.** Podsekcja po scaleniu nie powinna przekroczyć objętości
   prozy sprzed scalenia o więcej niż to, co wnoszą fakty z kategorii (b)
   i (c). Jeśli rośnie bardziej, znaczy, że wchodzą powtórzenia z (a) —
   wróć do kroku 4.

**Tytuł podsekcji.** 38 perykop ma podsekcję „Liturgia" i tam nie ma
pytania. 7 ma tytuł złożony: „Liturgia i duchowość" (`mowa.json`),
„Liturgia: Agnus Dei", „Liturgia i Andrzej Protokletos", „Liturgia
i kalendarz", „Liturgia: Epifania i lekcjonarz" (`continuation.json`),
„Liturgia: wielka katecheza chrzcielna" (`samarytanka.json`), „Adwent
i święta Chrzciciela" (`continuation.json`, bez słowa „liturgia" w ogóle).
Decyzja wykonawcy, nie Pawła: **tytuły zostają.** Są trafne i niosą treść,
a ujednolicenie 45 podsekcji do gołego słowa „Liturgia" odebrałoby
czytelnikowi informację, co w danej perykopie liturgia robi. Normalizujemy
tytuł tylko wtedy, gdy po scaleniu przestał opisywać zawartość.

**Perykopy zrośnięte.** W tych 7 podsekcja liturgiczna niesie też materię
nieliturgiczną (duchowość, kalendarz, ikonografia). Rekordy wchłaniamy do
części liturgicznej akapitu; materii nieliturgicznej nie ruszamy i nie
wynosimy nigdzie. Rozcinanie podsekcji na dwie jest dozwolone tylko wtedy,
gdy po wchłonięciu rekordów akapit przestaje się czytać jako jedna myśl.

## Zmiany techniczne

Wszystkie miejsca, które `liturgical_use` dotyka — lista zamknięta,
z `grep -rn liturg`:

| plik | co zrobić |
|---|---|
| `data/*.json` (45 perykop, 44 pliki) | wchłonąć rekordy w prozę; usunąć klucz `liturgy` z każdego bundle'a |
| `data/schema.sql:239–246` | usunąć `CREATE TABLE liturgical_use` |
| `data/schema.sql:3–11` | przenumerować warstwy w komentarzu nagłówkowym (warstwa 6 „recepcja" znika) |
| `tools/egzegeza_jana_build.py:80` | usunąć `"liturgical_use"` z `TABLES` |
| `tools/egzegeza_jana_build.py:163–165` | usunąć pętlę `INSERT INTO liturgical_use` |
| `browser/app.py:200–201` | usunąć zapytanie `liturgy` |
| `browser/app.py:266` | usunąć `"liturgy": liturgy` z odpowiedzi API |
| `browser/index.html:257–269, 473–474` | usunąć CSS `.liturgia-poz` |
| `browser/index.html:811–825` | usunąć `czescLiturgia()` |
| `browser/index.html:1040` | usunąć wpis `['cz-liturgia', …]` ze spisu części |
| `tools/export_typst.py:319–331` | usunąć `liturgia()` |
| `tools/export_typst.py:422` | usunąć `liturgia(d)` z krotki części |
| `tools/export_typst.py:456` | usunąć `("liturgia", …)` z kontroli warstw |
| `README.md:117` | warstwa „7. Recepcja: `liturgical_use`" znika; przenumerować |
| `README.md:271` | punkt 4 opisu interfejsu („Liturgia — recepcja liturgiczna") znika; przenumerować punkty |
| `README.md` (struktura bundle'a) | usunąć `liturgy` z listy kluczy |
| `data/REVIEW_LOG.md` | dopisać wiersz o scaleniu (data UTC, zakres, liczba rozstrzygniętych sprzeczności) |

`tools/export_site.py` i `.github/workflows/pages.yml` nie wymagają zmian —
eksport statyczny zrzuca endpointy `browser/app.py` w ciemno, więc znika
z nim razem. `tools/export_pericope.py` nie wymaga zmian, bo nigdy klucza
`liturgy` nie znał.

## Kolejność i weryfikacja

Robota idzie partiami, nie jednym rzutem — przy 45 perykopach jeden rzut
znaczy jeden nieprzeglądalny diff.

**Klucz `liturgy` opróżniamy, nie usuwamy — do samego końca.**
`tools/egzegeza_jana_build.py:163` indeksuje `bundle["liturgy"]` twardo, więc
usunięcie klucza w trakcie roboty wysadza `make build` po każdej partii.
Scalona perykopa dostaje `"liturgy": []`; niepusta tablica jest wtedy
widocznym znacznikiem „jeszcze nie scalone", a `make build` chodzi przez całą
robotę. Klucze opróżnione usuwamy hurtem na końcu, razem ze zmianami w kodzie.

Kolejność: najpierw **jedna perykopa wzorcowa** (`prolog.json` — 6 rekordów,
najwięcej w bazie, i to on jest wzorcem tonu projektu), do przyjęcia przez
Pawła. Przyjęty wzorzec ustala próg redakcyjny dla reszty. Potem partie po
kilka plików, alfabetycznie. Zmiany w kodzie i schemacie **na końcu**, po
wyczyszczeniu wszystkich plików danych — wcześniejsze usunięcie klucza
`liturgy` z bundle'a wysadziłoby build, a usunięcie go z build.py
zamaskowałoby nieprzescalone rekordy, zamiast je ujawnić.

**Krok zerowy: świeży punkt odniesienia.** `data/egzegeza_jana.sqlite`
w repozytorium jest nieaktualna (zbudowana 31 lipca, pliki danych zmieniane
28 października), więc nie nadaje się na bazę porównawczą. Przed pierwszą
zmianą: `make build`, potem kopia bazy do katalogu roboczego poza repo. To
wobec niej mierzymy, czy treść nie wyparowała.

Po każdej partii:

```bash
python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('data/*.json')]"
make build
```

Po całości:

```bash
make build && make export && make typst && make site
grep -rn "liturg" --include='*.py' --include='*.sql' --include='*.html' --include='*.json' . | grep -v REVIEW_LOG
```

Drugie polecenie musi nie zwrócić nic. Dodatkowo kontrola, że treść nie
wyparowała: liczba znaków podsekcji liturgicznych w bazie po scaleniu musi
być nie mniejsza niż przed scaleniem — porównanie na kopii bazy sprzed
zmiany.

Projekt nie ma testów automatycznych ani walidatora (`validate.py`
z `CLAUDE.md` nie istnieje), więc `make build` plus powyższe grepy są całą
dostępną siatką bezpieczeństwa. Build jest szczelny w jednym istotnym
miejscu: etykiety bloków muszą się zgadzać znak w znak, inaczej `KeyError`.
Scalenie etykiet nie dotyka.

## Co zostaje wykonawcy

- Konkretne brzmienie każdej z 45 scalonych podsekcji. Zasada redakcyjna
  wyżej mówi, co ma w nich być i czego nie; zdania są do napisania.
- Klasyfikacja (a)–(d) każdego rekordu. Nie da się jej zrobić z góry — to
  lektura dwóch tekstów obok siebie, perykopa po perykopie.
- Podział na partie i ich rozmiar.
- Decyzja, czy w danej z 7 zrośniętych perykop rozciąć podsekcję.

## Po robocie — do zgłoszenia Pawłowi

Obowiązek z `CLAUDE.md`: loci, daty i szczegóły liturgiczne pisane z pamięci
wymagają sprawdzenia przy źródłach. Podsumowanie ma zawierać:

- listę rozstrzygniętych sprzeczności proza/rekord, z informacją, co wybrano;
- listę sprzeczności, których rekord nie uzasadniał — te idą do weryfikacji
  przy źródłach (lekcjonarz rzymski, typikon bizantyjski) w pierwszej
  kolejności;
- przypomnienie, że sigla lekcjonarza wniesione z rekordów dziedziczą
  wiarygodność recenzji, która je wprowadziła, a nie lektury źródła.
