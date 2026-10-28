# Egzegeza Ewangelii według św. Jana

Baza SQLite z pełną egzegezą perykopa po perykopie. Docelowo: książka
i przeszukiwalna baza analizy wersetów. Język pracy i wszystkich treści:
**polski**.

## Zasada naczelna

Ten projekt to **warsztat teologiczny, nie generator tekstu**. Każda
perykopa dostaje osiem warstw analizy (I–VIII) i katenę Ojców. Objętość
nie jest celem — celem jest gęstość: każde zdanie ma nieść filologię,
kontekst albo teologię. Jeśli akapit da się skreślić bez straty, skreśl.

## Struktura repozytorium

```
data/*.json              # ŹRÓDŁO PRAWDY: 42 pliki (41 z perykopami + wprowadzenie.json)
data/schema.sql          # schemat bazy (warstwy 1–8)
data/egzegeza_jana.sqlite# baza (produkt make build; regenerowalna od zera)
data/REVIEW_LOG.md       # dziennik recenzji naukowej, wiersz na plik
tools/egzegeza_jana_build.py  # budowa bazy z data/*.json
tools/export_pericope.py # baza -> Markdown (pojedyncza perykopa albo 'all')
tools/export_typst.py    # baza -> Typst -> PDF
tools/export_site.py     # baza -> site/ (statyczna wersja dla GitHub Pages)
browser/app.py + browser/index.html   # przeglądarka webowa (localhost:8000)
Makefile                 # build, serve, export, site, typst, pdf, clean
README.md                # dokumentacja techniczna i spis 45 perykop
SKILL.md                 # procedura dodania perykopy (skill „perykopa")
```

Dane **nie mieszkają już w kodzie**. Perykopę dopisuje się jako wpis
w tablicy `pericopes` odpowiedniego `data/*.json`; `tools/egzegeza_jana_build.py`
to sam mechanizm budowy i nie zawiera treści.

## Przepływ pracy przy dodawaniu perykopy

```bash
make build                       # 1. budowa bazy od zera z data/*.json
python3 tools/export_pericope.py 8 /tmp/kontrola.md   # 2. kontrola jednej perykopy
make export                      # 3. regeneracja całości (egzegeza_jan1.md)
```

Walidatora nie ma — `validate.py` nie istnieje. Siatką bezpieczeństwa jest
`make build`: rozjazd etykiet bloków kończy się `KeyError`, a `CHECK`
w schemacie odrzuca wartości poza słownikami. Dodatkowo warto sprawdzić
konwencje grepem: półpauzę w zakresach i polskie cudzysłowy.

Baza jest **zawsze** budowana od zera. Nigdy nie edytuj
`data/egzegeza_jana.sqlite` ręcznie — jedynym źródłem prawdy są `data/*.json`.
Jeśli `make build` przechodzi, commituj.

Szczegółowa procedura dodania nowej perykopy: `SKILL.md` w korzeniu repozytorium.
Przeczytaj ją **zanim** zaczniesz pisać jakiekolwiek dane.

## Stan prac

Wszystkie **45 perykop** (J 1,1 – 21,25) ma status `ukonczona` i przeszło
recenzję naukową — pełny spis z siglami jest w `README.md`, a dziennik
recenzji w `data/REVIEW_LOG.md`. Ewangelia jest domknięta; bieżąca praca to
rewizje, nie nowe perykopy.

`status`: `szkic` → `w_opracowaniu` → `ukonczona` → `do_rewizji`.
Perykopy pisane przez Claude'a dostają **`w_opracowaniu`** — nigdy
`ukonczona`. Status `ukonczona` nadaje wyłącznie Paweł po weryfikacji
przy źródłach.

## Konwencje treści

**Języki obce.** Każde wyrażenie greckie, łacińskie, hebrajskie i aramejskie
dostaje polskie tłumaczenie w nawiasie bezpośrednio po nim — zawsze, także
przy powtórzeniach w tej samej perykopie i w odpowiedziach w czacie:

> ἐσκήνωσεν (rozbił namiot) · *gratia capitis* (łaska głowy) · chesed
> we'emet (łaska i wierność) · talja (baranek/sługa)

**Tekst grecki.** Nestle-Aland, wydanie 28 (NA28). Przekład polski jest
**roboczy, własny, celowo dosłowny** — nie cytuj Biblii Tysiąclecia ani
innych przekładów objętych prawem autorskim. Nie inwestuj w sekcję
„Nota warsztatowa": `browser/index.html` i `export_typst.py` ją filtrują, więc
nie widać jej ani w przeglądarce, ani w PDF — wchodzi tylko do eksportu
Markdown.

**Typografia.** Polskie cudzysłowy „…". Półpauza w zakresach: `w. 6–8`,
`J 1,1–14`. Kursywa Markdown dla terminów łacińskich w akapitach.

**Ton.** Rzeczowy, gęsty, bez egzaltacji i bez kaznodziejstwa. Zdania
oznajmujące. Wolno być pięknym w puencie, nie wolno być rozwlekłym
w wywodzie. Wzorzec: Prolog (perykopa 1) — czytaj go przed pisaniem.

## Uczciwość warsztatowa — WAŻNE

Treści patrystyczne piszesz **z pamięci**, nie z lektury źródeł. To znaczy:

1. Parafrazuj myśl Ojca, nie udawaj cytatu. Cytat dosłowny tylko wtedy,
   gdy jesteś pewien brzmienia (np. *Verbum caro factum est* — Słowo
   ciałem się stało).
2. *Locus* (miejsce w dziele) podawaj wedle standardowej numeracji, ale
   traktuj jako **wskazówkę do weryfikacji**, nie jako pewnik.
3. W podsumowaniu pracy **zawsze** przypomnij, że loci i szczegóły
   wymagają sprawdzenia przy źródłach (Źródła Myśli Teologicznej, PSP,
   Migne) przed publikacją.
4. Nie wymyślaj dzieł ani numerów homilii, których nie kojarzysz.
   Lepiej podać samego autora bez locus niż zmyślić sygnaturę.

Ta zasada obowiązuje tak samo przy datach soborów, wariantach rękopisów
i szczegółach liturgicznych.

## Pułapki techniczne (sprawdzone boleśnie)

**Cudzysłowy w Pythonie.** Polski cudzysłów „…" wewnątrz łańcucha
w podwójnych cudzysłowach wysadza parser, bo znak zamykający `"` kończy
łańcuch. Dane są dziś w JSON-ie, gdzie problem nie występuje, ale pułapka
wraca w **każdym skrypcie** dotykającym treści — przy scalaniu liturgii
w październiku 2026 wysadziła parser trzy razy. Treści z „…" pisz
w potrójnych apostrofach, a przy dłuższych blokach podawaj je skryptowi
przez plik (shellowy heredoc `<<'EOF'`), nie literałem:

```python
("κόσμος", "kosmos", "rzeczownik", '''świat — „ludzkość odwrócona od Boga"'''),
```

**Etykiety bloków muszą się zgadzać.** `patristic`, `refs` z kotwicą
`unit` i `theme_links` z kotwicą `block` odwołują się do etykiet z listy
`blocks` **znak w znak** — łącznie z półpauzą (`w. 6–8`, nie `w. 6-8`).
Rozjazd = `KeyError` przy budowie, i to jedyne miejsce, gdzie build łapie
błąd danych za ciebie.

**Nie edytuj `data/egzegeza_jana.sqlite`.** Zmiany wprowadzasz
w `data/*.json` i przebudowujesz bazę przez `make build`.

**Zapis plików danych.** `json.dumps(obj, ensure_ascii=False, indent=1)` —
dokładnie to formatowanie, inaczej diff obejmie cały plik zamiast
zmienionego łańcucha. `data/lazarz.json` i `data/pilat.json` nie mają
kończącego `\n`; zachowaj ten stan przy zapisie.

**Liturgia mieszka w prozie.** Recepcja liturgiczna jest podsekcją sekcji
VII, nie osobną tabelą — `liturgical_use` usunięto w październiku 2026,
bo dwie warstwy rozjechały się i zaczęły sobie przeczyć. Nie przywracaj
tabeli; sigla lekcjonarza i ryty wplataj w akapit.

**FTS5.** `remove_diacritics` działa tylko dla łaciny. Greki, hebrajskiego
i polskiego „ł" szukaj w pełnym zapisie: `MATCH 'λόγος'`, `MATCH 'światłość'`.
Indeksowane są `analysis_unit`, `section`, `commentary_block` i `lexeme` —
proza sekcji VII jest więc przeszukiwalna, czym tabela liturgii nigdy nie była.

## Słowniki (wartości dozwolone przez CHECK)

- `section_type`: filologia, kontekst, teologia, autor_ludzki, autor_bozy,
  odniesienia, patrystyka, recepcja, zakonczenie, nota, inne
- `relation` (odniesienia): cytat, aluzja, typologia, paralela, kontrast,
  rozwiniecie, tlo, por
- `tradition` (dzieła): patrystyka, scholastyka, magisterium, wspolczesna,
  judaizm, filozofia_antyczna, inna
- `status`: szkic, w_opracowaniu, ukonczona, do_rewizji
- `lang` (terminy semickie): hbr, aram

## Ojcowie obecni w bazie

Orygenes, Tertulian, św. Ireneusz z Lyonu, św. Justyn Męczennik,
św. Atanazy, św. Hilary z Poitiers, św. Grzegorz z Nazjanzu,
św. Jan Chryzostom, św. Augustyn, św. Cyryl Aleksandryjski,
św. Jan Damasceński. Do tego św. Tomasz z Akwinu (scholastyka) i komentarze
współczesne (Brown, Barrett, Schnackenburg, Mędala, Stachowiak).

Przy nowej perykopie sięgaj najpierw po tych, którzy ją realnie komentowali
— Chryzostom i Augustyn przeszli całą Ewangelię homilia po homilii, Cyryl
i Orygenes zostawili komentarze ciągłe. Nie dokładaj Ojca tylko dla
liczby głosów.
