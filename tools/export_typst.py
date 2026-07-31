#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eksport egzegezy do Typst — perykopy + motywy, gotowe do `typst compile`.

Uruchomienie:  python3 tools/export_typst.py   (wymaga zbudowanej bazy: make build)
Wynik:         egzegeza.typ  →  typst compile egzegeza.typ egzegeza.pdf

Zasada jak w export_site.py: żadnej drugiej implementacji API — importujemy
browser/app.py i korzystamy z tych samych funkcji (api_pericope, api_themes…),
więc treść jest identyczna z przeglądarką. Formatowanie jest standardowe
(domyślne nagłówki, krój New Athena Unicode); jedyne niestandardowe elementy —
karty interlinii ze Strongiem i morfologią (MorphGNT).
"""
import html.parser
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "browser"))
import app  # noqa: E402  (browser/app.py — wspólne API)

OUT = ROOT / "egzegeza.typ"

# znaki aparatu NA28 wplecione w tekst grecki — w druku pomijamy
SIGLA = re.compile("[°˸⸀-⸟][¹²³]?")


def bez_sigli(s):
    return SIGLA.sub("", s or "").strip()


# ---- escaping / markdown → Typst -------------------------------------------
def esc(s):
    """Ucieczka znaków specjalnych Typst w trybie treści (bez gwiazdek —
    te obsługuje md())."""
    s = (s or "")
    for a, b in (("\\", "\\\\"), ("#", "\\#"), ("[", "\\["), ("]", "\\]"),
                 ("$", "\\$"), ("`", "\\`"), ("_", "\\_"), ("<", "\\<"),
                 (">", "\\>"), ("@", "\\@"), ("~", "\\~")):
        s = s.replace(a, b)
    return s


def md(s):
    """body_md → treść Typst: akapity, **pogrubienie**, *kursywa*."""
    if not s:
        return ""
    akapity = []
    for blok in re.split(r"\n\n+", s.strip()):
        t = esc(blok).replace("\n", " ")
        t = re.sub(r"\*\*(.+?)\*\*", lambda m: "#strong[" + m.group(1) + "]", t)
        t = re.sub(r"\*(.+?)\*", lambda m: "#emph[" + m.group(1) + "]", t)
        t = t.replace("*", "\\*")
        akapity.append(t)
    return "\n\n".join(akapity)


def q(s):
    """Literał łańcuchowy Typst (bez podstawień pauz/cudzysłowów)."""
    return '"' + (s or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def morf_kod(kod):
    """Kompaktowy kod MorphGNT: bez końcowych myślników."""
    return (kod or "").rstrip("-")


def vnum(d, ch, v):
    return f"{ch},{v}" if d["head"]["chapter_start"] != d["head"]["chapter_end"] else str(v)


class _AparatTyp(html.parser.HTMLParser):
    """Aparat NA28 przychodzi z app.py jako okrojony HTML (sup, em, span.ap-gr…).
    Spłaszczamy go do zwykłego tekstu — świadkowie zostają w całości, tylko bez
    wynoszenia numerów do indeksu górnego. Nie emitujemy wywołań funkcji, więc
    nawias notacji (np. „(β)") nie połączy się w łańcuch wywołań Typst."""

    def __init__(self):
        super().__init__()
        self.buf = []

    def handle_data(self, data):
        # aparat to nie markdown — gwiazdka świadka (ℵ*, D*, B*) jest dosłowna
        self.buf.append(esc(data).replace("*", "\\*"))

    def wynik(self):
        return " ".join("".join(self.buf).split())


def aparat_typ(s):
    p = _AparatTyp()
    p.feed(s or "")
    p.close()
    return p.wynik()


# ---- preambuła --------------------------------------------------------------
PREAMBULA = r"""// PLIK GENEROWANY — python3 tools/export_typst.py. Nie edytować ręcznie.
#let verba    = rgb("#7a1f1f")   // verba Christi — tylko w interlinii
#let naglowek = rgb("#1f5a8f")   // nagłówki — pogrubione, niebieskawe
#let nrwers   = rgb("#c0392b")   // numery wersetów (interlinia i Aparat NA28)

#set document(title: "Egzegeza Ewangelii świętego Jana")
#set page(paper: "a4", margin: (x: 2.1cm, top: 2.4cm, bottom: 2cm),
  numbering: "1", number-align: center,
  header: context {
    // żywa pagina: tytuł bieżącej perykopy (ostatni nagłówek H1 z tej lub
    // wcześniejszej strony); pomijamy na stronie, gdzie tytuł już widnieje
    let p = here().page()
    let hs = query(heading.where(level: 1)).filter(h => h.location().page() <= p)
    if hs.len() > 0 and hs.last().location().page() != p { emph(hs.last().body) }
  })
#set text(font: "New Athena Unicode", size: 11pt, lang: "pl", hyphenate: true)
#set par(justify: true)
#show heading: set text(fill: naglowek, weight: "bold")
#set table(stroke: 0.5pt + luma(70%))   // ramki tabel — szare, cienkie

// karta interlinii — jedyne niestandardowe formatowanie w dokumencie:
// greka / przekład / Strong / morfologia (MorphGNT)
#let iw(gr, pl, s, m, red: false) = box(inset: (x: 1.5pt, y: 1pt), baseline: 0pt,
  stack(dir: ttb, spacing: 4.5pt,
    align(center, text(fill: if red { verba } else { black }, size: 10pt, gr)),
    align(center, text(size: 8pt, pl)),
    align(center, text(fill: luma(110), size: 6pt, s)),
    align(center, text(fill: luma(110), size: 6pt, m)),
  ))
#let iv(n) = text(size: 8.5pt, weight: "bold", fill: nrwers, n)
"""


def naglowek_glowny():
    return [
        PREAMBULA,
        r'#align(center)[',
        r'  #v(3cm)',
        r'  #text(size: 24pt)[Egzegeza Ewangelii świętego Jana]',
        r'  #v(0.6cm)',
        r'  #emph[perykopa po perykopie — filologia, kontekst, teologia, katena Ojców]',
        r']',
        r'#pagebreak()',
        r'#outline(title: [Spis perykop], depth: 1, indent: auto)',
    ]


def tekst_paralelny(d):
    """Grecko-polska (i łacińska) kolumna tekstu perykopy."""
    lac = {(l["chapter"], l["verse"]): l["text"] for l in d.get("lacina", [])}
    jest_lac = bool(lac)
    kol = "(auto, 1fr, 1fr, 1fr)" if jest_lac else "(auto, 1fr, 1fr)"
    out = [r'#block(breakable: true, above: 0.8em)[',
           f'#table(columns: {kol}, stroke: white, inset: (x: 5pt, y: 3pt), align: top + left,']
    rozdz = None
    for v in d["verses"]:
        klucz = (v["chapter"], v["verse_num"])
        if d["head"]["chapter_start"] != d["head"]["chapter_end"] and v["chapter"] != rozdz:
            rozdz = v["chapter"]
            out.append(f'  table.cell(colspan: {4 if jest_lac else 3}, '
                       f'strong[Rozdział {rozdz}]),')
        nr = (str(v["verse_num"]) if d["head"]["chapter_start"] == d["head"]["chapter_end"]
              else f'{v["chapter"]},{v["verse_num"]}')
        cele = [f'iv({q(nr)})',
                q(bez_sigli(v["text_greek"])),
                q(v["text_working_pl"] or "")]
        if jest_lac:
            cele.append(f'emph({q(lac.get(klucz, ""))})')
        out.append("  " + ", ".join(cele) + ",")
    out.append(")]")
    return "\n".join(out)


def interlinia_bloku(d, b):
    """Interlinia dla zakresu bloku: karty słowo-po-słowie ze Strongiem i morfologią."""
    od = (b["chapter_start"], b["verse_start"])
    az = (b["chapter_end"], b["verse_end"])
    slowa = [w for w in d.get("interlinia", [])
             if od <= (w["chapter"], w["verse"]) <= az]
    if not slowa:
        return None
    wersety = {}
    for w in slowa:
        wersety.setdefault((w["chapter"], w["verse"]), []).append(w)
    # każdy werset = wiersz siatki: numer (u góry) + zawijające się karty słów
    komorki = []
    wielo = d["head"]["chapter_start"] != d["head"]["chapter_end"]
    for (ch, v), ws in sorted(wersety.items()):
        nr = f"{ch},{v}" if wielo else str(v)
        karty = []
        for w in ws:
            karty.append('#iw({}, {}, {}, {}{})'.format(
                q(bez_sigli(w["text"])),
                q("" if not w["translation"] or w["translation"] == "-" else w["translation"]),
                q(w["strong"] or ""),
                q(morf_kod(w["morphology"])),
                ", red: true" if w["red"] else ""))
        komorki.append(f'iv({q(nr)})')
        komorki.append("par(justify: false, leading: 1.8em)[" + " ".join(karty) + "]")
    # numer wyrównany do góry wersetu (align: top); cały blok z marginesami
    return ("#block(breakable: true, above: 1.6em, below: 1.6em)[\n"
            "#grid(columns: (auto, 1fr), column-gutter: 5pt, row-gutter: 1.35em, align: top,\n  "
            + ",\n  ".join(komorki) + "\n)\n]")


def aparat_na28(d, b):
    """Aparat krytyczny NA28 (z bazy źródłowej) dla wersetów bloku."""
    od = (b["chapter_start"], b["verse_start"])
    az = (b["chapter_end"], b["verse_end"])
    wpisy = [a for a in d.get("aparat", []) if od <= (a["chapter"], a["verse"]) <= az]
    if not wpisy:
        return ""
    out = [r'#heading(level: 4)[Aparat NA28]']
    for a in wpisy:
        mk = f' {esc(a["marker"])}' if a["marker"] else ""
        out.append(f'#iv({q(vnum(d, a["chapter"], a["verse"]))}){mk} '
                   f'{aparat_typ(a["text"])}\n')
    return "\n".join(out)


def aparat_krytyczny(d, b):
    """Noty krytyki tekstu (własne: warianty, interpunkcja) dla wersetów bloku."""
    od = (b["chapter_start"], b["verse_start"])
    az = (b["chapter_end"], b["verse_end"])
    noty = [t for t in d.get("textual", []) if od <= (t["chapter"], t["verse_num"]) <= az]
    if not noty:
        return ""
    out = [r'#heading(level: 4)[Aparat krytyczny]']
    for t in noty:
        out.append(f'#strong[{esc(t["lemma_text"])}] '
                   f'#emph[(w. {esc(vnum(d, t["chapter"], t["verse_num"]))} · {esc(t["issue"])})]\n')
        if t["readings_md"]:
            out.append(md(t["readings_md"]))
        if t["assessment_md"]:
            out.append(md(t["assessment_md"]))
    return "\n".join(out)


def analiza(d):
    out = [r'#heading(level: 2)[Analiza wers po wersie]']
    catena = {}
    for c in d.get("catena", []):
        catena.setdefault(c["label"], []).append(c)
    for b in d["blocks"]:
        out.append(f'#heading(level: 3)[{esc(b["label"])}]')
        il = interlinia_bloku(d, b)
        if il:
            out.append(il)
        else:
            out.append(f'{q(bez_sigli(b["greek_text"]))}\n')
        if b["working_translation_pl"]:
            out.append(f'#emph[„{esc(b["working_translation_pl"])}”]\n')
        # aparat tuż po tekście (interlinia + przekład), przed egzegezą
        for cz in (aparat_na28(d, b), aparat_krytyczny(d, b)):
            if cz:
                out.append(cz)
        jednostki = [u for u in d["units"] if u["block_id"] == b["id"]]
        if jednostki:
            out.append(r'#heading(level: 4)[Egzegeza]')
        for u in jednostki:
            if u["phrase_greek"]:
                gl = f' #emph[— {esc(u["phrase_translation_pl"])}]' if u["phrase_translation_pl"] else ""
                out.append(f'#strong[{esc(u["phrase_greek"])}]{gl}\n')
            out.append(md(u["body_md"]))
        # katena Ojców przypięta do etykiety bloku
        glosy = catena.get(b["label"], [])
        if glosy:
            out.append(r'#heading(level: 4)[Ojcowie Kościoła]')
        for c in glosy:
            zrodlo = esc(c["title_pl"] or c["work_title"] or "")
            if c["locus"]:
                zrodlo += ", " + esc(c["locus"])
            out.append(f'#strong[{esc(c["author"])}] #emph[{zrodlo}]\n')
            out.append(md(c["body_md"]))
    return "\n\n".join(out)


def komentarz(d):
    glowne = [s for s in d["sections"]
              if s["parent_id"] is None and s["section_type"] not in ("filologia", "patrystyka", "nota")]
    struktura = next((s for s in d["sections"] if s["title"] == "Struktura całości"), None)
    if not glowne and not struktura:
        return ""
    # bez nadrzędnego „Komentarz" — sekcje są bezpośrednio na poziomie 2,
    # a ich podsekcje na 3 (jak wersety w analizie)
    out = []
    if struktura:
        out.append(f'#heading(level: 2)[{esc(struktura["title"])}]')
        out.append(md(struktura["body_md"]))
    for s in glowne:
        out.append(f'#heading(level: 2)[{esc(s["title"])}]')
        if s["body_md"]:
            out.append(md(s["body_md"]))
        for c in [x for x in d["sections"] if x["parent_id"] == s["id"]]:
            out.append(f'#heading(level: 3)[{esc(c["title"])}]')
            out.append(md(c["body_md"]))
    return "\n\n".join(out)


def liturgia(d):
    if not d.get("liturgy"):
        return ""
    out = [r'#heading(level: 2)[Liturgia]']
    for l in d["liturgy"]:
        wiersz = f'#strong[{esc(l["rite"])}] — {esc(l["occasion"])}'
        if l["passage"]:
            wiersz += f' ({esc(l["passage"])})'
        out.append(wiersz + "\n")
        if l["description_md"]:
            out.append(md(l["description_md"]))
    return "\n\n".join(out)


def odniesienia(d):
    if not d.get("refs") and not d.get("themes"):
        return ""
    out = [r'#heading(level: 2)[Odniesienia i motywy]']
    if d.get("refs"):
        out.append('#block(breakable: true)[#table(columns: (auto, auto, 1fr), '
                   'stroke: white, inset: (x: 5pt, y: 3pt), align: top + left,')
        out.append('  table.header(repeat: true, strong[Miejsce], strong[Relacja], strong[Uwaga]),')
        for r in d["refs"]:
            out.append("  " + ", ".join([
                f'strong[{esc(r["target_label"])}]',
                f'emph[{esc(r["relation"])}]',
                f'[{md(r["note_md"]) or ""}]']) + ",")
        out.append(")]")
    if d.get("themes"):
        out.append("*Motywy:* " + ", ".join(esc(t) for t in d["themes"]))
    return "\n".join(out)


def wprowadzenie():
    """Wprowadzenie do całej księgi — pierwszy rozdział dokumentu."""
    w = app.api_intro()
    glowne = [s for s in w["sections"] if not s["parent_id"]]
    dzieci = lambda sid: [s for s in w["sections"] if s["parent_id"] == sid]
    out = [r'#pagebreak(weak: true)',
           f'#heading(level: 1)[{esc(w["title"])}]']
    if w.get("motto"):
        out.append(f'#emph[{esc(w["motto"])}]\n')
    if w.get("lead"):
        out.append(md(w["lead"]))
    for s in glowne:
        out.append(f'#heading(level: 2)[{esc(s["title"])}]')
        if s["body_md"]:
            out.append(md(s["body_md"]))
        for c in dzieci(s["id"]):
            out.append(f'#heading(level: 3)[{esc(c["title"])}]')
            out.append(md(c["body_md"]))
    return "\n\n".join(out)


def perykopa(pid):
    d = app.api_pericope(pid)
    h = d["head"]
    if h["chapter_start"] == h["chapter_end"]:
        siglum = f'{h["abbrev_pl"]} {h["chapter_start"]},{h["verse_start"]}–{h["verse_end"]}'
    else:
        siglum = (f'{h["abbrev_pl"]} {h["chapter_start"]},{h["verse_start"]}'
                  f'–{h["chapter_end"]},{h["verse_end"]}')
    intro = next((s for s in d["sections"]
                  if s["section_type"] == "filologia" and s["parent_id"] is None), None)
    out = [r'#pagebreak(weak: true)']
    out.append(esc(siglum))
    out.append(f'#heading(level: 1)[{esc(h["title"])}]')
    if h["motto"]:
        out.append(f'#emph[{esc(h["motto"])}]\n')
    if intro and intro["body_md"]:
        out.append(md(intro["body_md"]))
    out.append(r'#heading(level: 2)[Tekst perykopy]')
    out.append(tekst_paralelny(d))
    for czesc in (komentarz(d), liturgia(d), analiza(d), odniesienia(d)):
        if czesc:
            out.append(czesc)
    return "\n\n".join(out)


def motywy():
    out = [r'#pagebreak(weak: true)', r'#heading(level: 1)[Motywy]',
           r'#emph[Nici tematyczne przez całą księgę]' + '\n']
    for m in app.api_themes():
        out.append(f'#heading(level: 2)[{esc(m["name"])}]')
        if m.get("description_md"):
            out.append(md(m["description_md"]))
        ps = m.get("pericopes") or []
        if ps:
            out.append("*Perykopy:* " + ", ".join(esc(p["siglum"]) for p in ps))
    return "\n\n".join(out)


def main():
    if not app.DB.exists():
        raise SystemExit(f"Brak bazy: {app.DB}\nUruchom najpierw: make build")
    czesci = naglowek_glowny()
    czesci.append(wprowadzenie())
    for p in app.api_pericopes():
        czesci.append(perykopa(p["id"]))
    czesci.append(motywy())
    OUT.write_text("\n\n".join(czesci) + "\n", encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size} bajtów)\n"
          f"     typst compile {OUT.name} egzegeza.pdf")


if __name__ == "__main__":
    main()
