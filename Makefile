# Egzegeza Ewangelii Jana — build & serve
#
#   make            # zbuduj bazę (jeśli brak) i uruchom serwer
#   make build      # (prze)buduj bazę SQLite od zera
#   make serve      # uruchom serwer webowy (index.html + API)
#   make clean      # usuń wygenerowaną bazę
#
# Wymaga tylko python3 (biblioteka standardowa) — patrz shell.nix.

PYTHON ?= python3
DB      = egzegeza_jana.sqlite
BUILD   = egzegeza_jana_build.py
APP     = app.py
PORT    ?= 8000

.PHONY: all serve build rebuild clean

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

## usuń wygenerowaną bazę
clean:
	rm -f $(DB)
