#!/usr/bin/env nix-shell
#! nix-shell -i python3 -p python3
"""Encode Greek text for the RGreekL font, the same way index.html does.

Reads text on stdin, writes the encoded text on stdout:

    echo 'Ἐν ἀρχῇ ἦν ὁ λόγος' | ./rgreekl.py
    ./rgreekl.py < na28-john.txt > john.rgreekl.txt

The output is ordinary characters from the font's Latin ranges, so it only looks
like Greek once the RGreekL font is applied to it.

This is a port of the engine between the /*ENGINE*/ markers in index.html and is
kept deliberately faithful to it, function for function, so that both produce
byte-identical output for the same settings. The ligature table below was lifted
from the ENTRIES constant there.

Run --help for every setting. The defaults are the ones the page is set to:

    kinds       whole words, beginnings and endings, letter groups
                (single-letter variants off)       --kinds / --amount
    circumflex  tilde ( ~ )                        --circumflex hat
    other form  ligatures drawn with the other circumflex are allowed
                                                   --no-other-circumflex
    set         Latin Extended-A preferred         --set B
    iota        combined glyphs # $ %              --iota sep
    breathing   combined marks with circumflex only, marks 192-197
                                                   --combined / --combined-set
    narrow iota off                                --narrow-iota
    varying     off                                --vary [--seed N]

The right-hand column is the flag that changes each one.
"""

import argparse
import sys
import unicodedata

# --------------------------------------------------------------------------
# The ligature table: code point, the key it draws, and which block it is in
# (S = Latin Supplement, A = Latin Extended-A, B = Latin Extended-B).
# --------------------------------------------------------------------------
_TABLE = r"""
161:a:S 162:a)po:S 163:b:S 165:ga\r:S 166:gg:S 168:gen:S 169:d:S 170:de\:S 171:dia:S 172:e:S
173:ei:S 174:ei:S 175:ek:S 176:en:S 177:ec:S 178:e)pi:S 179:eu:S 184:h:S 185:hn:S 186:kai:S
187:kata\:S 188:ll:S 189:mai:S 190:men:S 191:meta\:S 198:th\n:S 199:to\n:S 200:to:S
201:th\j:S 202:tw=n:S 203:tou=:S 204:tou\j:S 205:tai~j:S 216:on:S 217:oj:S 218:ou)k:S
219:ou)=n:S 220:...ouj:S 221:p:S 222:para:S 223:per...:S 224:peri:S 225:pro:S 226:r:S
227:ra:S 228:ri:S 229:ro:S 230:rw:S 231:s:S 232:s:S 233:sa:S 234:sai:S 235:sk:S 236:sq:S
237:sqai:S 238:so:S 239:ss:S 240:st:S 241:stai:S 242:sun:S 243:sx:S 244:sw:S 245:t:S
246:ta:S 247:tai:S 248:tai:S 249:tai:S 250:tau:S 251:tou:S 252:u=:S 253:u:S 254:u(p:S
255:w=:S 256:ai:A 257:ai:A 258:a)l:A 259:a)ll:A 260:an:A 261:ap:A 262:ar:A 263:ar:A 264:ar:A
265:aj:A 266:au:A 267:ga:A 268:ge:A 269:gei:A 270:geu:A 271:gi:A 272:gn:A 273:go:A 274:gr:A
275:gu:A 276:da:A 277:de:A 278:dei:A 279:deu:A 280:di:A 281:dio:A 282:du:A 283:dun:A
284:e)peu:A 285:er:A 286:e)sti:A 287:qa:A 288:qe:A 289:qei:A 290:qh:A 291:qi:A 292:qn:A
293:qo:A 294:qr:A 295:qu:A 296:in:A 297:ka:A 298:ko:A 299:ma:A 300:mhn:A 301:mi:A 302:mn:A
303:mu:A 304:mui:A 305:pa:A 306:pe:A 307:pei:A 308:phn:A 309:pi:A 310:pl:A 311:pn:A 312:po:A
313:pp:A 314:pr:A 315:pt:A 316:pu:A 317:pw:A 318:sa:A 319:se:A 320:sh:A 321:si:A 322:su:A
323:sp:A 324:spa:A 325:spai:A 326:span:A 327:spo:A 328:spw:A 329:ssa:A 330:ssan:A 331:ssw:A
332:sta:A 333:ste:A 334:stei:A 335:sth:A 336:sti:A 337:sto:A 340:stu:A 341:stw:A 342:sxa:A
343:sxei:A 344:sxhn:A 345:sxo:A 346:sxr:A 347:sxun:A 348:sxw:A 349:ta:A 350:te:A 351:tei:A
354:th:A 355:thn:A 356:ti:A 357:ti:A 358:to:A 359:tr:A 360:tt:A 361:tu:A 362:ui:A 363:un:A
364:uj:A 365:xa:A 366:xan:A 367:xh:A 368:xhn:A 369:xi:A 370:xr:A 371:xw:A 372:yan:A
373:yei:A 374:yi:A 375:yu:A 384:a:B 385:a:B 386:aqi:B 387:al:B 388:all:B 389:an:B 390:anti:B
391:ac:B 392:aorist:B 393:ara:B 394:a)uto:B 395:au)tou=:B 396:au)tw=:B 397:b:B 398:b:B
399:g:B 400:g:B 403:gai:B 404:gar:B 405:gar:B 406:gar:B 407:gg:B 408:gg:B 409:gi/netai:B
410:gk:B 411:gl:B 412:go:B 413:gra/fetai:B 414:gw:B 415:dec:B 416:dec:B 417:dh:B 418:dia:B
419:dio:B 420:do:B 421:dr:B 422:duadi:B 423:e:B 424:e:B 425:e:B 426:e)gw:B 427:ei:B
428:ei=:B 429:ei:B 430:ei=)nai:B 431:ei=)nai:B 432:ei=)nai:B 433:ei)si/:B 434:el:B 435:ell:B
436:en:B 437:e)peidh\:B 438:e)pi:B 439:e)pi\:B 440:epi:B 441:er:B 442:e)sti:B 443:e)sti:B
444:et:B 445:eto:B 446:eu:B 447:v:B 448:h:B 449:h:B 450:q:B 451:ql:B 452:qro:B 453:qrw:B
454:in:B 455:k:B 456:k:B 457:kai\:B 458:kan:B 459:kefa/laion:B 460:ki:B 461:kwn:B 462:kn:B
463:kr:B 464:l:B 465:la:B 466:lo:B 467:lo:B 468:m:B 469:ma/twn:B 470:meq:B 471:me\n:B
472:men:B 473:men...:B 474:mh:B 475:mes...:B 476:meta\:B 477:mo:B 478:mw:B 479:mw=n:B
480:n:B 481:n:B 482:nik...:B 483:c:B 484:oi:B 485:oi(on:B 486:on:B 487:on:B 488:o(ti:B
489:ou)=de:B 490:ou)=ka:B 491:ouj:B 492:ou(=toj:B 493:pai:B 494:par:B 495:par:B 496:para:B
497:parakei/menoj:B 498:per:B 499:peri\:B 500:peri:B 501:plhqunti...:B 502:po:B 503:pro:B
504:proj:B 505:or:B 506:san:B 507:sau=ta:B 508:sb:B 509:sei:B 510:sei:B 511:shn:B 512:sqai:B
513:si:B 514:ska:B 515:skh:B 516:sko:B 517:sm:B 518:so:B 519:sou:B 520:ssh:B 521:st:B
522:st:B 523:sth:B 524:sf:B 525:sxe:B 526:sxh:B 527:sxh:B 528:sxi:B 529:sxn:B 530:sxu:B
531:sw:B 532:sw=n:B 533:taj:B 534:tau=qa:B 535:tau=ta:B 536:thn:B 537:thj:B 538:ter:B
539:...tik...:B 540:to:B 541:to:B 542:ton:B 543:tro:B 544:tou=:B 545:tr:B 546:tw:B
547:tw|=:B 548:tw=n:B 549:u/:B 550:un:B 551:un:B 552:u(persuntelik...:B 553:usi:B 554:f:B
555:fi:B 556:fo:B 557:fr:B 558:xai:B 559:xari:B 560:xh:B 561:xq:B 562:ye:B 563:yh:B 564:yw:B
565:w:B 566:wj:B
"""

ENTRIES = []
for _tok in _TABLE.split():
    _code, _key, _set = _tok.split(":")
    ENTRIES.append((int(_code), _key, _set))

# --------------------------------------------------------------------------
# Greek <-> Beta code
# --------------------------------------------------------------------------
L2B = {
    "α": "a", "β": "b", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "h",
    "θ": "q", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "c",
    "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "j", "τ": "t", "υ": "u",
    "φ": "f", "χ": "x", "ψ": "y", "ω": "w", "ϲ": "s",
}
B2L = {}
G2B = {}
for _g, _b in L2B.items():
    G2B[_g] = _b
    if _g not in ("ς", "ϲ"):
        G2B[_g.upper()] = _b.upper()
for _g in "αβγδεζηθικλμνξοπρστυφχψω":
    B2L[L2B[_g]] = _g
B2L["j"] = "ς"
for _b in list(B2L):
    if _b != "j":
        B2L[_b.upper()] = B2L[_b].upper()

MARKU = {"̓": ")", "̔": "(", "́": "/", "̀": "\\",
         "̈": "+", "ͅ": "|"}
U_OF = {")": "̓", "(": "̔", "/": "́", "\\": "̀",
        "C": "͂", "T": "͂", "+": "̈", "|": "ͅ"}

ASCII_LETTERS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")


class Cluster:
    """One base character plus the marks that belong to it."""

    __slots__ = ("b", "m", "from_sigma")

    def __init__(self, b, m=None, from_sigma=False):
        self.b = b
        self.m = set() if m is None else m
        self.from_sigma = from_sigma


def is_l(c):
    return c is not None and c.b in ASCII_LETTERS


def parse_beta(s):
    out = []
    last = None
    for ch in s:
        if ch in ASCII_LETTERS:
            last = Cluster(ch)
            out.append(last)
        elif ch in ("#", "$", "%"):
            last = Cluster({"#": "a", "$": "h", "%": "w"}[ch], {"|"})
            out.append(last)
        elif last is not None and ch in ")(/\\=~+|":
            last.m.add("C" if ch == "=" else "T" if ch == "~" else ch)
        else:
            out.append(Cluster(ch))
            last = None
    return out


def parse_unicode(s, circ):
    """Returns (clusters, dropped) -- dropped counts macron/breve marks, which
    the chart has no key for."""
    out = []
    last = None
    dropped = 0
    for ch in unicodedata.normalize("NFD", s):
        if ch in G2B:
            last = Cluster(G2B[ch], from_sigma=(ch == "σ"))
            out.append(last)
            continue
        if ch in MARKU:
            if last is not None:
                last.m.add(MARKU[ch])
            continue
        if ch in ("͂", "̃"):
            if last is not None:
                last.m.add(circ)
            continue
        if ch in ("̄", "̆"):
            dropped += 1
            continue
        c = ch
        if c in ("’", "ʼ", "᾽", "᾿"):
            c = "'"
        elif c in ("·", "·"):
            c = ":"
        out.append(Cluster(c))
        last = None
    for i, cl in enumerate(out):
        nxt = out[i + 1] if i + 1 < len(out) else None
        if cl.from_sigma and not is_l(nxt):
            cl.b = "j"
    return out, dropped


def beta_to_unicode(clusters):
    s = []
    for i, c in enumerate(clusters):
        if not is_l(c):
            s.append(c.b)
            continue
        g = B2L.get(c.b, c.b)
        nxt = clusters[i + 1] if i + 1 < len(clusters) else None
        if c.b == "s" and not is_l(nxt):
            g = "ς"
        s.append(g)
        for k in ("+", ")", "(", "/", "\\", "C", "T", "|"):
            if k in c.m:
                s.append(U_OF[k])
    return unicodedata.normalize("NFC", "".join(s))


# --------------------------------------------------------------------------
# Which keys are ligatures of which kind
# --------------------------------------------------------------------------
WORD = set("""kai kai\\ tou= tw=n th\\n to\\n th\\j tou\\j tai~j ou)k ou)=n ou)=de
ou)=ka o(/ti e)sti ei)si/ e)gw au)tou= au)tw= tau=ta tau=qa sau=ta ou(=toj
ei=)nai kefa/laion gi/netai gra/fetai ma/twn e)peidh\\ me\\n de\\ ga\\r gar kata\\
meta\\ peri\\ e)pi\\ tw|= mw=n sw=n proj ton thn thj taj parakei/menoj oi(on
duadi aorist""".split())
PREFIX = set("""a)po dia para peri pro sun e)pi epi anti a)uto e)peu meq par per
u(p""".split())
SUFFIX_EXTRA = {"on"}
CATS = ["word", "affix", "letters", "variants"]
PRESETS = {
    "sparing": {"word": True, "affix": False, "letters": False, "variants": False},
    "moderate": {"word": True, "affix": True, "letters": False, "variants": False},
    "full": {"word": True, "affix": True, "letters": True, "variants": False},
}


def key_info(key):
    k = key
    pre = suf = False
    if k.startswith("..."):
        suf = True
        k = k[3:]
    if k.endswith("..."):
        pre = True
        k = k[:-3]
    clusters = parse_beta(k)
    norm = "|".join(c.b + "".join(sorted(c.m)) for c in clusters)
    start = end = False
    if suf and pre:
        cat = "affix"
    elif pre:
        cat, start = "affix", True
    elif suf:
        cat, end = "affix", True
    elif key in WORD:
        cat, start, end = "word", True, True
    elif len(clusters) == 1:
        cat = "variants"
    elif key in PREFIX:
        cat, start = "affix", True
    elif key.endswith("j") or key in SUFFIX_EXTRA:
        cat, end = "affix", True
    else:
        cat = "letters"
    return {"key": key, "clusters": clusters, "start": start, "end": end,
            "cat": cat, "norm": norm}


KEYS = {}
for _code, _key, _set in ENTRIES:
    if _key not in KEYS:
        KEYS[_key] = {"info": key_info(_key), "list": []}
    KEYS[_key]["list"].append({"code": _code, "set": _set})


# --------------------------------------------------------------------------
# Choosing a drawing for a key
# --------------------------------------------------------------------------
def rank_of(e, S):
    r = 0 if e["set"] == S["prefSet"] else (1 if e["set"] == "S" else 2)
    if e["code"] == 173:
        r += 10
    return r * 1000 + e["code"]


def chosen_for(key, S):
    v = KEYS[key]
    forced = S["pick"].get(key)
    if forced:
        for e in v["list"]:
            if e["code"] == forced:
                return e
    return sorted(v["list"], key=lambda e: rank_of(e, S))[0]


def key_enabled(key, S):
    cat = KEYS[key]["info"]["cat"]
    if S["off"].get(key):
        return False
    if S["on"].get(key):
        return True
    return bool(S["cats"].get(cat))


def hash32(s):
    """FNV-1a plus an avalanche step. Must stay bit-identical to the hash32 in
    index.html so both pick the same drawings for the same seed."""
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    h ^= h >> 15
    h = (h * 2246822507) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 3266489909) & 0xFFFFFFFF
    return (h ^ (h >> 16)) & 0xFFFFFFFF


def pick_variant(lig, i, S):
    vs = lig.get("variants")
    if not S["rand"] or not vs:
        return lig["code"]
    return vs[hash32("%d|%s|%d" % (S["seed"], lig["key"], i)) % len(vs)]


def build_ligs(S):
    by = {}
    for key, v in KEYS.items():
        if not key_enabled(key, S):
            continue
        ch = chosen_for(key, S)
        info = v["info"]
        lig = {"key": key, "code": ch["code"], "set": ch["set"],
               "clusters": info["clusters"], "start": info["start"],
               "end": info["end"],
               "spec": sum(len(c.m) for c in info["clusters"])}
        if not S["pick"].get(key):
            pool = [e["code"] for e in v["list"] if e["code"] != 173]
            if len(pool) > 1:
                lig["variants"] = pool
        by.setdefault(info["clusters"][0].b, []).append(lig)
    # index.html scans every candidate and keeps the first with the highest
    # (length, specificity); sorting stably by that and taking the first match
    # picks the same ligature while letting us stop at the first hit.
    for cands in by.values():
        cands.sort(key=lambda l: (-len(l["clusters"]), -l["spec"]))
    return by


def nm(marks, other):
    if not other:
        return marks
    return {"C" if x == "T" else x for x in marks}


def mark_eq(a, b, loose):
    return nm(a, loose) == nm(b, loose)


def mark_sub(key, text, loose):
    return nm(key, loose) <= nm(text, loose)


def try_lig(lig, cl, i, S):
    kc_list = lig["clusters"]
    n = len(kc_list)
    if i + n > len(cl):
        return None
    if lig["start"] and i > 0 and is_l(cl[i - 1]):
        return None
    for k in range(n):
        kc, tc = kc_list[k], cl[i + k]
        if kc.b != tc.b:
            return None
        if k < n - 1:
            if not mark_eq(kc.m, tc.m, S["otherCirc"]):
                return None
        elif not mark_sub(kc.m, tc.m, S["otherCirc"]):
            return None
    if lig["end"] and i + n < len(cl) and is_l(cl[i + n]):
        return None
    last = cl[i + n - 1]
    kn = nm(kc_list[n - 1].m, S["otherCirc"])
    extra = set()
    for x in last.m:
        if ("C" if S["otherCirc"] and x == "T" else x) not in kn:
            extra.add(x)
    return n, extra


# --------------------------------------------------------------------------
# Emitting
# --------------------------------------------------------------------------
_COMBINED = {"(/": 0, "(\\": 1, "(C": 2, ")/": 3, ")\\": 4, ")C": 5}


def emit_marks(m, base_letter, S):
    s = "+" if "+" in m else ""
    br = ")" if ")" in m else "(" if "(" in m else ""
    ac = ""
    for k in ("/", "\\", "C", "T"):
        if k in m:
            ac = k
            break
    circ = ac in ("C", "T")
    ac_ch = "=" if ac == "C" else "~" if ac == "T" else ac
    if br and ac and (S["comp"] == "all" or (S["comp"] == "circ" and circ)):
        base = 208 if S["compSet"] == "b" else 192
        s += chr(base + _COMBINED[br + ("C" if circ else ac)])
    elif br and not ac and S["narrowI"] and base_letter == "i":
        s += chr(206 if br == "(" else 207)
    else:
        s += br + ac_ch
    return s


def emit_cluster(c, S):
    m = set(c.m)
    base = c.b
    sep = False
    if "|" in m:
        m.discard("|")
        pre = {"a": "#", "h": "$", "w": "%"}.get(base)
        if S["sub"] == "pre" and pre:
            base = pre
        else:
            sep = True
    return base + ("|" if sep else "") + emit_marks(m, c.b, S)


def sig_at(cl, i):
    return "|".join(c.b + "".join(sorted(c.m)) for c in cl[i:i + 4])


def encode(clusters, S):
    ligs = build_ligs(S)
    loose = dict(S, otherCirc=True)
    tokens = []
    used = {}
    n_cl = len(clusters)
    i = 0
    while i < n_cl:
        c = clusters[i]
        fo = S["occ"].get(i)
        if fo is not None and fo.get("sig") != sig_at(clusters, i):
            fo = None
        if fo and fo.get("plain"):
            n = max(1, min(fo["plain"], n_cl - i))
            s = "".join(emit_cluster(clusters[i + k], S) if is_l(clusters[i + k])
                        else clusters[i + k].b for k in range(n))
            tokens.append({"s": s, "idx": i, "n": n, "forced": True})
            i += n
            continue
        best = None
        if fo and fo.get("key") in KEYS:
            v = KEYS[fo["key"]]
            info = v["info"]
            ent = next((e for e in v["list"] if e["code"] == fo["code"]), None)
            if ent and is_l(c):
                pseudo = {"key": fo["key"], "code": fo["code"], "set": ent["set"],
                          "clusters": info["clusters"], "start": info["start"],
                          "end": info["end"], "spec": 0}
                r = try_lig(pseudo, clusters, i, loose)
                if r:
                    best = (pseudo, r, True)
        if best is None and is_l(c):
            for lig in ligs.get(c.b, ()):
                r = try_lig(lig, clusters, i, S)
                if r:
                    best = (lig, r, False)
                    break
        if best is not None:
            lig, (rn, extra), forced = best
            last_b = clusters[i + rn - 1].b
            code = pick_variant(lig, i, S)
            s = chr(code) + emit_marks(extra, last_b, S)
            tokens.append({"s": s, "lig": lig, "code": code, "idx": i, "n": rn,
                           "forced": forced})
            u = used.setdefault(lig["key"], {"lig": lig, "n": 0, "codes": set()})
            u["n"] += 1
            u["codes"].add(code)
            i += rn
        elif is_l(c):
            tokens.append({"s": emit_cluster(c, S), "idx": i, "n": 1, "forced": False})
            i += 1
        else:
            tokens.append({"s": c.b})
            i += 1
    return {"tokens": tokens, "text": "".join(t["s"] for t in tokens), "used": used}


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------
def to_entities(s):
    out = []
    for ch in s:
        c = ord(ch)
        if ch == "\n":
            out.append("<br>\n")
        elif c > 126 or ch in "&<>\"":
            out.append("&#%d;" % c)
        else:
            out.append(ch)
    return "".join(out)


def build_parser():
    p = argparse.ArgumentParser(
        description="Encode Greek text for the RGreekL font (stdin -> stdout). "
                    "The defaults are the settings in use on the page: "
                    "all kinds but single-letter variants, the tilde "
                    "circumflex, ligatures drawn with the other circumflex "
                    "allowed, Latin Extended-A preferred, combined iota "
                    "glyphs, combined marks with circumflex only from 192-197, "
                    "no narrow iota, no varying.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--beta", action="store_true",
                   help="read Beta code instead of Unicode Greek")
    p.add_argument("--amount", choices=["sparing", "moderate", "full"],
                   default="full", help="how freely to use ligatures")
    p.add_argument("--kinds", metavar="LIST",
                   help="comma-separated kinds to allow, overriding --amount: "
                        + ",".join(CATS))
    p.add_argument("--circumflex", choices=["hat", "tilde"], default="tilde",
                   help="which circumflex key to emit (= or ~)")
    p.add_argument("--other-circumflex", action=argparse.BooleanOptionalAction,
                   default=True,
                   help="also match ligatures drawn with the other circumflex")
    p.add_argument("--set", choices=["A", "B"], default="A", dest="pref_set",
                   help="preferred block where both draw the same key")
    p.add_argument("--iota", choices=["pre", "sep"], default="pre",
                   help="iota subscript: combined glyphs or a separate | mark")
    p.add_argument("--combined", choices=["circ", "all", "off"], default="circ",
                   help="combined breathing+accent marks")
    p.add_argument("--combined-set", choices=["a", "b"], default="a",
                   help="which combined-mark block to use (192- or 208-)")
    p.add_argument("--narrow-iota", action="store_true",
                   help="narrow breathing mark on iota")
    p.add_argument("--vary", action="store_true",
                   help="vary the drawing of keys that have more than one")
    p.add_argument("--seed", type=int, default=1,
                   help="seed for --vary; same seed, same output")
    p.add_argument("--pin", metavar="KEY=CODE", action="append", default=[],
                   help="always draw KEY with code point CODE (repeatable)")
    p.add_argument("--on", metavar="KEY", action="append", default=[],
                   help="use KEY even if its kind is off (repeatable)")
    p.add_argument("--off", metavar="KEY", action="append", default=[],
                   help="never use KEY (repeatable)")
    p.add_argument("--reading", action="store_true",
                   help="print the Greek the encoder read, not the encoded text")
    p.add_argument("--html", action="store_true",
                   help="wrap the output in a span that applies the font")
    p.add_argument("--font-name", default="Rgreekl2",
                   help="font family to name in --html")
    p.add_argument("--stats", action="store_true",
                   help="write a summary and any warnings to stderr")
    return p


def settings_from(a):
    if a.kinds:
        names = [k.strip() for k in a.kinds.split(",") if k.strip()]
        bad = [k for k in names if k not in CATS]
        if bad:
            raise SystemExit("rgreekl: unknown kind(s): %s (choose from %s)"
                             % (", ".join(bad), ", ".join(CATS)))
        cats = {k: (k in names) for k in CATS}
    else:
        cats = dict(PRESETS[a.amount])
    pick = {}
    for item in a.pin:
        if "=" not in item:
            raise SystemExit("rgreekl: --pin wants KEY=CODE, got %r" % item)
        key, _, code = item.partition("=")
        if key not in KEYS:
            raise SystemExit("rgreekl: no such key: %r" % key)
        if not code.isdigit() or not any(e["code"] == int(code)
                                         for e in KEYS[key]["list"]):
            raise SystemExit("rgreekl: %s is not drawn at %r; it has %s"
                             % (key, code,
                                ", ".join(str(e["code"]) for e in KEYS[key]["list"])))
        pick[key] = int(code)
    for key in a.on + a.off:
        if key not in KEYS:
            raise SystemExit("rgreekl: no such key: %r" % key)
    return {
        "cats": cats,
        "circ": "C" if a.circumflex == "hat" else "T",
        "otherCirc": a.other_circumflex,
        "prefSet": a.pref_set,
        "sub": a.iota,
        "comp": a.combined,
        "compSet": a.combined_set,
        "narrowI": a.narrow_iota,
        "rand": a.vary,
        "seed": a.seed,
        "on": {k: True for k in a.on},
        "off": {k: True for k in a.off},
        "pick": pick,
        "occ": {},
    }


ODD = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
          "!\"#$%&()*+/<=>@[\\]^_`{|}~")


def main(argv=None):
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    a = build_parser().parse_args(argv)
    S = settings_from(a)
    src = sys.stdin.read()

    if a.beta:
        clusters, dropped = parse_beta(src), 0
    else:
        clusters, dropped = parse_unicode(src, S["circ"])
    result = encode(clusters, S)

    out = beta_to_unicode(clusters) if a.reading else result["text"]
    if a.html and not a.reading:
        out = ("<span style=\"font-family:'%s'\">%s</span>"
               % (a.font_name.replace("'", ""), to_entities(out)))
    sys.stdout.write(out)

    if a.stats:
        ligs = sum(u["n"] for u in result["used"].values())
        varying = sum(1 for u in result["used"].values() if len(u["codes"]) > 1)
        w = sys.stderr.write
        w("in        %d characters, %d clusters\n" % (len(src), len(clusters)))
        w("out       %d characters\n" % len(result["text"]))
        w("ligatures %d in %d distinct keys%s\n"
          % (ligs, len(result["used"]),
             ", %d drawn more than one way" % varying if varying else ""))
        if dropped:
            w("warning   %d macron/breve mark%s left out; the chart has no key "
              "for them\n" % (dropped, "" if dropped == 1 else "s"))
        if not a.beta:
            odd = sorted({ch for ch in src if ch in ODD})
            if odd:
                w("warning   these are keys in this font and will draw as Greek "
                  "letters or marks: %s\n" % " ".join(odd))
        if "­" in result["text"]:
            w("warning   the output contains U+00AD (soft hyphen), which many "
              "apps hide\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
