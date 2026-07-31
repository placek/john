#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eksport egzegezy do Typst — perykopy + motywy, gotowe do `typst compile`.

Uruchomienie:  python3 tools/export_typst.py   (wymaga zbudowanej bazy: make build)
Wynik:         egzegeza.typ  →  typst compile egzegeza.typ egzegeza.pdf

Zasada jak w export_site.py: żadnej drugiej implementacji API — importujemy
browser/app.py i korzystamy z tych samych funkcji (api_pericope, api_themes…),
więc treść jest identyczna z przeglądarką. Dokument stara się odwzorować wygląd
strony (paleta Solarized, układ sekcji). Komentarz jest justowany; interlinia
zawiera numery Stronga i morfologię (kod MorphGNT).
"""
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


# ---- preambuła --------------------------------------------------------------
PREAMBULA = r"""// PLIK GENEROWANY — python3 tools/export_typst.py. Nie edytować ręcznie.
// Neutralna typografia druku: czerń na bieli, szarości dla treści drugoplanowej.
#let tlo    = white
#let ink    = rgb("#1a1a1a")
#let muted  = rgb("#6b6b6b")
#let linia  = rgb("#cccccc")
#let accent = rgb("#111111")
#let greek  = rgb("#1a1a1a")
#let gold   = rgb("#7a7a7a")
#let verba  = rgb("#7a1f1f")   // verba Christi — tradycja czerwonej litery
#let latina = rgb("#555555")

#set document(title: "Egzegeza Ewangelii świętego Jana")
#set page(paper: "a4", margin: (x: 2.1cm, top: 2.2cm, bottom: 2cm), fill: tlo,
  numbering: "1", number-align: center)
#set text(font: ("New Computer Modern", "Noto Serif"), fill: ink, size: 10pt,
  lang: "pl", hyphenate: true)
#set par(justify: true, leading: 0.62em, spacing: 0.9em)
#show link: set text(fill: greek)

#show heading: set text(fill: accent, weight: "regular")
#show heading.where(level: 1): set text(size: 19pt)
#show heading.where(level: 2): set text(size: 13pt)
#show heading.where(level: 3): it => block(above: 1em, below: 0.5em,
  text(size: 10.5pt, fill: gold, weight: "bold", it.body))
#show heading.where(level: 4): it => text(size: 9.5pt, fill: muted,
  weight: "bold", tracking: 0.04em, upper(it.body))

// karta interlinii: greka / przekład / Strong / morfologia (MorphGNT)
#let iw(gr, pl, s, m, red: false) = box(inset: (x: 1.5pt, y: 1pt), baseline: 0pt,
  stack(dir: ttb, spacing: 1.2pt,
    align(center, text(fill: if red { verba } else { greek }, size: 9.5pt, weight: "medium", gr)),
    align(center, text(size: 7pt, pl)),
    align(center, text(fill: gold, size: 5.4pt, s)),
    align(center, text(fill: muted, size: 5.4pt, m)),
  ))
// numer wersetu w interlinii
#let iv(n) = text(fill: gold, weight: "bold", size: 8pt, n)
// żeton (siglum, relacja, motyw)
#let pill(body) = box(inset: (x: 4pt, y: 1pt), outset: (y: 1pt), radius: 3pt,
  stroke: 0.5pt + linia, text(size: 8pt, fill: gold, body))
#let sig(body) = text(size: 8.5pt, fill: gold, tracking: 0.08em, smallcaps(body))
"""


def naglowek_glowny():
    return [
        PREAMBULA,
        r'#align(center)[',
        r'  #v(3cm)',
        r'  #text(size: 26pt, fill: accent)[Egzegeza Ewangelii]',
        r'  #linebreak()',
        r'  #text(size: 26pt, fill: accent)[świętego Jana]',
        r'  #v(0.6cm)',
        r'  #text(size: 11pt, fill: muted, style: "italic")[perykopa po perykopie — filologia, kontekst, teologia, katena Ojców]',
        r'  #v(0.4cm)',
        r'  #line(length: 40%, stroke: 0.5pt + linia)',
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
           f'#table(columns: {kol}, stroke: none, inset: (x: 5pt, y: 3pt), align: top + left,']
    rozdz = None
    for v in d["verses"]:
        klucz = (v["chapter"], v["verse_num"])
        if d["head"]["chapter_start"] != d["head"]["chapter_end"] and v["chapter"] != rozdz:
            rozdz = v["chapter"]
            out.append(f'  table.cell(colspan: {4 if jest_lac else 3}, '
                       f'text(fill: gold, size: 8pt, weight: "bold")[Rozdział {rozdz}]),')
        nr = (str(v["verse_num"]) if d["head"]["chapter_start"] == d["head"]["chapter_end"]
              else f'{v["chapter"]},{v["verse_num"]}')
        cele = [f'text(fill: gold, size: 7.5pt)[{esc(nr)}]',
                f'text(fill: greek, size: 9.5pt, {q(bez_sigli(v["text_greek"]))})',
                f'text(size: 9.5pt, {q(v["text_working_pl"] or "")})']
        if jest_lac:
            cele.append(f'text(fill: latina, size: 9pt, style: "italic", {q(lac.get(klucz, ""))})')
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
    linie = []
    wielo = d["head"]["chapter_start"] != d["head"]["chapter_end"]
    for (ch, v), ws in sorted(wersety.items()):
        nr = f"{ch},{v}" if wielo else str(v)
        karty = [f'#iv({q(nr)})']
        for w in ws:
            karty.append('#iw({}, {}, {}, {}{})'.format(
                q(bez_sigli(w["text"])),
                q("" if not w["translation"] or w["translation"] == "-" else w["translation"]),
                q(w["strong"] or ""),
                q(morf_kod(w["morphology"])),
                ", red: true" if w["red"] else ""))
        linie.append("#par(justify: false, leading: 1.8em, spacing: 1.35em)[\n  "
                     + " ".join(karty) + "\n]")
    return "\n".join(linie)


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
            out.append(f'#text(fill: greek, size: 10pt, {q(bez_sigli(b["greek_text"]))})\n')
        if b["working_translation_pl"]:
            out.append(f'#block(above: 0.5em, below: 0.6em, text(style: "italic", fill: muted)[„{esc(b["working_translation_pl"])}”])')
        for u in [u for u in d["units"] if u["block_id"] == b["id"]]:
            if u["phrase_greek"]:
                gl = f' #emph[— {esc(u["phrase_translation_pl"])}]' if u["phrase_translation_pl"] else ""
                out.append(f'#text(fill: greek, weight: "bold")[{esc(u["phrase_greek"])}]{gl}\n')
            out.append(md(u["body_md"]))
        # katena Ojców przypięta do etykiety bloku
        for c in catena.get(b["label"], []):
            zrodlo = esc(c["title_pl"] or c["work_title"] or "")
            if c["locus"]:
                zrodlo += ", " + esc(c["locus"])
            out.append(f'#block(inset: (left: 8pt), stroke: (left: 1.5pt + linia))[')
            out.append(f'  #text(fill: accent, weight: "bold")[{esc(c["author"])}] '
                       f'#text(size: 8.5pt, fill: muted, style: "italic")[{zrodlo}]\n')
            out.append("  " + md(c["body_md"]))
            out.append("]")
    return "\n\n".join(out)


def komentarz(d):
    glowne = [s for s in d["sections"]
              if s["parent_id"] is None and s["section_type"] not in ("filologia", "patrystyka")]
    struktura = next((s for s in d["sections"] if s["title"] == "Struktura całości"), None)
    if not glowne and not struktura:
        return ""
    out = [r'#heading(level: 2)[Komentarz]']
    if struktura:
        out.append(f'#heading(level: 3)[{esc(struktura["title"])}]')
        out.append(md(struktura["body_md"]))
    for s in glowne:
        out.append(f'#heading(level: 3)[{esc(s["title"])}]')
        if s["body_md"]:
            out.append(md(s["body_md"]))
        for c in [x for x in d["sections"] if x["parent_id"] == s["id"]]:
            out.append(f'#heading(level: 4)[{esc(c["title"])}]')
            out.append(md(c["body_md"]))
    return "\n\n".join(out)


def liturgia(d):
    if not d.get("liturgy"):
        return ""
    out = [r'#heading(level: 2)[Liturgia]']
    for l in d["liturgy"]:
        wiersz = f'#text(fill: gold, weight: "bold")[{esc(l["rite"])}] — {esc(l["occasion"])}'
        if l["passage"]:
            wiersz += f' #sig({q(l["passage"])})'
        out.append(wiersz + "\n")
        if l["description_md"]:
            out.append(md(l["description_md"]))
    return "\n\n".join(out)


def odniesienia(d):
    if not d.get("refs") and not d.get("themes"):
        return ""
    out = [r'#heading(level: 2)[Odniesienia i motywy]']
    if d.get("refs"):
        out.append('#table(columns: (auto, auto, 1fr), stroke: (y: 0.5pt + linia), '
                   'inset: (x: 5pt, y: 3pt), align: top + left,')
        out.append('  table.header(text(fill: gold, size: 8pt)[Miejsce], '
                   'text(fill: gold, size: 8pt)[Relacja], text(fill: gold, size: 8pt)[Uwaga]),')
        for r in d["refs"]:
            out.append("  " + ", ".join([
                f'text(fill: greek, weight: "bold", size: 9pt)[{esc(r["target_label"])}]',
                f'text(size: 8.5pt, fill: muted)[{esc(r["relation"])}]',
                f'text(size: 9pt)[{md(r["note_md"]) or ""}]']) + ",")
        out.append(")")
    if d.get("themes"):
        pastylki = " ".join(f'#pill([{esc(t)}])' for t in d["themes"])
        out.append(f'#block(above: 0.8em)[{pastylki}]')
    return "\n".join(out)


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
    out.append(f'#sig({q(siglum)}) #h(0.6em) #text(size: 8pt, fill: muted)[{esc(h["status"].replace("_", " "))}]')
    out.append(f'#heading(level: 1)[{esc(h["title"])}]')
    if h["motto"]:
        out.append(f'#text(size: 11pt, fill: muted, style: "italic")[{esc(h["motto"])}]\n')
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
           r'#text(size: 11pt, fill: muted, style: "italic")[Nici tematyczne przez całą księgę]\n']
    for m in app.api_themes():
        out.append(f'#heading(level: 3)[{esc(m["name"])}]')
        if m.get("description_md"):
            out.append(md(m["description_md"]))
        ps = m.get("pericopes") or []
        if ps:
            zetony = " ".join(f'#pill([{esc(p["siglum"])}])' for p in ps)
            out.append(f'#block(above: 0.4em)[#text(size: 8pt, fill: muted, tracking: 0.06em)[PERYKOPY] #h(0.4em) {zetony}]')
    return "\n\n".join(out)


def main():
    if not app.DB.exists():
        raise SystemExit(f"Brak bazy: {app.DB}\nUruchom najpierw: make build")
    czesci = naglowek_glowny()
    for p in app.api_pericopes():
        czesci.append(perykopa(p["id"]))
    czesci.append(motywy())
    OUT.write_text("\n\n".join(czesci) + "\n", encoding="utf-8")
    print(f"OK -> {OUT} ({OUT.stat().st_size} bajtów)\n"
          f"     typst compile {OUT.name} egzegeza.pdf")


if __name__ == "__main__":
    main()
