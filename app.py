#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Przeglądarka egzegezy Ewangelii Jana — bardzo prosty serwer.

Uruchomienie:   python3 app.py
Potem:          http://localhost:8000

Bez zależności zewnętrznych (tylko biblioteka standardowa).
Baza jest otwierana w trybie tylko do odczytu.
"""
import http.server
import json
import os
import pathlib
import socketserver
import sqlite3
import urllib.parse

HERE = pathlib.Path(__file__).parent
DB = HERE / "egzegeza_jana.sqlite"
PORT = int(os.environ.get("PORT", "8000"))


def q(sql, args=()):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


# ---------------------------------------------------------------- API
def api_pericopes():
    return q("""
        SELECT p.id, p.title, p.motto, p.status,
               b.abbrev_pl || ' ' || p.chapter_start || ',' || p.verse_start ||
               '-' || CASE WHEN p.chapter_start = p.chapter_end
                           THEN p.verse_end
                           ELSE p.chapter_end || ',' || p.verse_end END AS siglum
        FROM pericope p JOIN book b ON b.id = p.book_id
        ORDER BY p.position
    """)


def api_pericope(pid):
    head = q("""SELECT p.*, b.abbrev_pl FROM pericope p
                JOIN book b ON b.id = p.book_id WHERE p.id = ?""", (pid,))
    if not head:
        return None
    head = head[0]

    verses = q("""SELECT v.verse_num, v.text_greek, v.text_working_pl
                  FROM verse v
                  WHERE v.book_id = ? AND v.chapter = ?
                    AND v.verse_num BETWEEN ? AND ?
                  ORDER BY v.verse_num""",
               (head["book_id"], head["chapter_start"],
                head["verse_start"], head["verse_end"]))

    sections = q("""SELECT id, parent_id, section_type, title, body_md, position
                    FROM section WHERE pericope_id = ?
                    ORDER BY position, id""", (pid,))

    blocks = q("""SELECT cb.id, cb.section_id, cb.label, cb.greek_text,
                         cb.working_translation_pl, cb.position
                  FROM commentary_block cb
                  JOIN section s ON s.id = cb.section_id
                  WHERE s.pericope_id = ? ORDER BY cb.position""", (pid,))

    units = q("""SELECT au.id, au.block_id, au.phrase_greek,
                        au.phrase_translation_pl, au.body_md, au.position
                 FROM analysis_unit au
                 JOIN commentary_block cb ON cb.id = au.block_id
                 JOIN section s ON s.id = cb.section_id
                 WHERE s.pericope_id = ? ORDER BY au.position""", (pid,))

    catena = q("""SELECT cb.label, w.author, w.title AS work_title,
                         w.title_pl, pc.locus, pc.body_md
                  FROM patristic_comment pc
                  JOIN work w ON w.id = pc.work_id
                  JOIN commentary_block cb ON cb.id = pc.block_id
                  JOIN section s ON s.id = cb.section_id
                  WHERE s.pericope_id = ?
                  ORDER BY cb.position, pc.position""", (pid,))

    # odniesienia mogą wisieć na perykopie, sekcji albo jednostce analizy
    refs = q("""SELECT sr.target_label, sr.relation, sr.note_md,
                       CASE WHEN sr.pericope_id IS NOT NULL THEN 'perykopa'
                            WHEN sr.section_id  IS NOT NULL THEN sec.title
                            ELSE 'analiza ' || cb.label END AS kotwica
                FROM scripture_ref sr
                LEFT JOIN section sec ON sec.id = sr.section_id
                LEFT JOIN analysis_unit au ON au.id = sr.analysis_unit_id
                LEFT JOIN commentary_block cb ON cb.id = au.block_id
                LEFT JOIN section s2 ON s2.id = cb.section_id
                WHERE sr.pericope_id = ? OR sec.pericope_id = ? OR s2.pericope_id = ?
                ORDER BY sr.id""", (pid, pid, pid))

    liturgy = q("""SELECT rite, occasion, passage, description_md
                   FROM liturgical_use WHERE pericope_id = ? ORDER BY id""", (pid,))

    textual = q("""SELECT v.verse_num, tn.lemma_text, tn.issue,
                          tn.readings_md, tn.assessment_md
                   FROM textual_note tn JOIN verse v ON v.id = tn.verse_id
                   WHERE v.book_id = ? AND v.chapter = ?
                     AND v.verse_num BETWEEN ? AND ?
                   ORDER BY v.verse_num""",
                (head["book_id"], head["chapter_start"],
                 head["verse_start"], head["verse_end"]))

    themes = q("""SELECT DISTINCT t.name FROM theme_link tl
                  JOIN theme t ON t.id = tl.theme_id
                  LEFT JOIN section s  ON s.id  = tl.section_id
                  LEFT JOIN commentary_block cb ON cb.id = tl.block_id
                  LEFT JOIN section s2 ON s2.id = cb.section_id
                  LEFT JOIN analysis_unit au ON au.id = tl.analysis_unit_id
                  LEFT JOIN commentary_block cb2 ON cb2.id = au.block_id
                  LEFT JOIN section s3 ON s3.id = cb2.section_id
                  WHERE tl.pericope_id = ? OR s.pericope_id = ?
                     OR s2.pericope_id = ? OR s3.pericope_id = ?
                  ORDER BY t.name""", (pid, pid, pid, pid))

    return {"head": head, "verses": verses, "sections": sections,
            "blocks": blocks, "units": units, "catena": catena,
            "refs": refs, "liturgy": liturgy, "textual": textual,
            "themes": [t["name"] for t in themes]}


def api_search(term):
    term = term.strip()
    if not term:
        return []
    rows = q("""SELECT entity, entity_id,
                       snippet(fts_tresc, 0, '<mark>', '</mark>', '…', 18) AS snip
                FROM fts_tresc WHERE fts_tresc MATCH ? LIMIT 60""", (f'"{term}"',))
    out = []
    for r in rows:
        loc = _locate(r["entity"], r["entity_id"])
        if loc:
            out.append({**loc, "snippet": r["snip"], "entity": r["entity"]})
    return out


def _locate(entity, eid):
    """Ustala perykopę i etykietę dla trafienia FTS."""
    if entity == "analysis_unit":
        r = q("""SELECT s.pericope_id AS pid, p.title, cb.label
                 FROM analysis_unit au JOIN commentary_block cb ON cb.id = au.block_id
                 JOIN section s ON s.id = cb.section_id
                 JOIN pericope p ON p.id = s.pericope_id WHERE au.id = ?""", (eid,))
        if r:
            return {"pericope_id": r[0]["pid"], "pericope": r[0]["title"],
                    "where": f"analiza {r[0]['label']}"}
    elif entity == "patristic_comment":
        r = q("""SELECT s.pericope_id AS pid, p.title, cb.label, w.author
                 FROM patristic_comment pc JOIN commentary_block cb ON cb.id = pc.block_id
                 JOIN section s ON s.id = cb.section_id
                 JOIN pericope p ON p.id = s.pericope_id
                 JOIN work w ON w.id = pc.work_id WHERE pc.id = ?""", (eid,))
        if r:
            return {"pericope_id": r[0]["pid"], "pericope": r[0]["title"],
                    "where": f"katena {r[0]['label']} — {r[0]['author']}"}
    elif entity == "section":
        r = q("""SELECT s.pericope_id AS pid, p.title, s.title AS stitle
                 FROM section s JOIN pericope p ON p.id = s.pericope_id
                 WHERE s.id = ?""", (eid,))
        if r:
            return {"pericope_id": r[0]["pid"], "pericope": r[0]["title"],
                    "where": (r[0]["stitle"] or "sekcja")[:60]}
    elif entity == "commentary_block":
        r = q("""SELECT s.pericope_id AS pid, p.title, cb.label
                 FROM commentary_block cb JOIN section s ON s.id = cb.section_id
                 JOIN pericope p ON p.id = s.pericope_id WHERE cb.id = ?""", (eid,))
        if r:
            return {"pericope_id": r[0]["pid"], "pericope": r[0]["title"],
                    "where": f"tekst {r[0]['label']}"}
    elif entity == "lexeme":
        r = q("SELECT lemma FROM lexeme WHERE id = ?", (eid,))
        if r:
            return {"pericope_id": None, "pericope": "Leksykon",
                    "where": r[0]["lemma"]}
    return None


def api_lexicon():
    return q("""SELECT l.lemma, l.translit, l.pos, l.gloss_pl,
                       group_concat(v.chapter || ',' || v.verse_num, '; ') AS miejsca
                FROM lexeme l
                LEFT JOIN lexeme_occurrence lo ON lo.lexeme_id = l.id
                LEFT JOIN verse v ON v.id = lo.verse_id
                GROUP BY l.id HAVING miejsca IS NOT NULL
                ORDER BY l.lemma""")


def api_themes():
    return q("""SELECT t.name, t.description_md,
                       count(tl.id) AS powiazania
                FROM theme t LEFT JOIN theme_link tl ON tl.theme_id = t.id
                GROUP BY t.id ORDER BY t.name""")


ROUTES = {
    "/api/pericopes": lambda p: api_pericopes(),
    "/api/pericope":  lambda p: api_pericope(int(p.get("id", ["1"])[0])),
    "/api/search":    lambda p: api_search(p.get("q", [""])[0]),
    "/api/lexicon":   lambda p: api_lexicon(),
    "/api/themes":    lambda p: api_themes(),
}


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ROUTES:
            try:
                data = ROUTES[parsed.path](urllib.parse.parse_qs(parsed.query))
                payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as exc:  # czytelny błąd zamiast stack trace w przeglądarce
                payload = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(payload)
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, fmt, *args):
        pass  # cisza w konsoli


if __name__ == "__main__":
    os.chdir(HERE)
    if not DB.exists():
        raise SystemExit(f"Brak bazy: {DB}\nUruchom najpierw: python3 egzegeza_jana_build.py")
    socketserver.TCPServer.allow_reuse_address = True  # pozwól ponownie zająć port po restarcie
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Egzegeza Jana — serwer działa:  http://localhost:{PORT}")
        print("Zatrzymanie: Ctrl+C")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nZatrzymano.")
