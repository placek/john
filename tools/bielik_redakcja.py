#!/usr/bin/env python3
"""
bielik_redakcja.py - redakcja polskich tekstów w JSON-ach lokalnym modelem Bielik.

Skrypt przechodzi rekurencyjnie po strukturze JSON (obiekty, listy, zagnieżdżenia),
znajduje wartości tekstowe, które wyglądają na prozę (nie id, nie URL, nie daty),
wysyła je do lokalnego modelu Bielik i podmienia na wersję bardziej elegancką
i naturalną. Struktura, klucze i pozostałe wartości zostają nietknięte.

Wymaga lokalnego serwera z API zgodnym z OpenAI, np. llama.cpp:

    llama-server -m Bielik-11B-v3.0-Instruct.Q6_K.gguf --port 8080 -c 4096

albo Ollamy (--base-url http://localhost:11434/v1 --model <nazwa>).

Użycie:
    python bielik_redakcja.py dane.json
    python bielik_redakcja.py katalog/ --out wynik/ --keys opis,tytul,tresc
    python bielik_redakcja.py dane.jsonl --workers 2 --temperature 0.2
    python bielik_redakcja.py dane.json --dry-run     # tylko pokaż, co zostanie przeredagowane

Dla tego repozytorium (egzegeza Jana) -- wybór pól po ŚCIEŻCE, nie po kluczu:
    python tools/bielik_redakcja.py data/ --profil jan-proza --dry-run

Tylko biblioteka standardowa.
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import re
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = (
    "Jesteś doświadczonym redaktorem i korektorem języka polskiego. "
    "Dostajesz fragment tekstu i zwracasz jego poprawioną wersję: elegancką, "
    "płynną i naturalną, taką, jaką napisałby dobry autor, a nie tłumacz maszynowy.\n"
    "Zasady:\n"
    "1. Zachowaj dokładnie to samo znaczenie i wszystkie fakty. Niczego nie dodawaj, "
    "niczego nie pomijaj, nie wyciągaj własnych wniosków.\n"
    "2. Nie zmieniaj liczb, dat, kwot, nazw własnych, nazw produktów, adresów URL, "
    "adresów e-mail, kodów ani zmiennych w nawiasach klamrowych, np. {imie}, %s.\n"
    "3. Popraw ortografię, interpunkcję i szyk zdania, usuń kalki z angielskiego, "
    "powtórzenia i niezgrabne konstrukcje.\n"
    "4. Zachowaj ogólny rejestr (formalny/nieformalny) i podobną długość tekstu; "
    "nie rozwlekaj i nie streszczaj.\n"
    "5. Zachowaj formatowanie: podziały linii, wypunktowania, znaczniki HTML/Markdown.\n"
    "6. Jeśli tekst jest już dobry, zwróć go bez zmian.\n"
    "7. Odpowiedz WYŁĄCZNIE przeredagowanym tekstem: bez wstępu, komentarza, "
    "cudzysłowów ani wyjaśnień."
)

# Prompt CZYTELNY: rozpisanie gęstej, skrótowej prozy naukowej na tekst, który
# da się czytać ciągiem. Treść ta sama, rejestr inny. To domyślny tryb dla
# --profil jan-*, bo o to chodzi w tym repozytorium (patrz README).
SYSTEM_PROMPT_CZYTELNY = (
    "Jesteś pisarzem, który tłumaczy gęsty tekst naukowy na język zrozumiały dla "
    "uważnego czytelnika bez wykształcenia teologicznego. Dostajesz fragment "
    "komentarza biblijnego i przepisujesz go tak, żeby czytał się jak proza "
    "napisana przez człowieka, a nie jak notatka albo hasło encyklopedyczne.\n"
    "CO MASZ ZROBIĆ:\n"
    "1. Rozwiń skróty myślowe w pełne zdania. Tam, gdzie autor nagromadził "
    "wyliczenia rozdzielone średnikami i myślnikami, zrób z nich zdania "
    "następujące po sobie i powiedz, co je łączy.\n"
    "2. Wyjaśnij pojęcia techniczne zwykłymi słowami. Termin zostaw, ale dopisz "
    "krótko, co znaczy — albo najpierw wyjaśnij rzecz, a potem ją nazwij.\n"
    "3. Nazwij myśl wprost. Jeśli zdanie tylko sugeruje wniosek, dopowiedz go "
    "tym, co już w tekście jest — nie dokładając nowej treści.\n"
    "4. Wolno Ci WYDŁUŻYĆ tekst; rozpisanie skrótu na zdanie zajmuje miejsce. "
    "Nie streszczaj.\n"
    "5. Pisz zdaniami oznajmującymi, spokojnie, bez egzaltacji i bez "
    "kaznodziejstwa. Nie zwracaj się do czytelnika w drugiej osobie.\n"
    "CZEGO NIE WOLNO:\n"
    "6. Nie dodawaj ŻADNEGO faktu, którego w tekście nie ma, i nie usuwaj "
    "żadnego, który jest. Żadnych własnych wniosków teologicznych.\n"
    "7. Wszystkie wyrażenia greckie, hebrajskie, aramejskie i łacińskie przepisz "
    "DOKŁADNIE tak, jak stoją, razem z ich polskimi tłumaczeniami w nawiasach. "
    "To materiał dowodowy, nie ozdoba — nie pomijaj ich i nie zmieniaj liter. "
    "Zachowaj też KOLEJNOŚĆ: najpierw wyrażenie obce, potem polskie tłumaczenie "
    "w nawiasie — ἦν (było), nie „było\" (ἦν).\n"
    "8. Wszystkie sigla biblijne (J 1,1–14), miejsca w dziełach (Tract. in Io. 10), "
    "daty, liczby i nazwy własne przepisz bez zmiany.\n"
    "8b. NAJWAŻNIEJSZE: stosy odsyłaczy w nawiasach to główne źródło nieczytelności "
    "tego tekstu — i właśnie dlatego nie wolno ich USUWAĆ, tylko trzeba je "
    "PRZENIEŚĆ. Jeśli nawias z siglami rozbija zdanie, wyprowadź go na koniec tego "
    "zdania i zbierz wszystkie odsyłacze w jednym nawiasie, zachowując ich "
    "kolejność. Zdanie ma płynąć, a odsyłacze mają zostać — co do jednego. "
    "Przykład: „trzy deklaracje niewinności, cztery okrzyki oskarżycieli "
    "\u27e60\u27e7, trzykrotne przedstawienie Jezusa jako króla \u27e61\u27e7\" "
    "zapisz jako „Trzy razy Piłat ogłasza niewinność, cztery razy krzyczą "
    "oskarżyciele, trzy razy Jezus zostaje przedstawiony jako król "
    "(\u27e60\u27e7; \u27e61\u27e7).\"\n"
    "8a. W tekście mogą stać nieprzejrzyste znaczniki w rodzaju \u27e60\u27e7, "
    "\u27e61\u27e7 — to zasłonięte sigla i liczby. Przepisz je BEZ ZMIANY, co do "
    "znaku, i zostaw w tych samych miejscach zdania. Nie licz ich, nie tłumacz, "
    "nie pomijaj.\n"
    "8c. Każdy fragment w cudzysłowie „…\" dłuższy niż kilka słów to PRZYTOCZENIE "
    "źródła — wersetu, formuły liturgicznej, zdania Ojca Kościoła. Przepisz go "
    "co do słowa, razem z cudzysłowami. Nie streszczaj go, nie parafrazuj i nie "
    "zastępuj samym odsyłaczem.\n"
    "9. Nie zmieniaj kwalifikatorów pewności: „prawdopodobnie\", „bywa "
    "kwestionowane\", „aluzja\" kontra „cytat\". Ich osłabienie albo wzmocnienie "
    "jest zmianą twierdzenia.\n"
    "10. W zakresach używaj półpauzy (J 1,1–14), nigdy dywizu. Cudzysłowy pisz "
    "polskie: „tak\".\n"
    "Odpowiedz wyłącznie przepisanym tekstem, bez wstępu i komentarza."
)

# Prompt OSTROŻNY: dla korpusu naukowego zadaniem nie jest elegancja, lecz
# wyłapanie faktycznych błędów. Używany zamiast SYSTEM_PROMPT przy --profil jan-*
# (chyba że podasz --styl elegancki).
SYSTEM_PROMPT_OSTROZNY = (
    "Jesteś korektorem naukowego komentarza biblijnego. Tekst jest po recenzji "
    "przy źródłach — każde sformułowanie jest ważone i autorskie.\n"
    "Twoim zadaniem NIE jest upiększanie. Poprawiasz wyłącznie faktyczne błędy:\n"
    "1. literówki, błędy ortograficzne i fleksyjne;\n"
    "2. błędy interpunkcyjne (brakujący przecinek przed zdaniem podrzędnym, "
    "zdublowana spacja);\n"
    "3. zdania niegramatyczne albo urwane w połowie.\n"
    "CZEGO NIE WOLNO RUSZAĆ:\n"
    "4. doboru słów — jeśli autor napisał „czwartej Ewangelii\", „odsłona\", "
    "„sędzia\", zostaw dokładnie to słowo; nie podstawiaj synonimów ani imion;\n"
    "5. szyku zdania, długości zdań, myślników i średników — to styl autora;\n"
    "6. terminologii teologicznej i filologicznej, sigli, loci, nazw świąt, "
    "rytów, dokumentów i dzieł;\n"
    "7. kwalifikatorów pewności („prawdopodobnie\", „bywa kwestionowane\", "
    "„aluzja\" kontra „cytat\") — ich zmiana jest zmianą twierdzenia;\n"
    "8. znaków: gwiazdek kursywy *tak*, cudzysłowów „…\", półpauz (J 1,1–14), "
    "em-pauz (—) i wielokropków (…) — zachowaj je znak w znak, nie zamieniaj "
    "cudzysłowu zamykającego na ” ani em-pauzy na dywiz;\n"
    "9. wyrażeń obcych i ich polskich tłumaczeń w nawiasach.\n"
    "Jeśli w tekście nie ma błędu, zwróć go ZNAK W ZNAK bez zmian. To najczęstszy "
    "poprawny wynik. Odpowiedz wyłącznie tekstem, bez komentarza."
)

# Dopisek do promptu dla korpusu naukowego (--profil jan-*, --styl elegancki).
SYSTEM_PROMPT_NAUKOWY = (
    "KONTEKST: to fragment naukowego komentarza biblijnego, po recenzji przy źródłach. "
    "Każde sformułowanie jest ważone.\n"
    "8. NIE zmieniaj terminologii teologicznej, filologicznej ani nazw własnych "
    "(sigla biblijne, loci patrystyczne, nazwy ksiąg, świąt, rytów i dokumentów).\n"
    "9. NIE zmieniaj kwalifikatorów pewności: „prawdopodobnie\", „bywa kwestionowane\", "
    "„hipoteza\", „aluzja\" kontra „cytat\". Osłabienie albo wzmocnienie takiego "
    "sformułowania jest zmianą twierdzenia, nie stylu.\n"
    "10. Zachowaj gwiazdki kursywy Markdown (*tak*) i polskie cudzysłowy „…\" "
    "w dokładnie tej samej liczbie.\n"
    "11. W zakresach używaj półpauzy (J 1,1–14), nigdy dywizu.\n"
    "12. Każde wyrażenie obce ma po sobie polskie tłumaczenie w nawiasie — zostaw je."
)

# Tokeny, które muszą przetrwać redakcję w niezmienionej postaci.
PROTECTED_RE = re.compile(
    r"https?://\S+|www\.\S+|[\w.+-]+@[\w-]+\.[\w.-]+|\{[^{}]*\}|<[^<>]+>|\d+(?:[.,:/–-]\d+)*"
)
LETTER_RE = re.compile(r"[^\W\d_]", re.UNICODE)
SKIP_PATTERNS = [
    re.compile(r"^https?://\S+$"),
    re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$"),
    re.compile(r"^\d{4}-\d{2}-\d{2}([T ][\d:.+Z-]+)?$"),  # ISO daty
    re.compile(r"^[0-9a-fA-F-]{16,}$"),  # uuid / hash
]

# --------------------------------------------------------------------------- #
# PROFILE ŚCIEŻEK
#
# Ten korpus trzyma treść w tablicach POZYCYJNYCH, więc filtrowanie po kluczu
# nie wystarcza: units[j][1] to dosłowny przekład frazy, a units[j][2] to akapit
# analizy — oba mają ten sam klucz „units". Wybór musi iść po ścieżce.
#
# Świadomie POZA zakresem (nigdy nie wysyłane do modelu):
#   verses.items[*][1] i [2]        greka NA28 i przekład roboczy (interlinia)
#   blocks[*].greek / .transl       to samo na poziomie bloku
#   units[*][0] i [1]               fraza grecka i jej dosłowna glosa
#   patristic[*][0..3]              etykieta bloku (klucz!), autor, dzieło, locus
#   refs[*][6] i [7]                siglum i relacja (słownik CHECK)
#   theme_links, occurrences, lexeme_semitic, books, works, semitic, meta
#   pericope.{title,motto,status,source_url}, sections[*].{type,title}
#   children[*][0]                  tytuły podsekcji
#   lexemes[*][0..2]                lemat, transliteracja, część mowy
#   revision_note                   dziennik warsztatu, nie proza dla czytelnika
#   textual[*][*]                   aparat krytyczny — precyzja ponad styl
# --------------------------------------------------------------------------- #
PROFILE = {
    "jan-proza": [
        r"^pericopes\[\d+\]\.intro$",
        r"^pericopes\[\d+\]\.struktura$",
        r"^pericopes\[\d+\]\.sections\[\d+\]\.body$",
        r"^pericopes\[\d+\]\.sections\[\d+\]\.children\[\d+\]\[1\]$",
        r"^pericopes\[\d+\]\.section_viii\.body$",
        r"^pericopes\[\d+\]\.blocks\[\d+\]\.units\[\d+\]\[2\]$",
        r"^pericopes\[\d+\]\.patristic\[\d+\]\[4\]$",
        r"^intro\.lead$",
        r"^intro\.sections\[\d+\]\.body$",
        r"^intro\.sections\[\d+\]\.children\[\d+\]\[1\]$",
    ],
    # dodatkowo aparat: uwagi przy odniesieniach, cytowaniach i motywach
    "jan-aparat": [
        r"^pericopes\[\d+\]\.refs\[\d+\]\[8\]$",
        r"^pericopes\[\d+\]\.citations\[\d+\]\[3\]$",
        r"^themes\[\d+\]\[1\]$",
        r"^lexemes\[\d+\]\[3\]$",
    ],
}


# --------------------------------------------------------------------------- #
# Ochrona przed tekstami obcojęzycznymi (łacina, greka, hebrajski, angielski...)
#
# Jeśli w wartości wykryto cokolwiek nie-polskiego, CAŁA wartość zostaje
# nietknięta (model w ogóle nie dostaje jej do redakcji). Wykrywanie:
#   1. pismo: każda litera spoza alfabetu łacińskiego (greka, hebrajski,
#      cyrylica, arabski, ...) => pomiń;
#   2. słowa jednoznacznie obce (łacińskie) => pomiń przy jednym trafieniu;
#   3. słowa dwuznaczne (łac./ang./niem./fr.) => pomiń przy 2 w oknie 5 słów;
#   4. dłuższy tekst bez ani jednego polskiego znaku diakrytycznego
#      i polskiego słowa funkcyjnego => pomiń.
# Greka/hebrajski zapisane literami łacińskimi (np. "logos", "agape") da się
# wychwycić tylko z listy podanej w --foreign-words.
# --------------------------------------------------------------------------- #
ALLOWED_NON_LATIN = set("µªº")
WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
PL_DIACRITICS = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
WINDOW = 5

LATIN_STRONG = set("""
deus dei deo deum domine dominus domini domino dominum christus christi christo
jesu spiritus sanctus sancti sancto sanctum gloria pater noster ecclesia verbum
quae quod qui quia quoniam quem quos nobis vobis omnia omnes saecula saeculorum
nomen tuum meus mea meum tibi mihi sicut autem enim tamen etiam ergo igitur
sine nec aut atque itaque namque propter sed lorem ipsum dolor amet consectetur
caelo coelo caeli mundi mundo vita vitam lux lucis ave maria misericordia
miserere eleison kyrie
""".split())

FOREIGN_WEAK = set("""
et est non ad cum per pro ex ab ac ut sunt esse in de si
the and of is are with for that this which from be at an
der die das und ist nicht ein eine zu den dem auf von sich
les des une dans pour que
""".split())

PL_FUNCTION_WORDS = set("""
i w z na się nie że jest jak ale po od dla przez oraz czy są był była było
może który która które których tym tego tej lub bez gdy jako tak już tylko
za przy ich jego jej ze
""".split())


def foreign_reason(text: str, mode: str, extra_strong: frozenset | set = frozenset()) -> str | None:
    """Zwraca powód pominięcia (str) albo None, jeśli tekst wygląda na czysto polski."""
    if mode == "off":
        return None

    # 1. Inne pisma (greka, hebrajski, cyrylica, ...).
    for ch in text:
        if ch.isalpha() and ch not in ALLOWED_NON_LATIN:
            name = unicodedata.name(ch, "")
            if not name.startswith("LATIN"):
                script = (name.split(" ")[0] or "?").lower()
                return f"inne pismo ({script}): {ch!r}"
    if mode == "scripts":
        return None

    words = [w.lower() for w in WORD_RE.findall(text)]

    # 2. Słowa jednoznacznie obce.
    strong = LATIN_STRONG | set(extra_strong)
    for w in words:
        if w in strong:
            return f"słowo obcojęzyczne: {w!r}"

    # 3. Dwa dwuznaczne słowa obce blisko siebie.
    flags = [w in FOREIGN_WEAK for w in words]
    for i in range(len(flags)):
        if sum(flags[i:i + WINDOW]) >= 2:
            return f"fragment obcojęzyczny: {' '.join(words[i:i + WINDOW])!r}"

    # 4. Dłuższy tekst bez żadnych śladów polszczyzny.
    if len(words) >= 6:
        has_pl = any(c in PL_DIACRITICS for c in text) or any(w in PL_FUNCTION_WORDS for w in words)
        if not has_pl:
            return "brak śladów języka polskiego"
    return None


# --------------------------------------------------------------------------- #
# Klient LLM
# --------------------------------------------------------------------------- #
class BielikClient:
    def __init__(self, base_url: str, model: str, temperature: float,
                 max_tokens: int, timeout: float, api_key: str = "local",
                 system_extra: str = "", system_base: str = SYSTEM_PROMPT):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.api_key = api_key
        self.system_extra = system_extra
        self.system_base = system_base

    def rewrite(self, text: str, extra_hint: str = "") -> str:
        system = self.system_base
        if self.system_extra:
            system += "\n" + self.system_extra
        if extra_hint:
            system += "\n" + extra_hint
        budzet = max(self.max_tokens, int(len(text) / 2.2) + 256)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            "temperature": self.temperature,
            "top_p": 0.9,
            "max_tokens": budzet,
            "stream": False,
        }
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        wybor = data["choices"][0]
        return wybor["message"]["content"], wybor.get("finish_reason", "")


# --------------------------------------------------------------------------- #
# Cache (append-only JSONL, pozwala wznowić przerwaną pracę)
# --------------------------------------------------------------------------- #
class Cache:
    def __init__(self, path: Path | None, model: str):
        self.path = path
        self.model = model
        self.data: dict[str, str] = {}
        self.lock = threading.Lock()
        if path and path.exists():
            with path.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                        self.data[rec["k"]] = rec["v"]
                    except (json.JSONDecodeError, KeyError):
                        continue

    def key(self, text: str) -> str:
        raw = f"{PROMPT_VERSION}|{self.model}|{text}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def get(self, text: str) -> str | None:
        return self.data.get(self.key(text))

    def put(self, text: str, result: str) -> None:
        k = self.key(text)
        with self.lock:
            self.data[k] = result
            if self.path:
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"k": k, "v": result}, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- #
# Wybór i walidacja tekstów
# --------------------------------------------------------------------------- #
def looks_like_prose(s: str, min_chars: int, min_words: int) -> bool:
    s = s.strip()
    if len(s) < min_chars or len(s.split()) < min_words:
        return False
    if any(p.match(s) for p in SKIP_PATTERNS):
        return False
    letters = len(LETTER_RE.findall(s))
    return letters / max(len(s), 1) > 0.5


# Znaki, które model emituje zamiast projektowych, a których w korpusie nie ma
# ANI RAZU (sprawdzone: ” 0×, ’ 0× wobec „ 4987×). Podmiana jest więc bezstratna
# i robimy ją deterministycznie, zamiast prosić o nią model.
TYPO_NORM = {"\u201d": '"', "\u2019": "'"}
# Dywiz ze spacjami: w korpusie 0 wystąpień wobec 11900 em-pauz, a model degraduje
# „ — " na „ - " niemal w każdym tekście. Podmiana jest więc bezstratna.
SPACJOWANY_DYWIZ = re.compile(r"(?<=\s)-(?=\s)")


def normalizuj_typografie(s: str) -> str:
    for zly, dobry in TYPO_NORM.items():
        s = s.replace(zly, dobry)
    return SPACJOWANY_DYWIZ.sub("\u2014", s)


# Maskowanie sigli i liczb. Pomiar na 40 tekstach pokazał, że 74% odrzuceń
# w trybie czytelnym to „zmienione liczby" — model gubi sigla (18,40; 19,6.12.15),
# kiedy przebudowuje zdanie. Sigla nie muszą być dla modelu zrozumiałe, tylko
# przetrwać, więc zasłaniamy je nieprzejrzystym znacznikiem i przywracamy po.
MASKA = "\u27e6{}\u27e7"
MASKA_RE = re.compile(r"\u27e6(\d+)\u27e7")


def maskuj(s: str) -> tuple[str, list[str]]:
    schowek: list[str] = []

    def podmien(m):
        schowek.append(m.group(0))
        return MASKA.format(len(schowek) - 1)

    return PROTECTED_RE.sub(podmien, s), schowek


def odmaskuj(s: str, schowek: list[str]) -> str:
    def wroc(m):
        i = int(m.group(1))
        return schowek[i] if 0 <= i < len(schowek) else m.group(0)

    return MASKA_RE.sub(wroc, s)


def clean_output(original: str, out: str, pl_guards: bool = False) -> str:
    out = out.strip()
    # Modele czasem owijają odpowiedź w cudzysłów lub blok kodu.
    out = re.sub(r"^```(?:\w+)?\n?|\n?```$", "", out).strip()
    if len(out) > 1 and out[0] in "\"„«" and out[-1] in "\"”»" and original.strip()[0] not in "\"„«":
        out = out[1:-1].strip()
    if pl_guards:
        out = normalizuj_typografie(out)
    # Zachowaj białe znaki z brzegów oryginału.
    lead = original[: len(original) - len(original.lstrip())]
    trail = original[len(original.rstrip()):]
    return lead + out + trail


# Konwencje typograficzne tego repozytorium (CLAUDE.md): liczba gwiazdek kursywy,
# liczba cudzysłowów „ i ", liczba półpauz i zakaz dywizu w zakresach.
PL_ZNAKI = (("*", "gwiazdki kursywy"), ("„", "cudzysłowy otwierające"),
            ('"', "cudzysłowy zamykające"), ("–", "półpauzy"),
            ("—", "em-pauzy"), ("…", "wielokropki"))
DYWIZ_W_ZAKRESIE = re.compile(r"(?<=\d)-(?=\d)")


OBCE_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def obce_tokeny(s: str) -> Counter:
    """Wyrazy zawierające choć jedną literę spoza alfabetu łacińskiego
    (greka, hebrajski, aramejski). To materiał dowodowy — musi przetrwać."""
    out = Counter()
    for w in OBCE_RE.findall(s):
        for ch in w:
            nazwa = unicodedata.name(ch, "")
            if nazwa and not nazwa.startswith("LATIN") and ch not in ALLOWED_NON_LATIN:
                out[w] += 1
                break
    return out


# Cytat treściowy: „…" dłuższy niż 25 znaków. To przytoczone źródło — werset,
# formuła liturgiczna, zdanie Ojca — i musi przetrwać co do słowa. Krótkie
# cudzysłowy przy pojedynczych terminach to znaczniki, nie cytaty, więc wolno im
# się przesuwać. W zakresie profilu jest 3758 cytatów, z czego 1140 treściowych.
CYTAT_RE = re.compile(r"\u201e([^\u201e\"]{3,})\"")
MIN_CYTAT = 25


def cytaty(s: str) -> Counter:
    return Counter(re.sub(r"\s+", " ", m.group(1)).strip()
                   for m in CYTAT_RE.finditer(s)
                   if len(m.group(1)) > MIN_CYTAT)


KURSYWA_RE = re.compile(r"\*([^*\n]{2,})\*")


def kursywy(s: str) -> Counter:
    """Fragmenty w kursywie Markdown. W tym projekcie kursywą stoi łacina
    (*admirabile commercium*), tytuły dzieł i dokumentów — czyli materiał,
    którego strażnik pism niełacińskich nie widzi, bo łacina jest alfabetem
    łacińskim."""
    return Counter(m.group(1).strip() for m in KURSYWA_RE.finditer(s))


def validate(original: str, new: str, max_ratio: float, pl_guards: bool = False,
             typografia: bool = True, chron_obce: bool = False) -> str | None:
    """Zwraca None, gdy wynik jest OK, w przeciwnym razie opis problemu."""
    if not new.strip():
        return "pusty wynik"
    if Counter(PROTECTED_RE.findall(original)) != Counter(PROTECTED_RE.findall(new)):
        return "zmienione liczby/URL/zmienne"
    ratio = len(new.strip()) / max(len(original.strip()), 1)
    if ratio > max_ratio or ratio < 1 / max_ratio:
        return f"podejrzana zmiana długości (x{ratio:.2f})"
    low = new.lower()
    if low.startswith(("oto ", "poniżej ", "przeredagowany", "wersja")):
        return "komentarz modelu zamiast tekstu"
    if original.rstrip()[-1:] in '.!?…":)' and new.rstrip()[-1:] not in '.!?…":)':
        return f"wynik urwany (kończy się na {new.rstrip()[-12:]!r})"
    if chron_obce:
        brak = obce_tokeny(original) - obce_tokeny(new)
        if brak:
            return f"zgubione wyrażenia obce: {', '.join(list(brak)[:4])}"
        brak_cyt = cytaty(original) - cytaty(new)
        if brak_cyt:
            skr = [c[:44] + ("…" if len(c) > 44 else "") for c in list(brak_cyt)[:2]]
            return f"zgubiony cytat: {'; '.join(skr)}"
        brak_kur = kursywy(original) - kursywy(new)
        if brak_kur:
            skr = [k[:38] + ("…" if len(k) > 38 else "") for k in list(brak_kur)[:3]]
            return f"zgubiona kursywa (łacina/tytuły): {'; '.join(skr)}"
    if pl_guards:
        if typografia:
            for znak, nazwa in PL_ZNAKI:
                if original.count(znak) != new.count(znak):
                    return (f"zmieniona liczba znaków „{nazwa}\": "
                            f"{original.count(znak)} → {new.count(znak)}")
        if DYWIZ_W_ZAKRESIE.search(new) and not DYWIZ_W_ZAKRESIE.search(original):
            return "wprowadzony dywiz w zakresie (konwencja: półpauza)"
        if '\u201d' in new or '\u2019' in new:
            return "obcy cudzysłów typograficzny (konwencja: „…\")"
    return None


# --------------------------------------------------------------------------- #
# Przechodzenie po JSON
# --------------------------------------------------------------------------- #
def wyklucz_strukturalnie(rec: Any) -> set:
    """Ścieżki, które wyglądają na prozę, a prozą nie są — rozpoznane po STRUKTURZE,
    nie po długości:

    1. `sections[i].body`, gdy sekcja ma podsekcje → to lid, spis treści dla
       podsekcji niżej, zwykle kończący się dwukropkiem (mediana długości takiego
       body to 0 znaków: 91 z 181 jest pustych). Rozpisanie go powtarza podsekcje.
    2. `sections[i].children[j][1]` w sekcji typu `odniesienia` → wpis aparatu
       (tytuł w rodzaju „Iz 53,1 → w. 38 (cytat)"), czyli pozycja listy odniesień,
       celowo skrótowa. Wszystkie 409 wpisów ze strzałką siedzi w tym jednym typie.
    """
    wykluczone = set()
    for nazwa_listy in ("pericopes",):
        for pi, per in enumerate(rec.get(nazwa_listy, []) if isinstance(rec, dict) else []):
            for si, s in enumerate(per.get("sections", [])):
                baza = f"{nazwa_listy}[{pi}].sections[{si}]"
                if s.get("children"):
                    wykluczone.add(f"{baza}.body")
                if s.get("type") == "odniesienia":
                    for ci in range(len(s.get("children") or [])):
                        wykluczone.add(f"{baza}.children[{ci}][1]")
    return wykluczone


def collect(node: Any, path: tuple, out: list, args, key: str | None = None,
            skipped: list | None = None) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            collect(v, path + (k,), out, args, k, skipped)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            collect(v, path + (i,), out, args, key, skipped)
    elif isinstance(node, str):
        # wybór po ŚCIEŻCE ma pierwszeństwo przed wyborem po kluczu
        if args.include_path or args.exclude_path or getattr(args, "_strukturalne", None):
            sp = fmt_path(path)
            if sp in getattr(args, "_strukturalne", ()):
                return
            if any(r.search(sp) for r in args.exclude_path):
                return
            if args.include_path and not any(r.search(sp) for r in args.include_path):
                return
        if args.keys and key not in args.keys:
            return
        if key in args.exclude_keys:
            return
        if looks_like_prose(node, args.min_chars, args.min_words):
            reason = foreign_reason(node, args.lang_guard, args.foreign_words)
            if reason:
                if skipped is not None:
                    skipped.append((path, node, reason))
                return
            out.append((path, node))


def set_path(root: Any, path: tuple, value: str) -> None:
    cur = root
    for p in path[:-1]:
        cur = cur[p]
    cur[path[-1]] = value


def fmt_path(path: tuple) -> str:
    return "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in path).lstrip(".")


# --------------------------------------------------------------------------- #
# Redakcja pojedynczego tekstu
# --------------------------------------------------------------------------- #
class BladApi(Exception):
    """Serwer nie odpowiada poprawnie — to nie jest przypadek do fallbacku."""


# Błąd API to NIE to samo co odrzucenie przez walidację: zły adres serwera dawałby
# cichy przebieg „bez zmian" na całym korpusie i zatruty cache (tekst → tekst).
LICZNIK_BLEDOW_API = {"pod_rzad": 0, "razem": 0}
PROG_BLEDOW_API = 5


def redact_text(text: str, client: BielikClient, cache: Cache, args) -> tuple[str, str]:
    """Zwraca (wynik, status): status in {cache, ok, fallback}.
    Podnosi BladApi, gdy serwer konsekwentnie nie odpowiada."""
    cached = cache.get(text)
    if cached is not None:
        return cached, "cache"

    hint = ""
    last_problem = ""
    for attempt in range(args.retries + 1):
        wejscie, schowek = (maskuj(text) if args.maskuj else (text, []))
        try:
            raw, powod = client.rewrite(wejscie, hint)
        except (urllib.error.URLError, TimeoutError, ConnectionError, KeyError, json.JSONDecodeError) as e:
            last_problem = f"błąd API: {e}"
            LICZNIK_BLEDOW_API["pod_rzad"] += 1
            LICZNIK_BLEDOW_API["razem"] += 1
            if LICZNIK_BLEDOW_API["pod_rzad"] >= PROG_BLEDOW_API:
                raise BladApi(
                    f"{PROG_BLEDOW_API} błędów API pod rząd ({e}). "
                    f"Sprawdź --base-url (teraz: {client.url}) i czy serwer stoi. "
                    "Przebieg przerwany, żeby nie zapisać oryginałów jako wyniku."
                ) from e
            time.sleep(min(2 ** attempt, 10))
            continue
        LICZNIK_BLEDOW_API["pod_rzad"] = 0
        if args.maskuj:
            raw = odmaskuj(raw, schowek)
        new = clean_output(text, raw, args.pl_guards)
        if powod == "length":
            problem = "wynik ucięty na limicie tokenów (finish_reason=length)"
        else:
            problem = validate(text, new, args.max_len_ratio, args.pl_guards,
                               typografia=args.styl != "czytelny",
                               chron_obce=args.styl == "czytelny")
        if problem is None:
            cache.put(text, new)
            return new, "ok"
        last_problem = problem
        hint = (
            f"UWAGA: poprzednia próba została odrzucona ({problem}). "
            "Zachowaj wszystkie liczby, adresy i zmienne dokładnie jak w oryginale, "
            "nie dodawaj komentarzy i zachowaj podobną długość."
        )
    print(f"  ! zostawiam oryginał ({last_problem}): {text[:60]!r}", file=sys.stderr)
    if not last_problem.startswith("błąd API"):
        cache.put(text, text)  # nie męcz modelu w kółko tym samym
    return text, "fallback"


# --------------------------------------------------------------------------- #
# Pliki
# --------------------------------------------------------------------------- #
def load_records(path: Path) -> tuple[list[Any], bool]:
    """Zwraca (lista rekordów, czy_jsonl)."""
    if path.suffix.lower() == ".jsonl":
        recs = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
        return recs, True
    with path.open(encoding="utf-8") as f:
        return [json.load(f)], False


def save_records(path: Path, recs: list[Any], is_jsonl: bool, indent: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Zachowaj stan kończącego \n z pliku źródłowego, jeśli nadpisujemy w miejscu:
    # data/lazarz.json i data/pilat.json go nie mają, a doklejenie daje zbędny
    # wiersz w diffie przy niezmienionej treści.
    eol = True
    if path.exists():
        try:
            eol = path.read_text(encoding="utf-8").endswith("\n")
        except OSError:
            pass
    with path.open("w", encoding="utf-8") as f:
        if is_jsonl:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        else:
            json.dump(recs[0], f, ensure_ascii=False, indent=indent)
            if eol:
                f.write("\n")


def process_file(src: Path, dst: Path, client: BielikClient, cache: Cache, args) -> None:
    print(f"== {src}")
    recs, is_jsonl = load_records(src)

    targets: list[tuple[int, tuple, str]] = []
    skipped_all: list[tuple[int, tuple, str, str]] = []
    for ri, rec in enumerate(recs):
        found: list = []
        skipped: list = []
        args._strukturalne = wyklucz_strukturalnie(rec) if args.struktura_jan else set()
        collect(rec, (), found, args, skipped=skipped)
        targets.extend((ri, p, t) for p, t in found)
        skipped_all.extend((ri, p, t, r) for p, t, r in skipped)

    print(f"   do redakcji: {len(targets)} tekstów; pominięte jako obcojęzyczne: {len(skipped_all)}")
    if args.verbose_skips:
        for ri, p, t, r in skipped_all:
            print(f"   ~ pominięto [{ri}] {fmt_path(p)} ({r}): {t[:60]!r}")
    if args.dry_run:
        for ri, p, t in targets:
            print(f"   - [{ri}] {fmt_path(p)}: {t[:80]!r}")
        return

    stats: Counter = Counter()
    t0 = time.time()

    def work(item):
        ri, p, t = item
        new, status = redact_text(t, client, cache, args)
        return ri, p, new, status

    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, (ri, p, new, status) in enumerate(pool.map(work, targets), 1):
            stats[status] += 1
            set_path(recs[ri], p, new)
            if n % 10 == 0 or n == len(targets):
                print(f"   {n}/{len(targets)}  ({time.time() - t0:.0f}s)", end="\r")
    print()
    save_records(dst, recs, is_jsonl, args.indent)
    print(f"   zapisano: {dst}  | {dict(stats)}")


def resolve_jobs(inp: Path, out: Path | None, suffix: str) -> list[tuple[Path, Path]]:
    if inp.is_dir():
        files = sorted(list(inp.rglob("*.json")) + list(inp.rglob("*.jsonl")))
        jobs = []
        for f in files:
            if out:
                dst = out / f.relative_to(inp)
            else:
                dst = f.with_name(f.stem + suffix + f.suffix)
            if suffix and f.stem.endswith(suffix):
                continue
            jobs.append((f, dst))
        return jobs
    if out and (out.suffix == "" or out.is_dir()):
        return [(inp, out / inp.name)]
    dst = out if out else inp.with_name(inp.stem + suffix + inp.suffix)
    return [(inp, dst)]


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="Redakcja polskich tekstów w JSON-ach lokalnym Bielikiem.")
    ap.add_argument("input", type=Path, help="plik .json/.jsonl lub katalog")
    ap.add_argument("--out", type=Path, help="plik lub katalog wyjściowy (domyślnie obok, z sufiksem)")
    ap.add_argument("--suffix", default=".redacted", help="sufiks pliku wynikowego (domyślnie .redacted)")
    ap.add_argument("--base-url", default="http://localhost:8080/v1")
    ap.add_argument("--model", default="bielik", help="nazwa modelu (llama-server ją ignoruje)")
    ap.add_argument("--temperature", type=float, default=0.3, help="niska = wierniejsza redakcja")
    ap.add_argument("--max-tokens", type=int, default=1024)
    ap.add_argument("--timeout", type=float, default=180)
    ap.add_argument("--workers", type=int, default=1, help="równoległe zapytania (zgodnie z --parallel serwera)")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--keys", type=lambda s: set(filter(None, s.split(","))), default=set(),
                    help="redaguj tylko wartości pod tymi kluczami (po przecinku); domyślnie wszystkie teksty")
    ap.add_argument("--exclude-keys", type=lambda s: set(filter(None, s.split(","))),
                    default={"id", "uuid", "slug", "url", "email", "sku", "kod", "code", "type", "status"},
                    help="klucze, które pomijamy")
    ap.add_argument("--profil", choices=sorted(PROFILE) + ["jan-wszystko"], action="append", default=[],
                    help="gotowy zestaw ścieżek dla tego repozytorium (można podać wielokrotnie); "
                         "jan-wszystko = jan-proza + jan-aparat")
    ap.add_argument("--include-path", action="append", default=[], metavar="RE",
                    help="redaguj tylko ścieżki pasujące do tego wyrażenia (można wielokrotnie); "
                         "ścieżka w zapisie pericopes[0].sections[5].children[1][1]")
    ap.add_argument("--exclude-path", action="append", default=[], metavar="RE",
                    help="pomiń ścieżki pasujące do wyrażenia (wygrywa nad --include-path)")
    ap.add_argument("--maskuj", action=argparse.BooleanOptionalAction, default=None,
                    help="zasłoń sigla, liczby, URL-e i zmienne nieprzejrzystym "
                         "znacznikiem przed wysłaniem i przywróć po (domyślnie "
                         "włączone przy --styl czytelny — model gubi sigla przy "
                         "przebudowie zdania)")
    ap.add_argument("--struktura-jan", action=argparse.BooleanOptionalAction, default=None,
                    help="pomijaj lidy sekcji (body przy niepustych children) i wpisy "
                         "aparatu odniesień (children sekcji typu odniesienia) — "
                         "domyślnie włączone przy --profil jan-*")
    ap.add_argument("--styl", choices=["czytelny", "ostrozny", "elegancki"], default="czytelny",
                    help="przy --profil jan-*: ostrozny (domyślnie) poprawia tylko błędy "
                         "i zachowuje dobór słów; elegancki używa oryginalnego promptu "
                         "redakcyjnego (przeredagowuje styl — na tym korpusie spłaszcza "
                         "terminologię, patrz README)")
    ap.add_argument("--pl-guards", action=argparse.BooleanOptionalAction, default=None,
                    help="dodatkowa walidacja konwencji repo: liczba gwiazdek kursywy, "
                         "cudzysłowów „…\", półpauz i zakaz dywizu w zakresach "
                         "(domyślnie włączone przy --profil jan-*)")
    ap.add_argument("--lang-guard", choices=["strict", "scripts", "off"], default="strict",
                    help="strict (domyślnie): pomiń wartości z jakimkolwiek obcym fragmentem "
                         "(inne pismo, łacina, ang./niem.); scripts: tylko inne pisma; off: wyłączone")
    ap.add_argument("--foreign-words", type=lambda s: {w.strip().lower() for w in s.split(",") if w.strip()},
                    default=set(),
                    help="dodatkowe obce słowa (po przecinku), np. logos,agape,shalom; "
                         "wartość z takim słowem zostanie pominięta")
    ap.add_argument("--min-chars", type=int, default=20)
    ap.add_argument("--min-words", type=int, default=3)
    ap.add_argument("--max-len-ratio", type=float, default=1.6,
                    help="odrzuć wynik, gdy długość zmieni się bardziej niż tylokrotnie")
    ap.add_argument("--cache", type=Path, default=Path(".bielik_cache.jsonl"),
                    help="plik cache (wznawianie pracy); '' wyłącza")
    ap.add_argument("--indent", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true", help="tylko wypisz teksty do redakcji")
    ap.add_argument("--verbose-skips", action="store_true", help="wypisz każdą pominiętą wartość z powodem")
    args = ap.parse_args()

    # profile -> wzorce ścieżek
    jan = False
    for p in args.profil:
        jan = True
        nazwy = sorted(PROFILE) if p == "jan-wszystko" else [p]
        for n in nazwy:
            args.include_path.extend(PROFILE[n])
    if args.pl_guards is None:
        args.pl_guards = jan
    if args.struktura_jan is None:
        args.struktura_jan = jan
    if args.maskuj is None:
        args.maskuj = jan and args.styl == "czytelny"
    args.include_path = [re.compile(r) for r in args.include_path]
    args.exclude_path = [re.compile(r) for r in args.exclude_path]

    if not args.input.exists():
        sys.exit(f"Nie ma takiej ścieżki: {args.input}")

    if jan and args.styl == "czytelny":
        baza, dopisek = SYSTEM_PROMPT_CZYTELNY, ""
        if args.lang_guard == "strict":      # greka ma być przepisana, nie pominięta
            args.lang_guard = "off"
        if args.max_len_ratio < 2.2:         # rozpisanie skrótu wydłuża tekst
            args.max_len_ratio = 2.2
    elif jan and args.styl == "ostrozny":
        baza, dopisek = SYSTEM_PROMPT_OSTROZNY, ""
    elif jan:
        baza, dopisek = SYSTEM_PROMPT, SYSTEM_PROMPT_NAUKOWY
    else:
        baza, dopisek = SYSTEM_PROMPT, ""
    client = BielikClient(args.base_url, args.model, args.temperature, args.max_tokens,
                          args.timeout, system_extra=dopisek, system_base=baza)
    # UWAGA: str(Path("")) == "." — puste --cache dawało próbę otwarcia katalogu
    sciezka_cache = None if str(args.cache) in ("", ".") else args.cache
    cache = Cache(sciezka_cache, args.model)

    if not args.dry_run:
        try:
            client.rewrite("Zdanie próbne.")
        except Exception as e:
            sys.exit(f"Serwer nie odpowiada na {client.url}: {e}\n"
                     f"Podaj --base-url wskazujący na działający llama-server.")

    jobs = resolve_jobs(args.input, args.out, args.suffix)
    if not jobs:
        sys.exit("Brak plików .json/.jsonl do przetworzenia.")
    for src, dst in jobs:
        process_file(src, dst, client, cache, args)


if __name__ == "__main__":
    main()
