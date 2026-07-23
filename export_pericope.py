# -*- coding: utf-8 -*-
"""
Eksport perykopy z bazy egzegeza_jana.sqlite do Markdown.
Użycie: python3 export_pericope.py [id_perykopy|all] [plik_wyjsciowy.md]
Domyślnie: perykopa 1 -> prolog_export.md; 'all' -> wszystkie perykopy do jednego pliku.
Z tego samego źródła można później generować LaTeX/PDF (pandoc), stronę www itd.
"""
import sqlite3, pathlib, sys

DB = pathlib.Path(__file__).with_name("egzegeza_jana.sqlite")
ARG = sys.argv[1] if len(sys.argv) > 1 else "1"
OUT = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else pathlib.Path(__file__).with_name(
    "egzegeza_jan1.md" if ARG == "all" else "prolog_export.md")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
cur = con.cursor()

meta = dict(cur.execute("SELECT key, value FROM meta"))
out = []
out.append(f"# {meta.get('projekt', 'Egzegeza')}")

def emit_section(sec):
    out.append(f"\n## {sec['title']}" if sec["parent_id"] is None else f"\n### {sec['title']}")
    if sec["body_md"]:
        out.append("\n" + sec["body_md"])
    # bloki komentarza wersetowego w tej sekcji
    for blk in cur.execute("""SELECT * FROM commentary_block WHERE section_id = ?
                              ORDER BY position""", (sec["id"],)).fetchall():
        out.append(f"\n### {blk['label']}")
        if blk["greek_text"]:
            out.append("\n" + blk["greek_text"])
        if blk["working_translation_pl"]:
            out.append(f"\n„{blk['working_translation_pl']}\u201d")
        for u in cur.execute("""SELECT * FROM analysis_unit WHERE block_id = ?
                                ORDER BY position""", (blk["id"],)).fetchall():
            if u["phrase_greek"]:
                gloss = f" ({u['phrase_translation_pl']})" if u["phrase_translation_pl"] else ""
                out.append(f"\n**{u['phrase_greek']}**{gloss}")
            out.append("\n" + u["body_md"])
    # podsekcje
    for child in cur.execute("""SELECT * FROM section WHERE parent_id = ?
                                ORDER BY position""", (sec["id"],)).fetchall():
        emit_section(child)
    # katena patrystyczna (sekcja typu 'patrystyka' składa się z tabeli)
    if sec["section_type"] == "patrystyka" and sec["parent_id"] is None:
        for c in cur.execute("""SELECT b.label, w.author, w.title, p.locus, p.body_md
                                FROM patristic_comment p
                                JOIN work w ON w.id = p.work_id
                                JOIN commentary_block b ON b.id = p.block_id
                                JOIN section s2 ON s2.id = b.section_id
                                WHERE s2.pericope_id = ?
                                ORDER BY b.position, p.position""", (sec["pericope_id"],)).fetchall():
            out.append(f"\n### {c['label']} — {c['author']}")
            out.append(f"\n*{c['title']}*, {c['locus']}" if c["locus"] else f"\n*{c['title']}*")
            out.append("\n" + c["body_md"])

def emit_pericope(PER_ID):
    p = cur.execute("""SELECT p.*, b.abbrev_pl FROM pericope p
                   JOIN book b ON b.id = p.book_id WHERE p.id = ?""", (PER_ID,)).fetchone()
    siglum = (f"{p['abbrev_pl']} {p['chapter_start']},{p['verse_start']}-{p['verse_end']}"
              if p["chapter_start"] == p["chapter_end"]
              else f"{p['abbrev_pl']} {p['chapter_start']},{p['verse_start']}-{p['chapter_end']},{p['verse_end']}")
    out.append(f"\n\n---\n\n# {p['title']} ({siglum})")
    if p["motto"]:
        out.append(f"\n*{p['motto']}*")

    for sec in cur.execute("""SELECT * FROM section WHERE pericope_id = ? AND parent_id IS NULL
                              ORDER BY position""", (PER_ID,)).fetchall():
        emit_section(sec)

    refs = cur.execute("""SELECT target_label, relation, note_md FROM scripture_ref
                          WHERE pericope_id = ? ORDER BY id""", (PER_ID,)).fetchall()
    if refs:
        out.append("\n## Indeks odniesień (z bazy)")
        for r in refs:
            note = f" — {r['note_md']}" if r["note_md"] else ""
            out.append(f"\n- **{r['target_label']}** ({r['relation']}){note}")

if ARG == "all":
    ids = [r[0] for r in cur.execute("SELECT id FROM pericope ORDER BY position")]
else:
    ids = [int(ARG)]
for pid_ in ids:
    emit_pericope(pid_)

OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"OK -> {OUT} ({OUT.stat().st_size} bajtów)")
con.close()
