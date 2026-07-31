# Egzegeza Ewangelii Jana — build & serve
#
#   make            # zbuduj bazę (jeśli brak) i uruchom serwer
#   make build      # (prze)buduj bazę SQLite od zera z data/*.json
#   make serve      # uruchom serwer webowy (browser/: index.html + API)
#   make export     # wyeksportuj wszystkie perykopy do Markdown
#   make export PID=4 [OUT=baranek.md]   # jedną perykopę
#   make site       # statyczna wersja przeglądarki (site/) — np. GitHub Pages
#   make typst      # reprezentacja Typst (egzegeza.typ)
#   make pdf        # złóż PDF (egzegeza.pdf) — wymaga typst
#   make clean      # usuń wygenerowaną bazę, site/ i eksport Typst
#
# Układ repozytorium:
#   data/     — źródła: schema.sql + *.json (oraz generowana baza)
#   tools/    — narzędzia: egzegeza_jana_build.py, export_pericope.py
#   browser/  — przeglądarka: app.py (backend) + index.html
#
# Wymaga tylko python3 (biblioteka standardowa) — patrz shell.nix.

PYTHON ?= python3
TYPST  ?= typst
DB      = data/egzegeza_jana.sqlite
TYP     = egzegeza.typ
PDF     = egzegeza.pdf
SOURCES = tools/egzegeza_jana_build.py data/schema.sql \
          data/prolog.json data/continuation.json data/kana.json \
          data/swiatynia.json data/nikodem.json data/oblubieniec.json \
          data/samarytanka.json data/dworzanin.json data/betesda.json \
          data/mowa.json data/chleb.json data/eucharystia.json \
          data/bracia.json data/swieto.json data/woda.json data/adultera.json \
          data/swiatlosc.json data/abraham.json data/niewidomy.json data/pasterz.json data/poswiecenie.json data/lazarz.json data/kajfasz.json
BUILD   = tools/egzegeza_jana_build.py
APP     = browser/app.py
EXPORT  = tools/export_pericope.py
PORT    ?= 8000
PID     ?= all
OUT     ?=

.PHONY: all serve build rebuild export site typst pdf clean

## zbuduj bazę (jeśli brak) i wystaw stronę z backendem
all: serve

## uruchom serwer — serwuje index.html oraz /api/* na http://localhost:$(PORT)
serve: $(DB)
	PORT=$(PORT) $(PYTHON) $(APP)

## zbuduj bazę SQLite tylko gdy brak lub gdy zmieniły się źródła
$(DB): $(SOURCES)
	$(PYTHON) $(BUILD)

## wymuś przebudowę bazy od zera
build: $(SOURCES)
	$(PYTHON) $(BUILD)

rebuild: clean build

## eksport perykopy do Markdown; PID=all (domyślnie) lub numer, OUT=plik.md (opcjonalnie)
export: $(DB)
	$(PYTHON) $(EXPORT) $(PID) $(OUT)

## statyczna wersja przeglądarki: site/ (index.html + api/*.json) — hosting bez Pythona
site: $(DB)
	$(PYTHON) tools/export_site.py

## reprezentacja Typst: egzegeza.typ (perykopy + motywy)
typst: $(TYP)

$(TYP): $(DB) tools/export_typst.py
	$(PYTHON) tools/export_typst.py

## złóż PDF z reprezentacji Typst (wymaga typst — patrz shell.nix)
pdf: $(PDF)

$(PDF): $(TYP)
	$(TYPST) compile $(TYP) $(PDF)

## usuń wygenerowaną bazę, stronę statyczną i eksport Typst
clean:
	rm -f $(DB) egzegeza.typ egzegeza.pdf
	rm -rf site
