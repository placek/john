#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eksport statycznej wersji przeglądarki (browser/) — np. dla GitHub Pages.

Uruchomienie:  python3 tools/export_site.py   (wymaga zbudowanej bazy: make build)
Wynik:         site/  — index.html + api/*.json, gotowe do hostingu statycznego

Zasada: żadnej drugiej implementacji API. Importujemy browser/app.py i wołamy
te same funkcje, którymi odpowiada serwer — każdy endpoint zamienia się w plik:

    /api/pericopes        → api/pericopes.json
    /api/pericope?id=N    → api/pericope-N.json
    /api/lexicon          → api/lexicon.json
    /api/themes           → api/themes.json
    /api/search?q=…       → api/szukaj.json (indeks; filtrowanie robi przeglądarka)

index.html jest kopiowany z atrybutem data-static na <html> — frontend sam
przełącza się wtedy na pliki JSON i wyszukiwanie klienckie (zob. browser/index.html).
"""
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "browser"))
import app  # noqa: E402  (browser/app.py — wspólne API)

SITE = ROOT / "site"
API = SITE / "api"


def zapisz(sciezka, dane):
    sciezka.write_text(json.dumps(dane, ensure_ascii=False), encoding="utf-8")
    return sciezka.stat().st_size


def indeks_szukania():
    """Statyczny odpowiednik FTS: te same encje, które indeksuje fts_tresc."""
    wpisy = []

    def dodaj(entity, eid, *czesci):
        tekst = " — ".join(str(c).strip() for c in czesci if c and str(c).strip())
        if not tekst:
            return
        loc = app._locate(entity, eid)
        if loc:
            wpisy.append({**loc, "entity": entity, "tekst": tekst})

    for r in app.q("SELECT id, phrase_greek, phrase_translation_pl, body_md FROM analysis_unit"):
        dodaj("analysis_unit", r["id"], r["phrase_greek"], r["phrase_translation_pl"], r["body_md"])
    for r in app.q("SELECT id, title, body_md FROM section"):
        dodaj("section", r["id"], r["title"], r["body_md"])
    for r in app.q("SELECT id, label, greek_text, working_translation_pl FROM commentary_block"):
        dodaj("commentary_block", r["id"], r["label"], r["greek_text"], r["working_translation_pl"])
    for r in app.q("SELECT id, body_md FROM patristic_comment"):
        dodaj("patristic_comment", r["id"], r["body_md"])
    for r in app.q("SELECT id, lemma, translit, gloss_pl FROM lexeme"):
        dodaj("lexeme", r["id"], r["lemma"], r["translit"], r["gloss_pl"])
    return wpisy


def main():
    if not app.DB.exists():
        raise SystemExit(f"Brak bazy: {app.DB}\nUruchom najpierw: make build")

    if SITE.exists():
        shutil.rmtree(SITE)
    API.mkdir(parents=True)

    perykopy = app.api_pericopes()
    zapisz(API / "pericopes.json", perykopy)
    for p in perykopy:
        zapisz(API / f"pericope-{p['id']}.json", app.api_pericope(p["id"]))
    zapisz(API / "lexicon.json", app.api_lexicon())
    zapisz(API / "themes.json", app.api_themes())
    zapisz(API / "szukaj.json", indeks_szukania())

    html = (ROOT / "browser" / "index.html").read_text(encoding="utf-8")
    znacznik = '<html lang="pl">'
    if znacznik not in html:
        raise SystemExit("Nie znaleziono znacznika <html lang=\"pl\"> w browser/index.html")
    (SITE / "index.html").write_text(
        html.replace(znacznik, '<html lang="pl" data-static>', 1), encoding="utf-8")
    # GitHub Pages: wyłącz Jekylla, żeby nie przetwarzał plików
    (SITE / ".nojekyll").write_text("", encoding="utf-8")

    # pełny tekst w PDF (jeśli złożony: make pdf) — do pobrania z nagłówka strony
    pdf = ROOT / "egzegeza.pdf"
    if pdf.exists():
        shutil.copy(pdf, SITE / "egzegeza.pdf")

    # krój grecki (New Athena Unicode) używany przez @font-face w index.html
    font = ROOT / "newathu.ttf"
    if font.exists():
        shutil.copy(font, SITE / "newathu.ttf")

    rozmiar = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file())
    print(f"OK -> {SITE}  ({len(perykopy)} perykop, {rozmiar} bajtów)")


if __name__ == "__main__":
    main()
