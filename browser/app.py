#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Przeglądarka egzegezy Ewangelii Jana — bardzo prosty serwer.

Uruchomienie:   python3 browser/app.py   (lub: make serve)
Potem:          http://localhost:8000

Bez zależności zewnętrznych (tylko biblioteka standardowa).
Baza jest otwierana w trybie tylko do odczytu.
"""
import html
import html.parser
import http.server
import json
import os
import pathlib
import re
import socketserver
import sqlite3
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent          # browser/
ROOT = HERE.parent
DB = ROOT / "data" / "egzegeza_jana.sqlite"
# Baza źródłowa tekstu: interlinia grecko-polska (words), aparat (commentaries)
# i Wulgata (latin_verses). Ewangelia Jana ma w niej numer księgi 500.
# Dołączamy ją do połączenia przez ATTACH jako `zrodlo` — jedno połączenie
# obsługuje obie bazy, a zapytania mogą łączyć egzegezę z tekstem w SQL.
DB_TEKST = ROOT / "db.sqlite"
MA_TEKST = DB_TEKST.exists()
KSIEGA_JANA = 500
PORT = int(os.environ.get("PORT", "8000"))


def _pytaj(sql, args=()):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    if MA_TEKST:
        con.execute("ATTACH DATABASE ? AS zrodlo", (f"file:{DB_TEKST}?mode=ro",))
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def q(sql, args=()):
    return _pytaj(sql, args)


def qt(sql, args=()):
    """Zapytanie sięgające tabel bazy źródłowej (zrodlo.*); bez niej brak danych."""
    if not MA_TEKST:
        return []
    return _pytaj(sql, args)


class _CzystyAparat(html.parser.HTMLParser):
    """Aparat w bazie jest HTML-em z odsyłaczami do wewnętrznej pomocy
    (`href="C:@1018 0"`). Zostawiamy sam tekst i minimalny zestaw znaczników:
    <el> (greka) zamieniamy na rozpoznawalny <span>, resztę odrzucamy."""

    DOZWOLONE = {"sup", "sub", "em", "i", "b", "small"}

    def __init__(self):
        super().__init__()
        self.kawalki = []
        self.stos = []          # źródło bywa niedomknięte — domykamy sami

    def handle_starttag(self, tag, attrs):
        if tag in self.DOZWOLONE:
            self.kawalki.append(f"<{tag}>")
            self.stos.append(tag)
        elif tag == "el":
            self.kawalki.append('<span class="ap-gr">')
            self.stos.append("span")

    def handle_endtag(self, tag):
        znacznik = "span" if tag == "el" else tag
        if znacznik not in self.stos:
            return                       # zamknięcie bez otwarcia — pomijamy
        while self.stos:                 # domknij też to, co zostało otwarte w środku
            otwarty = self.stos.pop()
            self.kawalki.append(f"</{otwarty}>")
            if otwarty == znacznik:
                break

    def handle_data(self, data):
        self.kawalki.append(html.escape(data))

    def zamknij(self):
        self.close()
        while self.stos:
            self.kawalki.append(f"</{self.stos.pop()}>")
        return " ".join("".join(self.kawalki).split())


_SUP = re.compile(r"<sup>((?:(?!</?sup>).)*)</sup>")


def oczysc_aparat(tekst):
    p = _CzystyAparat()
    p.feed(tekst or "")
    wynik = p.zamknij()
    # W źródle bywa gubione </sup>, więc po zbilansowaniu indeksem górnym
    # obejmowane są całe frazy. Prawdziwe siglum jest krótkie (75, *, ms,
    # v.l., 1.13) — dłuższe zawartości rozwijamy do zwykłego tekstu.
    while True:
        krotszy = _SUP.sub(lambda m: m.group(0) if len(m.group(1)) <= 6 else m.group(1), wynik)
        if krotszy == wynik:
            return wynik
        wynik = krotszy


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

    # zakres wersetów porównujemy parami (rozdział, werset) — perykopa może
    # przekraczać granicę rozdziałów (np. J 7,53-8,11)
    zakres = (head["book_id"], head["chapter_start"], head["verse_start"],
              head["chapter_end"], head["verse_end"])

    verses = q("""SELECT v.chapter, v.verse_num, v.text_greek, v.text_working_pl
                  FROM verse v
                  WHERE v.book_id = ?
                    AND (v.chapter, v.verse_num) BETWEEN (?, ?) AND (?, ?)
                  ORDER BY v.chapter, v.verse_num""", zakres)

    sections = q("""SELECT id, parent_id, section_type, title, body_md, position
                    FROM section WHERE pericope_id = ?
                    ORDER BY position, id""", (pid,))

    blocks = q("""SELECT cb.id, cb.section_id, cb.label, cb.greek_text,
                         cb.working_translation_pl, cb.position,
                         cb.chapter_start, cb.verse_start,
                         cb.chapter_end, cb.verse_end
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

    textual = q("""SELECT v.chapter, v.verse_num, tn.lemma_text, tn.issue,
                          tn.readings_md, tn.assessment_md
                   FROM textual_note tn JOIN verse v ON v.id = tn.verse_id
                   WHERE v.book_id = ?
                     AND (v.chapter, v.verse_num) BETWEEN (?, ?) AND (?, ?)
                   ORDER BY v.chapter, v.verse_num""", zakres)

    # leksemy występujące w perykopie — do przypisów słownikowych przy blokach
    lexemes = q("""SELECT l.lemma, l.translit, l.pos, l.gloss_pl,
                          lo.form_in_text, v.chapter, v.verse_num
                   FROM lexeme_occurrence lo
                   JOIN lexeme l ON l.id = lo.lexeme_id
                   JOIN verse v ON v.id = lo.verse_id
                   WHERE v.book_id = ?
                     AND (v.chapter, v.verse_num) BETWEEN (?, ?) AND (?, ?)
                   ORDER BY v.chapter, v.verse_num, l.lemma""", zakres)

    # interlinia grecko-polska z bazy źródłowej (db.sqlite): słowo po słowie,
    # z kodem Stronga, morfologią i znacznikiem `red` (słowa Jezusa)
    interlinia = qt("""SELECT chapter, verse, position, text, translation,
                              strong, morphology, red
                       FROM zrodlo.words
                       WHERE book = ?
                         AND (chapter, verse) BETWEEN (?, ?) AND (?, ?)
                       ORDER BY chapter, verse, position""",
                    (KSIEGA_JANA, head["chapter_start"], head["verse_start"],
                     head["chapter_end"], head["verse_end"]))

    # Wulgata — trzecia kolumna tekstu paralelnego
    lacina = qt("""SELECT chapter, verse, text
                   FROM zrodlo.latin_verses
                   WHERE book = ?
                     AND (chapter, verse) BETWEEN (?, ?) AND (?, ?)
                   ORDER BY chapter, verse""",
                (KSIEGA_JANA, head["chapter_start"], head["verse_start"],
                 head["chapter_end"], head["verse_end"]))

    # aparat krytyczny NA28 (commentaries) — wpisy kluczowane markerem, który
    # jest wpleciony w tekst grecki interlinii (np. °, ⸀, ⸂)
    aparat = [{"chapter": r["chapter_from"], "verse": r["verse_from"],
               "marker": r["marker"], "text": oczysc_aparat(r["text"])}
              for r in qt("""SELECT chapter_from, verse_from, marker, text
                             FROM zrodlo.commentaries
                             WHERE book = ?
                               AND (chapter_from, verse_from) BETWEEN (?, ?) AND (?, ?)
                             ORDER BY chapter_from, verse_from, marker""",
                          (KSIEGA_JANA, head["chapter_start"], head["verse_start"],
                           head["chapter_end"], head["verse_end"]))]

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
            "lexemes": lexemes, "interlinia": interlinia, "aparat": aparat,
            "lacina": lacina, "themes": [t["name"] for t in themes]}


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
    # Każdy motyw rozwijamy do perykop, których dotyka — kotwica motywu
    # (theme_link) wisi na perykopie, sekcji, bloku albo jednostce analizy,
    # więc do perykopy docieramy przez COALESCE po całym łańcuchu.
    rows = q("""
        SELECT t.id AS theme_id, t.name, t.description_md,
               p.id AS pericope_id, p.position, p.title,
               b.abbrev_pl || ' ' || p.chapter_start || ',' || p.verse_start ||
               '-' || CASE WHEN p.chapter_start = p.chapter_end
                           THEN p.verse_end
                           ELSE p.chapter_end || ',' || p.verse_end END AS siglum
        FROM theme t
        LEFT JOIN theme_link tl ON tl.theme_id = t.id
        LEFT JOIN section s   ON s.id  = tl.section_id
        LEFT JOIN commentary_block cb  ON cb.id  = tl.block_id
        LEFT JOIN section s2  ON s2.id = cb.section_id
        LEFT JOIN analysis_unit au ON au.id = tl.analysis_unit_id
        LEFT JOIN commentary_block cb2 ON cb2.id = au.block_id
        LEFT JOIN section s3  ON s3.id = cb2.section_id
        LEFT JOIN pericope p ON p.id = COALESCE(tl.pericope_id, s.pericope_id,
                                                s2.pericope_id, s3.pericope_id)
        LEFT JOIN book b ON b.id = p.book_id
        ORDER BY t.name, p.position, p.id""")
    motywy, indeks = [], {}
    for r in rows:
        m = indeks.get(r["theme_id"])
        if m is None:
            m = {"name": r["name"], "description_md": r["description_md"],
                 "pericopes": [], "_pid": {}}
            indeks[r["theme_id"]] = m
            motywy.append(m)
        pid = r["pericope_id"]
        if pid is None:
            continue
        pp = m["_pid"].get(pid)
        if pp is None:
            pp = {"id": pid, "siglum": r["siglum"], "title": r["title"], "n": 0}
            m["_pid"][pid] = pp
            m["pericopes"].append(pp)
        pp["n"] += 1
    for m in motywy:
        m.pop("_pid")
        m["powiazania"] = sum(pp["n"] for pp in m["pericopes"])
    return motywy


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
        raise SystemExit(f"Brak bazy: {DB}\nUruchom najpierw: python3 tools/egzegeza_jana_build.py")
    socketserver.TCPServer.allow_reuse_address = True  # pozwól ponownie zająć port po restarcie
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Egzegeza Jana — serwer działa:  http://localhost:{PORT}")
        print("Zatrzymanie: Ctrl+C")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nZatrzymano.")
