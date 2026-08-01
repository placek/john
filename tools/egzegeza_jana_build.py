#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Buduje bazę egzegeza_jana.sqlite z plików źródłowych w katalogu ../data.

Ten plik to WYŁĄCZNIE narzędzie — cała treść (schemat i dane) leży osobno:

    data/schema.sql        — schemat bazy (DDL)
    data/wprowadzenie.json — Wprowadzenie do całej księgi (meta + intro_section)
    data/prolog.json       — Prolog (J 1,1-14) + katena
    data/continuation.json — J 1,15-51 (pięć perykop)
    data/kana.json         — J 2,1-11 (Wesele w Kanie)
    data/swiatynia.json    — J 2,12-25 (Oczyszczenie świątyni)
    data/nikodem.json      — J 3,1-21 (Rozmowa z Nikodemem)
    data/oblubieniec.json  — J 3,22-36 (Przyjaciel Oblubieńca)
    data/samarytanka.json  — J 4,1-42 (Samarytanka)
    data/dworzanin.json    — J 4,43-54 (Syn dworzanina)
    data/betesda.json      — J 5,1-18 (Uzdrowienie nad Betesdą)
    data/mowa.json         — J 5,19-47 (Mowa o Synu i świadectwach)
    data/chleb.json        — J 6,1-21 (Rozmnożenie chleba i przejście przez morze)
    data/eucharystia.json  — J 6,22-71 (Mowa eucharystyczna o chlebie życia)
    data/bracia.json       — J 7,1-13 (Niewiara braci i wejście na Święto Namiotów)
    data/swieto.json       — J 7,14-36 (Nauczanie w połowie święta)
    data/woda.json         — J 7,37-52 (Rzeki wody żywej)
    data/adultera.json     — J 7,53-8,11 (Kobieta cudzołożna)
    data/swiatlosc.json    — J 8,12-30 (Światłość świata)
    data/abraham.json      — J 8,31-59 (Prawda, wolność i Abraham)
    data/niewidomy.json    — J 9,1-41 (Uzdrowienie niewidomego od urodzenia)
    data/pasterz.json      — J 10,1-21 (Dobry Pasterz)
    data/poswiecenie.json  — J 10,22-42 (Święto Poświęcenia)
    data/lazarz.json       — J 11,1-44 (Wskrzeszenie Łazarza)
    data/kajfasz.json      — J 11,45-57 (Narada Sanhedrynu i proroctwo Kajfasza)
    data/namaszczenie.json — J 12,1-11 (Namaszczenie w Betanii)
    data/wjazd.json        — J 12,12-19 (Wjazd do Jerozolimy)
    data/ziarno.json       — J 12,20-36 (Grecy i mowa o ziarnie)
    data/bilans.json       — J 12,37-50 (Bilans niewiary i ostatnie wołanie)

Uruchomienie:  python3 tools/egzegeza_jana_build.py
Wynik:         data/egzegeza_jana.sqlite (budowana od zera)

Każdy plik danych ma jednolitą strukturę: słownictwo współdzielone na
poziomie pliku (books, verses, lexemes, semitic, occurrences, works,
themes) oraz listę samodzielnych „perykop" (pericopes). Kolejność wstawień
odtwarza kolejność z oryginalnego monolitu, więc identyfikatory wierszy są
identyczne jak wcześniej.
"""
import json
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "egzegeza_jana.sqlite"
SCHEMA = DATA / "schema.sql"
PHASES = ["prolog.json", "continuation.json", "kana.json", "swiatynia.json",
          "nikodem.json", "oblubieniec.json", "samarytanka.json",
          "dworzanin.json", "betesda.json", "mowa.json", "chleb.json", "eucharystia.json", "bracia.json", "swieto.json", "woda.json", "adultera.json", "swiatlosc.json", "abraham.json", "niewidomy.json", "pasterz.json", "poswiecenie.json", "lazarz.json", "kajfasz.json", "namaszczenie.json", "wjazd.json", "ziarno.json", "bilans.json"]

# Tytuł sekcji I jest strukturalnym szkieletem każdej perykopy (nie treścią).
SECTION_I_TITLE = ("Tekst grecki (Nestle-Aland, wyd. 28) z przekładem "
                   "roboczym i analizą filologiczną")

TABLES = ["intro_section", "book", "verse", "pericope", "section", "commentary_block",
          "analysis_unit", "lexeme", "semitic_term", "lexeme_semitic",
          "lexeme_occurrence", "scripture_ref", "work", "citation",
          "patristic_comment", "liturgical_use", "textual_note",
          "theme", "theme_link"]


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def insert_pericope(cur, bundle, chapter, resolve):
    """Wstawia jedną perykopę wraz z całą jej zawartością."""
    book_of, verse_of, work_of, theme_of = resolve
    pd = bundle["pericope"]
    cur.execute("""INSERT INTO pericope(book_id, chapter_start, verse_start, chapter_end,
                   verse_end, title, motto, status, position, source_url)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (book_of(pd.get("book", "J")), pd["cs"], pd["vs"], pd["ce"], pd["ve"],
                 pd["title"], pd["motto"], pd["status"], pd["position"], pd.get("source_url")))
    pid = cur.lastrowid

    section_id, block_id, unit_id = {}, {}, {}

    def add_section(stype, title, body, parent, pos):
        cur.execute("""INSERT INTO section(pericope_id, parent_id, section_type, title, body_md, position)
                       VALUES (?,?,?,?,?,?)""", (pid, parent, stype, title, body, pos))
        section_id[title] = cur.lastrowid
        return cur.lastrowid

    # Sekcja I: tekst grecki + bloki wersetowe + jednostki analizy
    sec1 = add_section("filologia", SECTION_I_TITLE, bundle["intro"], None, 1)
    for bpos, b in enumerate(bundle["blocks"], start=1):
        cur.execute("""INSERT INTO commentary_block(section_id, chapter_start, verse_start,
                       chapter_end, verse_end, label, greek_text, working_translation_pl, position)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (sec1, b["cs"], b["vs"], b["ce"], b["ve"], b["label"], b["greek"], b["transl"], bpos))
        block_id[b["label"]] = cur.lastrowid
        for upos, (phr, phr_pl, body) in enumerate(b["units"]):
            cur.execute("""INSERT INTO analysis_unit(block_id, phrase_greek, phrase_translation_pl,
                           body_md, position) VALUES (?,?,?,?,?)""",
                        (block_id[b["label"]], phr, phr_pl, body.strip(), upos))
            unit_id[(b["label"], upos)] = cur.lastrowid
    if "struktura" in bundle:
        add_section("filologia", "Struktura całości", bundle["struktura"].strip(), sec1, 99)

    # Sekcje II.. (Prolog: katena/VIII wstrzelona przed dwie ostatnie)
    sections = bundle["sections"]
    if "section_viii" in bundle:
        sections = sections[:-2] + [bundle["section_viii"]] + sections[-2:]
    for spos, s in enumerate(sections, start=2):
        top = add_section(s["type"], s["title"], s["body"], None, spos)
        for cpos, (ct, cb) in enumerate(s["children"], start=1):
            add_section(s["type"], ct, cb.strip(), top, cpos)

    def source_cols(src):
        if src[0] == "pericope":
            return pid, None, None
        if src[0] == "section":
            return None, section_id[src[1]], None
        if src[0] == "unit":
            return None, None, unit_id[(src[1], src[2])]
        raise ValueError(src)

    for src, tb, cs, vs, ce, ve, label, rel, note in bundle["refs"]:
        sp, ss, su = source_cols(src)
        cur.execute("""INSERT INTO scripture_ref(pericope_id, section_id, analysis_unit_id,
                       target_book_id, target_chapter_start, target_verse_start,
                       target_chapter_end, target_verse_end, target_label, relation, note_md)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (sp, ss, su, book_of(tb), cs, vs, ce, ve, label, rel, note))

    for author, locus, src, note, title in bundle.get("citations", []):
        sp, ss, su = source_cols(src)
        cur.execute("""INSERT INTO citation(work_id, locus, pericope_id, section_id,
                       analysis_unit_id, note_md) VALUES (?,?,?,?,?,?)""",
                    (work_of(author, title), locus, sp, ss, su, note))

    pos_per_block = {}
    for blabel, author, wtitle, locus, body in bundle["patristic"]:
        pos_per_block[blabel] = pos_per_block.get(blabel, 0) + 1
        cur.execute("""INSERT INTO patristic_comment(work_id, block_id, locus, body_md, position)
                       VALUES (?,?,?,?,?)""",
                    (work_of(author, wtitle), block_id[blabel], locus, body.strip(),
                     pos_per_block[blabel]))

    for rite, occ, passage, desc in bundle["liturgy"]:
        cur.execute("""INSERT INTO liturgical_use(pericope_id, rite, occasion, passage, description_md)
                       VALUES (?,?,?,?,?)""", (pid, rite, occ, passage, desc))

    for vn, lemma, issue, readings, assessment in bundle["textual"]:
        cur.execute("""INSERT INTO textual_note(verse_id, lemma_text, issue, readings_md, assessment_md)
                       VALUES (?,?,?,?,?)""", (verse_of(chapter, vn), lemma, issue, readings, assessment))

    for name, link in bundle["theme_links"]:
        cols = {"pericope_id": None, "section_id": None, "block_id": None, "analysis_unit_id": None}
        if link[0] == "pericope":
            cols["pericope_id"] = pid
        elif link[0] == "section":
            cols["section_id"] = section_id[link[1]]
        elif link[0] == "block":
            cols["block_id"] = block_id[link[1]]
        elif link[0] == "unit":
            cols["analysis_unit_id"] = unit_id[(link[1], link[2])]
        cur.execute("""INSERT INTO theme_link(theme_id, pericope_id, section_id, block_id, analysis_unit_id)
                       VALUES (?,?,?,?,?)""",
                    (theme_of(name), cols["pericope_id"], cols["section_id"],
                     cols["block_id"], cols["analysis_unit_id"]))

    note = bundle.get("revision_note")
    if not note:
        note = f"Dodano perykopę {pd['title']} (J {pd['cs']},{pd['vs']}-{pd['ve']}) z kateną"
    cur.execute("INSERT INTO revision_log(entity, entity_id, note) VALUES (?,?,?)",
                ("pericope", pid, note))


def insert_phase(cur, data):
    """Wstawia słownictwo współdzielone i wszystkie perykopy jednego pliku."""
    def book_of(ab):
        return cur.execute("SELECT id FROM book WHERE abbrev_pl=?", (ab,)).fetchone()[0]

    def lex_of(lemma):
        return cur.execute("SELECT id FROM lexeme WHERE lemma=?", (lemma,)).fetchone()[0]

    def sem_of(tr):
        return cur.execute("SELECT id FROM semitic_term WHERE translit=?", (tr,)).fetchone()[0]

    def verse_of(chapter, vn):
        return cur.execute("SELECT id FROM verse WHERE chapter=? AND verse_num=?",
                           (chapter, vn)).fetchone()[0]

    def work_of(author, title):
        # `IS` jest bezpieczne dla NULL — część dzieł ma tylko autora (title=None)
        return cur.execute("SELECT id FROM work WHERE author IS ? AND title IS ?",
                           (author, title)).fetchone()[0]

    def theme_of(name):
        return cur.execute("SELECT id FROM theme WHERE name=?", (name,)).fetchone()[0]

    for key, value in data.get("meta", []):
        cur.execute("INSERT INTO meta(key, value) VALUES (?,?)", (key, value))

    for ab, nm, tst, ordn in data["books"]:
        cur.execute("INSERT OR IGNORE INTO book(abbrev_pl, name_pl, testament, canon_order) VALUES (?,?,?,?)",
                    (ab, nm, tst, ordn))

    chapter = data["verses"]["chapter"]
    # pozycja wersetu to [nr, greka, przekład] w rozdziale pliku albo
    # [rozdział, nr, greka, przekład] — dla perykop przekraczających granicę
    # rozdziałów (np. J 7,53 na progu perykopy o cudzołożnicy)
    for item in data["verses"]["items"]:
        ch, vn, gk, pl = item if len(item) == 4 else (chapter, *item)
        cur.execute("INSERT INTO verse(book_id, chapter, verse_num, text_greek, text_working_pl) VALUES (?,?,?,?,?)",
                    (book_of("J"), ch, vn, gk, pl))

    for lemma, tr, pos_, gl in data["lexemes"]:
        cur.execute("INSERT OR IGNORE INTO lexeme(lemma, translit, pos, gloss_pl) VALUES (?,?,?,?)",
                    (lemma, tr, pos_, gl))

    for term, tr, lang, gl in data["semitic"]:
        cur.execute("INSERT OR IGNORE INTO semitic_term(term, translit, lang, gloss_pl) VALUES (?,?,?,?)",
                    (term, tr, lang, gl))

    for lemma, sem_tr, note in data.get("lexeme_semitic", []):
        cur.execute("INSERT OR IGNORE INTO lexeme_semitic(lexeme_id, semitic_id, relation_note) VALUES (?,?,?)",
                    (lex_of(lemma), sem_of(sem_tr), note))

    for lemma, vn, form in data["occurrences"]:
        cur.execute("INSERT INTO lexeme_occurrence(lexeme_id, verse_id, form_in_text) VALUES (?,?,?)",
                    (lex_of(lemma), verse_of(chapter, vn), form))

    for author, title, title_pl, century, trad in data["works"]:
        cur.execute("INSERT OR IGNORE INTO work(author, title, title_pl, century, tradition) VALUES (?,?,?,?,?)",
                    (author, title, title_pl, century, trad))

    for name, desc in data["themes"]:
        cur.execute("INSERT OR IGNORE INTO theme(name, description_md) VALUES (?,?)", (name, desc))

    resolve = (book_of, verse_of, work_of, theme_of)
    for bundle in data["pericopes"]:
        insert_pericope(cur, bundle, chapter, resolve)


def insert_intro(cur, data):
    """Wprowadzenie do całej księgi: meta (tytuł/motto/lead) + drzewo intro_section."""
    intro = data["intro"]
    for key in ("title", "motto", "lead"):
        cur.execute("INSERT INTO meta(key, value) VALUES (?,?)",
                    (f"intro_{key}", intro[key]))
    for spos, s in enumerate(intro["sections"], start=1):
        cur.execute("""INSERT INTO intro_section(parent_id, title, body_md, position)
                       VALUES (NULL,?,?,?)""", (s["title"], s["body"].strip(), spos))
        top = cur.lastrowid
        for cpos, (ct, cb) in enumerate(s.get("children", []), start=1):
            cur.execute("""INSERT INTO intro_section(parent_id, title, body_md, position)
                           VALUES (?,?,?,?)""", (top, ct, cb.strip(), cpos))


def build():
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    cur = con.cursor()

    insert_intro(cur, load("wprowadzenie.json"))
    for name in PHASES:
        insert_phase(cur, load(name))

    con.commit()
    for t in TABLES:
        n = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"{t:20s} {n:4d}")
    con.close()
    print(f"\nOK -> {DB}")


if __name__ == "__main__":
    if not SCHEMA.exists():
        raise SystemExit(f"Brak schematu: {SCHEMA}")
    build()
