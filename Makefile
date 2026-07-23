# Egzegeza Ewangelii Jana — build & serve
#
#   make            # zbuduj bazę (jeśli brak) i uruchom serwer
#   make build      # (prze)buduj bazę SQLite od zera
#   make serve      # uruchom serwer webowy (index.html + API)
#   make export     # wyeksportuj wszystkie perykopy do Markdown
#   make export PID=4 [OUT=baranek.md]   # jedną perykopę
#   make clean      # usuń wygenerowaną bazę
#
# Wymaga tylko python3 (biblioteka standardowa) — patrz shell.nix.

PYTHON ?= python3
DB      = egzegeza_jana.sqlite
BUILD   = egzegeza_jana_build.py
APP     = app.py
EXPORT  = export_pericope.py
PORT    ?= 8000
PID     ?= all
OUT     ?=

.PHONY: all serve build rebuild export clean

## zbuduj bazę (jeśli brak) i wystaw stronę z backendem
all: serve

## uruchom serwer — serwuje index.html oraz /api/* na http://localhost:$(PORT)
serve: $(DB)
	PORT=$(PORT) $(PYTHON) $(APP)

## zbuduj bazę SQLite tylko gdy jej nie ma
$(DB): $(BUILD)
	$(PYTHON) $(BUILD)

## wymuś przebudowę bazy od zera
build: $(BUILD)
	$(PYTHON) $(BUILD)

rebuild: clean build

## eksport perykopy do Markdown; PID=all (domyślnie) lub numer, OUT=plik.md (opcjonalnie)
export: $(DB)
	$(PYTHON) $(EXPORT) $(PID) $(OUT)

## usuń wygenerowaną bazę
clean:
	rm -f $(DB)
