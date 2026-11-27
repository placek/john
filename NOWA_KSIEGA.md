---
name: nowa-ksiega
description: Jak postawić repozytorium egzegezy dla innej księgi Pisma na wzór tego. Zakres: wymagania wstępne, co się kopiuje, co się przepisuje, decyzje podejmowane raz dla całej księgi, pułapki. Użyj, gdy zadanie brzmi „zrób to samo dla Marka / Rzymian / Amosa" albo „postaw nowe repozytorium egzegezy".
---

# Nowa księga: jak postawić takie repozytorium dla innej księgi Pisma

Ten dokument opisuje przeniesienie **maszynerii**, nie treści. Treść każdej
perykopy pisze się wedle `SKILL.md`, który zostaje aktualny bez zmian — zmienia
się księga, nie kształt pracy. Tu stoi tylko to, czego `SKILL.md` nie obejmuje:
założenie repozytorium od zera i decyzje, które podejmuje się raz.

Stan wzorca na dziś: 45 perykop Jana, 1365 sekcji, 603 jednostki analizy
filologicznej, 783 odniesienia biblijne, 285 głosów kateny, 392 leksemy,
53 motywy przekrojowe, 129 not tekstualnych. Ewangelia jest domknięta.

## Zasada naczelna, od której wszystko zależy

To **warsztat teologiczny, nie generator tekstu**. Objętość nie jest celem —
celem jest gęstość: każde zdanie ma nieść filologię, kontekst albo teologię.
Jeśli akapit da się skreślić bez straty, skreśl. Repozytorium, które produkuje
dużo gładkiego tekstu o niczym, jest porażką, choćby build przechodził.

Druga zasada, równie twarda: **uczciwość warsztatowa**. Treści patrystyczne
pisze się z pamięci, nie z lektury źródeł. Parafrazuj myśl Ojca, nie udawaj
cytatu. Locus podawaj wedle standardowej numeracji, ale jako wskazówkę do
weryfikacji, nie jako pewnik. Nie wymyślaj dzieł ani numerów homilii. To samo
dotyczy dat soborów, wariantów rękopisów i szczegółów liturgicznych. W każdym
podsumowaniu pracy przypominaj, że loci wymagają sprawdzenia przy źródłach.

## Twarde wymaganie wstępne: źródło tekstu

W korzeniu leży `db.sqlite` (24 MB) — źródło prawdy dla samego tekstu, osobne
od egzegezy. Zawiera **wyłącznie Jana**, księgę o numerze 500: 15 635 słów,
879 wersetów Wulgaty, 1528 komentarzy. Dla nowej księgi nie ma w nim nic.
To najdroższy element całego przedsięwzięcia i trzeba go rozstrzygnąć, zanim
napiszesz pierwszą perykopę.

Trzy tabele, które muszą dostać wiersze nowej księgi:

```sql
words(book, chapter, verse, position, text, strong, morphology, translation, red)
latin_verses(book, chapter, verse, text, eusebeios)
commentaries(book, chapter_from, verse_from, chapter_to, verse_to, is_preceding, marker, text)
```

`words` niesie interlinię: wyraz oryginału, numer Stronga, kod morfologiczny,
polski odpowiednik oraz `red` — znacznik słów Jezusa (*verba Christi*).
Przykład z J 1,1: `(500, 1, 1, 1, 'ἀρχῇ', '746', 'n-----dsf-', 'początku', 0)`.
Numer księgi jest w kodzie: `KSIEGA_JANA = 500` w `browser/app.py`. Dla nowej
księgi podstaw jej numer i **zmień nazwę stałej** — inaczej zostanie kłamliwa.

Jeśli nie masz interlinii dla swojej księgi, masz dwa wyjścia: zdobyć ją
z zewnątrz (morfologia i numery Stronga są publicznie dostępne dla całego
kanonu) albo zrezygnować z sekcji interlinearnej i oprzeć sekcję I wyłącznie
na własnym rozbiorze. Drugie wyjście jest uczciwe, ale traci warstwę, która
w przeglądarce jest najmocniejsza. Nie udawaj, że masz dane, których nie masz,
i nie generuj morfologii „z głowy" — kod `n-----dsf-` zmyślony to błąd
faktograficzny podany z pozorem precyzji.

### Księga Starego Testamentu zmienia więcej, niż się wydaje

Cała maszyneria zakłada grekę. Dla księgi hebrajskiej przemyśl osobno:

- tekst źródłowy to BHS, nie NA28 — zmienia się nazwa wydania w tytule
  sekcji I (`SECTION_I_TITLE` w `tools/egzegeza_jana_build.py`);
- kierunek pisma jest prawo-do-lewa, co dotyka CSS przeglądarki i Typsta;
- ligatury RGreekL nie mają zastosowania — cały ten tor wypada;
- `semitic_term` przestaje być tabelą pomocniczą dla obcych wtrąceń
  i staje się trzonem, bo `lang` dopuszcza `hbr` i `aram`;
- aparat krytyczny ma inną postać (Qere/Ketiw, świadkowie masoreccy).

## Co kopiujesz, co przepisujesz, co wyrzucasz

| plik | co z nim zrobić |
|---|---|
| `data/schema.sql` | **kopiuj bez zmian** — osiem warstw jest niezależne od księgi |
| `tools/egzegeza_jana_build.py` | kopiuj, przepisz `PHASES`, `DB`, `SECTION_I_TITLE` i nazwę pliku |
| `tools/export_pericope.py` | kopiuj, przepisz ścieżkę bazy i nazwę pliku eksportu |
| `tools/export_typst.py` | kopiuj, sprawdź kroje i tytuły |
| `tools/export_site.py` | kopiuj bez zmian |
| `browser/app.py` | kopiuj, przepisz `KSIEGA_JANA`, ścieżkę bazy i tytuł serwera |
| `browser/index.html` | kopiuj, przepisz tytuł i kotwicę domyślną |
| `Makefile` | kopiuj, przepisz `SOURCES` i nazwy produktów |
| `.github/workflows/pages.yml` | kopiuj bez zmian |
| `CLAUDE.md`, `SKILL.md` | kopiuj i przepisz pod księgę — to nie są pliki dekoracyjne, agent z nich żyje |
| `humanizer.md` | kopiuj bez zmian |
| `newathu.ttf`, `rgreek.ttf`, `rgreek.ttf.LICENSE`, `tools/rgreekl.py` | tylko dla księgi greckiej |
| `data/*.json` | **nie kopiuj** — to treść Jana |
| `db.sqlite` | nie kopiuj — zobacz wyżej |

## Kolejność robót

1. **Źródło tekstu.** Zdobądź interlinię i Wulgatę (albo odpowiednik) dla
   swojej księgi, złóż `db.sqlite`, sprawdź liczbę słów i rozdziałów.
2. **Szkielet.** Skopiuj schemat, narzędzia, przeglądarkę, Makefile, workflow.
   Przepisz stałe z tabeli powyżej. Zweryfikuj: `make build` na pustym
   `data/` musi przejść i dać bazę z zerami.
3. **Delimitacja.** Podziel księgę na perykopy i zapisz podział **przed**
   pisaniem treści. To decyzja kompozycyjna, nie techniczna, i zmiana jej
   w połowie pracy oznacza przepisywanie odniesień i klamer.
4. **Wprowadzenie.** `data/wprowadzenie.json` — meta księgi plus drzewo
   `intro_section` (we wzorcu 28 sekcji). Wprowadzenie ustawia ton całości,
   więc pisz je po delimitacji, ale przed pierwszą perykopą.
5. **Pierwsza perykopa jako wzorzec.** Opracuj jedną, najchętniej otwierającą
   księgę, i doprowadź ją do stanu, który chcesz powtarzać 40 razy. To ona
   będzie miarą gęstości dla wszystkich następnych, tak jak Prolog jest nią
   tutaj. Nie zaczynaj masowej produkcji przed jej domknięciem.
6. **Reszta perykop** wedle `SKILL.md`, po jednej, z `make build` po każdej.
7. **Przekroje.** Motywy (`theme`, `theme_link`) i leksykon domykaj na końcu,
   gdy widać całą księgę — wcześniej nie wiesz, co jest motywem, a co
   jednorazowym obrazem.
8. **Recenzja przy źródłach.** Dziennik w `data/REVIEW_LOG.md`, wiersz na plik.
   Dopiero po niej status `ukonczona`.

## Decyzje podejmowane raz dla całej księgi

**Delimitacja perykop.** Kieruj się jednostką narracyjną i tradycją
lekcjonarzy, nie równą liczbą wersetów. We wzorcu wyszło 45 perykop na 21
rozdziałów, ale Jan jest księgą o wyraźnych szwach; księga mądrościowa albo
prorocka da inny rozkład i wolno jej go dać.

**Którzy Ojcowie.** Sięgaj po tych, którzy **realnie komentowali tę księgę**.
Dla Jana to Chryzostom i Augustyn (homilia po homilii całą Ewangelię), Cyryl
Aleksandryjski i Orygenes (komentarze ciągłe). Dla innej księgi ten zestaw
będzie inny i trzeba go ustalić na wstępie — dla Psalmów Augustyn i Hilary,
dla Rzymian Chryzostom i Ambrozjaster, dla Izajasza Hieronim i Cyryl.
**Nie dokładaj Ojca tylko dla liczby głosów.** Jeśli księgi nikt z Ojców nie
komentował ciągle, powiedz to w nocie i oprzyj katenę na wzmiankach
rozproszonych, zamiast udawać komentarz, którego nie ma.

**Czy osiem warstw.** Układ I–VIII jest dobrany do Ewangelii. Dla listu
warstwa „autor ludzki" znaczy co innego i waży więcej; dla księgi prorockiej
sekcja o kontekście historycznym rozsadzi resztę, jeśli nie postawisz jej
granic. Wolno zmienić układ — ale zrób to raz, w schemacie i w `SKILL.md`,
nie perykopa po perykopie.

**Przekład.** Własny, roboczy, celowo dosłowny. **Nie cytuj przekładów
objętych prawem autorskim** — ani Biblii Tysiąclecia, ani Paulistów, ani
Warszawskiej. To nie jest ostrożność nadmiarowa, to warunek publikacji.

## Konwencje treści

**Języki obce.** Każde wyrażenie greckie, łacińskie, hebrajskie i aramejskie
dostaje polskie tłumaczenie w nawiasie bezpośrednio po nim — zawsze, także
przy powtórzeniach w tej samej perykopie i w odpowiedziach w czacie:

> ἐσκήνωσεν (rozbił namiot) · *gratia capitis* (łaska głowy) · chesed
> we'emet (łaska i wierność)

Kolejność jest wiążąca: najpierw wyrażenie obce, potem tłumaczenie —
ἦν (było), nie „było" (ἦν).

**Typografia.** Polskie cudzysłowy `„…"`, gdzie znak zamykający jest **zwykłym
ASCII `"`**, nie `”`. Półpauza w zakresach: `w. 6–8`, `J 1,1–14`. Kursywa
Markdown dla terminów łacińskich.

**Ton.** Rzeczowy, gęsty, bez egzaltacji i bez kaznodziejstwa. Zdania
oznajmujące, bez zwracania się do czytelnika w drugiej osobie. Wolno być
pięknym w puencie, nie wolno być rozwlekłym w wywodzie.

**Słowniki (wartości dopuszczane przez `CHECK`).** `section_type`: filologia,
kontekst, teologia, autor_ludzki, autor_bozy, odniesienia, patrystyka,
recepcja, zakonczenie, nota, inne. `relation`: cytat, aluzja, typologia,
paralela, kontrast, rozwiniecie, tlo, por. `tradition`: patrystyka,
scholastyka, magisterium, wspolczesna, judaizm, filozofia_antyczna, inna.
`status`: szkic, w_opracowaniu, ukonczona, do_rewizji. `lang`: hbr, aram.

**Status.** Perykopy pisane przez agenta dostają `w_opracowaniu` — **nigdy**
`ukonczona`. Ten status nadaje wyłącznie człowiek po weryfikacji przy źródłach.

## Pułapki techniczne (sprawdzone boleśnie)

**Etykiety bloków muszą się zgadzać znak w znak.** `patristic`, `refs`
z kotwicą `unit` i `theme_links` z kotwicą `block` odwołują się do `label`
z listy `blocks` — łącznie z półpauzą (`w. 6–8`, nie `w. 6-8`). Rozjazd
kończy się `KeyError` przy budowie, i to **jedyne miejsce, gdzie build łapie
błąd danych za ciebie**. Walidatora nie ma; siatką bezpieczeństwa jest
`make build` plus `CHECK` w schemacie.

**Cudzysłów polski wysadza parser Pythona.** Znak zamykający `"` kończy
łańcuch w podwójnych cudzysłowach. W JSON-ie problem nie występuje, ale wraca
w **każdym skrypcie** dotykającym treści — przy scalaniu liturgii wysadził
parser trzy razy. Treści z `„…"` pisz w potrójnych apostrofach, a dłuższe
bloki podawaj skryptowi przez plik (heredoc `<<'EOF'`), nie literałem.

**Format zapisu plików danych.** `json.dumps(obj, ensure_ascii=False, indent=1)`
— dokładnie to, inaczej diff obejmie cały plik zamiast zmienionego łańcucha.
Sprawdź też, czy plik kończy się nową linią: w tym repozytorium
`data/lazarz.json` i `data/pilat.json` jej nie mają i trzeba ten stan zachować.

**Nigdy nie edytuj zbudowanej bazy.** `data/*.json` są jedynym źródłem prawdy,
baza jest produktem `make build` i powstaje od zera. Jeśli build przechodzi,
commituj.

**Liturgia mieszka w prozie.** Tabelę `liturgical_use` usunięto w październiku
2026, bo dwie warstwy rozjechały się i zaczęły sobie przeczyć. Recepcja
liturgiczna jest podsekcją sekcji VII — sigla lekcjonarza i ryty wplataj
w akapit. Nie przywracaj tabeli. Przy obu tradycjach, rzymskiej i bizantyjskiej,
pisz osobno; gdzie związek ze świętem jest kalendarzowy albo kaznodziejski,
a nie lekcjonarzowy, powiedz to wprost — przemilczenie tej różnicy było
źródłem jedynego błędu faktograficznego, jaki ta baza miała w liturgii.

**FTS5 i diakrytyki.** `remove_diacritics` działa tylko dla łaciny. Greki,
hebrajskiego i polskiego „ł" szukaj w pełnym zapisie: `MATCH 'λόγος'`,
`MATCH 'światłość'`. Indeksowane są `analysis_unit`, `section`,
`commentary_block` i `lexeme`.

**`.gitignore` ignoruje `*.md` i ma białą listę.** Nowy plik Markdown, który
ma być śledzony, trzeba do niej dopisać. Ta reguła raz już połknęła
`CLAUDE.md` i `SKILL.md`: niewidoczne dla przeglądu, rozjechały się z repo.

**Nota warsztatowa nie jest widoczna.** `browser/index.html` i
`export_typst.py` filtrują sekcję „Nota warsztatowa" — wchodzi tylko do
eksportu Markdown. Nie inwestuj w nią pracy.

## Standard redakcyjny: usuwanie wzorców AI

Proza pisana przez model ma rozpoznawalne nawyki i trzeba je usuwać świadomie.
Procedura stoi w `humanizer.md`. Najważniejsza lekcja z przebiegu na Janie:
**najgroźniejszy jest szablon powtórzony między perykopami**, nie pojedyncza
niezgrabność. Sekcję zamykającą 22 perykop otwierało to samo zdanie
(„Jeśli zebrać wszystko w jedno zdanie:"), a ten sam aforyzm wracał w trzech
sekcjach jednej perykopy w trzech wariantach. Żadnej z tych rzeczy nie widać,
czytając jedną perykopę — widać je tylko w przebiegu po całości.

Pisząc, nie zapowiadaj, że przejdziesz do sedna, tylko przejdź. Nie dawaj
jednozdaniowych podsumowań powtarzających wniosek. Nie stawiaj co zdanie
dwukropka zapowiadającego własną kategorię („Epistemologia sceny jest
precyzyjna:"). Antytezę „nie X, lecz Y" zostaw tam, gdzie faktycznie koryguje
błędne przekonanie, a nie jako rytm.

Przy redakcji po fakcie chroń bezwzględnie: wyrażenia w pismach niełacińskich,
przytoczenia w `„…"` dłuższe niż kilka słów, kursywę (łacina i tytuły dzieł),
sigla i liczby. Powtórzenie **wersetu kluczowego** perykopy w intro, strukturze
i zakończeniu jest zamierzone i nie jest wzorcem AI — nie ruszaj go.

## CI, Pages i kroje

`.github/workflows/pages.yml` buduje bazę, składa PDF i eksportuje `site/`
przy każdym pushu na `master`. Dwie rzeczy, które kosztowały tu dzień pracy:

**Wszystko, czego potrzebuje build, musi być w repozytorium.** Runner robi
checkout jednego repozytorium i nie ma dostępu do katalogów obok. Silnik
ligatur i krój trzymane w `../rgreekl` były dla CI niewidoczne i funkcja
degradowała się dokładnie tam, gdzie powstaje publikacja.

**Degradacja bywa cicha i to jest najgorsze.** Brak kroju dawał
`greek_rgreekl: null` we wszystkich 878 wersetach, nieskopiowany font w `site/`
i `unknown font family` od Typsta — a wszystkie trzy kroki kończyły się kodem 0.
Pages wdrażało się na zielono bez ligatur. Jeśli dokładasz krok, który może nie
mieć czegoś potrzebnego, **niech pada albo krzyczy**, bo zielony znaczek
przestaje wtedy cokolwiek znaczyć. Weryfikuj produkt, nie status przebiegu.

**Licencje krojów.** `rgreek.ttf` (Rgreekl2, Vernon E. Kooy) jest freeware:
wolno rozprowadzać i osadzać w dokumencie, **nie wolno modyfikować ani używać
komercyjnie**. Warunki w `rgreek.ttf.LICENSE`. Jeśli planujesz płatne wydanie,
ten krój trzeba zastąpić. `newathu.ttf` ma własne, odrębne warunki.

## Czego nie robić

- Nie nadawaj statusu `ukonczona`.
- Nie edytuj zbudowanej bazy SQLite.
- Nie zmieniaj schematu bez wyraźnej potrzeby; jeśli nowa warstwa danych się
  nie mieści, najpierw zapytaj człowieka.
- Nie parafrazuj przekładów objętych prawem autorskim.
- Nie zmyślaj loci, numerów homilii, kodów morfologicznych ani wariantów
  rękopisów. Lepiej podać autora bez locus niż wymyślić sygnaturę.
- Nie dubluj leksemów i motywów — `INSERT OR IGNORE` je przemilczy, ale dane
  zostaną niespójne. Sprawdź `SELECT lemma FROM lexeme` i `SELECT name FROM theme`.
- Nie puszczaj lokalnego modelu po całym korpusie „dla poprawy stylu".
  Próbowano tu tego: przebieg spłaszczał autorską dykcję, rozdymał tekst o 6%
  i w leksemach **wymyślał grekę**. Został porzucony i usunięty.

## Jak raportować i co znaczy „gotowe"

Raportuj skutki, nie czynności: co powstało w liczbach (bloki, jednostki,
odniesienia, katena), jaka jest oś interpretacyjna perykopy, jakie doszły
motywy i leksemy. Krok, który się wywalił albo dał inny wynik niż zakładano,
podaj wprost — to skutek, nie wątpliwość. Nie dopisuj zastrzeżeń z własnej
inicjatywy, z jednym wyjątkiem, który jest obowiązkowy: **przypomnienie
o weryfikacji loci patrystycznych i szczegółów liturgicznych przy źródłach**
(Źródła Myśli Teologicznej, PSP, Migne) przed publikacją.

Perykopa jest gotowa, gdy `make build` przechodzi, eksport wygląda jak wzorzec,
a treść spełnia kryteria z `SKILL.md`. Księga jest gotowa, gdy przeszła
recenzję przy źródłach, a dziennik recenzji ma wiersz na plik. Build, który
przechodzi, jest warunkiem koniecznym i niczym więcej.
