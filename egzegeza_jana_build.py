# -*- coding: utf-8 -*-
"""
EGZEGEZA EWANGELII WEDŁUG ŚW. JANA — skonsolidowany plik roboczy.

Jeden plik = schemat (SCHEMA_SQL) + wszystkie dane (Prolog J 1,1-14
z pełną kateną Ojców Kościoła) + migracja.

Uruchomienie:  python3 egzegeza_jana_build.py
Buduje od zera: egzegeza_jana.sqlite
"""
import sqlite3, pathlib

DB = pathlib.Path(__file__).with_name("egzegeza_jana.sqlite")

SCHEMA_SQL = r"""
-- ============================================================
--  EGZEGEZA EWANGELII WEDŁUG ŚW. JANA — schemat bazy (SQLite)
--  Warstwy:
--    1. kanon        : book, verse
--    2. perykopa     : pericope
--    3. komentarz    : section (drzewo), commentary_block, analysis_unit
--    4. słowniki     : lexeme, semitic_term (+ powiązania, wystąpienia)
--    5. aparat       : scripture_ref, textual_note, work, citation
--    6. recepcja     : liturgical_use
--    7. przekroje    : theme (+ theme_link)
--    8. warsztat     : meta, revision_log, FTS5, widoki
--  Wymaga SQLite >= 3.37 (STRICT). Zalecane: PRAGMA foreign_keys = ON;
-- ============================================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 0. Metadane projektu
-- ------------------------------------------------------------
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
) STRICT;

-- ------------------------------------------------------------
-- 1. KANON
-- ------------------------------------------------------------
CREATE TABLE book (
    id          INTEGER PRIMARY KEY,
    abbrev_pl   TEXT NOT NULL UNIQUE,          -- 'J', 'Rdz', 'Wj', '1 Kor'
    name_pl     TEXT NOT NULL,
    testament   TEXT NOT NULL CHECK (testament IN ('ST','NT')),
    canon_order INTEGER
) STRICT;

-- Werset kanoniczny: jedna krotka na werset; tekst grecki wg NA28
-- oraz przekład roboczy (własny, dosłowny). Wersety ST/innych ksiąg
-- mogą nie mieć wierszy — odniesienia trzymają współrzędne, nie FK.
CREATE TABLE verse (
    id              INTEGER PRIMARY KEY,
    book_id         INTEGER NOT NULL REFERENCES book(id),
    chapter         INTEGER NOT NULL,
    verse_num       INTEGER NOT NULL,
    text_greek      TEXT,                      -- NA28
    text_working_pl TEXT,                      -- przekład roboczy
    UNIQUE (book_id, chapter, verse_num)
) STRICT;

-- ------------------------------------------------------------
-- 2. PERYKOPA
-- ------------------------------------------------------------
CREATE TABLE pericope (
    id            INTEGER PRIMARY KEY,
    book_id       INTEGER NOT NULL REFERENCES book(id),
    chapter_start INTEGER NOT NULL,
    verse_start   INTEGER NOT NULL,
    chapter_end   INTEGER NOT NULL,
    verse_end     INTEGER NOT NULL,
    title         TEXT NOT NULL,               -- 'Prolog'
    motto         TEXT,                        -- 'In principio erat Verbum…'
    status        TEXT NOT NULL DEFAULT 'szkic'
                  CHECK (status IN ('szkic','w_opracowaniu','ukonczona','do_rewizji')),
    position      INTEGER,                     -- kolejność w księdze
    source_url    TEXT,                        -- np. link deepbible
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (chapter_start*1000 + verse_start <= chapter_end*1000 + verse_end)
) STRICT;

-- ------------------------------------------------------------
-- 3. KOMENTARZ
-- ------------------------------------------------------------
-- Sekcje dokumentu (I–VII, Zakończenie, Nota) jako drzewo:
-- parent_id = NULL  -> sekcja główna; inaczej podsekcja.
CREATE TABLE section (
    id           INTEGER PRIMARY KEY,
    pericope_id  INTEGER NOT NULL REFERENCES pericope(id) ON DELETE CASCADE,
    parent_id    INTEGER REFERENCES section(id) ON DELETE CASCADE,
    section_type TEXT NOT NULL CHECK (section_type IN
                 ('filologia','kontekst','teologia','autor_ludzki','autor_bozy',
                  'odniesienia','patrystyka','recepcja','zakonczenie','nota','inne')),
    title        TEXT,
    body_md      TEXT,                         -- treść w Markdown (NULL = kontener)
    position     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
) STRICT;

-- Blok komentarza wersetowego: 'w. 1', 'w. 6–8' — zakres wersetów
-- wewnątrz sekcji filologicznej, z tekstem greckim jak wydrukowano
-- i przekładem roboczym całego zakresu.
CREATE TABLE commentary_block (
    id                     INTEGER PRIMARY KEY,
    section_id             INTEGER NOT NULL REFERENCES section(id) ON DELETE CASCADE,
    chapter_start          INTEGER NOT NULL,
    verse_start            INTEGER NOT NULL,
    chapter_end            INTEGER NOT NULL,
    verse_end              INTEGER NOT NULL,
    label                  TEXT NOT NULL,      -- 'w. 1', 'w. 12–13'
    greek_text             TEXT,
    working_translation_pl TEXT,
    position               INTEGER NOT NULL DEFAULT 0,
    created_at             TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at             TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (chapter_start*1000 + verse_start <= chapter_end*1000 + verse_end)
) STRICT;

-- Jednostka analizy: najmniejszy klocek egzegezy — zwykle fraza grecka
-- + akapit analizy. phrase_greek = NULL oznacza uwagę ogólną do bloku.
CREATE TABLE analysis_unit (
    id                   INTEGER PRIMARY KEY,
    block_id             INTEGER NOT NULL REFERENCES commentary_block(id) ON DELETE CASCADE,
    phrase_greek         TEXT,                 -- 'πρὸς τὸν θεόν'
    phrase_translation_pl TEXT,                -- 'u Boga, dosł. „ku Bogu"'
    body_md              TEXT NOT NULL,
    position             INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
) STRICT;

-- ------------------------------------------------------------
-- 4. SŁOWNIKI (wielokrotnego użytku w całej Ewangelii)
-- ------------------------------------------------------------
CREATE TABLE lexeme (
    id         INTEGER PRIMARY KEY,
    lemma      TEXT NOT NULL UNIQUE,           -- 'λόγος'
    translit   TEXT,                           -- 'logos'
    pos        TEXT,                           -- część mowy
    gloss_pl   TEXT,                           -- krótkie znaczenie
    article_md TEXT,                           -- hasło zbiorcze (rozwijane)
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
) STRICT;

CREATE TABLE semitic_term (
    id       INTEGER PRIMARY KEY,
    term     TEXT NOT NULL,                    -- 'דָּבָר'
    translit TEXT NOT NULL,                    -- 'dawar'
    lang     TEXT NOT NULL CHECK (lang IN ('hbr','aram')),
    gloss_pl TEXT,
    notes_md TEXT,
    UNIQUE (term, lang)
) STRICT;

-- Podwójne dno grecko-semickie: λόγος ↔ דָּבָר, δόξα ↔ כָּבוֹד itd.
CREATE TABLE lexeme_semitic (
    lexeme_id     INTEGER NOT NULL REFERENCES lexeme(id) ON DELETE CASCADE,
    semitic_id    INTEGER NOT NULL REFERENCES semitic_term(id) ON DELETE CASCADE,
    relation_note TEXT,
    PRIMARY KEY (lexeme_id, semitic_id)
) STRICT;

-- Wystąpienie leksemu w wersecie; opcjonalnie spięte z jednostką
-- analizy, w której jest omawiane. Daje mapę semantyczną słów-kluczy.
CREATE TABLE lexeme_occurrence (
    id               INTEGER PRIMARY KEY,
    lexeme_id        INTEGER NOT NULL REFERENCES lexeme(id) ON DELETE CASCADE,
    verse_id         INTEGER NOT NULL REFERENCES verse(id) ON DELETE CASCADE,
    form_in_text     TEXT,                     -- 'σὰρξ'
    analysis_unit_id INTEGER REFERENCES analysis_unit(id) ON DELETE SET NULL,
    note             TEXT
) STRICT;

-- ------------------------------------------------------------
-- 5. APARAT: odniesienia, warianty, autorzy
-- ------------------------------------------------------------
-- Odniesienie biblijne. Źródło = dokładnie jedno z trzech (CHECK).
CREATE TABLE scripture_ref (
    id                   INTEGER PRIMARY KEY,
    pericope_id          INTEGER REFERENCES pericope(id)      ON DELETE CASCADE,
    section_id           INTEGER REFERENCES section(id)       ON DELETE CASCADE,
    analysis_unit_id     INTEGER REFERENCES analysis_unit(id) ON DELETE CASCADE,
    target_book_id       INTEGER NOT NULL REFERENCES book(id),
    target_chapter_start INTEGER,
    target_verse_start   INTEGER,
    target_chapter_end   INTEGER,
    target_verse_end     INTEGER,
    target_label         TEXT NOT NULL,        -- 'Wj 34,6', 'Ps 33(32),6'
    relation             TEXT NOT NULL CHECK (relation IN
                         ('cytat','aluzja','typologia','paralela',
                          'kontrast','rozwiniecie','tlo','por')),
    note_md              TEXT,
    CHECK ((pericope_id IS NOT NULL) + (section_id IS NOT NULL)
         + (analysis_unit_id IS NOT NULL) = 1)
) STRICT;

-- Nota krytyki tekstu (warianty, interpunkcja).
CREATE TABLE textual_note (
    id            INTEGER PRIMARY KEY,
    verse_id      INTEGER NOT NULL REFERENCES verse(id) ON DELETE CASCADE,
    lemma_text    TEXT NOT NULL,               -- 'ὃ γέγονεν'
    issue         TEXT NOT NULL,               -- 'interpunkcja', 'wariant lekcji'
    readings_md   TEXT,                        -- lekcje i świadkowie
    assessment_md TEXT                         -- ocena
) STRICT;

-- Dzieła i autorzy (patrystyka, scholastyka, magisterium, literatura).
CREATE TABLE work (
    id        INTEGER PRIMARY KEY,
    author    TEXT,
    title     TEXT,                            -- tytuł oryginalny
    title_pl  TEXT,                            -- tytuł polski
    century   TEXT,                            -- 'II', 'XIII', 'XX'
    tradition TEXT CHECK (tradition IN
              ('patrystyka','scholastyka','magisterium','wspolczesna',
               'judaizm','filozofia_antyczna','inna')),
    CHECK (author IS NOT NULL OR title IS NOT NULL),
    UNIQUE (author, title)
) STRICT;

-- Cytowanie dzieła w konkretnym miejscu komentarza (źródło: jedno z trzech).
CREATE TABLE citation (
    id               INTEGER PRIMARY KEY,
    work_id          INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    locus            TEXT,                     -- 'nr 11–13', 'ks. I'
    pericope_id      INTEGER REFERENCES pericope(id)      ON DELETE CASCADE,
    section_id       INTEGER REFERENCES section(id)       ON DELETE CASCADE,
    analysis_unit_id INTEGER REFERENCES analysis_unit(id) ON DELETE CASCADE,
    note_md          TEXT,
    CHECK ((pericope_id IS NOT NULL) + (section_id IS NOT NULL)
         + (analysis_unit_id IS NOT NULL) = 1)
) STRICT;

-- ------------------------------------------------------------
-- 6. RECEPCJA LITURGICZNA
-- ------------------------------------------------------------
CREATE TABLE liturgical_use (
    id             INTEGER PRIMARY KEY,
    pericope_id    INTEGER NOT NULL REFERENCES pericope(id) ON DELETE CASCADE,
    rite           TEXT NOT NULL,              -- 'rzymski', 'bizantyjski', …
    occasion       TEXT NOT NULL,              -- 'Msza w dzień Narodzenia Pańskiego'
    passage        TEXT,                       -- 'J 1,1–14'
    description_md TEXT
) STRICT;

-- ------------------------------------------------------------
-- 7. PRZEKROJE TEMATYCZNE
-- ------------------------------------------------------------
CREATE TABLE theme (
    id             INTEGER PRIMARY KEY,
    name           TEXT NOT NULL UNIQUE,       -- 'ἦν / ἐγένετο — trwanie a stawanie się'
    description_md TEXT
) STRICT;

-- Nić tematyczna przypięta do perykopy / sekcji / bloku / jednostki
-- (dokładnie jedno źródło).
CREATE TABLE theme_link (
    id               INTEGER PRIMARY KEY,
    theme_id         INTEGER NOT NULL REFERENCES theme(id) ON DELETE CASCADE,
    pericope_id      INTEGER REFERENCES pericope(id)         ON DELETE CASCADE,
    section_id       INTEGER REFERENCES section(id)          ON DELETE CASCADE,
    block_id         INTEGER REFERENCES commentary_block(id) ON DELETE CASCADE,
    analysis_unit_id INTEGER REFERENCES analysis_unit(id)    ON DELETE CASCADE,
    CHECK ((pericope_id IS NOT NULL) + (section_id IS NOT NULL)
         + (block_id IS NOT NULL) + (analysis_unit_id IS NOT NULL) = 1)
) STRICT;

-- ------------------------------------------------------------
-- 8. WARSZTAT: dziennik zmian
-- ------------------------------------------------------------
CREATE TABLE revision_log (
    id         INTEGER PRIMARY KEY,
    entity     TEXT NOT NULL,                  -- 'pericope', 'analysis_unit', …
    entity_id  INTEGER NOT NULL,
    changed_at TEXT NOT NULL DEFAULT (datetime('now')),
    note       TEXT
) STRICT;

-- ------------------------------------------------------------
-- INDEKSY (SQLite nie indeksuje FK automatycznie)
-- ------------------------------------------------------------
CREATE INDEX idx_section_pericope ON section(pericope_id, position);
CREATE INDEX idx_section_parent   ON section(parent_id);
CREATE INDEX idx_block_section    ON commentary_block(section_id, position);
CREATE INDEX idx_unit_block       ON analysis_unit(block_id, position);
CREATE INDEX idx_occ_lexeme       ON lexeme_occurrence(lexeme_id);
CREATE INDEX idx_occ_verse        ON lexeme_occurrence(verse_id);
CREATE INDEX idx_ref_target       ON scripture_ref(target_book_id);
CREATE INDEX idx_ref_pericope     ON scripture_ref(pericope_id);
CREATE INDEX idx_ref_section      ON scripture_ref(section_id);
CREATE INDEX idx_ref_unit         ON scripture_ref(analysis_unit_id);
CREATE INDEX idx_cit_work         ON citation(work_id);
CREATE INDEX idx_theme_link_theme ON theme_link(theme_id);
CREATE INDEX idx_txtnote_verse    ON textual_note(verse_id);

-- ------------------------------------------------------------
-- TRIGGERY updated_at
-- ------------------------------------------------------------
CREATE TRIGGER trg_pericope_upd AFTER UPDATE ON pericope
BEGIN UPDATE pericope SET updated_at = datetime('now') WHERE id = NEW.id; END;

CREATE TRIGGER trg_section_upd AFTER UPDATE ON section
BEGIN UPDATE section SET updated_at = datetime('now') WHERE id = NEW.id; END;

CREATE TRIGGER trg_block_upd AFTER UPDATE ON commentary_block
BEGIN UPDATE commentary_block SET updated_at = datetime('now') WHERE id = NEW.id; END;

CREATE TRIGGER trg_unit_upd AFTER UPDATE ON analysis_unit
BEGIN UPDATE analysis_unit SET updated_at = datetime('now') WHERE id = NEW.id; END;

CREATE TRIGGER trg_lexeme_upd AFTER UPDATE ON lexeme
BEGIN UPDATE lexeme SET updated_at = datetime('now') WHERE id = NEW.id; END;

-- ------------------------------------------------------------
-- PEŁNOTEKSTOWE WYSZUKIWANIE (FTS5)
-- Uwaga: remove_diacritics działa tylko dla znaków łacińskich
-- rozkładalnych (ó, é, á...). Grekę, hebrajski i polskie „ł"
-- wyszukuj w pełnym zapisie: MATCH 'λόγος', MATCH 'światłość'.
-- ------------------------------------------------------------
CREATE VIRTUAL TABLE fts_tresc USING fts5(
    tekst,
    entity    UNINDEXED,
    entity_id UNINDEXED,
    tokenize = "unicode61 remove_diacritics 2"
);

-- analysis_unit -> FTS
CREATE TRIGGER trg_fts_unit_ins AFTER INSERT ON analysis_unit BEGIN
    INSERT INTO fts_tresc(tekst, entity, entity_id)
    VALUES (coalesce(NEW.phrase_greek,'') || ' ' ||
            coalesce(NEW.phrase_translation_pl,'') || ' ' || NEW.body_md,
            'analysis_unit', NEW.id);
END;
CREATE TRIGGER trg_fts_unit_del AFTER DELETE ON analysis_unit BEGIN
    DELETE FROM fts_tresc WHERE entity='analysis_unit' AND entity_id=OLD.id;
END;
CREATE TRIGGER trg_fts_unit_upd AFTER UPDATE ON analysis_unit BEGIN
    DELETE FROM fts_tresc WHERE entity='analysis_unit' AND entity_id=OLD.id;
    INSERT INTO fts_tresc(tekst, entity, entity_id)
    VALUES (coalesce(NEW.phrase_greek,'') || ' ' ||
            coalesce(NEW.phrase_translation_pl,'') || ' ' || NEW.body_md,
            'analysis_unit', NEW.id);
END;

-- section -> FTS
CREATE TRIGGER trg_fts_section_ins AFTER INSERT ON section
WHEN NEW.body_md IS NOT NULL BEGIN
    INSERT INTO fts_tresc(tekst, entity, entity_id)
    VALUES (coalesce(NEW.title,'') || ' ' || NEW.body_md, 'section', NEW.id);
END;
CREATE TRIGGER trg_fts_section_del AFTER DELETE ON section BEGIN
    DELETE FROM fts_tresc WHERE entity='section' AND entity_id=OLD.id;
END;
CREATE TRIGGER trg_fts_section_upd AFTER UPDATE ON section BEGIN
    DELETE FROM fts_tresc WHERE entity='section' AND entity_id=OLD.id;
    INSERT INTO fts_tresc(tekst, entity, entity_id)
    SELECT coalesce(NEW.title,'') || ' ' || NEW.body_md, 'section', NEW.id
    WHERE NEW.body_md IS NOT NULL;
END;

-- commentary_block -> FTS (greka + przekład)
CREATE TRIGGER trg_fts_block_ins AFTER INSERT ON commentary_block BEGIN
    INSERT INTO fts_tresc(tekst, entity, entity_id)
    VALUES (NEW.label || ' ' || coalesce(NEW.greek_text,'') || ' ' ||
            coalesce(NEW.working_translation_pl,''), 'commentary_block', NEW.id);
END;
CREATE TRIGGER trg_fts_block_del AFTER DELETE ON commentary_block BEGIN
    DELETE FROM fts_tresc WHERE entity='commentary_block' AND entity_id=OLD.id;
END;
CREATE TRIGGER trg_fts_block_upd AFTER UPDATE ON commentary_block BEGIN
    DELETE FROM fts_tresc WHERE entity='commentary_block' AND entity_id=OLD.id;
    INSERT INTO fts_tresc(tekst, entity, entity_id)
    VALUES (NEW.label || ' ' || coalesce(NEW.greek_text,'') || ' ' ||
            coalesce(NEW.working_translation_pl,''), 'commentary_block', NEW.id);
END;

-- lexeme -> FTS
CREATE TRIGGER trg_fts_lexeme_ins AFTER INSERT ON lexeme BEGIN
    INSERT INTO fts_tresc(tekst, entity, entity_id)
    VALUES (NEW.lemma || ' ' || coalesce(NEW.translit,'') || ' ' ||
            coalesce(NEW.gloss_pl,'') || ' ' || coalesce(NEW.article_md,''),
            'lexeme', NEW.id);
END;
CREATE TRIGGER trg_fts_lexeme_del AFTER DELETE ON lexeme BEGIN
    DELETE FROM fts_tresc WHERE entity='lexeme' AND entity_id=OLD.id;
END;
CREATE TRIGGER trg_fts_lexeme_upd AFTER UPDATE ON lexeme BEGIN
    DELETE FROM fts_tresc WHERE entity='lexeme' AND entity_id=OLD.id;
    INSERT INTO fts_tresc(tekst, entity, entity_id)
    VALUES (NEW.lemma || ' ' || coalesce(NEW.translit,'') || ' ' ||
            coalesce(NEW.gloss_pl,'') || ' ' || coalesce(NEW.article_md,''),
            'lexeme', NEW.id);
END;

-- ------------------------------------------------------------
-- WIDOKI
-- ------------------------------------------------------------
-- Werset z siglum ('J 1,14')
CREATE VIEW v_verse AS
SELECT v.id,
       b.abbrev_pl || ' ' || v.chapter || ',' || v.verse_num AS siglum,
       v.text_greek, v.text_working_pl, v.book_id, v.chapter, v.verse_num
FROM verse v JOIN book b ON b.id = v.book_id;

-- Spis perykop z licznikami
CREATE VIEW v_spis_perykop AS
SELECT p.id,
       b.abbrev_pl || ' ' ||
       CASE WHEN p.chapter_start = p.chapter_end
            THEN p.chapter_start || ',' || p.verse_start || '–' || p.verse_end
            ELSE p.chapter_start || ',' || p.verse_start || ' – '
                 || p.chapter_end || ',' || p.verse_end
       END AS siglum,
       p.title, p.motto, p.status,
       (SELECT count(*) FROM section s
         WHERE s.pericope_id = p.id)                             AS sekcje,
       (SELECT count(*) FROM commentary_block cb
         JOIN section s2 ON s2.id = cb.section_id
        WHERE s2.pericope_id = p.id)                             AS bloki,
       (SELECT count(*) FROM analysis_unit u
         JOIN commentary_block cb2 ON cb2.id = u.block_id
         JOIN section s3 ON s3.id = cb2.section_id
        WHERE s3.pericope_id = p.id)                             AS jednostki
FROM pericope p JOIN book b ON b.id = p.book_id
ORDER BY p.book_id, p.chapter_start, p.verse_start;

-- Przynależność wersetów do perykop (po zakresie)
CREATE VIEW v_pericope_verse AS
SELECT p.id AS pericope_id, v.id AS verse_id, v.chapter, v.verse_num
FROM pericope p
JOIN verse v ON v.book_id = p.book_id
 AND (v.chapter*1000 + v.verse_num)
     BETWEEN (p.chapter_start*1000 + p.verse_start)
         AND (p.chapter_end*1000  + p.verse_end);

-- Leksykon z listą wystąpień
CREATE VIEW v_leksykon AS
SELECT l.id, l.lemma, l.translit, l.pos, l.gloss_pl,
       (SELECT group_concat(b.abbrev_pl || ' ' || v.chapter || ',' || v.verse_num, '; ')
          FROM lexeme_occurrence o
          JOIN verse v ON v.id = o.verse_id
          JOIN book  b ON b.id = v.book_id
         WHERE o.lexeme_id = l.id) AS wystapienia
FROM lexeme l;

-- ------------------------------------------------------------
-- 9. KATENA PATRYSTYCZNA
--    Komentarz Ojca Kościoła przypięty do bloku wersetowego
--    (lub całej perykopy). work = autor+dzieło, locus = miejsce.
-- ------------------------------------------------------------
CREATE TABLE patristic_comment (
    id          INTEGER PRIMARY KEY,
    work_id     INTEGER NOT NULL REFERENCES work(id) ON DELETE CASCADE,
    pericope_id INTEGER REFERENCES pericope(id)         ON DELETE CASCADE,
    block_id    INTEGER REFERENCES commentary_block(id) ON DELETE CASCADE,
    locus       TEXT,                          -- 'Tract. in Io. 1,17'
    body_md     TEXT NOT NULL,                 -- parafraza/streszczenie + cytaty
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK ((pericope_id IS NOT NULL) + (block_id IS NOT NULL) = 1)
) STRICT;

CREATE INDEX idx_patristic_block ON patristic_comment(block_id, position);
CREATE INDEX idx_patristic_work  ON patristic_comment(work_id);

CREATE TRIGGER trg_patristic_upd AFTER UPDATE ON patristic_comment
BEGIN UPDATE patristic_comment SET updated_at = datetime('now') WHERE id = NEW.id; END;

-- patristic_comment -> FTS
CREATE TRIGGER trg_fts_patristic_ins AFTER INSERT ON patristic_comment BEGIN
    INSERT INTO fts_tresc(tekst, entity, entity_id)
    VALUES (coalesce(NEW.locus,'') || ' ' || NEW.body_md, 'patristic_comment', NEW.id);
END;
CREATE TRIGGER trg_fts_patristic_del AFTER DELETE ON patristic_comment BEGIN
    DELETE FROM fts_tresc WHERE entity='patristic_comment' AND entity_id=OLD.id;
END;
CREATE TRIGGER trg_fts_patristic_upd AFTER UPDATE ON patristic_comment BEGIN
    DELETE FROM fts_tresc WHERE entity='patristic_comment' AND entity_id=OLD.id;
    INSERT INTO fts_tresc(tekst, entity, entity_id)
    VALUES (coalesce(NEW.locus,'') || ' ' || NEW.body_md, 'patristic_comment', NEW.id);
END;

-- Katena: blok -> autor -> komentarz
CREATE VIEW v_catena AS
SELECT b.label AS blok, w.author AS autor, w.title AS dzielo,
       p.locus, p.body_md, p.position
FROM patristic_comment p
JOIN work w ON w.id = p.work_id
LEFT JOIN commentary_block b ON b.id = p.block_id
ORDER BY b.position, p.position;

"""

# ------------------------------------------------------------------
# 1. KSIĘGI (kanon potrzebny dla perykopy i celów odniesień)
# ------------------------------------------------------------------
BOOKS = [
    # (abbrev, nazwa, testament, canon_order)
    ("Rdz",   "Księga Rodzaju",                    "ST", 1),
    ("Wj",    "Księga Wyjścia",                    "ST", 2),
    ("Ps",    "Księga Psalmów",                    "ST", 19),
    ("Prz",   "Księga Przysłów",                   "ST", 20),
    ("Mdr",   "Księga Mądrości",                   "ST", 22),
    ("Syr",   "Mądrość Syracha",                   "ST", 23),
    ("Iz",    "Księga Izajasza",                   "ST", 24),
    ("Łk",    "Ewangelia według św. Łukasza",      "NT", 49),
    ("J",     "Ewangelia według św. Jana",         "NT", 50),
    ("Dz",    "Dzieje Apostolskie",                "NT", 51),
    ("Rz",    "List do Rzymian",                   "NT", 52),
    ("1 Kor", "1 List do Koryntian",               "NT", 53),
    ("Flp",   "List do Filipian",                  "NT", 57),
    ("Kol",   "List do Kolosan",                   "NT", 58),
    ("Hbr",   "List do Hebrajczyków",              "NT", 65),
    ("Jk",    "List św. Jakuba",                   "NT", 66),
    ("1 P",   "1 List św. Piotra",                 "NT", 67),
    ("2 P",   "2 List św. Piotra",                 "NT", 68),
    ("1 J",   "1 List św. Jana",                   "NT", 69),
    ("Ap",    "Apokalipsa św. Jana",               "NT", 73),
]

# ------------------------------------------------------------------
# 2. WERSETY J 1,1-14 — tekst grecki NA28 + przekład roboczy
#    (dla w. 6-8 i 12-13 przekład podzielony wg wersyfikacji;
#     przekład łączny zakresu przechowuje commentary_block)
# ------------------------------------------------------------------
VERSES = {
    1:  ("Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος.",
         "Na początku było Słowo, a Słowo było u Boga, i Bogiem było Słowo."),
    2:  ("οὗτος ἦν ἐν ἀρχῇ πρὸς τὸν θεόν.",
         "Ono było na początku u Boga."),
    3:  ("πάντα δι᾿ αὐτοῦ ἐγένετο, καὶ χωρὶς αὐτοῦ ἐγένετο οὐδὲ ἕν. ὃ γέγονεν",
         "Wszystko przez Nie się stało, a bez Niego nic się nie stało, [z tego] co się stało."),
    4:  ("ἐν αὐτῷ ζωὴ ἦν, καὶ ἡ ζωὴ ἦν τὸ φῶς τῶν ἀνθρώπων·",
         "W Nim było życie, a życie było światłością ludzi."),
    5:  ("καὶ τὸ φῶς ἐν τῇ σκοτίᾳ φαίνει, καὶ ἡ σκοτία αὐτὸ οὐ κατέλαβεν.",
         "A światłość w ciemności świeci i ciemność jej nie ogarnęła."),
    6:  ("Ἐγένετο ἄνθρωπος, ἀπεσταλμένος παρὰ θεοῦ, ὄνομα αὐτῷ Ἰωάννης·",
         "Pojawił się człowiek posłany od Boga — imię jego Jan."),
    7:  ("οὗτος ἦλθεν εἰς μαρτυρίαν ἵνα μαρτυρήσῃ περὶ τοῦ φωτός, ἵνα πάντες πιστεύσωσιν δι᾿ αὐτοῦ.",
         "Przyszedł on na świadectwo, aby zaświadczyć o światłości, aby wszyscy przez niego uwierzyli."),
    8:  ("οὐκ ἦν ἐκεῖνος τὸ φῶς, ἀλλ᾿ ἵνα μαρτυρήσῃ περὶ τοῦ φωτός.",
         "Nie był on światłością, ale [przyszedł], aby zaświadczyć o światłości."),
    9:  ("Ἦν τὸ φῶς τὸ ἀληθινόν, ὃ φωτίζει πάντα ἄνθρωπον, ἐρχόμενον εἰς τὸν κόσμον.",
         "Była światłość prawdziwa, która oświeca każdego człowieka, przychodząc na świat."),
    10: ("ἐν τῷ κόσμῳ ἦν, καὶ ὁ κόσμος δι᾿ αὐτοῦ ἐγένετο, καὶ ὁ κόσμος αὐτὸν οὐκ ἔγνω.",
         "Na świecie było, i świat przez Nie się stał, a świat Go nie poznał."),
    11: ("εἰς τὰ ἴδια ἦλθεν, καὶ οἱ ἴδιοι αὐτὸν οὐ παρέλαβον.",
         "Do swojej własności przyszło, a swoi Go nie przyjęli."),
    12: ("ὅσοι δὲ ἔλαβον αὐτόν, ἔδωκεν αὐτοῖς ἐξουσίαν τέκνα θεοῦ γενέσθαι, τοῖς πιστεύουσιν εἰς τὸ ὄνομα αὐτοῦ,",
         "Tym zaś wszystkim, którzy Je przyjęli, dało moc, aby się stali dziećmi Bożymi — tym, którzy wierzą w imię Jego,"),
    13: ("οἳ οὐκ ἐξ αἱμάτων οὐδὲ ἐκ θελήματος σαρκὸς οὐδὲ ἐκ θελήματος ἀνδρὸς ἀλλ᾿ ἐκ θεοῦ ἐγεννήθησαν.",
         "którzy nie z krwi ani z woli ciała, ani z woli męża, ale z Boga zostali zrodzeni."),
    14: ("Καὶ ὁ λόγος σὰρξ ἐγένετο καὶ ἐσκήνωσεν ἐν ἡμῖν, καὶ ἐθεασάμεθα τὴν δόξαν αὐτοῦ, δόξαν ὡς μονογενοῦς παρὰ πατρός, πλήρης χάριτος καὶ ἀληθείας.",
         "A Słowo ciałem się stało i rozbiło namiot wśród nas, i oglądaliśmy chwałę Jego — chwałę, jaką Jednorodzony [ma] od Ojca — pełne łaski i prawdy."),
}

# ------------------------------------------------------------------
# 3. PERYKOPA
# ------------------------------------------------------------------
PERICOPE = {
    "book": "J", "cs": 1, "vs": 1, "ce": 1, "ve": 14,
    "title": "Prolog",
    "motto": "In principio erat Verbum (Na początku było Słowo)",
    "status": "ukonczona",
    "position": 1,
    "source_url": ("https://deepbible.online/?pericopes=J+1,1-14%7CNA28;J+1,1-14%7CPAU;"
                   "Rdz+1,1-5%7CPAU;Rdz+22,1-19%7CPAU;Wj+25,8%7CPAU;Wj+33,18-23%7CPAU;"
                   "Wj+34,6%7CPAU;Wj+40,34-35%7CPAU;Ps+33,6%7CPAU;Prz+8,22-31%7CPAU;"
                   "Mdr+7,25-26%7CPAU;Syr+24,1-23%7CPAU;Iz+55,10-11%7CPAU"),
}

SECTION_I_INTRO = ("Poniższy przekład jest przekładem roboczym, wykonanym bezpośrednio "
                   "z tekstu greckiego na potrzeby analizy — celowo dosłownym, aby "
                   "uwidocznić niuanse oryginału.")

# ------------------------------------------------------------------
# 4. BLOKI KOMENTARZA WERSETOWEGO (sekcja I) + jednostki analizy
#    unit = (phrase_greek | None, phrase_translation_pl | None, body_md)
# ------------------------------------------------------------------
BLOCKS = [
{
 "label": "w. 1", "cs": 1, "vs": 1, "ce": 1, "ve": 1,
 "greek": VERSES[1][0], "transl": VERSES[1][1],
 "units": [
 ("ἦν", "było (imperfectum od εἰμί — być)",
"""Trzy zdania, trzy stopnie objawienia — a każde z nich zbudowane wokół czasownika ἦν (było), imperfectum od εἰμί (być). To rozstrzygnięcie gramatyczne o ogromnej doniosłości teologicznej: imperfectum wyraża trwanie ciągłe, bez punktu początkowego. Jan nie mówi, że Słowo stało się na początku (wtedy użyłby aorystu ἐγένετο — stało się, zaistniało, jak w w. 3 o stworzeniu), lecz że było — trwało już, gdy „początek" się zaczynał. Kontrast ἦν (było) / ἐγένετο (stało się) jest osią całego Prologu: to, co jest, wobec tego, co powstaje. Na tym jednym imperfectum załamie się później cała argumentacja Ariusza, którego hasło brzmiało ἦν ποτε ὅτε οὐκ ἦν (był kiedyś czas, gdy Go nie było) — Jan mówi dokładnie odwrotnie."""),
 ("Ἐν ἀρχῇ", "na początku",
"""Bez rodzajnika, dokładnie jak w Septuagincie w Rdz 1,1: ἐν ἀρχῇ ἐποίησεν ὁ θεός (na początku uczynił Bóg). Aluzja jest zamierzona i dla każdego czytelnika znającego grecką Biblię natychmiastowa: Jan pisze nową Księgę Rodzaju. Ale u Jana ἀρχή (początek) sięga głębiej niż w Rdz — nie jest to początek stwarzania, lecz to, co „przed" wszelkim stwarzaniem, absolutna anterioryzacja Słowa względem czasu."""),
 ("πρὸς τὸν θεόν", 'u Boga, dosł. „ku Bogu"',
"""Przyimek πρός (ku, w stronę) z biernikiem wyraża zwykle ruch lub dynamiczne skierowanie ku komuś. Jan mógł napisać παρὰ τῷ θεῷ (przy Bogu, obok Boga — tak zresztą pisze w J 17,5) albo ἐν τῷ θεῷ (w Bogu). Wybrał πρός: Słowo jest zwrócone ku Bogu, w wiecznej relacji, twarzą w twarz. Nie statyczne współistnienie, lecz odwieczna komunia osobowa. To najstarsze w Nowym Testamencie zdanie, które gramatyką wyraża to, co teologia nazwie później relacjami trynitarnymi."""),
 ("καὶ θεὸς ἦν ὁ λόγος", "i Bogiem było Słowo",
"""Najbardziej dyskutowane zdanie Prologu. Zwróćmy uwagę na trzy rzeczy. Po pierwsze, szyk: orzecznik θεός (Bóg) stoi emfatycznie na pierwszym miejscu, przed czasownikiem — akcent pada na *boskość* Słowa. Po drugie, θεός jest bez rodzajnika, podczas gdy podmiot ὁ λόγος (Słowo) ma rodzajnik. Zgodnie z tzw. regułą Colwella (orzecznik określony, stojący przed czasownikiem, zwykle traci rodzajnik) brak rodzajnika nie osłabia znaczenia — wskazuje natomiast, że θεός pełni tu funkcję jakościową: Słowo jest wszystkim tym, czym jest Bóg, ma boską naturę. Po trzecie — i to kluczowe — Jan *nie* napisał ὁ λόγος ἦν ὁ θεός (Słowo było tym-oto-Bogiem), co utożsamiłoby Osobę Słowa z Osobą Ojca (błąd, który później nazwiemy modalizmem), ani ὁ λόγος ἦν θεῖος (Słowo było boskie/bosko-podobne), co uczyniłoby ze Słowa jedynie istotę „boskawą". Grecka składnia tego pół wersetu jest cudem precyzji: pełna boskość natury, realna odrębność osoby. Przekład strażnicy „Słowo było bogiem" (z małej litery) gwałci zarówno regułę Colwella, jak i kontekst całej Ewangelii (por. J 20,28, gdzie Tomasz mówi do Jezusa: ὁ κύριός μου καὶ ὁ θεός μου — Pan mój i Bóg mój, z rodzajnikami!)."""),
 ("ὁ λόγος", "Słowo",
"""O zapleczu tego pojęcia szerzej w części II. Filologicznie: λόγος znaczy zarówno „słowo", jak „rozum", „racja", „zasada", „rachunek", „mowa". Łacińskie *Verbum* (Słowo) i *Ratio* (Rozum) obie strony tego znaczenia rozdzielają; greka trzyma je razem — i Jan z tej dwuznaczności korzysta."""),
 ]},
{
 "label": "w. 2", "cs": 1, "vs": 2, "ce": 1, "ve": 2,
 "greek": VERSES[2][0], "transl": VERSES[2][1],
 "units": [
 ("οὗτος", "ten, ten właśnie",
"""Pozorna redundancja — Jan powtarza w. 1, ale z zaimkiem οὗτος (ten, ten właśnie). Funkcja jest podwójna: retoryczna (styl semicki lubi paralelizm i inkluzje) i teologiczna — Jan zbiera trzy twierdzenia w. 1 w jedno i zamyka drogę błędnej interpretacji, jakoby Słowo „stało się" Bogiem w pewnym momencie. Ten, który jest Bogiem, jest odwiecznie *u* Boga: jedność natury nie znosi odrębności osoby, odrębność nie rozbija jedności."""),
 ]},
{
 "label": "w. 3", "cs": 1, "vs": 3, "ce": 1, "ve": 3,
 "greek": VERSES[3][0], "transl": VERSES[3][1],
 "units": [
 ("πάντα δι᾿ αὐτοῦ ἐγένετο", "wszystko przez Nie się stało",
"""Pierwsze ἐγένετο (stało się) — aoryst od γίνομαι (stawać się, powstawać). Wchodzimy w porządek stworzenia. Πάντα (wszystko) bez rodzajnika — nie ὁ κόσμος (świat) jako całość uporządkowana, lecz dystrybutywnie: każda rzecz z osobna. Δι᾿ αὐτοῦ (przez Nie) — przyimek διά (przez, za pośrednictwem) z dopełniaczem wyraża pośrednictwo sprawcze: Słowo jest tym, *przez* którego Ojciec stwarza (por. 1 Kor 8,6: δι᾿ οὗ τὰ πάντα — przez którego wszystko; Hbr 1,2; Kol 1,16). Negatywna paralela χωρὶς αὐτοῦ οὐδὲ ἕν (bez Niego ani jedno) jest emfatyczna: οὐδὲ ἕν (ani jedna rzecz) mocniejsze niż zwykłe οὐδέν (nic) — żaden byt, choćby najmniejszy, nie wymyka się przyczynowości Słowa. To wyklucza wszelki dualizm: nie ma drugiej zasady stwórczej, nie ma materii samoistnej ani złego demiurga (przeciw proto-gnostykom)."""),
 ("ὃ γέγονεν", "co się stało",
"""Problem interpunkcyjny ὃ γέγονεν (co się stało): NA28, za najstarszymi świadkami i interpunkcją ojców przednicejskich, dopuszcza lekturę łączącą te słowa z w. 4: ὃ γέγονεν ἐν αὐτῷ ζωὴ ἦν (to, co się stało, w Nim było życiem) — tzn. stworzenie, zanim zaistniało w sobie, istniało w Słowie jako życie, jako odwieczna idea. Po kryzysie ariańskim ojcowie zaczęli łączyć ὃ γέγονεν z w. 3 (jak w przekładach współczesnych), by arianie nie czytali „Duch też się stał". Obie lektury są prawowierne; pierwsza, starsza, jest głęboko zbieżna z nauką o *rationes aeternae* (racjach odwiecznych) — rzeczy istnieją w Bogu wcześniej i doskonalej niż w sobie samych."""),
 ]},
{
 "label": "w. 4", "cs": 1, "vs": 4, "ce": 1, "ve": 4,
 "greek": VERSES[4][0], "transl": VERSES[4][1],
 "units": [
 (None, None,
"""Powrót imperfectum ἦν (było) — życie w Słowie nie „stało się", lecz *jest* odwiecznie. Ζωή (życie) u Jana to nigdy zwykła biologiczna żywotność (na to greka ma słowo βίος — życie doczesne, sposób życia), lecz życie Boże, które w dalszej Ewangelii stanie się ζωὴ αἰώνιος (życie wieczne). Φῶς (światłość) — pierwsze stworzenie z Rdz 1,3 — tutaj jest niestworzone: życie Słowa *jest* światłem dla ludzi, tzn. źródłem poznania i sensu. Τῶν ἀνθρώπων (ludzi) — nie „Żydów", nie „wierzących": uniwersalizm od pierwszych wersów."""),
 ]},
{
 "label": "w. 5", "cs": 1, "vs": 5, "ce": 1, "ve": 5,
 "greek": VERSES[5][0], "transl": VERSES[5][1],
 "units": [
 ("φαίνει", "świeci (praesens)",
"""Nagła zmiana czasu: φαίνει (świeci) — praesens (czas teraźniejszy). Pośród opowieści o odwiecznej przeszłości Jan mówi: światłość świeci *teraz*, w chwili gdy czytasz. Prolog nie jest kroniką, jest liturgią. Σκοτία (ciemność) — u Jana zawsze nacechowana moralnie: sfera odrzucenia Boga, nie zwykły brak światła."""),
 ("οὐ κατέλαβεν", "nie ogarnęła",
"""Czasownik καταλαμβάνω (chwytać, pojmować, ogarniać, dopadać) jest celowo wieloznaczny: (1) „nie pojęła" — intelektualnie; (2) „nie pochwyciła/nie zwyciężyła" — w sensie zmagania (tak w J 12,35: μὴ σκοτία ὑμᾶς καταλάβῃ — aby ciemność was nie ogarnęła); (3) „nie przyjęła". Aoryst wskazuje na konkretne wydarzenie — z perspektywy całej Ewangelii: na Krzyż, gdzie ciemność uczyniła wszystko, co mogła, i przegrała. Wulgata oddała to jako *tenebrae eam non comprehenderunt* (ciemności jej nie ogarnęły), zachowując dwuznaczność. Najlepszy przekład powinien ją zachować: ciemność światłości ani nie pojęła, ani nie pokonała."""),
 ]},
{
 "label": "w. 6–8", "cs": 1, "vs": 6, "ce": 1, "ve": 8,
 "greek": VERSES[6][0] + " " + VERSES[7][0] + " " + VERSES[8][0],
 "transl": ("Pojawił się człowiek posłany od Boga — imię jego Jan. Przyszedł on na świadectwo, "
            "aby zaświadczyć o światłości, aby wszyscy przez niego uwierzyli. Nie był on "
            "światłością, ale [przyszedł], aby zaświadczyć o światłości."),
 "units": [
 (None, None,
"""O Janie Chrzcicielu: ἐγένετο ἄνθρωπος (pojawił się / stał się człowiek) — ten sam aoryst, którym opisano stworzenie. Chrzciciel należy do porządku rzeczy, które się stały; Słowo — do porządku tego, co jest. Gramatyka sama ustawia hierarchię. Ἀπεσταλμένος (posłany) — participium perfecti od ἀποστέλλω (posyłać; stąd ἀπόστολος — apostoł, posłany): Jan ma mandat Boży, ale mandat świadka. Rzeczownik μαρτυρία (świadectwo) i czasownik μαρτυρέω (świadczyć) pojawiają się tu trzykrotnie — to jedno z wielkich słów-kluczy czwartej Ewangelii (użyte w niej łącznie kilkadziesiąt razy), zaczerpnięte z języka procesowego: cała Ewangelia Jana jest skonstruowana jak wielki proces sądowy o tożsamość Jezusa. Emfatyczne οὐκ ἦν ἐκεῖνος τὸ φῶς (nie był on ową światłością) sugeruje polemikę z kręgami, które za wysoko ceniły Chrzciciela (por. Dz 19,1–7: uczniowie w Efezie znający tylko chrzest Janowy — a tradycja wiąże czwartą Ewangelię właśnie z Efezem)."""),
 ]},
{
 "label": "w. 9", "cs": 1, "vs": 9, "ce": 1, "ve": 9,
 "greek": VERSES[9][0], "transl": VERSES[9][1],
 "units": [
 ("ἀληθινός", "prawdziwy: autentyczny, nie-kopiowany",
"""Ἀληθινός (prawdziwy w sensie: autentyczny, oryginalny, nie-kopiowany) — greka rozróżnia ἀληθής (prawdomówny, zgodny z prawdą) i ἀληθινός (prawdziwy jako archetyp wobec cieni i odbić). Światłość Słowa jest tym, czego wszystkie inne „światła" — Tora, prorocy, filozofia, sam Chrzciciel — są tylko odblaskiem. Konstrukcja ἐρχόμενον εἰς τὸν κόσμον (przychodząc na świat) może gramatycznie określać „każdego człowieka" (rabiniczny idiom o rodzeniu się: „wszyscy przychodzący na świat") albo światłość — NA28 i większość egzegetów łączy ją ze światłością: peryfrastyczne ἦν ... ἐρχόμενον (była przychodząca) opisuje wcielenie jako proces, który w. 14 nazwie po imieniu. Φωτίζει πάντα ἄνθρωπον (oświeca każdego człowieka) — fundament nauki o powszechnym oświeceniu: żaden człowiek nie jest całkiem pozbawiony światła Logosu; każde poznanie prawdy, także u pogan, jest uczestnictwem w Nim."""),
 ]},
{
 "label": "w. 10", "cs": 1, "vs": 10, "ce": 1, "ve": 10,
 "greek": VERSES[10][0], "transl": VERSES[10][1],
 "units": [
 ("κόσμος", "świat (trzykrotnie, w trzech znaczeniach)",
"""Trzykrotne κόσμος (świat) w trzech znaczeniach, które Jan rozwinie w całej Ewangelii: świat jako miejsce (ἐν τῷ κόσμῳ — na świecie), świat jako stworzenie (δι᾿ αὐτοῦ ἐγένετο — przez Nie się stał), świat jako ludzkość odwrócona od Boga (αὐτὸν οὐκ ἔγνω — Go nie poznała). Οὐκ ἔγνω (nie poznał) — aoryst od γινώσκω (poznawać), które w grece biblijnej, pod wpływem hebrajskiego יָדַע (jada — poznać, także: wejść w zażyłość), oznacza poznanie relacyjne, osobowe, nie akademickie. Tragedia w trzech słowach: dzieło nie rozpoznało Twórcy."""),
 ]},
{
 "label": "w. 11", "cs": 1, "vs": 11, "ce": 1, "ve": 11,
 "greek": VERSES[11][0], "transl": VERSES[11][1],
 "units": [
 ("τὰ ἴδια / οἱ ἴδιοι", "swoja własność / swoi",
"""Gra rodzajów gramatycznych: τὰ ἴδια (neutrum: to, co własne — swoja własność, swój dom; tego samego zwrotu użyje J 19,27 o Janie biorącym Maryję εἰς τὰ ἴδια — do siebie) i οἱ ἴδιοι (masculinum: swoi — właśni ludzie). Słowo przyszło do swojego domu — Izraela, ziemi obiecanej, świątyni — a domownicy Go nie przyjęli. Παρέλαβον (przyjęli) od παραλαμβάνω (przyjmować do siebie, brać ze sobą) — mocniejsze niż samo λαμβάνω (brać): przyjąć jak gościa, jak swojego. Werset streszcza w jednym zdaniu całą historię odrzucenia opisaną w rozdziałach 1–12 czwartej Ewangelii."""),
 ]},
{
 "label": "w. 12–13", "cs": 1, "vs": 12, "ce": 1, "ve": 13,
 "greek": VERSES[12][0] + " " + VERSES[13][0],
 "transl": ("Tym zaś wszystkim, którzy Je przyjęli, dało moc, aby się stali dziećmi Bożymi — "
            "tym, którzy wierzą w imię Jego, którzy nie z krwi ani z woli ciała, ani z woli "
            "męża, ale z Boga zostali zrodzeni."),
 "units": [
 ("ἐξουσία", "moc, władza, uprawnienie",
"""Ἐξουσία (moc, władza, uprawnienie) — nie δύναμις (siła, moc fizyczna): stać się dzieckiem Bożym to nie kwestia energii, lecz nadanego prawa, statusu. Τέκνα θεοῦ (dzieci Boże) — Jan konsekwentnie rezerwuje υἱός (syn) dla Jezusa; wierzący są τέκνα (dzieci) — od τίκτω (rodzić): dziecięctwo przez zrodzenie, nie przez adopcyjny dekret (to subtelnie inna perspektywa niż Pawłowa υἱοθεσία — usynowienie, adopcja, Rz 8,15). Γενέσθαι (stać się) — ten sam czasownik stawania się: oto jedyne miejsce, gdzie ἐγένετο (stało się) jest dobrą nowiną o człowieku, bo jest to stawanie się z Boga."""),
 ("πιστεύουσιν εἰς", 'wierzącym w, dosł. „wierzącym ku"',
"""Πιστεύουσιν εἰς (wierzącym w, dosł. „wierzącym *ku*") — konstrukcja πιστεύω εἰς z biernikiem, praktycznie nieobecna w grece pozabiblijnej, to Janowy znak firmowy: wiara nie jako uznanie twierdzeń (temu służy πιστεύω z celownikiem — wierzyć komuś), lecz jako ruch całej osoby ku Osobie. Participium praesentis (imiesłów czasu teraźniejszego): wierzenie trwałe, nie jednorazowy akt. Εἰς τὸ ὄνομα αὐτοῦ (w imię Jego) — hebraizm: imię to sama osoba (por. שֵׁם, szem — imię, obecność)."""),
 (None, None,
"""Potrójna negacja w w. 13: οὐκ ἐξ αἱμάτων (nie z krwi — liczba mnoga! dosł. „ze krwi", wedle starożytnej fizjologii poczęcie łączy krew obojga rodziców, a być może aluzja też do krwi ofiar i genealogii), οὐδὲ ἐκ θελήματος σαρκός (ani z woli ciała — σάρξ, ciało, tu: natura ludzka z jej popędem), οὐδὲ ἐκ θελήματος ἀνδρός (ani z woli męża — ἀνήρ, mężczyzna, mąż: inicjatywa ojcowska, decyzja o potomstwie). Nowe narodzenie nie ma nic z mechanizmów naturalnego rodzenia — wyprzedza to nocną rozmowę z Nikodemem o narodzeniu ἄνωθεν (z góry / na nowo, J 3,3, kolejna celowa dwuznaczność Janowa). Wariant tekstualny: garść świadków łacińskich i cytaty niektórych ojców (m.in. u Ireneusza i Tertuliana) czytają liczbę pojedynczą ὃς ... ἐγεννήθη (który ... został zrodzony) — odnosząc werset do dziewiczego poczęcia Chrystusa. NA28 słusznie utrzymuje liczbę mnogą (całość tradycji greckiej), ale stara lekcja świadczy, że już w II wieku widziano tu analogię: narodzenie wierzących z Boga jest odwzorowaniem narodzenia Słowa — z Ojca w wieczności, z Dziewicy w czasie."""),
 ]},
{
 "label": "w. 14", "cs": 1, "vs": 14, "ce": 1, "ve": 14,
 "greek": VERSES[14][0], "transl": VERSES[14][1],
 "units": [
 ("ὁ λόγος σὰρξ ἐγένετο", "Słowo ciałem się stało",
"""Szczyt Prologu. Ὁ λόγος σὰρξ ἐγένετο (Słowo ciałem się stało) — dwa porządki, dotąd starannie rozdzielane (ἦν — było / ἐγένετο — stało się), zderzają się czołowo: Ten, który *jest*, wszedł w to, co *się staje*. I nie mówi Jan, że Słowo stało się ἄνθρωπος (człowiekiem) — co byłoby prawdą łagodniejszą — ani że przyjęło σῶμα (ciało jako organizm), lecz σάρξ (ciało-mięso, ciało w jego słabości, śmiertelności, kruchości; hebr. בָּשָׂר, basar). To słowo najostrzejsze z możliwych, dobrane jakby na złość każdemu doketyzmowi (doketyzm: pogląd, że Chrystus miał ciało tylko pozorne, od δοκεῖν — wydawać się): Bóg nie ubrał się w człowieczeństwo jak w kostium — stał się tym, co w człowieku najbardziej narażone."""),
 ("ἐσκήνωσεν", "rozbił namiot, zamieszkał w namiocie",
"""Ἐσκήνωσεν (rozbił namiot, zamieszkał w namiocie) — od σκηνή (namiot, przybytek). Czasownik-klejnot. Septuaginta słowem σκηνή oddaje hebrajski מִשְׁכָּן (miszkan — przybytek, namiot spotkania), a spółgłoski σ-κ-ν brzmią jak hebrajski rdzeń שׁכן (szakan — mieszkać, przebywać), od którego późniejszy judaizm utworzył słowo שְׁכִינָה (Szechina — zamieszkiwanie, obecność Boża). Jan mówi więc: ciało Jezusa jest nowym Namiotem Spotkania, nową Świątynią (co powie wprost w J 2,21: mówił o świątyni swego ciała), miejscem Szechiny. Ἐν ἡμῖν (wśród nas / w nas) — pośród wspólnoty, jak niegdyś przybytek pośrodku obozu Izraela (Wj 25,8: uczynią Mi święty przybytek i zamieszkam pośród nich)."""),
 ("ἐθεασάμεθα", "oglądaliśmy",
"""Ἐθεασάμεθα (oglądaliśmy) — od θεάομαι (przyglądać się, kontemplować, oglądać jako widz w teatrze; stąd θέατρον — teatr): nie przelotne dostrzeżenie, lecz uważna, świadoma kontemplacja naocznych świadków. Pierwsza osoba liczby mnogiej: „my" — wspólnota apostolska; por. 1 J 1,1: co ujrzeliśmy własnymi oczami, na co patrzyliśmy i czego dotykały nasze ręce."""),
 ("δόξα", "chwała",
"""Δόξα (chwała) — w grece klasycznej: mniemanie, opinia, sława; w Septuagincie słowo to przejęło ciężar hebrajskiego כָּבוֹד (kawod — chwała, dosł. ciężar, waga): widzialna manifestacja obecności Boga, obłok wypełniający przybytek (Wj 40,34: chwała Pana wypełniła przybytek). Jan zestawia: gdzie namiot (ἐσκήνωσεν — rozbił namiot), tam chwała (δόξα) — dokładnie jak w Wj 40. Tyle że chwałą nowego Przybytku nie jest obłok, lecz — jak pokaże cała Ewangelia — miłość aż po Krzyż, który Jan konsekwentnie nazywa „uwielbieniem" (δοξασθῆναι — być uwielbionym, J 12,23)."""),
 ("μονογενής", "jednorodzony, jedyny w swoim rodzaju",
"""Μονογενής (jednorodzony, jedyny w swoim rodzaju) — od μόνος (jedyny) i γένος (ród, rodzaj): jedyny tego rodzaju, jedyny zrodzony. Septuaginta używa tego słowa m.in. o Izaaku w tle Rdz 22 (por. Hbr 11,17: jednorodzonego składał w ofierze) — jedyny, umiłowany syn, przeznaczony na ofiarę. Παρὰ πατρός (od Ojca) — παρά z dopełniaczem: pochodzenie, „od strony" Ojca."""),
 ("πλήρης χάριτος καὶ ἀληθείας", "pełne łaski i prawdy",
"""Πλήρης χάριτος καὶ ἀληθείας (pełne łaski i prawdy) — formuła ta jest niemal na pewno kalką hebrajskiego רַב־חֶסֶד וֶאֱמֶת (raw chesed we'emet — bogaty w łaskę i wierność) z Wj 34,6, z teofanii synajskiej, gdy Bóg objawia Mojżeszowi swoje imię. Χάρις (łaska, dar darmowy, życzliwość) oddaje חֶסֶד (chesed — miłość wierna przymierzu, miłosierdzie), a ἀλήθεια (prawda) oddaje אֱמֶת (emet — prawda jako niezawodność, wierność). Wniosek egzegetyczny doniosły: w. 14 opisuje Wcielenie językiem teofanii synajskiej — to, co Mojżesz słyszał zza skały, widząc jedynie „tył" chwały (Wj 33,23), wspólnota Janowa *oglądała* w ciele. Stąd w. 17–18 (już poza naszą perykopą) dopowiedzą: Prawo przez Mojżesza, łaska i prawda przez Jezusa Chrystusa; Boga nikt nigdy nie widział — Jednorodzony Bóg objawił."""),
 ]},
]

# Podsekcja sekcji I (po blokach): „Struktura całości"
STRUKTURA = """Prolog ma budowę chiastyczną (koncentryczną, zwierciadlaną): (A) Słowo u Boga, w. 1–2 — (B) stworzenie przez Słowo, w. 3 — (C) życie i światłość, w. 4–5 — (D) świadectwo Jana, w. 6–8 — (E) przyjście światłości i odrzucenie, w. 9–11 — (X, centrum) *dar stania się dziećmi Bożymi*, w. 12–13 — i dalej lustrzane odbicie: Wcielenie i chwała (w. 14), ponowne świadectwo Jana (w. 15), pełnia daru (w. 16), objawienie Ojca (w. 17–18). Środkiem ciężkości Prologu — wbrew intuicji — nie jest w. 14, lecz w. 12: cały ruch Słowa ku światu ma jeden cel — nasze narodzenie z Boga. Zstąpienie jest dla wstąpienia; *admirabile commercium* (przedziwna wymiana): Bóg stał się tym, czym my, abyśmy my stali się tym, czym On jest — dziećmi w Synu.

Wielu badaczy widzi w Prologu wcześniejszy hymn chrześcijański (rytmiczne wersy 1–5.9–14, tzw. paralelizm klimaktyczny: ostatnie słowo wersu staje się pierwszym następnego — λόγος...λόγος, θεόν...θεός, ζωή...ζωή), w który ewangelista wplótł prozatorskie wstawki o Chrzcicielu (w. 6–8.15). Jeśli tak, Prolog byłby jednym z najstarszych zachowanych hymnów Kościoła — śpiewanym wyznaniem wiary w boskość i wcielenie Słowa jeszcze z I wieku, obok Flp 2,6–11 i Kol 1,15–20."""

# ------------------------------------------------------------------
# 5. SEKCJE II-VII + Zakończenie + Nota (drzewo: parent -> children)
# ------------------------------------------------------------------
SECTIONS = [
{
 "type": "kontekst",
 "title": "II. Kontekst historyczny, językowy, kulturowy i religijny",
 "body": None,
 "children": [
 ("Świat Prologu: judaizm Drugiej Świątyni",
"""Czwarta Ewangelia powstała najpewniej w ostatniej dekadzie I wieku (tradycja: Efez, środowisko Jana; najstarszy zachowany fragment NT w ogóle, papirus P52 z J 18, datowany na ok. 125 r., potwierdza wczesne rozpowszechnienie tekstu aż po Egipt). Jej autor myśli po hebrajsku i aramejsku, a pisze po grecku — i Prolog jest tego najlepszym dowodem: każde niemal pojęcie ma podwójne dno, greckie i semickie.

Najważniejszym tłem pojęcia λόγος (Słowo) nie jest — wbrew dawnym podręcznikom — filozofia grecka, lecz sama Biblia i judaizm epoki:

**Słowo stwórcze.** Rdz 1: dziesięciokrotne „i rzekł Bóg" (וַיֹּאמֶר אֱלֹהִים, wajjomer Elohim); Ps 33,6: przez słowo Pana (בִּדְבַר יְהוָה, bidwar Adonaj; LXX: τῷ λόγῳ τοῦ κυρίου — słowem Pana) powstały niebiosa. Hebrajskie דָּבָר (dawar) znaczy zarazem „słowo" i „rzecz", „sprawa", „wydarzenie" — słowo Boże nie jest dźwiękiem, jest czynem: Iz 55,10–11 mówi o słowie, które wychodzi z ust Boga i nie wraca bezowocne, lecz *dokonuje* tego, po co zostało posłane. Słowo, które wychodzi od Boga, działa w świecie i wraca do Boga — to już niemal fabuła czwartej Ewangelii (por. J 16,28: wyszedłem od Ojca i przyszedłem na świat; znowu opuszczam świat i idę do Ojca).

**Memra.** W targumach (aramejskich parafrazach Biblii czytanych w synagodze — a więc w tekstach, które słyszał każdy Żyd I wieku) tam, gdzie tekst hebrajski mówi o bezpośrednim działaniu Boga, tłumacz z rewerencji wstawia מֵימְרָא דַּיהוה (Memra da-Adonaj — Słowo Pana): to Memra stwarza, Memra objawia się Abrahamowi, Memra zawiera przymierze, Memra zbawia. Słuchacz synagogi był więc oswojony z mową o „Słowie Pana" jako o Bożej obecności działającej w świecie. Jan czyni krok, którego targum nigdy nie zrobił: to Słowo jest Osobą i stało się ciałem.

**Mądrość uosobiona.** Trzeci nurt, najbliższy literacko: Prz 8,22–31 — Mądrość (חָכְמָה, Chochma; gr. Σοφία, Sofia) zrodzona przed wiekami, obecna przy stwarzaniu jako mistrzyni-budowniczyni, rozkoszująca się synami ludzkimi; Syr 24 — Mądrość szuka miejsca odpoczynku wśród narodów i na rozkaz Stwórcy *rozbija namiot w Jakubie* (Syr 24,8: ἐν Ιακωβ κατασκήνωσον — w Jakubie rozbij namiot; ten sam rdzeń, co Janowe ἐσκήνωσεν — rozbił namiot!); Mdr 7,25–26 — Mądrość jest tchnieniem mocy Bożej, odblaskiem światłości wiecznej, obrazem dobroci Boga. Prolog Janowy jest świadomie zbudowany na szkielecie tych tekstów — z jedną korektą: zamiast żeńskiej Sofii (Mądrości) — Logos (Słowo), być może dlatego, że Mądrość w Syr 24,23 została już utożsamiona z Torą, a Jan chce powiedzieć: nie księga, lecz Osoba; nie Prawo, lecz λόγος, który jest πλήρης χάριτος καὶ ἀληθείας (pełen łaski i prawdy).

**Filon z Aleksandrii** (zm. ok. 50 r.) — żydowski filozof piszący po grecku, używa słowa λόγος (Słowo, Rozum) setki razy: Logos jest u niego obrazem Boga, narzędziem stwarzania, arcykapłanem kosmosu, „drugim Bogiem" (δεύτερος θεός) — ale zawsze pozostaje bytem pośrednim, metaforą lub mocą, nigdy osobą równą Bogu i nigdy, przenigdy wcieloną. Dla Filona zdanie ὁ λόγος σὰρξ ἐγένετο (Słowo ciałem się stało) byłoby bluźnierstwem i absurdem. Jan być może zna aleksandryjską terminologię (Efez i Aleksandria to naczynia połączone; por. Apollos z Dz 18,24) — ale jego treść jest z innego świata."""),
 ("Tło greckie",
"""Dla czytelnika helleńskiego λόγος (rozum, zasada) niósł echa Heraklita (wszystko dzieje się według Logosu — rozumnej zasady świata) i przede wszystkim stoików, dla których λόγος był immanentnym rozumem przenikającym kosmos, a λόγος σπερματικός (logos spermatikos — rozum zarodkowy, rozumne nasienie) — racją rozwoju każdej rzeczy i iskrą rozumu w każdym człowieku. Jan tego języka nie cytuje, ale jego uniwersalizm (φωτίζει πάντα ἄνθρωπον — oświeca każdego człowieka, w. 9) pozwolił później Justynowi Męczennikowi (II w.) rozwinąć naukę o λόγος σπερματικός: wszystko, co filozofowie powiedzieli prawdziwego, powiedzieli dzięki uczestnictwu w Logosie, który w pełni objawił się w Chrystusie. Prolog stał się w ten sposób mostem między Jerozolimą a Atenami — pierwszym tekstem, w którym wiara Izraela przemówiła słowem zrozumiałym dla filozofii, nie tracąc nic ze swej treści."""),
 ("Tło polemiczne",
"""Prolog ma też ostrza polemiczne: przeciw przecenianiu Jana Chrzciciela (w. 6–8.15 — patrz wyżej); przeciw rodzącemu się doketyzmowi i proto-gnozie (σάρξ — ciało, w. 14; por. 1 J 4,2–3: każdy duch, który uznaje, że Jezus Chrystus przyszedł w ciele, jest z Boga); przeciw dualizmowi (w. 3: nic nie powstało bez Słowa — nie ma złego stwórcy materii); wreszcie — po wykluczeniu chrześcijan z synagogi (por. J 9,22: ἀποσυνάγωγος — wyłączony z synagogi; sytuacja po tzw. birkat ha-minim, בִּרְכַּת הַמִּינִים — „błogosławieństwie" przeciw heretykom, włączonym do modlitwy synagogalnej pod koniec I w.) — Prolog odpowiada na bolesne pytanie wspólnoty: jeśli Jezus jest Mesjaszem, czemu Izrael Go odrzucił? Odpowiedź w. 11: to nie nowość — Słowo od zawsze przychodziło do swoich, i swoi Go nie przyjmowali; ale każdemu, kto przyjmuje, daje moc stania się dzieckiem Bożym."""),
 ("Kontekst moralny i filozoficzny epoki",
"""Świat, do którego wchodzi Prolog, jest światem głębokiego kryzysu sensu. Filozofia popularna I wieku (stoicyzm Seneki i Epikteta, średni platonizm, epikureizm) jest przede wszystkim terapią duszy: uczy, jak nie cierpieć, jak być niezależnym od losu (ἀπάθεια — beznamiętność; ἀταραξία — niewzruszoność). Bóg filozofów jest albo rozproszony w kosmosie (stoicy), albo tak transcendentny, że światem nie może się splamić (platonizm — stąd cała drabina bytów pośrednich: dajmony, moce, u Filona Logos). Wspólnym aksjomatem elit była zasada, że bóstwo nie miesza się z materią, a ciało jest — jak mówiło orfickie porzekadło σῶμα σῆμα (soma sema — ciało grobem) — więzieniem duszy. Moralnie epoka łączyła wysokie ideały elit (Seneka pisze o miłosierdziu) z powszechną praktyką niewolnictwa, porzucania niemowląt i pogardy dla słabych; ciało ludzkie — zwłaszcza ciało niewolnika, kobiety, dziecka — było rzeczą.

Na tym tle w. 14 jest rewolucją antropologiczną: jeżeli Bóg stał się σάρξ (ciałem-mięsem), to ciało nie jest grobem ani rzeczą — jest zdolne nosić chwałę Bożą. Żadna filozofia starożytna nie mogła tego zdania wypowiedzieć; Celsus (II w.) i Porfiriusz (III w.) atakowali chrześcijaństwo dokładnie w tym punkcie jako skandal metafizyczny. A jednak to właśnie ten „skandal" odpowiadał na pytania, których filozofia nie umiała domknąć: skąd zło (nie z materii — w. 3); czy prawda jest osiągalna dla wszystkich (tak — w. 9, światłość oświeca *każdego* człowieka, nie tylko mędrców); czy człowiek może przekroczyć swą kondycję (tak, ale nie własną ascezą, lecz darem — w. 12, ἐξουσία, moc-uprawnienie *dana*). Prolog przenosi też środek ciężkości etyki: z samodoskonalenia na przyjęcie (λαμβάνειν — przyjmować) i wiarę (πιστεύειν — wierzyć), z autarkii (samowystarczalności) na dziecięctwo."""),
 ]},
{
 "type": "teologia",
 "title": "III. Obserwacje teologiczne i filozoficzne w duchu tomistycznym",
 "body": """Św. Tomasz z Akwinu zostawił obszerny wykład czwartej Ewangelii — *Super Evangelium S. Ioannis lectura* (Wykład Ewangelii św. Jana), owoc wykładów paryskich; sam Prolog komentuje także w *Summa Theologiae* (Suma teologii) i *Summa contra Gentiles* (Suma przeciw poganom). Poniższe obserwacje idą jego tropem.""",
 "children": [
 ("1. Verbum mentis — Słowo jako pojęcie umysłu",
"""Dlaczego Syn nazwany jest Słowem? Tomasz odpowiada analogią psychologiczną (odziedziczoną po Augustynie, doprecyzowaną metafizycznie): gdy umysł poznaje, rodzi w sobie *verbum cordis / verbum mentis* (słowo serca / słowo umysłu) — wewnętrzne pojęcie, które pozostaje w umyśle, jest z nim współnaturalne, a zarazem od aktu poznającego realnie pochodzi. Otóż Bóg, poznając siebie jednym wiecznym aktem, wypowiada jedno Słowo, w którym wyraża całą swoją istotę — a ponieważ w Bogu nie ma przypadłości, to Słowo nie jest „czymś w Bogu", lecz jest współistotne: *Deus de Deo* (Bóg z Boga). Tak analogia wyjaśnia wszystkie trzy zdania w. 1: Słowo jest odwieczne jak akt samopoznania Boga (ἐν ἀρχῇ ἦν — na początku było); jest zwrócone ku Wypowiadającemu (πρὸς τὸν θεόν — u Boga, ku Bogu); jest tym, czym On (θεὸς ἦν — Bogiem było). Pochodzenie bez początku, zrodzenie bez podziału: jak słowo umysłu nie uszczupla umysłu, tak zrodzenie Syna nie dzieli istoty Bożej — *lumen de lumine* (światłość ze światłości)."""),
 ("2. Ipsum esse subsistens a porządek stawania się",
"""Kontrast ἦν / ἐγένετο (było / stało się) jest u Jana dokładnie tym, co metafizyka Tomasza nazywa różnicą między *ipsum esse subsistens* (samoistne istnienie samo w sobie — Bóg, którego istotą jest istnieć) a bytami, w których *essentia* (istota) i *esse* (istnienie) są realnie różne, które więc istnienie *otrzymują*. Wszystko, co się „stało" (ἐγένετο), jest bytem przez uczestnictwo (*per participationem*); Słowo, które „było" (ἦν), jest bytem przez istotę (*per essentiam*). Stąd w. 3 czytany po tomistycznie: stworzenie nie jest przelaniem substancji Boga ani formowaniem odwiecznej materii, lecz *creatio ex nihilo* (stworzeniem z niczego) — całkowitym udzieleniem istnienia; a ponieważ Bóg stwarza przez swoje Słowo-Pojęcie, każda rzecz niesie w sobie ślad rozumności: świat jest inteligibilny (poznawalny rozumem), bo jest *pomyślany*. Tu tkwi metafizyczny fundament wszelkiej nauki: badając świat, sylabizujemy Słowo."""),
 ("3. Rationes aeternae — w Nim było życie",
"""Starsza interpunkcja w. 3b–4a (to, co się stało, w Nim było życiem) jest dla Tomasza okazją do wykładu o ideach Bożych: rzeczy istnieją w Bogu wcześniej i szlachetniej niż w sobie — a w Bogu nie są martwymi wzorcami, lecz samym Jego życiem, bo poznanie Boga jest Jego życiem, a Jego życie Jego istotą. Stworzenie w sobie jest zmienne i śmiertelne; stworzenie w Słowie jest życiem. Dlatego zbawienie u Jana nazywa się „życiem wiecznym" — jest powrotem rzeczy do ich prawdy w Słowie."""),
 ("4. Światłość ludzi — iluminacja po tomistycznie",
"""W. 4–5.9: Tomasz odczytuje „światłość, która oświeca każdego człowieka" nie jako szczególne natchnienie mistyczne, lecz jako samo *lumen intellectus agentis* (światło intelektu czynnego) — naturalną zdolność umysłu do ujmowania prawdy, która jest w każdym człowieku uczestnictwem w Światłości niestworzonej (*participatio luminis increati* — uczestnictwo w świetle niestworzonym). Każdy akt poznania prawdy — u poganina, u ateisty — dokonuje się mocą tego uczestnictwa. To rozwiązuje spór o „prawdy pogan" bez dwuznaczności: prawda jest jedna, bo Światłość jest jedna; a zarazem w. 5 uczy realizmu: naturalne światło nie wystarcza, by „ogarnąć" (καταλαμβάνειν) Boga — potrzeba, by Światłość sama przyszła. Rozum i wiara nie konkurują: mają to samo Źródło."""),
 ("5. Wcielenie — conveniens (stosowne), nie konieczne",
"""W. 14 w optyce tomistycznej: Bóg nie musiał się wcielić; Wcielenie jest najwyższą *convenientia* (stosownością, wewnętrzną harmonią) — bo naturą Dobra jest się udzielać (*bonum est diffusivum sui* — dobro jest rozlewne, udziela się), a najwyższe Dobro udzieliło się w sposób najwyższy: jednocząc stworzoną naturę z Osobą Słowa. Unia hipostatyczna (zjednoczenie osobowe): Słowo stało się ciałem nie przez zamianę (boskość nie przestała być boskością), nie przez zmieszanie, lecz przez przyjęcie — *assumpsit quod non erat, mansit quod erat* (przyjęło, czym nie było; pozostało, czym było — formuła patrystyczna, którą Tomasz chętnie powtarza). Dlaczego wcielił się Syn, a nie Ojciec lub Duch? Odpowiedź Tomasza jest przepiękna i czysto Janowa: bo rzeczy zostały stworzone przez Słowo — wypada, aby były naprawione przez to samo Słowo, jak dzieło naprawia się wedle tego samego projektu, wedle którego powstało; i bo Słowo jest naturalnym Synem — wypada, aby przez Nie ludzie stawali się synami przybranymi (w. 12!)."""),
 ("6. Łaska i przebóstwienie",
"""W. 12–13 po tomistycznie: „moc stania się dziećmi Bożymi" to łaska uświęcająca (*gratia gratum faciens* — łaska czyniąca miłym Bogu) — nie zewnętrzny dekret, lecz realna, stworzona partycypacja w naturze Bożej (por. 2 P 1,4: uczestnicy Boskiej natury), zaszczepiona w istocie duszy, z której wyrastają wiara, nadzieja i miłość. Narodzenie „z Boga" jest więc nowym aktem stwórczym w duszy — dlatego Jan wyklucza wszystkie przyczyny naturalne (w. 13). A racją formalną całego daru jest formuła, którą Tomasz mógłby podpisać cały Prolog: *gratia est participatio divinae naturae* (łaska jest uczestnictwem w naturze Bożej) — czyli dokładnie owa przedziwna wymiana: Słowo przyjęło naszą naturę, abyśmy my uczestniczyli w Jego."""),
 ("7. Filozoficzny bilans",
"""Prolog rozstrzyga — na poziomie zasad — główne pytania metafizyki: (a) u początku rzeczywistości nie stoi chaos, materia ani ślepa siła, lecz Rozum-Słowo: byt jest starszy niż stawanie się, sens starszy niż absurd; (b) rzeczywistość jest poznawalna, bo pomyślana; (c) zło nie jest zasadą (nic nie istnieje poza przyczynowością Słowa), lecz brakiem — ciemność nie ma własnej substancji, jest tylko nie-przyjęciem światła; (d) osoba jest szczytem bytu — skoro absolutny Początek jest relacją Osób (πρὸς τὸν θεόν — ku Bogu), to nie samotna substancja, lecz komunia jest ostateczną prawdą rzeczywistości; (e) historia ma środek: nie wieczny powrót (Grecy), lecz jednorazowe, nieodwołalne ἐγένετο (stało się) Wcielenia."""),
 ]},
{
 "type": "autor_ludzki",
 "title": "IV. Autor ludzki: kim jest i co chce przekazać",
 "body": """Tradycja kościelna od Ireneusza (ok. 180 r., uczeń Polikarpa, ucznia Jana) wskazuje Jana, ucznia Pańskiego, piszącego w Efezie; sam tekst mówi o „uczniu, którego Jezus miłował" jako świadku i autorze (J 21,24: ten właśnie uczeń daje świadectwo o tych sprawach i on je opisał, a wiemy, że świadectwo jego jest prawdziwe — zauważmy „wiemy": wspólnota potwierdza świadka). Niezależnie od dyskusji o etapach redakcji, tekst sam deklaruje swoją intencję z rzadką u starożytnych autorów jasnością — J 20,31: to zaś napisano, abyście wierzyli (πιστεύητε), że Jezus jest Mesjaszem, Synem Bożym, i abyście wierząc, mieli życie w imię Jego. Ewangelia nie jest biografią ani kroniką — jest świadectwem procesowym pisanym po to, by czytelnik wydał werdykt wiary i przez ten werdykt otrzymał życie. Prolog jest do tego procesu mową otwierającą: ujawnia od pierwszego zdania to, czego bohaterowie narracji będą się domyślać przez dwadzieścia rozdziałów. Czytelnik wie, kim jest Jezus, zanim Jezus wypowie pierwsze słowo — i dzięki temu każdą scenę Ewangelii czyta podwójnie: widzi człowieka zmęczonego przy studni i wie, że to Ten, przez którego wszystko się stało.

Intencje autora ludzkiego, które da się z tekstu wyczytać: (1) osadzić Jezusa nie w genealogii Dawidowej (jak Mateusz) ani w historii Cesarstwa (jak Łukasz), lecz w wieczności — odpowiedzieć na pytanie „skąd jest" Jezus (pytanie, które w Ewangelii wraca obsesyjnie: J 7,27n; 8,14; 19,9 — Piłat: skąd Ty jesteś?); (2) dać wspólnocie wyrzuconej z synagogi nową tożsamość: to my, nie budynek i nie rodowód, jesteśmy miejscem Szechiny (obecności), bo nosimy w sobie narodzenie z Boga; (3) zabezpieczyć wiarę przed dwiema przepaściami — przed uznaniem Jezusa za samego tylko człowieka (stąd w. 1) i za pozornego człowieka (stąd w. 14); (4) powiedzieć poganom: Logos (Rozum), którego szukacie, ma imię i twarz. Jest wreszcie w Prologu rys osobisty, niemal liryczny: ἐθεασάμεθα (oglądaliśmy) — starzec piszący te słowa twierdzi, że patrzył na to własnymi oczami. Cały Prolog jest wspomnieniem przetopionym w hymn: tak pisze ktoś, kto przez kilkadziesiąt lat rozważał to, co widział, aż zobaczył w tym, co widział, To, czego nie widać.""",
 "children": []},
{
 "type": "autor_bozy",
 "title": "V. Autor Boży: co Duch Święty chce przekazać",
 "body": """Katolicka nauka o natchnieniu (zob. konstytucja *Dei Verbum* — O Objawieniu Bożym, nr 11–13) uczy, że Bóg jest prawdziwym Autorem Pisma, działającym *w* ludzkim autorze i *przez* niego, nie obok niego — tak, że wszystko, co twierdzi autor ludzki, twierdzi Duch Święty, a sens Boży może przewyższać to, co pisarz w pełni ogarniał (*sensus plenior* — sens pełniejszy). Co zatem mówi sam Duch przez tę perykopę?""",
 "children": [
 ("Po pierwsze: objawia wewnętrzne życie Boga",
"""Żaden ludzki namysł nie mógłby ustalić, że w jedynym Bogu jest odwieczne Słowo zwrócone ku Ojcu. W. 1–2 to nie wniosek — to objawienie tajemnicy trynitarnej, dane językiem tak precyzyjnym, że po wiekach sporów Kościół nie musiał tekstu poprawiać, tylko bronić jego naturalnej lektury. Warto zauważyć rzecz przedziwną: Duch Święty w Prologu o samym sobie milczy — jak w całej Ewangelii Janowej Duch „nie mówi od siebie", lecz otacza chwałą Syna (J 16,13–14). Prolog jest napisany tak, jak działa jego Autor: całe światło kieruje na Słowo. A przecież jest w nim obecny ukrycie: narodzenie „z Boga" (w. 13) to narodzenie z wody i Ducha (J 3,5); namaszczenie chwałą, którą „oglądaliśmy", Duch właśnie daje oczom wiary."""),
 ("Po drugie: ustanawia klucz do całego Pisma",
"""Jeżeli Słowo jest jedno i odwieczne, to wszystkie słowa Boże — od Rdz po proroków — są jednym mówieniem jednego Słowa. Duch Święty umieszcza Prolog na czele Ewangelii jak klucz wiolinowy na początku pięciolinii: odtąd całe Pismo należy czytać chrystologicznie, i to w obie strony — Stary Testament jako brzemienny Słowem, Nowy jako jego odsłonięcie. Sam Prolog daje tego wzór, przepisując Rdz 1, Wj 33–34, Prz 8 i Syr 24 (zob. cz. VI)."""),
 ("Po trzecie: mówi o czytelniku",
"""Sensem, na którym Duchowi najbardziej zależy — bo umieścił go w samym centrum chiazmu (w. 12) — nie jest informacja o Bogu, lecz transformacja człowieka: *abyście się stali dziećmi Bożymi*. Prolog jest performatywny: nie tylko opisuje przyjęcie Słowa — dokonuje go w tym, kto czyta z wiarą. Duch, który natchnął te zdania, ten sam działa w słuchającym; dlatego Kościół zawsze traktował ten tekst nie jak traktat, lecz jak sakramentalium (zob. cz. VII)."""),
 ("Po czwarte: strzeże realizmu ciała",
"""To Duch Święty — który ukształtował ciało Słowa w łonie Dziewicy (Łk 1,35) — podyktował twarde słowo σάρξ (ciało). Przez wieki, przeciw każdej „uduchowionej" redukcji chrześcijaństwa (gnoza, doketyzm, spirytualizmy wszystkich epok), w. 14 stoi jak zasieka: zbawienie dokonuje się w ciele, łaska przychodzi przez materię (sakramenty!), ciało jest na zawsze — bo Słowo σὰρξ ἐγένετο (ciałem się stało) i ciała już nie porzuciło."""),
 ]},
{
 "type": "odniesienia",
 "title": "VI. Sieć odniesień biblijnych",
 "body": None,
 "children": [
 ("Rdz 1,1–5 → J 1,1–5",
"""Fundament. Te same pierwsze słowa (ἐν ἀρχῇ — na początku), ta sama sekwencja: początek — słowo — życie — światłość — rozdzielenie światłości od ciemności. Jan pisze świadomie „nową Księgę Rodzaju": w Jezusie zaczyna się nowe stworzenie. Symetria działa też korygująco wstecz: teraz wiemy, że owo „i rzekł Bóg" z Rdz nie było figurą retoryczną — Mówiący nigdy nie mówił bez swojego Słowa. Warto dopowiedzieć: pierwszy tydzień Ewangelii Janowej (J 1,19–2,11) jest odliczany dzień po dniu jak tydzień stworzenia, a jego siódmym dniem są gody w Kanie — nowe stworzenie kończy się weselem."""),
 ("Ps 33(32),6; Iz 55,10–11",
"""Słowo jako sprawcza moc stwórcza i posłaniec, który wychodzi od Boga, dokonuje dzieła i wraca — schemat zstąpienia i wstąpienia Słowa, który Prolog zakłada, a J 16,28 wypowiada wprost."""),
 ("Prz 8,22–31; Syr 24; Mdr 7,22–8,1",
"""Mądrość przy stwarzaniu, Mądrość rozbijająca namiot w Izraelu, Mądrość jako odblask wiecznej światłości — literacki szkielet Prologu (omówiony w cz. II). Relacja jest typologiczna: Mądrość ksiąg sapiencjalnych jest cieniem i zapowiedzią; Prolog mówi, kim Ona jest naprawdę. Stąd liturgia bez wahania czyta te teksty o Chrystusie (i, wtórnie, o Tej, która Go nosiła)."""),
 ("Wj 25,8; 33,18–23; 34,6; 40,34–35 → J 1,14",
"""Najgęstszy węzeł. Przybytek, w którym Bóg mieszka pośród ludu (ἐσκήνωσεν — rozbił namiot); prośba Mojżesza „pokaż mi swoją chwałę" i odmowa: „nie może człowiek ujrzeć mojego oblicza"; imię Boże: bogaty w łaskę i wierność (chesed we'emet → χάρις καὶ ἀλήθεια — łaska i prawda); obłok chwały wypełniający przybytek. Prolog ogłasza: to, czego Mojżeszowi odmówiono, nam dano — oglądaliśmy chwałę. Wcielenie jest teofanią większą niż Synaj; dopowie to w. 17, zestawiając Prawo dane przez Mojżesza z łaską i prawdą, które *stały się* (ἐγένετο!) przez Jezusa Chrystusa."""),
 ("Rdz 22 (ofiarowanie Izaaka) → μονογενής (jednorodzony)",
"""Syn jedyny, umiłowany, niosący drzewo na górę — typ Jednorodzonego; Jan dopowie w 3,16: tak Bóg umiłował świat, że Syna Jednorodzonego dał — czasownikiem „dał" (ἔδωκεν) nawiązując do języka ofiarniczego."""),
 ("Paralele nowotestamentalne — hymny chrystologiczne",
"""Flp 2,6–11 (istniejący w postaci Bożej ogołocił samego siebie — ta sama parabola zstąpienia i wywyższenia, akcent na kenozę, czyli ogołocenie); Kol 1,15–20 (obraz Boga niewidzialnego, w Nim wszystko zostało stworzone i w Nim ma istnienie — najbliższa paralela do w. 3–4); Hbr 1,1–4 (wielokrotnie i na różne sposoby przemawiał niegdyś Bóg... na końcu przemówił w Synu, który jest odblaskiem Jego chwały i przez którego stworzył wszechświat — ta sama teologia Słowa ostatecznego). Zbieżność trzech niezależnych tradycji (Pawłowej, aleksandryjsko-judeochrześcijańskiej i Janowej) dowodzi, że wiara w preegzystencję i boskość Chrystusa nie jest późnym rozwinięciem, lecz należy do najstarszej warstwy chrześcijaństwa."""),
 ("1 J 1,1–4",
"""Autokomentarz środowiska Janowego: co było od początku, cośmy usłyszeli, co ujrzeliśmy własnymi oczami, czego dotykały nasze ręce — o Słowie życia. Ten sam słownik (ἀρχή — początek, λόγος — słowo, ζωή — życie, θεάομαι — oglądać), z dodanym dotykiem: przeciw doketom świadectwo zmysłów."""),
 ("Ap 19,13",
"""Jeździec na białym koniu: a imię Jego nazwano — Słowo Boga (ὁ λόγος τοῦ θεοῦ). Tylko pisma Janowe nazywają Chrystusa wprost Logosem (Słowem) — klamra spinająca corpus Joanneum (zbiór pism Janowych) od Prologu po Apokalipsę: Słowo, które było na początku, jest też Słowem końca, Alfą i Omegą dziejów."""),
 ("J 3,3–8; 1 P 1,23; Jk 1,18",
"""Narodzenie z Boga (w. 12–13) rozwinięte: narodzenie z wody i Ducha; zrodzeni nie z nasienia zniszczalnego, ale z niezniszczalnego — przez słowo Boga; zrodził nas słowem prawdy. Nowy Testament jednogłośnie wiąże nowe narodzenie ze Słowem — Prolog podaje tego metafizyczną rację: rodzić z Boga może tylko Ten, kto sam jest z Boga zrodzony."""),
 ]},
{
 "type": "recepcja",
 "title": "VII. Znaczenie w historii i liturgii Kościoła",
 "body": None,
 "children": [
 ("Historia dogmatu",
"""Prolog jest tekstem, na którym Kościół przepracował swoją wiarę w Boga. W II wieku Justyn Męczennik buduje na w. 9 teologię λόγος σπερματικός (rozumu zarodkowego) — pierwszą chrześcijańską teologię kultury i dialogu z filozofią. Ireneusz z Lyonu w sporze z gnozą opiera na w. 3 i 14 zasadę jedności Stwórcy i Zbawiciela oraz realności ciała. W III wieku Orygenes pisze do Prologu najobszerniejszy starożytny komentarz biblijny w ogóle (jego *Komentarz do Jana* poświęca pierwszym wersetom całe księgi). W IV wieku Prolog staje się polem bitwy ariańskiej: Ariusz czyta „zrodzony", dodając „a więc miał początek"; Atanazy i ojcowie Soboru Nicejskiego (325 r.) odpowiadają wprost z w. 1: skoro ἐν ἀρχῇ ἦν (na początku *było*), nie ma „przedtem" bez Słowa — i kują formułę ὁμοούσιος τῷ πατρί (współistotny Ojcu), która jest w istocie dogmatyczną parafrazą trzeciego zdania Prologu (θεὸς ἦν ὁ λόγος — Bogiem było Słowo). Sobór Efeski (431 r.) i Chalcedoński (451 r.) bronią z kolei w. 14: Słowo *samo* stało się ciałem (przeciw rozdzielaniu Chrystusa na dwa podmioty — stąd tytuł Θεοτόκος, Theotokos — Boża Rodzicielka) i stało się ciałem *prawdziwie*, bez zmieszania i bez zmiany natur. Można bez przesady powiedzieć: pierwsze cztery sobory powszechne są przypisami do czternastu wersetów Prologu. Później w. 14 karmi teologię ikony (Jan Damasceński: skoro Niewidzialny stał się widzialny w ciele, wolno Go malować), średniowieczną teologię sakramentów, a w XX wieku — teologię Słowa i konstytucję *Dei Verbum*, której pierwsze rozdziały są utkane z Prologu."""),
 ("Liturgia",
"""Mało który tekst biblijny wrósł w liturgię tak głęboko:

**Ewangelia dnia Bożego Narodzenia.** Od starożytności J 1,1–14 (lub 1,1–18) jest Ewangelią głównej Mszy w dzień Narodzenia Pańskiego (*Missa in die* — Msza w dzień, 25 grudnia) — po nocnej Ewangelii o żłóbku Kościół w pełnym świetle dnia czyta metafizykę tej nocy. Tak jest w rycie rzymskim do dziś; Prolog powraca też w dni powszednie przed Epifanią (Objawieniem Pańskim) i jako Ewangelia uroczystości.

**Ostatnia Ewangelia.** W tradycyjnym rycie rzymskim (dziś: nadzwyczajna forma rytu) kapłan po błogosławieństwie końcowym każdej Mszy odczytywał przy ołtarzu J 1,1–14 jako *ultimum Evangelium* (ostatnią Ewangelię) — zwyczaj wyrosły w średniowieczu z prywatnej pobożności kapłańskiej, utrwalony w Mszale Piusa V (1570 r.). Msza kończyła się więc codziennie słowami *Et Verbum caro factum est* (A Słowo ciałem się stało) — jakby pieczęcią: to, co dokonało się na ołtarzu, jest dalszym ciągiem w. 14.

**Przyklęknięcie.** Na słowa *Et Verbum caro factum est* (A Słowo ciałem się stało) przyklękano — tak jak przyklęka się (dziś: w Boże Narodzenie i Zwiastowanie, dawniej: zawsze) na słowa *Et incarnatus est* (I wcielił się) w Credo (Wyznaniu wiary). Ciało liturgii samo wykłada egzegezę: wobec tego zdania nie wystarczy skłonić głowy.

**Anioł Pański.** Codzienna modlitwa maryjna odmawiana rano, w południe i wieczorem ma za trzecie wezwanie właśnie w. 14: *Et Verbum caro factum est — et habitavit in nobis* (A Słowo ciałem się stało — i zamieszkało między nami). Miliony ludzi trzy razy dziennie od stuleci wypowiadają zdanie z naszej perykopy — trudno o mocniejszy dowód jej liturgicznej żywotności.

**Sakramentalia i pobożność.** Prolog odmawiano nad chorymi, przy błogosławieństwach, w rytuałach egzorcyzmów mniejszych, nad noworodkami i na cztery strony świata przy błogosławieństwie pól; noszono go zapisany przy sobie (praktykę wypaczoną w amulet piętnowały synody — co samo świadczy o randze tekstu w wyobraźni wiernych). Początkowe słowa *In principio erat Verbum* (Na początku było Słowo) otwierały ewangeliarze iluminowane najświetniejszymi kartami (Book of Kells — Księga z Kells — poświęca inicjałom Prologu osobne arcydzieło strony).

**Godzina czytań i tradycje wschodnie.** W liturgii bizantyjskiej J 1,1–17 jest Ewangelią głównej liturgii Paschy (!) — Wschód czyta Prolog nie przy żłóbku, lecz przy pustym grobie: światłość, której ciemność nie ogarnęła, objawia się w Zmartwychwstaniu; w praktyce paschalnej bywa odczytywany w wielu językach naraz — znak, że Słowo oświeca każdego człowieka. Ta podwójna lokalizacja (Zachód: Narodzenie; Wschód: Pascha) jest sama w sobie znakomitą egzegezą: Prolog opowiada jedną tajemnicę Słowa, które przyszło, zostało odrzucone i zwyciężyło."""),
 ]},
{
 "type": "zakonczenie",
 "title": "Zakończenie: intencja całości",
 "body": """Jeśli zebrać wszystko w jedno zdanie: Prolog objawia, że u korzenia rzeczywistości nie leży ani przypadek, ani prawo, ani nawet „coś boskiego" — lecz Ktoś: odwieczne Słowo zwrócone ku Ojcu; że to Słowo jest racją istnienia i poznawalności każdej rzeczy oraz światłem każdego ludzkiego umysłu; że weszło ono w historię aż po kruchość ciała, by w swoim ciele stać się nową Świątynią; i że celem tego zstąpienia jest nasze narodzenie z Boga. *Verbum caro factum est, ut caro Verbi capax fieret* (Słowo stało się ciałem, aby ciało stało się zdolne pojąć Słowo) — a ciemność, która ani tego nie pojęła, ani nie pokonała, nie ma już nic do powiedzenia.""",
 "children": []},
{
 "type": "nota",
 "title": "Nota warsztatowa",
 "body": """*Nota warsztatowa: analiza gramatyczna oparta na tekście greckim w brzmieniu wydania krytycznego Nestle-Aland 28; przekłady polskie wersetów są robocze (własne, dosłowne), przekłady terminów hebrajskich i aramejskich podane w transkrypcji uproszczonej. Przy pracy kaznodziejskiej lub publikacyjnej warto zestawić przekład roboczy z Biblią Tysiąclecia i Biblią Paulistów oraz sięgnąć po komentarze: R. E. Brown (Anchor Bible), C. K. Barrett, R. Schnackenburg, a po polsku S. Mędala (Nowy Komentarz Biblijny) i L. Stachowiak (KUL); z klasyki — Orygenes, św. Augustyn (In Iohannis Evangelium tractatus — Homilie na Ewangelię św. Jana), św. Jan Chryzostom i św. Tomasz (Super Ioannem — Wykład Ewangelii Jana).*""",
 "children": []},
]

# ------------------------------------------------------------------
# 6. LEKSYKON GRECKI (lemma, translit, pos, gloss)
# ------------------------------------------------------------------
LEXEMES = [
    ("λόγος", "logos", "rzeczownik", "słowo, rozum, racja, zasada, mowa"),
    ("ἀρχή", "arche", "rzeczownik", "początek, zasada"),
    ("εἰμί", "eimi", "czasownik", "być (ἦν — imperfectum: trwanie bez początku)"),
    ("γίνομαι", "ginomai", "czasownik", "stawać się, powstawać (ἐγένετο — aoryst)"),
    ("θεός", "theos", "rzeczownik", "Bóg"),
    ("ζωή", "zoe", "rzeczownik", "życie (Boże, nie biologiczne — por. βίος)"),
    ("βίος", "bios", "rzeczownik", "życie doczesne, sposób życia (kontrast do ζωή)"),
    ("φῶς", "phos", "rzeczownik", "światłość"),
    ("σκοτία", "skotia", "rzeczownik", "ciemność (u Jana nacechowana moralnie)"),
    ("φαίνω", "phaino", "czasownik", "świecić"),
    ("καταλαμβάνω", "katalambano", "czasownik", "chwytać, pojmować, ogarniać, dopadać"),
    ("μαρτυρία", "martyria", "rzeczownik", "świadectwo (język procesowy)"),
    ("μαρτυρέω", "martyreo", "czasownik", "świadczyć"),
    ("ἀποστέλλω", "apostello", "czasownik", "posyłać (stąd ἀπόστολος — apostoł)"),
    ("ἀληθινός", "alethinos", "przymiotnik", "prawdziwy: autentyczny, archetypiczny (por. ἀληθής)"),
    ("ἀληθής", "alethes", "przymiotnik", "prawdomówny, zgodny z prawdą (kontrast do ἀληθινός)"),
    ("φωτίζω", "photizo", "czasownik", "oświecać"),
    ("κόσμος", "kosmos", "rzeczownik", "świat: miejsce / stworzenie / ludzkość odwrócona od Boga"),
    ("γινώσκω", "ginosko", "czasownik", "poznawać (relacyjnie, por. hebr. jada)"),
    ("ἴδιος", "idios", "przymiotnik", "własny (τὰ ἴδια — swoja własność; οἱ ἴδιοι — swoi)"),
    ("παραλαμβάνω", "paralambano", "czasownik", "przyjmować do siebie (mocniejsze niż λαμβάνω)"),
    ("λαμβάνω", "lambano", "czasownik", "brać, przyjmować"),
    ("ἐξουσία", "exousia", "rzeczownik", "moc, władza, uprawnienie (nie δύναμις)"),
    ("δύναμις", "dynamis", "rzeczownik", "siła, moc fizyczna (kontrast do ἐξουσία)"),
    ("τέκνον", "teknon", "rzeczownik", "dziecko (od τίκτω — rodzić; kontrast do υἱός)"),
    ("υἱός", "hyios", "rzeczownik", "syn (u Jana zarezerwowane dla Jezusa)"),
    ("πιστεύω", "pisteuo", "czasownik", "wierzyć (πιστεύω εἰς — wiara jako ruch ku Osobie)"),
    ("ὄνομα", "onoma", "rzeczownik", "imię (hebraizm: imię = osoba)"),
    ("σάρξ", "sarx", "rzeczownik", "ciało-mięso, ciało w słabości i śmiertelności"),
    ("σῶμα", "soma", "rzeczownik", "ciało jako organizm (kontrast do σάρξ)"),
    ("σκηνόω", "skenoo", "czasownik", "rozbić namiot, zamieszkać (od σκηνή — namiot)"),
    ("θεάομαι", "theaomai", "czasownik", "kontemplować, oglądać uważnie (stąd θέατρον)"),
    ("δόξα", "doxa", "rzeczownik", "chwała (LXX: ciężar kawod — manifestacja obecności Boga)"),
    ("μονογενής", "monogenes", "przymiotnik", "jednorodzony, jedyny w swoim rodzaju"),
    ("χάρις", "charis", "rzeczownik", "łaska, dar darmowy, życzliwość"),
    ("ἀλήθεια", "aletheia", "rzeczownik", "prawda (LXX: emet — niezawodność, wierność)"),
    ("σοφία", "sophia", "rzeczownik", "mądrość (tło sapiencjalne Logosu)"),
]

# ------------------------------------------------------------------
# 7. TERMINY SEMICKIE
# ------------------------------------------------------------------
SEMITIC = [
    ("דָּבָר", "dawar", "hbr", "słowo, rzecz, sprawa, wydarzenie"),
    ("מֵימְרָא", "Memra", "aram", "Słowo (Pana) — targumy: Boża obecność działająca"),
    ("חָכְמָה", "chochma", "hbr", "Mądrość (uosobiona: Prz 8, Syr 24, Mdr 7)"),
    ("שְׁכִינָה", "Szechina", "hbr", "zamieszkiwanie, obecność Boża"),
    ("מִשְׁכָּן", "miszkan", "hbr", "przybytek, namiot spotkania"),
    ("שׁכן", "szakan", "hbr", "rdzeń: mieszkać, przebywać (por. σκηνόω)"),
    ("כָּבוֹד", "kawod", "hbr", "chwała, dosł. ciężar, waga"),
    ("חֶסֶד", "chesed", "hbr", "miłość wierna przymierzu, miłosierdzie"),
    ("אֱמֶת", "emet", "hbr", "prawda jako niezawodność, wierność"),
    ("יָדַע", "jada", "hbr", "poznać, także: wejść w zażyłość"),
    ("בָּשָׂר", "basar", "hbr", "ciało"),
    ("שֵׁם", "szem", "hbr", "imię, obecność"),
    ("בִּרְכַּת הַמִּינִים", "birkat ha-minim", "hbr", '„błogosławieństwo" przeciw heretykom (koniec I w.)'),
]

# lexeme_lemma -> [(semitic_translit, relation_note)]
LEXEME_SEMITIC = [
    ("λόγος", "dawar", "dawar = słowo i czyn zarazem; tło Rdz 1, Ps 33,6, Iz 55"),
    ("λόγος", "Memra", "targumiczne Słowo Pana — najbliższe tło judaizmu synagogalnego"),
    ("σοφία", "chochma", "Mądrość uosobiona — literacki szkielet Prologu"),
    ("δόξα", "kawod", "LXX oddaje kawod przez doksa — chwała jako obecność"),
    ("χάρις", "chesed", "Wj 34,6: raw chesed → plēres charitos"),
    ("ἀλήθεια", "emet", "Wj 34,6: we'emet → kai alētheias"),
    ("σκηνόω", "szakan", "spółgłoski σ-κ-ν brzmią jak rdzeń szakan"),
    ("σκηνόω", "miszkan", "LXX: skēnē za miszkan — namiot spotkania"),
    ("σκηνόω", "Szechina", "ciało Jezusa miejscem Szechiny"),
    ("γινώσκω", "jada", "poznanie relacyjne, osobowe"),
    ("σάρξ", "basar", "ciało w kruchości i śmiertelności"),
    ("ὄνομα", "szem", "imię = sama osoba"),
]

# ------------------------------------------------------------------
# 8. WYSTĄPIENIA LEKSEMÓW: (lemma, verse_num, form_in_text | None)
# ------------------------------------------------------------------
OCCURRENCES = [
    ("λόγος", 1, "ὁ λόγος"), ("λόγος", 14, "ὁ λόγος"),
    ("ἀρχή", 1, "ἐν ἀρχῇ"), ("ἀρχή", 2, "ἐν ἀρχῇ"),
    ("εἰμί", 1, "ἦν"), ("εἰμί", 4, "ἦν"), ("εἰμί", 9, "ἦν"), ("εἰμί", 10, "ἦν"),
    ("γίνομαι", 3, "ἐγένετο"), ("γίνομαι", 6, "ἐγένετο"), ("γίνομαι", 10, "ἐγένετο"),
    ("γίνομαι", 12, "γενέσθαι"), ("γίνομαι", 14, "ἐγένετο"),
    ("θεός", 1, "θεός"), ("θεός", 2, "θεόν"), ("θεός", 6, "θεοῦ"),
    ("θεός", 12, "θεοῦ"), ("θεός", 13, "θεοῦ"),
    ("ζωή", 4, "ζωή"),
    ("φῶς", 4, "φῶς"), ("φῶς", 5, "φῶς"), ("φῶς", 7, "φωτός"),
    ("φῶς", 8, "φῶς"), ("φῶς", 9, "φῶς"),
    ("σκοτία", 5, "σκοτίᾳ"),
    ("φαίνω", 5, "φαίνει"),
    ("καταλαμβάνω", 5, "κατέλαβεν"),
    ("μαρτυρία", 7, "μαρτυρίαν"),
    ("μαρτυρέω", 7, "μαρτυρήσῃ"), ("μαρτυρέω", 8, "μαρτυρήσῃ"),
    ("ἀποστέλλω", 6, "ἀπεσταλμένος"),
    ("ἀληθινός", 9, "ἀληθινόν"),
    ("φωτίζω", 9, "φωτίζει"),
    ("κόσμος", 9, "κόσμον"), ("κόσμος", 10, "κόσμος"),
    ("γινώσκω", 10, "ἔγνω"),
    ("ἴδιος", 11, "τὰ ἴδια / οἱ ἴδιοι"),
    ("παραλαμβάνω", 11, "παρέλαβον"),
    ("λαμβάνω", 12, "ἔλαβον"),
    ("ἐξουσία", 12, "ἐξουσίαν"),
    ("τέκνον", 12, "τέκνα"),
    ("πιστεύω", 12, "πιστεύουσιν"),
    ("ὄνομα", 6, "ὄνομα"), ("ὄνομα", 12, "ὄνομα"),
    ("σάρξ", 13, "σαρκός"), ("σάρξ", 14, "σάρξ"),
    ("σκηνόω", 14, "ἐσκήνωσεν"),
    ("θεάομαι", 14, "ἐθεασάμεθα"),
    ("δόξα", 14, "δόξαν"),
    ("μονογενής", 14, "μονογενοῦς"),
    ("χάρις", 14, "χάριτος"),
    ("ἀλήθεια", 14, "ἀληθείας"),
]

# ------------------------------------------------------------------
# 9. ODNIESIENIA BIBLIJNE
#    (source: ("pericope",) | ("section", tytuł) | ("unit", label_bloku, idx),
#     target_book, cs, vs, ce, ve, label, relation, note)
# ------------------------------------------------------------------
REFS = [
    (("pericope",), "Rdz", 1, 1, 1, 5,   "Rdz 1,1–5",     "aluzja",     "Fundament: nowa Księga Rodzaju — ta sama sekwencja początek-słowo-życie-światłość"),
    (("pericope",), "Ps",  33, 6, 33, 6, "Ps 33(32),6",   "tlo",        "Słowo jako sprawcza moc stwórcza"),
    (("pericope",), "Iz",  55, 10, 55, 11, "Iz 55,10–11", "tlo",        "Słowo posłane, które dokonuje dzieła i wraca — schemat zstąpienia i wstąpienia"),
    (("pericope",), "Prz", 8, 22, 8, 31, "Prz 8,22–31",   "typologia",  "Mądrość przy stwarzaniu — literacki szkielet Prologu"),
    (("pericope",), "Syr", 24, 1, 24, 23, "Syr 24,1–23",  "typologia",  "Mądrość rozbija namiot w Jakubie (κατασκήνωσον — ten sam rdzeń co ἐσκήνωσεν)"),
    (("pericope",), "Mdr", 7, 22, 8, 1,  "Mdr 7,22–8,1",  "typologia",  "Mądrość odblaskiem wiecznej światłości"),
    (("pericope",), "Wj",  25, 8, 25, 8, "Wj 25,8",       "tlo",        "Przybytek: zamieszkam pośród nich"),
    (("pericope",), "Wj",  33, 18, 33, 23, "Wj 33,18–23", "kontrast",   "Mojżeszowi odmówiono oglądania chwały — nam dano (w. 14)"),
    (("pericope",), "Wj",  34, 6, 34, 6, "Wj 34,6",       "aluzja",     "chesed we'emet → χάρις καὶ ἀλήθεια: Wcielenie językiem teofanii synajskiej"),
    (("pericope",), "Wj",  40, 34, 40, 35, "Wj 40,34–35", "typologia",  "Obłok chwały wypełnia przybytek — gdzie namiot, tam doksa"),
    (("pericope",), "Rdz", 22, 1, 22, 19, "Rdz 22,1–19",  "typologia",  "Ofiarowanie Izaaka: syn jedyny, umiłowany → μονογενής"),
    (("pericope",), "Flp", 2, 6, 2, 11,  "Flp 2,6–11",    "paralela",   "Hymn: parabola zstąpienia i wywyższenia, kenoza"),
    (("pericope",), "Kol", 1, 15, 1, 20, "Kol 1,15–20",   "paralela",   "W Nim wszystko stworzone — najbliższa paralela do w. 3–4"),
    (("pericope",), "Hbr", 1, 1, 1, 4,   "Hbr 1,1–4",     "paralela",   "Bóg przemówił w Synu — teologia Słowa ostatecznego"),
    (("pericope",), "1 J", 1, 1, 1, 4,   "1 J 1,1–4",     "paralela",   "Autokomentarz środowiska Janowego — ten sam słownik plus dotyk"),
    (("pericope",), "Ap",  19, 13, 19, 13, "Ap 19,13",    "paralela",   "Imię Jego: Słowo Boga — klamra corpus Joanneum"),
    (("pericope",), "J",   3, 3, 3, 8,   "J 3,3–8",       "rozwiniecie","Narodzenie z wody i Ducha — rozwinięcie w. 12–13"),
    (("pericope",), "1 P", 1, 23, 1, 23, "1 P 1,23",      "paralela",   "Zrodzeni z niezniszczalnego nasienia — przez słowo Boga"),
    (("pericope",), "Jk",  1, 18, 1, 18, "Jk 1,18",       "paralela",   "Zrodził nas słowem prawdy"),
    (("unit", "w. 1", 3),  "J", 20, 28, 20, 28, "J 20,28", "por",       "Tomasz: Pan mój i Bóg mój — z rodzajnikami"),
    (("unit", "w. 1", 2),  "J", 17, 5, 17, 5,  "J 17,5",  "por",        "παρὰ σοί — przy Tobie: alternatywna konstrukcja, której Jan tu nie wybrał"),
    (("unit", "w. 3", 0),  "1 Kor", 8, 6, 8, 6, "1 Kor 8,6", "por",     "δι᾿ οὗ τὰ πάντα — przez którego wszystko"),
    (("unit", "w. 5", 1),  "J", 12, 35, 12, 35, "J 12,35", "por",       "aby ciemność was nie ogarnęła — ta sama wieloznaczność καταλαμβάνω"),
    (("unit", "w. 6–8", 0),"Dz", 19, 1, 19, 7, "Dz 19,1–7", "por",      "Uczniowie w Efezie znający tylko chrzest Janowy"),
    (("unit", "w. 12–13", 0), "Rz", 8, 15, 8, 15, "Rz 8,15", "kontrast","Pawłowa υἱοθεσία (adopcja) vs Janowe zrodzenie"),
    (("unit", "w. 12–13", 2), "J", 3, 3, 3, 3, "J 3,3",   "rozwiniecie","Narodzenie ἄνωθεν — z góry / na nowo"),
    (("unit", "w. 14", 1), "J", 2, 21, 2, 21,  "J 2,21",  "rozwiniecie","Mówił o świątyni swego ciała"),
    (("section", "Świat Prologu: judaizm Drugiej Świątyni"), "J", 16, 28, 16, 28, "J 16,28", "por", "Wyszedłem od Ojca... znowu opuszczam świat — fabuła zstąpienia i wstąpienia"),
    (("section", "Świat Prologu: judaizm Drugiej Świątyni"), "Syr", 24, 8, 24, 8, "Syr 24,8", "cytat", "ἐν Ιακωβ κατασκήνωσον — w Jakubie rozbij namiot"),
    (("section", "Świat Prologu: judaizm Drugiej Świątyni"), "Dz", 18, 24, 18, 24, "Dz 18,24", "por", "Apollos — Efez i Aleksandria naczyniami połączonymi"),
    (("section", "Tło polemiczne"), "J", 9, 22, 9, 22, "J 9,22", "por",  "ἀποσυνάγωγος — wyłączony z synagogi"),
    (("section", "6. Łaska i przebóstwienie"), "2 P", 1, 4, 1, 4, "2 P 1,4", "por", "Uczestnicy Boskiej natury"),
    (("section", "Po czwarte: strzeże realizmu ciała"), "Łk", 1, 35, 1, 35, "Łk 1,35", "por", "Duch ukształtował ciało Słowa w łonie Dziewicy"),
]

# ------------------------------------------------------------------
# 10. DZIEŁA I CYTOWANIA
# ------------------------------------------------------------------
WORKS = [
    ("św. Tomasz z Akwinu", "Super Evangelium S. Ioannis lectura", "Wykład Ewangelii św. Jana", "XIII", "scholastyka"),
    ("św. Tomasz z Akwinu", "Summa Theologiae", "Suma teologii", "XIII", "scholastyka"),
    ("św. Tomasz z Akwinu", "Summa contra Gentiles", "Suma przeciw poganom", "XIII", "scholastyka"),
    ("Orygenes", "Komentarz do Ewangelii Jana", None, "III", "patrystyka"),
    ("św. Augustyn", "In Iohannis Evangelium tractatus", "Homilie na Ewangelię św. Jana", "IV/V", "patrystyka"),
    ("św. Jan Chryzostom", "Homilie na Ewangelię Jana", None, "IV", "patrystyka"),
    ("św. Justyn Męczennik", None, None, "II", "patrystyka"),
    ("św. Ireneusz z Lyonu", None, None, "II", "patrystyka"),
    ("św. Atanazy", None, None, "IV", "patrystyka"),
    ("św. Jan Damasceński", None, None, "VIII", "patrystyka"),
    ("Filon z Aleksandrii", None, None, "I", "judaizm"),
    ("Sobór Watykański II", "Dei Verbum", "Konstytucja o Objawieniu Bożym", "XX", "magisterium"),
    ("R. E. Brown", "The Gospel According to John (Anchor Bible)", None, "XX", "wspolczesna"),
    ("C. K. Barrett", "The Gospel According to St John", None, "XX", "wspolczesna"),
    ("R. Schnackenburg", "Das Johannesevangelium", None, "XX", "wspolczesna"),
    ("S. Mędala", "Ewangelia według świętego Jana (Nowy Komentarz Biblijny)", None, "XXI", "wspolczesna"),
    ("L. Stachowiak", "Ewangelia według św. Jana (KUL)", None, "XX", "wspolczesna"),
]

# (author, locus, source: ("section", tytuł) | ("pericope",), note)
CITATIONS = [
    ("św. Tomasz z Akwinu",  None, ("section", "III. Obserwacje teologiczne i filozoficzne w duchu tomistycznym"), "Super Ioannem, ST i ScG — podstawa całej sekcji III", "Super Evangelium S. Ioannis lectura"),
    ("św. Tomasz z Akwinu",  None, ("section", "III. Obserwacje teologiczne i filozoficzne w duchu tomistycznym"), None, "Summa Theologiae"),
    ("św. Tomasz z Akwinu",  None, ("section", "III. Obserwacje teologiczne i filozoficzne w duchu tomistycznym"), None, "Summa contra Gentiles"),
    ("Sobór Watykański II",  "nr 11–13", ("section", "V. Autor Boży: co Duch Święty chce przekazać"), "Nauka o natchnieniu; sensus plenior", "Dei Verbum"),
    ("św. Justyn Męczennik", None, ("section", "Historia dogmatu"), "Teologia λόγος σπερματικός zbudowana na w. 9", None),
    ("św. Ireneusz z Lyonu", None, ("section", "Historia dogmatu"), "Jedność Stwórcy i Zbawiciela oparta na w. 3 i 14; świadectwo autorstwa (ok. 180 r.)", None),
    ("Orygenes",             None, ("section", "Historia dogmatu"), "Najobszerniejszy starożytny komentarz biblijny — całe księgi o pierwszych wersetach", "Komentarz do Ewangelii Jana"),
    ("św. Atanazy",          None, ("section", "Historia dogmatu"), "Odpowiedź na arianizm z w. 1; ὁμοούσιος jako parafraza θεὸς ἦν ὁ λόγος", None),
    ("św. Jan Damasceński",  None, ("section", "Historia dogmatu"), "Teologia ikony: skoro Niewidzialny stał się widzialny, wolno Go malować", None),
    ("Filon z Aleksandrii",  None, ("section", "Świat Prologu: judaizm Drugiej Świątyni"), "Logos jako byt pośredni — nigdy osoba, nigdy wcielony", None),
    ("św. Augustyn",         None, ("section", "Nota warsztatowa"), "Zalecany komentarz klasyczny", "In Iohannis Evangelium tractatus"),
    ("R. E. Brown",          None, ("section", "Nota warsztatowa"), "Zalecany komentarz współczesny", "The Gospel According to John (Anchor Bible)"),
]

# ------------------------------------------------------------------
# 11. RECEPCJA LITURGICZNA
# ------------------------------------------------------------------
LITURGY = [
    ("rzymski", "Ewangelia głównej Mszy w dzień Narodzenia Pańskiego (Missa in die, 25 XII)", "J 1,1–14 (lub 1,1–18)",
     "Po nocnej Ewangelii o żłóbku Kościół w pełnym świetle dnia czyta metafizykę tej nocy; Prolog powraca też w dni powszednie przed Epifanią."),
    ("rzymski (forma nadzwyczajna)", "Ostatnia Ewangelia (ultimum Evangelium) na końcu każdej Mszy", "J 1,1–14",
     "Zwyczaj wyrosły w średniowieczu z prywatnej pobożności kapłańskiej, utrwalony w Mszale Piusa V (1570)."),
    ("rzymski", "Przyklęknięcie na Et Verbum caro factum est", "J 1,14",
     "Jak na Et incarnatus est w Credo — ciało liturgii samo wykłada egzegezę."),
    ("pobożność", "Anioł Pański — trzecie wezwanie", "J 1,14",
     "Et Verbum caro factum est — et habitavit in nobis; trzy razy dziennie od stuleci."),
    ("bizantyjski", "Ewangelia głównej liturgii Paschy", "J 1,1–17",
     "Wschód czyta Prolog przy pustym grobie, często w wielu językach naraz."),
    ("sakramentalia", "Błogosławieństwa, modlitwy nad chorymi, egzorcyzmy mniejsze, błogosławieństwo pól", "J 1,1–14",
     "Noszony zapisany przy sobie; inicjały In principio otwierały iluminowane ewangeliarze (Book of Kells)."),
]

# ------------------------------------------------------------------
# 12. NOTY KRYTYKI TEKSTU
# ------------------------------------------------------------------
TEXTUAL_NOTES = [
    (3, "ὃ γέγονεν", "interpunkcja",
     '''NA28, za najstarszymi świadkami i interpunkcją ojców przednicejskich, dopuszcza łączenie z w. 4: ὃ γέγονεν ἐν αὐτῷ ζωὴ ἦν. Po kryzysie ariańskim ojcowie zaczęli łączyć z w. 3, by arianie nie czytali „Duch też się stał".''',
     "Obie lektury prawowierne; starsza zbieżna z nauką o rationes aeternae."),
    (13, "ὃς … ἐγεννήθη", "wariant lekcji",
     "Garść świadków łacińskich i cytaty ojców (m.in. Ireneusz, Tertulian) czytają liczbę pojedynczą — odnosząc werset do dziewiczego poczęcia Chrystusa.",
     "NA28 słusznie utrzymuje liczbę mnogą (całość tradycji greckiej); stara lekcja świadczy o wczesnej analogii: narodzenie wierzących odwzorowaniem narodzenia Słowa."),
]

# ------------------------------------------------------------------
# 13. MOTYWY PRZEKROJOWE
#     (name, description, [links: ("block", label) | ("unit", label, idx) | ("section", tytuł) | ("pericope",)])
# ------------------------------------------------------------------
THEMES = [
    ("ἦν / ἐγένετο — trwanie a stawanie się",
     "Oś Prologu: to, co jest, wobec tego, co powstaje; tomistycznie: esse per essentiam vs per participationem.",
     [("unit", "w. 1", 0), ("section", "2. Ipsum esse subsistens a porządek stawania się"), ("unit", "w. 14", 0)]),
    ("światłość i ciemność",
     "Dualizm etyczny (nie ontologiczny): ciemność jako nie-przyjęcie światła, bez własnej substancji.",
     [("block", "w. 4"), ("block", "w. 5"), ("unit", "w. 9", 0)]),
    ("świadectwo (μαρτυρία)",
     "Język procesowy czwartej Ewangelii — Ewangelia jako wielki proces o tożsamość Jezusa.",
     [("block", "w. 6–8")]),
    ("Szechina — zamieszkanie Boga",
     "Od miszkanu i obłoku chwały do ciała Jezusa jako nowego Przybytku.",
     [("unit", "w. 14", 1), ("unit", "w. 14", 3), ("section", "Świat Prologu: judaizm Drugiej Świątyni")]),
    ("narodzenie z Boga",
     "Centrum chiazmu (w. 12): cel całego ruchu Słowa ku światu; łaska jako partycypacja w naturze Bożej.",
     [("block", "w. 12–13"), ("section", "6. Łaska i przebóstwienie"), ("section", "Po trzecie: mówi o czytelniku")]),
    ("chiazm Prologu",
     "Budowa koncentryczna z centrum w w. 12; hipoteza wcześniejszego hymnu z prozatorskimi wstawkami.",
     [("section", "Struktura całości")]),
    ("Logos a Mądrość",
     "Prolog na szkielecie tekstów sapiencjalnych — z korektą: nie księga, lecz Osoba.",
     [("section", "Świat Prologu: judaizm Drugiej Świątyni"), ("unit", "w. 1", 4)]),
    ("anty-doketyzm",
     "σάρξ jako słowo najostrzejsze z możliwych — realizm ciała przeciw gnozie i spirytualizmom.",
     [("unit", "w. 14", 0), ("section", "Tło polemiczne"), ("section", "Po czwarte: strzeże realizmu ciała")]),
]

META = [
    ("projekt", "Egzegeza Ewangelii według św. Jana"),
    ("zrodlo", "Google Docs — dokument roboczy (Prolog, J 1,1-14)"),
    ("edycja_tekstu_greckiego", "Nestle-Aland, wyd. 28 (NA28)"),
    ("przeklad", "roboczy, własny, celowo dosłowny"),
]

# ------------------------------------------------------------------
# 15. WARSTWA PATRYSTYCZNA — katena Ojców Kościoła do J 1,1-14
# ------------------------------------------------------------------
WORKS += [
    ("św. Ireneusz z Lyonu", "Adversus haereses", "Przeciw herezjom", "II", "patrystyka"),
    ("Tertulian", "Adversus Praxean", "Przeciw Prakseaszowi", "III", "patrystyka"),
    ("św. Hilary z Poitiers", "De Trinitate", "O Trójcy Świętej", "IV", "patrystyka"),
    ("św. Atanazy", "De incarnatione Verbi", "O wcieleniu Słowa", "IV", "patrystyka"),
    ("św. Grzegorz z Nazjanzu", "Epistula 101 (do Kledoniusza)", "List 101", "IV", "patrystyka"),
    ("św. Cyryl Aleksandryjski", "Commentarii in Ioannem", "Komentarz do Ewangelii Jana", "V", "patrystyka"),
    ("św. Justyn Męczennik", "Apologie", None, "II", "patrystyka"),
    ("św. Augustyn", "Confessiones", "Wyznania", "IV/V", "patrystyka"),
    ("św. Tomasz z Akwinu", "Catena aurea", "Złoty łańcuch", "XIII", "scholastyka"),
]

SECTION_VIII = {
 "type": "patrystyka",
 "title": "VIII. Komentarze Ojców Kościoła (catena patrum)",
 "body": """Katena (łac. *catena* — łańcuch) to klasyczna forma egzegezy kościelnej: pod tekstem biblijnym nawleka się, ogniwo po ogniwie, głosy Ojców, tak by nad jednym wersetem spotkały się stulecia. Wzorem gatunku pozostaje *Catena aurea* (Złoty łańcuch) św. Tomasza z Akwinu — ciągły komentarz do czterech Ewangelii utkany wyłącznie z cytatów patrystycznych; dla Prologu Tomasz splata tam przede wszystkim Chryzostoma, Augustyna, Orygenesa, Hilarego, Bedę i Teofilakta. Poniższa katena idzie za blokami części I: przy każdym zakresie wersetów zebrano najważniejsze głosy — od Ireneusza po Cyryla — z miejscem (*locus* — miejsce w dziele) i parafrazą, tak by można było wrócić do źródeł. Zasada lektury Ojców jest wspólna: Prolog czytali oni zarazem doksologicznie (jako hymn Kościoła) i polemicznie (jako mur przeciw kolejnym redukcjom wiary) — i właśnie na ich egzegezie tego tekstu wyrosły formuły Nicei, Efezu i Chalcedonu, omówione w części VII.""",
 "children": []}

# (block_label, author, work_title, locus, body_md)
PATRISTIC = [
("w. 1", "Tertulian", "Adversus Praxean", "Adv. Prax. 5",
"""Pierwsza łacińska egzegeza w. 1 zmaga się z samym przekładem: λόγος (słowo, rozum) to po łacinie zarazem *Ratio* (Rozum) i *Sermo* (Mowa, Słowo). Tertulian rozstrzyga: zanim cokolwiek powstało, Bóg nie był sam — miał w sobie Rozum, a w Rozumie Słowo, które „rozmawiał w sobie". Przeciw Prakseaszowi (modaliście, dla którego Ojciec i Syn to jedna osoba w dwóch maskach) podkreśla: Słowo jest *alius* (inny — jako osoba), nie *aliud* (co innego — jako substancja); odrębność bez podziału, ekonomia (*dispositio* — rozporządzenie) bez rozdarcia monarchii. To surowe, przednicejskie żelazo, z którego później wykuto precyzyjniejsze formuły."""),
("w. 1", "Orygenes", "Komentarz do Ewangelii Jana", "Comm. in Io., ks. I–II",
"""Najobszerniejszy starożytny komentarz do jednego wersetu: Orygenes bada kolejno każde słowo. Ἀρχή (początek) ma wiele znaczeń — początek drogi, tworzywo, zasada rządzenia — ale tu oznacza Mądrość: „na początku" znaczy „w Mądrości", bo Chrystus sam jest ἀρχή (zasadą). Orygenes pierwszy zauważa też grę rodzajnika w w. 1c: ὁ θεός (ten-oto Bóg, z rodzajnikiem) o Ojcu jako źródle bóstwa, θεός (Bóg, bez rodzajnika) o Słowie. Jego wyjaśnienie — Słowo jest Bogiem przez odwieczne trwanie przy Ojcu — czytano po Nicei ostrożnie (subordynacjanizm), ale dokumentuje ono, że gramatyka tego półwersetu była przedmiotem drobiazgowego namysłu już w III wieku."""),
("w. 1", "św. Hilary z Poitiers", "De Trinitate", "De Trin. I,10–12",
"""Świadectwo autobiograficzne, jedyne w swoim rodzaju: Hilary opisuje, jak szukając Boga u filozofów — przez naturę, przez piękno, przez nieskończoność — trafił na Prolog Jana i „przekroczył pojmowanie rozumu". *In principio erat Verbum* (Na początku było Słowo) dało mu to, czego filozofia obiecać nie mogła: Boga, który nie jest samotną monadą, lecz Ojcem mającym współwiecznego Syna. „Umysł mój przekroczył swoją naturalną pojętność i nauczyłem się o Bogu więcej, niż się spodziewałem". Prolog jako droga nawrócenia intelektu — nie argument, lecz objawienie, które rozum przyjmuje, klękając."""),
("w. 1", "św. Jan Chryzostom", "Homilie na Ewangelię Jana", "Hom. in Io. 2–4",
"""Chryzostom każe liczyć: czterokrotne ἦν (było) w w. 1–2 to cztery uderzenia młota w fundament arianizmu — „był" nie ma punktu początkowego, więc pytanie „kiedy powstał?" jest źle postawione. Rybak z Galilei „zagrzmiał" (stąd tytuł ὁ βροντῆς υἱός — syn gromu) prawdą, której nie ośmieliła się wypowiedzieć żadna filozofia: nie zaczyna od ziemi jak Mateusz i Łukasz, lecz od nieba, „bo duchem został uniesiony ponad wszystko, co zmysłowe". A jednak — dodaje kaznodzieja — mówi o Bogu tylko tyle, ile człowiek unieść może: imię „Słowo" samo jest zniżeniem się (συγκατάβασις — synkatabasis, łaskawe zejście do słabości słuchacza)."""),
("w. 1", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 1,8; por. Conf. VII,9",
"""Augustyn podsuwa analogię, którą Tomasz rozwinie w naukę o *verbum mentis* (słowie umysłu): zanim słowo zabrzmi, jest noszone w sercu — *verbum quod corde gestamus* (słowo, które nosimy w sercu) — i nie umniejsza się, gdy je wypowiadamy. Tak Słowo Boże: zrodzone, a nie oddzielone; wypowiedziane, a pozostające u Ojca. W *Wyznaniach* zaś Augustyn zeznaje, że treść w. 1–5 wyczytał wcześniej „nie tymi słowami, ale co do sensu" w księgach platoników — i właśnie dlatego wie, gdzie przebiega granica: filozofia dosięgła Słowa u Boga, lecz zdania *Verbum caro factum est* (Słowo ciałem się stało) u platoników nie znalazł nikt."""),
("w. 2", "św. Jan Chryzostom", "Homilie na Ewangelię Jana", "Hom. in Io. 4",
"""Po co powtórzenie? Chryzostom: bo herezja czyha na każdą szczelinę. Gdyby Jan poprzestał na w. 1, ktoś mógłby czytać: Słowo „było Bogiem" — czyli kiedyś nim się stało; οὗτος (ten właśnie) zbiera wszystko w jedno i zatrzaskuje furtkę: Ten, który jest Bogiem, ten sam był na początku u Boga. Ewangelista pisze jak dobry budowniczy — kładzie kamień i zaraz go sprawdza, zanim położy następny."""),
("w. 3", "św. Ireneusz z Lyonu", "Adversus haereses", "Adv. haer. I,22,1; III,8,3",
"""Dla Ireneusza w. 3 jest artykułem reguły prawdy (*regula veritatis*): jeden i ten sam Bóg wszystko uczynił przez swoje Słowo — nie aniołowie, nie eony, nie niższy demiurg gnostyków. „Wszystko" znaczy wszystko: świat materialny nie jest pomyłką ani upadkiem, lecz dziełem tego samego Słowa, które potem stało się ciałem. Jedność Stwórcy i Zbawiciela — najkrótsza definicja ortodoksji II wieku — wisi na jednym Janowym πάντα (wszystko)."""),
("w. 3", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 1,16–17",
"""Do starszej interpunkcji (to, co się stało, *w Nim* było życiem) Augustyn dodaje obraz, który stał się klasyką: stolarz robi skrzynię. Najpierw ma ją w swojej sztuce (*in arte*) — i skrzynia w sztuce żyje, bo żyje dusza rzemieślnika; potem robi ją z drewna — i skrzynia wykonana życiem nie jest, może spróchnieć i rozpaść się. Tak wszystkie rzeczy: w sobie są zmienne i śmiertelne, w Słowie są życiem — bo istnieją tam odwiecznie jako zamysł Tego, który żyje. Ziemia jest w Słowie życiem, choć w sobie jest tylko ziemią. Stąd prosta rada egzegety: chcesz zobaczyć rzecz naprawdę — szukaj jej tam, gdzie jest żywa."""),
("w. 4", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 1,18",
"""Światłość ludzi — Augustyn pyta: czym różni się człowiek od zwierzęcia, jeśli nie umysłem (*mens*), rozumem serca, którym widzi się sprawiedliwość i prawdę? Ta właśnie władza jest oświecana przez Życie, które jest w Słowie. Człowiek jest więc zapalony, nie samoświecący: *lucerna* (lampa) może zgasnąć — Światłość zgasnąć nie może. Cała augustyńska nauka o iluminacji (oświeceniu umysłu), którą Tomasz przełoży później na uczestnictwo w świetle niestworzonym, wyrasta z tego półwersetu."""),
("w. 5", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 1,19",
"""„Ciemność jej nie ogarnęła" — Augustyn tłumaczy obrazem ślepca w słońcu: słońce jest obecne przy nim, ale on jest nieobecny dla słońca. Tak głupota i grzech: światłość świeci w ciemności, lecz serca odwrócone nie widzą — nie dlatego, że światła brak, ale że oko chore. Stąd wezwanie zamykające homilię: nie wystarczy, by światło przyszło — trzeba oczyścić oko, którym się je widzi; a oczyszcza je Ten sam, który świeci."""),
("w. 6–8", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 2,2–5",
"""Skąd wiedzieć o Światłości, której zobaczyć nie można? Augustyn: spójrz na górę o świcie. Jan Chrzciciel jest górą oświeconą (*mons illuminatus*) — góry pierwsze chwytają wschodzące słońce, ale góra nie jest słońcem; kto by się zatrzymał na górze, zostanie w cieniu. Dlatego sam Jan powie o sobie tylko tyle: głos; a Pan nazwie go lampą (λύχνος — lucerna, J 5,35) — zapaloną, więc mogącą zgasnąć. Podnieś oczy znad góry ku Temu, który ją oświecił — oto cała teologia świadectwa w jednym obrazie."""),
("w. 6–8", "św. Jan Chryzostom", "Homilie na Ewangelię Jana", "Hom. in Io. 6",
"""Czy Światłość potrzebuje świadka-człowieka? Chryzostom: nie Światłość — słuchacze. Bóg zniża się (συγκατάβασις — synkatabasis, łaskawe zejście) do miary słabych: posyła głos znajomy, proroka w duchu Eliasza, aby ci, którzy nie unieśli jeszcze blasku, poszli za świadkiem aż do Świadczonego. Świadectwo Jana jest więc rusztowaniem: potrzebne, dopóki trwa budowa wiary, i pięknie usuwające się w cień, gdy przychodzi Ten, o którym świadczyło — „trzeba, by On wzrastał, a ja się umniejszał" (J 3,30)."""),
("w. 9", "św. Justyn Męczennik", "Apologie", "Apol. I 46; II 8.13",
"""Pierwsza chrześcijańska filozofia kultury wyrasta wprost z w. 9: jeżeli Słowo oświeca każdego człowieka, to każdy, kto żył według Logosu (rozumu-Słowa), miał w nim udział. Justyn ośmiela się napisać, że Sokrates i Heraklit byli „chrześcijanami przed Chrystusem" — o tyle, o ile żyli μετὰ λόγου (według Słowa/rozumu); wszystko bowiem, co filozofowie i prawodawcy powiedzieli prawdziwego, powiedzieli dzięki nasieniu Słowa (λόγος σπερματικός — rozum zarodkowy) w sobie. W Chrystusie zaś objawił się cały Logos — dlatego chrześcijaństwo nie boi się żadnej prawdy: każda jest jego własnością."""),
("w. 10", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 2,11–13",
"""„Świat Go nie poznał" — kim jest ten ślepy świat? Augustyn: miłośnicy świata, ludzie, którzy sercem zamieszkali w tym, co stworzone, i dlatego nie rozpoznali Stwórcy stojącego pośrodku. Przyszedł tu, gdzie zawsze był — *huc venit, ubi erat* (przyszedł tam, gdzie był) — bo nie zmienił miejsca, lecz stał się widzialny. A „swoi nie przyjęli": Augustyn czyta to i o Izraelu, i o każdym ochrzczonym, który nosi imię Chrystusa, a żyje jak obcy — Prolog nie pozwala czytelnikowi ustawić się wygodnie po stronie przyjmujących bez pytania o siebie."""),
("w. 12–13", "św. Cyryl Aleksandryjski", "Commentarii in Ioannem", "In Io., ks. I",
"""Cyryl precyzuje mechanikę usynowienia: Syn jest Synem z natury (φύσει — z natury), my stajemy się synami przez uczestnictwo (μετοχῇ — przez udział) i łaskę — Duch Święty odciska w ochrzczonych podobieństwo Jednorodzonego jak pieczęć w wosku. Dlatego Jan mówi „dało im moc *stać się*": dziecięctwo Boże nie jest ani metaforą, ani tytułem honorowym, lecz realnym przeobrażeniem, którego zasadą jest Ten, który sam z Boga jest zrodzony. Aleksandryjska teologia przebóstwienia — którą Tomasz odda formułą łaski jako uczestnictwa w naturze Bożej — ma tu swoje Janowe źródło."""),
("w. 12–13", "św. Jan Chryzostom", "Homilie na Ewangelię Jana", "Hom. in Io. 10–11",
"""Chryzostom zatrzymuje się nad słowem ἐξουσία (moc, uprawnienie): dlaczego „dał moc stać się", a nie po prostu „uczynił dziećmi"? Bo łaska nie gwałci wolności — dar trzeba przyjąć, a przyjęcie kosztuje trud całego życia; władza stania się dzieckiem jest jak żagiel: wiatr daje Bóg, ale żagiel trzeba postawić. Narodzenie „z Boga" wskazuje na chrzest — kąpiel odrodzenia, w której zaczyna się to, co w. 13 opisuje potrójnym przeczeniem: pochodzenie już nie z krwi i woli ciała, lecz z góry."""),
("w. 14", "św. Ireneusz z Lyonu", "Adversus haereses", "Adv. haer. V, praef.; III,18,1",
"""Najstarsza formuła przedziwnej wymiany: Słowo „stało się tym, czym my jesteśmy, aby nas uczynić tym, czym samo jest" (*factus est quod sumus nos, uti nos perficeret esse quod est ipse*). Ireneusz nazywa dzieło Wcielenia rekapitulacją (ἀνακεφαλαίωσις — anakefalaiosis, ponowne zjednoczenie pod jedną Głową): Słowo przeszło przez wszystkie etapy ludzkiego życia, aby każdy z nich uświęcić od środka i zawrócić historię Adama. Przeciw gnostykom, dla których ciało było odpadem: to samo Słowo, które ciało stworzyło (w. 3), ciało przyjęło (w. 14) — stworzenie i zbawienie są jednym łukiem."""),
("w. 14", "św. Atanazy", "De incarnatione Verbi", "De inc. 54",
"""Zdanie, które streszcza całą sotoriologię grecką: Αὐτὸς γὰρ ἐνηνθρώπησεν, ἵνα ἡμεῖς θεοποιηθῶμεν (On bowiem stał się człowiekiem, abyśmy my zostali przebóstwieni). Atanazy czyta w. 14 celowościowo: Wcielenie nie jest epizodem ratunkowym, lecz otwarciem wymiany — Słowo wzięło to, co nasze (σάρξ — ciało w jego śmiertelności), aby dać nam to, co swoje (nieśmiertelność, synostwo, poznanie Ojca). Dlatego w sporze ariańskim stawką nie była subtelność metafizyczna, lecz samo zbawienie: gdyby Słowo było stworzeniem, wymiana nie miałaby pokrycia — stworzenie nie może przebóstwić stworzenia."""),
("w. 14", "św. Grzegorz z Nazjanzu", "Epistula 101 (do Kledoniusza)", "Ep. 101,32",
"""Τὸ γὰρ ἀπρόσληπτον, ἀθεράπευτον (co bowiem nie zostało przyjęte, nie zostało uleczone). Przeciw Apolinaremu, który odmawiał Chrystusowi ludzkiego umysłu: σάρξ w w. 14 to nie tylko tkanka — to całe człowieczeństwo, z duszą i umysłem, bo właśnie umysł pierwszy zgrzeszył i najbardziej potrzebuje uleczenia. Zasada Grzegorza stała się probierzem chrystologii: zakres Wcielenia wyznacza zakres zbawienia; gdzie Słowo nie weszło, tam terapia nie sięga. Jan, pisząc σὰρξ ἐγένετο (ciałem się stało), użył części za całość — i Ojcowie pilnowali, by tej całości nikt nie okroił."""),
("w. 14", "św. Jan Chryzostom", "Homilie na Ewangelię Jana", "Hom. in Io. 11",
"""„Stało się" — ale jak? Chryzostom odpowiada z precyzją, którą powtórzy Chalcedon: nie przez przemianę (natura Boża nie przeszła w ciało), nie przez zmieszanie, lecz przez przyjęcie: pozostał, czym był, a stał się, czym nie był. Słowo zamieszkało w ciele jak w świątyni — μένων ὅ ἦν, ἔλαβεν ὃ οὐκ ἦν (pozostając, czym był, przyjął, czym nie był). Ewangelista dlatego zaraz dodaje „i oglądaliśmy chwałę Jego": ciało nie zasłoniło bóstwa, lecz stało się jego widzialnością — namiotem, przez którego zasłonę prześwieca Szechina (obecność)."""),
("w. 14", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 2,15–16; Conf. VII,18",
"""Dla Augustyna w. 14 jest lekarstwem — i to celowanym: na pychę. Filozofowie dojrzeli ojczyznę z daleka, ale nie znaleźli drogi; droga zaś jest pokorna: *Verbum caro factum est* (Słowo ciałem się stało). Bóg stał się niski, aby uleczyć nadętych; Mądrość stała się mlekiem — bo pokarmu stałego nie unieśliśmy — „abyśmy przez Tego, przez którego wszystko się stało, ssali mądrość jak niemowlęta". W *Wyznaniach* dopowie: dopóki nie uchwyciłem się pokornego Jezusa, wiedza mnie nadymała, zamiast budować. Egzegeza w. 14 jest u Augustyna nierozdzielnie doktryną i terapią duszy."""),
("w. 14", "św. Cyryl Aleksandryjski", "Commentarii in Ioannem", "In Io., ks. I",
"""Cyryl waży każde słowo przeciw dwóm przepaściom naraz: „stało się ciałem" nie znaczy, że natura Słowa uległa zamianie (przeciw pomysłom o przemianie bóstwa), ani że Słowo tylko zamieszkało w człowieku jak w kimś drugim (przeciw temu, co wkrótce zarzuci Nestoriuszowi): jedno i to samo jest Słowo i Jego ciało ożywione rozumną duszą — dlatego o Maryi wolno i trzeba mówić Θεοτόκος (Theotokos — Boża Rodzicielka). Formuła Efezu (431 r.) jest w istocie egzegezą w. 14 doprowadzoną do końca: podmiotem zdania „Słowo ciałem się stało" jest Słowo — więc i podmiotem narodzenia, głodu, łez i krzyża."""),
]

# ------------------------------------------------------------------
# 16. MIGRACJA (całość: kanon + Prolog + katena patrystyczna)
# ------------------------------------------------------------------
def main():
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_SQL)
    cur = con.cursor()

    cur.executemany("INSERT INTO meta(key, value) VALUES (?,?)", META)

    book_id = {}
    for ab, nm, tst, ordn in BOOKS:
        cur.execute("INSERT INTO book(abbrev_pl, name_pl, testament, canon_order) VALUES (?,?,?,?)",
                    (ab, nm, tst, ordn))
        book_id[ab] = cur.lastrowid

    verse_id = {}
    for vn, (gk, pl) in VERSES.items():
        cur.execute("INSERT INTO verse(book_id, chapter, verse_num, text_greek, text_working_pl) VALUES (?,?,?,?,?)",
                    (book_id["J"], 1, vn, gk, pl))
        verse_id[vn] = cur.lastrowid

    p = PERICOPE
    cur.execute("""INSERT INTO pericope(book_id, chapter_start, verse_start, chapter_end, verse_end,
                   title, motto, status, position, source_url) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (book_id[p["book"]], p["cs"], p["vs"], p["ce"], p["ve"],
                 p["title"], p["motto"], p["status"], p["position"], p["source_url"]))
    pid = cur.lastrowid

    section_id = {}
    def add_section(stype, title, body, parent, pos):
        cur.execute("""INSERT INTO section(pericope_id, parent_id, section_type, title, body_md, position)
                       VALUES (?,?,?,?,?,?)""", (pid, parent, stype, title, body, pos))
        section_id[title] = cur.lastrowid
        return cur.lastrowid

    sec1 = add_section("filologia",
                       "I. Tekst grecki (Nestle-Aland, wyd. 28) z przekładem roboczym i analizą filologiczną",
                       SECTION_I_INTRO, None, 1)
    block_id, unit_id = {}, {}
    for bpos, b in enumerate(BLOCKS, start=1):
        cur.execute("""INSERT INTO commentary_block(section_id, chapter_start, verse_start, chapter_end,
                       verse_end, label, greek_text, working_translation_pl, position)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (sec1, b["cs"], b["vs"], b["ce"], b["ve"], b["label"], b["greek"], b["transl"], bpos))
        block_id[b["label"]] = cur.lastrowid
        for upos, (phr, phr_pl, body) in enumerate(b["units"]):
            cur.execute("""INSERT INTO analysis_unit(block_id, phrase_greek, phrase_translation_pl, body_md, position)
                           VALUES (?,?,?,?,?)""",
                        (block_id[b["label"]], phr, phr_pl, body.strip(), upos))
            unit_id[(b["label"], upos)] = cur.lastrowid
    add_section("filologia", "Struktura całości", STRUKTURA.strip(), sec1, 99)

    # sekcja VIII (katena) przed Zakończeniem i Notą
    all_sections = SECTIONS[:-2] + [SECTION_VIII] + SECTIONS[-2:]
    for spos, s in enumerate(all_sections, start=2):
        top = add_section(s["type"], s["title"], s["body"], None, spos)
        for cpos, (ct, cb) in enumerate(s["children"], start=1):
            add_section(s["type"], ct, cb.strip(), top, cpos)

    lex_id = {}
    for lemma, tr, pos_, gl in LEXEMES:
        cur.execute("INSERT INTO lexeme(lemma, translit, pos, gloss_pl) VALUES (?,?,?,?)",
                    (lemma, tr, pos_, gl))
        lex_id[lemma] = cur.lastrowid

    sem_id = {}
    for term, tr, lang, gl in SEMITIC:
        cur.execute("INSERT INTO semitic_term(term, translit, lang, gloss_pl) VALUES (?,?,?,?)",
                    (term, tr, lang, gl))
        sem_id[tr] = cur.lastrowid

    for lemma, sem_tr, note in LEXEME_SEMITIC:
        cur.execute("INSERT INTO lexeme_semitic(lexeme_id, semitic_id, relation_note) VALUES (?,?,?)",
                    (lex_id[lemma], sem_id[sem_tr], note))

    for lemma, vn, form in OCCURRENCES:
        cur.execute("INSERT INTO lexeme_occurrence(lexeme_id, verse_id, form_in_text) VALUES (?,?,?)",
                    (lex_id[lemma], verse_id[vn], form))

    def source_cols(src):
        if src[0] == "pericope":
            return pid, None, None
        if src[0] == "section":
            return None, section_id[src[1]], None
        if src[0] == "unit":
            return None, None, unit_id[(src[1], src[2])]
        raise ValueError(src)

    for src, tb, cs, vs, ce, ve, label, rel, note in REFS:
        sp, ss, su = source_cols(src)
        cur.execute("""INSERT INTO scripture_ref(pericope_id, section_id, analysis_unit_id,
                       target_book_id, target_chapter_start, target_verse_start,
                       target_chapter_end, target_verse_end, target_label, relation, note_md)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (sp, ss, su, book_id[tb], cs, vs, ce, ve, label, rel, note))

    work_id = {}
    for author, title, title_pl, century, trad in WORKS:
        cur.execute("INSERT INTO work(author, title, title_pl, century, tradition) VALUES (?,?,?,?,?)",
                    (author, title, title_pl, century, trad))
        work_id[(author, title)] = cur.lastrowid

    for author, locus, src, note, title in CITATIONS:
        sp, ss, su = source_cols(src) if src[0] != "pericope" else (pid, None, None)
        cur.execute("""INSERT INTO citation(work_id, locus, pericope_id, section_id, analysis_unit_id, note_md)
                       VALUES (?,?,?,?,?,?)""",
                    (work_id[(author, title)], locus, sp, ss, su, note))

    for rite, occ, passage, desc in LITURGY:
        cur.execute("""INSERT INTO liturgical_use(pericope_id, rite, occasion, passage, description_md)
                       VALUES (?,?,?,?,?)""", (pid, rite, occ, passage, desc))

    for vn, lemma, issue, readings, assessment in TEXTUAL_NOTES:
        cur.execute("""INSERT INTO textual_note(verse_id, lemma_text, issue, readings_md, assessment_md)
                       VALUES (?,?,?,?,?)""", (verse_id[vn], lemma, issue, readings, assessment))

    for name, desc, links in THEMES:
        cur.execute("INSERT INTO theme(name, description_md) VALUES (?,?)", (name, desc))
        tid = cur.lastrowid
        for link in links:
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
                        (tid, cols["pericope_id"], cols["section_id"], cols["block_id"], cols["analysis_unit_id"]))

    # KATENA PATRYSTYCZNA
    pos_per_block = {}
    for blabel, author, wtitle, locus, body in PATRISTIC:
        pos_per_block[blabel] = pos_per_block.get(blabel, 0) + 1
        cur.execute("""INSERT INTO patristic_comment(work_id, block_id, locus, body_md, position)
                       VALUES (?,?,?,?,?)""",
                    (work_id[(author, wtitle)], block_id[blabel], locus, body.strip(),
                     pos_per_block[blabel]))

    cur.execute("INSERT INTO revision_log(entity, entity_id, note) VALUES (?,?,?)",
                ("pericope", pid, "Migracja Prologu (J 1,1-14) + katena Ojców Kościoła"))

    con.commit()
    for t in ["book", "verse", "pericope", "section", "commentary_block", "analysis_unit",
              "lexeme", "semitic_term", "lexeme_semitic", "lexeme_occurrence",
              "scripture_ref", "work", "citation", "patristic_comment",
              "liturgical_use", "textual_note", "theme", "theme_link"]:
        n = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"{t:20s} {n:4d}")
    con.close()
    print(f"\nOK -> {DB}")

# ------------------------------------------------------------------
# 17. KONTYNUACJA: J 1,15-51 — pięć perykop
# ------------------------------------------------------------------
VERSES2 = {
    15: ("Ἰωάννης μαρτυρεῖ περὶ αὐτοῦ καὶ κέκραγεν λέγων· οὗτος ἦν ὃν εἶπον· ὁ ὀπίσω μου ἐρχόμενος ἔμπροσθέν μου γέγονεν, ὅτι πρῶτός μου ἦν.",
        "Jan świadczy o Nim i wołał głośno: Ten był, o którym powiedziałem: Ten, który za mną przychodzi, przede mną się stał, bo wcześniej ode mnie był."),
    16: ("ὅτι ἐκ τοῦ πληρώματος αὐτοῦ ἡμεῖς πάντες ἐλάβομεν καὶ χάριν ἀντὶ χάριτος·",
        "Z Jego bowiem pełni myśmy wszyscy otrzymali — i łaskę za łaską."),
    17: ("ὅτι ὁ νόμος διὰ Μωϋσέως ἐδόθη, ἡ χάρις καὶ ἡ ἀλήθεια διὰ Ἰησοῦ Χριστοῦ ἐγένετο.",
        "Bo Prawo zostało dane przez Mojżesza, łaska i prawda stała się przez Jezusa Chrystusa."),
    18: ("Θεὸν οὐδεὶς ἑώρακεν πώποτε· μονογενὴς θεὸς ὁ ὢν εἰς τὸν κόλπον τοῦ πατρὸς ἐκεῖνος ἐξηγήσατο.",
        "Boga nikt nigdy nie widział; Jednorodzony Bóg, który jest w łonie Ojca — On opowiedział."),
    19: ("Καὶ αὕτη ἐστὶν ἡ μαρτυρία τοῦ Ἰωάννου, ὅτε ἀπέστειλαν [πρὸς αὐτὸν] οἱ Ἰουδαῖοι ἐξ Ἱεροσολύμων ἱερεῖς καὶ Λευίτας ἵνα ἐρωτήσωσιν αὐτόν· σὺ τίς εἶ;",
        "A takie jest świadectwo Jana, gdy Żydzi z Jerozolimy posłali do niego kapłanów i lewitów, aby go zapytali: Ty kto jesteś?"),
    20: ("καὶ ὡμολόγησεν καὶ οὐκ ἠρνήσατο, καὶ ὡμολόγησεν ὅτι ἐγὼ οὐκ εἰμὶ ὁ χριστός.",
        "I wyznał, a nie zaprzeczył; i wyznał: Ja nie jestem Mesjaszem."),
    21: ("καὶ ἠρώτησαν αὐτόν· τί οὖν; σὺ Ἠλίας εἶ; καὶ λέγει· οὐκ εἰμί. ὁ προφήτης εἶ σύ; καὶ ἀπεκρίθη· οὔ.",
        "I zapytali go: Cóż więc? Ty jesteś Eliaszem? I mówi: Nie jestem. Ty jesteś Prorokiem? I odpowiedział: Nie."),
    22: ("εἶπαν οὖν αὐτῷ· τίς εἶ; ἵνα ἀπόκρισιν δῶμεν τοῖς πέμψασιν ἡμᾶς· τί λέγεις περὶ σεαυτοῦ;",
        "Powiedzieli mu więc: Kim jesteś? — abyśmy dali odpowiedź tym, którzy nas posłali. Co mówisz o samym sobie?"),
    23: ("ἔφη· ἐγὼ φωνὴ βοῶντος ἐν τῇ ἐρήμῳ· εὐθύνατε τὴν ὁδὸν κυρίου, καθὼς εἶπεν Ἠσαΐας ὁ προφήτης.",
        "Rzekł: Ja — głos wołającego na pustyni: Prostujcie drogę Pana, jak powiedział prorok Izajasz."),
    24: ("Καὶ ἀπεσταλμένοι ἦσαν ἐκ τῶν Φαρισαίων.",
        "A wysłani byli spośród faryzeuszów."),
    25: ("καὶ ἠρώτησαν αὐτὸν καὶ εἶπαν αὐτῷ· τί οὖν βαπτίζεις εἰ σὺ οὐκ εἶ ὁ χριστὸς οὐδὲ Ἠλίας οὐδὲ ὁ προφήτης;",
        "I zapytali go, i powiedzieli mu: Czemu więc chrzcisz, skoro ty nie jesteś ani Mesjaszem, ani Eliaszem, ani Prorokiem?"),
    26: ("ἀπεκρίθη αὐτοῖς ὁ Ἰωάννης λέγων· ἐγὼ βαπτίζω ἐν ὕδατι· μέσος ὑμῶν ἕστηκεν ὃν ὑμεῖς οὐκ οἴδατε,",
        "Odpowiedział im Jan, mówiąc: Ja chrzczę w wodzie; pośród was stoi Ten, którego wy nie znacie —"),
    27: ("ὁ ὀπίσω μου ἐρχόμενος, οὗ οὐκ εἰμὶ [ἐγὼ] ἄξιος ἵνα λύσω αὐτοῦ τὸν ἱμάντα τοῦ ὑποδήματος.",
        "Ten, który za mną przychodzi, któremu ja nie jestem godzien rozwiązać rzemienia sandała."),
    28: ("ταῦτα ἐν Βηθανίᾳ ἐγένετο πέραν τοῦ Ἰορδάνου, ὅπου ἦν ὁ Ἰωάννης βαπτίζων.",
        "To działo się w Betanii za Jordanem, gdzie Jan chrzcił."),
    29: ("Τῇ ἐπαύριον βλέπει τὸν Ἰησοῦν ἐρχόμενον πρὸς αὐτὸν καὶ λέγει· ἴδε ὁ ἀμνὸς τοῦ θεοῦ ὁ αἴρων τὴν ἁμαρτίαν τοῦ κόσμου.",
        "Nazajutrz widzi Jezusa przychodzącego ku niemu i mówi: Oto Baranek Boży, który dźwiga grzech świata."),
    30: ("οὗτός ἐστιν ὑπὲρ οὗ ἐγὼ εἶπον· ὀπίσω μου ἔρχεται ἀνὴρ ὃς ἔμπροσθέν μου γέγονεν, ὅτι πρῶτός μου ἦν.",
        "Ten jest, o którym ja powiedziałem: Za mną przychodzi mąż, który przede mną się stał, bo wcześniej ode mnie był."),
    31: ("κἀγὼ οὐκ ᾔδειν αὐτόν, ἀλλ᾿ ἵνα φανερωθῇ τῷ Ἰσραὴλ διὰ τοῦτο ἦλθον ἐγὼ ἐν ὕδατι βαπτίζων.",
        "I ja Go nie znałem; ale po to przyszedłem, chrzcząc w wodzie, aby został objawiony Izraelowi."),
    32: ("Καὶ ἐμαρτύρησεν Ἰωάννης λέγων ὅτι τεθέαμαι τὸ πνεῦμα καταβαῖνον ὡς περιστερὰν ἐξ οὐρανοῦ καὶ ἔμεινεν ἐπ᾿ αὐτόν.",
        "I zaświadczył Jan, mówiąc: Oglądałem Ducha zstępującego jak gołębica z nieba — i pozostał na Nim."),
    33: ("κἀγὼ οὐκ ᾔδειν αὐτόν, ἀλλ᾿ ὁ πέμψας με βαπτίζειν ἐν ὕδατι ἐκεῖνός μοι εἶπεν· ἐφ᾿ ὃν ἂν ἴδῃς τὸ πνεῦμα καταβαῖνον καὶ μένον ἐπ᾿ αὐτόν, οὗτός ἐστιν ὁ βαπτίζων ἐν πνεύματι ἁγίῳ.",
        "I ja Go nie znałem; ale Ten, który mnie posłał chrzcić w wodzie, On mi powiedział: Na kogo zobaczysz Ducha zstępującego i pozostającego na Nim — Ten jest, który chrzci w Duchu Świętym."),
    34: ("κἀγὼ ἑώρακα καὶ μεμαρτύρηκα ὅτι οὗτός ἐστιν ὁ υἱὸς τοῦ θεοῦ.",
        "I ja zobaczyłem, i zaświadczyłem: Ten jest Synem Bożym."),
    35: ("Τῇ ἐπαύριον πάλιν εἱστήκει ὁ Ἰωάννης καὶ ἐκ τῶν μαθητῶν αὐτοῦ δύο",
        "Nazajutrz znowu stał Jan i dwaj z jego uczniów."),
    36: ("καὶ ἐμβλέψας τῷ Ἰησοῦ περιπατοῦντι λέγει· ἴδε ὁ ἀμνὸς τοῦ θεοῦ.",
        "I wpatrzywszy się w Jezusa przechodzącego, mówi: Oto Baranek Boży."),
    37: ("καὶ ἤκουσαν οἱ δύο μαθηταὶ αὐτοῦ λαλοῦντος καὶ ἠκολούθησαν τῷ Ἰησοῦ.",
        "I usłyszeli dwaj jego uczniowie, jak mówił, i poszli za Jezusem."),
    38: ("στραφεὶς δὲ ὁ Ἰησοῦς καὶ θεασάμενος αὐτοὺς ἀκολουθοῦντας λέγει αὐτοῖς· τί ζητεῖτε; οἱ δὲ εἶπαν αὐτῷ· ῥαββί, ὃ λέγεται μεθερμηνευόμενον διδάσκαλε, ποῦ μένεις;",
        "Jezus zaś, odwróciwszy się i zobaczywszy ich idących za Nim, mówi im: Czego szukacie? Oni powiedzieli Mu: Rabbi — co się tłumaczy: Nauczycielu — gdzie mieszkasz?"),
    39: ("λέγει αὐτοῖς· ἔρχεσθε καὶ ὄψεσθε. ἦλθαν οὖν καὶ εἶδαν ποῦ μένει καὶ παρ᾿ αὐτῷ ἔμειναν τὴν ἡμέραν ἐκείνην· ὥρα ἦν ὡς δεκάτη.",
        "Mówi im: Przyjdźcie, a zobaczycie. Przyszli więc i zobaczyli, gdzie mieszka, i pozostali u Niego owego dnia; a była godzina około dziesiątej."),
    40: ("Ἦν Ἀνδρέας ὁ ἀδελφὸς Σίμωνος Πέτρου εἷς ἐκ τῶν δύο τῶν ἀκουσάντων παρὰ Ἰωάννου καὶ ἀκολουθησάντων αὐτῷ·",
        "Andrzej, brat Szymona Piotra, był jednym z dwóch, którzy usłyszeli od Jana i poszli za Nim."),
    41: ("εὑρίσκει οὗτος πρῶτον τὸν ἀδελφὸν τὸν ἴδιον Σίμωνα καὶ λέγει αὐτῷ· εὑρήκαμεν τὸν Μεσσίαν, ὅ ἐστιν μεθερμηνευόμενον χριστός.",
        "Znajduje on najpierw brata swego, Szymona, i mówi mu: Znaleźliśmy Mesjasza — co się tłumaczy: Chrystus."),
    42: ("ἤγαγεν αὐτὸν πρὸς τὸν Ἰησοῦν. ἐμβλέψας αὐτῷ ὁ Ἰησοῦς εἶπεν· σὺ εἶ Σίμων ὁ υἱὸς Ἰωάννου, σὺ κληθήσῃ Κηφᾶς, ὃ ἑρμηνεύεται Πέτρος.",
        "Przyprowadził go do Jezusa. Wpatrzywszy się w niego, Jezus powiedział: Ty jesteś Szymon, syn Jana; ty będziesz nazwany Kefas — co się tłumaczy: Piotr."),
    43: ("Τῇ ἐπαύριον ἠθέλησεν ἐξελθεῖν εἰς τὴν Γαλιλαίαν καὶ εὑρίσκει Φίλιππον. καὶ λέγει αὐτῷ ὁ Ἰησοῦς· ἀκολούθει μοι.",
        "Nazajutrz postanowił wyruszyć do Galilei i znajduje Filipa. I mówi mu Jezus: Pójdź za Mną."),
    44: ("ἦν δὲ ὁ Φίλιππος ἀπὸ Βηθσαϊδά, ἐκ τῆς πόλεως Ἀνδρέου καὶ Πέτρου.",
        "A Filip był z Betsaidy, z miasta Andrzeja i Piotra."),
    45: ("εὑρίσκει Φίλιππος τὸν Ναθαναὴλ καὶ λέγει αὐτῷ· ὃν ἔγραψεν Μωϋσῆς ἐν τῷ νόμῳ καὶ οἱ προφῆται εὑρήκαμεν, Ἰησοῦν υἱὸν τοῦ Ἰωσὴφ τὸν ἀπὸ Ναζαρέτ.",
        "Filip znajduje Natanaela i mówi mu: Znaleźliśmy Tego, o którym pisał Mojżesz w Prawie i Prorocy — Jezusa, syna Józefa, z Nazaretu."),
    46: ("καὶ εἶπεν αὐτῷ Ναθαναήλ· ἐκ Ναζαρὲτ δύναταί τι ἀγαθὸν εἶναι; λέγει αὐτῷ [ὁ] Φίλιππος· ἔρχου καὶ ἴδε.",
        "I powiedział mu Natanael: Czy z Nazaretu może być coś dobrego? Mówi mu Filip: Przyjdź i zobacz."),
    47: ("εἶδεν ὁ Ἰησοῦς τὸν Ναθαναὴλ ἐρχόμενον πρὸς αὐτὸν καὶ λέγει περὶ αὐτοῦ· ἴδε ἀληθῶς Ἰσραηλίτης ἐν ᾧ δόλος οὐκ ἔστιν.",
        "Zobaczył Jezus Natanaela przychodzącego ku Niemu i mówi o nim: Oto prawdziwie Izraelita, w którym nie ma podstępu."),
    48: ("λέγει αὐτῷ Ναθαναήλ· πόθεν με γινώσκεις; ἀπεκρίθη Ἰησοῦς καὶ εἶπεν αὐτῷ· πρὸ τοῦ σε Φίλιππον φωνῆσαι ὄντα ὑπὸ τὴν συκῆν εἶδόν σε.",
        "Mówi Mu Natanael: Skąd mnie znasz? Odpowiedział Jezus i rzekł mu: Zanim cię Filip zawołał, widziałem cię, gdy byłeś pod figowcem."),
    49: ("ἀπεκρίθη αὐτῷ Ναθαναήλ· ῥαββί, σὺ εἶ ὁ υἱὸς τοῦ θεοῦ, σὺ βασιλεὺς εἶ τοῦ Ἰσραήλ.",
        "Odpowiedział Mu Natanael: Rabbi, Ty jesteś Synem Bożym, Ty jesteś Królem Izraela."),
    50: ("ἀπεκρίθη Ἰησοῦς καὶ εἶπεν αὐτῷ· ὅτι εἶπόν σοι ὅτι εἶδόν σε ὑποκάτω τῆς συκῆς, πιστεύεις; μείζω τούτων ὄψῃ.",
        "Odpowiedział Jezus i rzekł mu: Wierzysz, bo ci powiedziałem, że cię widziałem pod figowcem? Większe od tych rzeczy zobaczysz."),
    51: ("καὶ λέγει αὐτῷ· ἀμὴν ἀμὴν λέγω ὑμῖν, ὄψεσθε τὸν οὐρανὸν ἀνεῳγότα καὶ τοὺς ἀγγέλους τοῦ θεοῦ ἀναβαίνοντας καὶ καταβαίνοντας ἐπὶ τὸν υἱὸν τοῦ ἀνθρώπου.",
        "I mówi mu: Amen, amen, mówię wam: zobaczycie niebo otwarte i aniołów Bożych wstępujących i zstępujących na Syna Człowieczego."),
}

BOOKS2 = [
    ("Pwt", "Księga Powtórzonego Prawa", "ST", 5),
    ("Pnp", "Pieśń nad Pieśniami",       "ST", 21),
    ("Mi",  "Księga Micheasza",          "ST", 39),
    ("So",  "Księga Sofoniasza",         "ST", 42),
    ("Za",  "Księga Zachariasza",        "ST", 44),
    ("Ml",  "Księga Malachiasza",        "ST", 45),
    ("Dn",  "Księga Daniela",            "ST", 32),
    ("Mt",  "Ewangelia według św. Mateusza", "NT", 47),
    ("Mk",  "Ewangelia według św. Marka",    "NT", 48),
]

LEXEMES2 = [
    ("πλήρωμα", "pleroma", "rzeczownik", "pełnia (później słowo-klucz gnozy — tu wcześniejsze i ortodoksyjne)"),
    ("ἐξηγέομαι", "eksegeomai", "czasownik", '''wyłożyć, opowiedzieć, objaśnić (stąd „egzegeza")'''),
    ("κόλπος", "kolpos", "rzeczownik", "łono, pierś, zanadrze (bliskość przy stole — por. J 13,23)"),
    ("νόμος", "nomos", "rzeczownik", "Prawo, Tora"),
    ("φωνή", "phone", "rzeczownik", "głos (w kontraście do λόγος — słowa)"),
    ("βαπτίζω", "baptizo", "czasownik", "zanurzać, chrzcić"),
    ("ἀμνός", "amnos", "rzeczownik", "baranek (aram. talja: baranek i sługa zarazem)"),
    ("αἴρω", "airo", "czasownik", "podnosić, dźwigać, usuwać (celowa dwuznaczność w 1,29)"),
    ("ἁμαρτία", "hamartia", "rzeczownik", "grzech (w 1,29 w liczbie pojedynczej: grzech świata jako całość)"),
    ("πνεῦμα", "pneuma", "rzeczownik", "duch, tchnienie, wiatr (hebr. ruach)"),
    ("μένω", "meno", "czasownik", "pozostawać, trwać, mieszkać — wielkie słowo Janowe (ok. 40 wystąpień)"),
    ("ἀκολουθέω", "akoloutheo", "czasownik", "iść za, towarzyszyć — techniczne słowo uczniostwa"),
    ("ζητέω", "zeteo", "czasownik", "szukać"),
    ("εὑρίσκω", "heurisko", "czasownik", '''znajdować (łańcuch „znalezień" w 1,41-45)'''),
    ("Μεσσίας", "Messias", "rzeczownik", "Mesjasz — semicka forma w greckim tekście (tylko J 1,41 i 4,25 w NT)"),
    ("Χριστός", "Christos", "rzeczownik", "Pomazaniec, Chrystus (grecki przekład: masziach)"),
    ("ῥαββί", "rabbi", "rzeczownik", "rabbi, mój mistrzu (transliteracja hebr.)"),
    ("ἀμήν", "amen", "partykuła", "amen — zaprawdę; podwojone tylko u Jana (25 razy)"),
    ("ἐμβλέπω", "emblepo", "czasownik", "wpatrzeć się, spojrzeć przenikliwie (spojrzenie Jezusa: 1,42; Chrzciciela: 1,36)"),
    ("δόλος", "dolos", "rzeczownik", "podstęp, fałsz (antyteza Jakuba-oszusta z Rdz 27)"),
]

SEMITIC2 = [
    ("טַלְיָא", "talja", "aram", "baranek / sługa / dziecko — trójznaczność za ἀμνός w 1,29"),
    ("מָשִׁיחַ", "masziach", "hbr", "pomazaniec, namaszczony"),
    ("כֵּיפָא", "kefa", "aram", "skała, opoka — nowe imię Szymona"),
    ("רַבִּי", "rabbi", "hbr", "mój wielki, mój mistrzu"),
    ("אָמֵן", "amen", "hbr", "niech się stanie; od rdzenia aman — być pewnym, wiernym (por. emet)"),
    ("בַּר אֱנָשׁ", "bar enasz", "aram", "syn człowieczy (Dn 7,13) — tło tytułu ὁ υἱὸς τοῦ ἀνθρώπου"),
    ("נָבִיא", "nawi", "hbr", '''prorok; „ha-nawi" — Prorok obiecany w Pwt 18,15'''),
]

LEXSEM2 = [
    ("ἀμνός", "talja", "aramejskie talja znaczy i baranek, i sługa — most między Iz 53 a barankiem paschalnym"),
    ("Μεσσίας", "masziach", "surowa transliteracja — ślad aramejskiego środowiska pierwszych uczniów"),
    ("Χριστός", "masziach", "grecki przekład tytułu"),
    ("ῥαββί", "rabbi", "tytuł nauczycielski, który Jan za każdym razem tłumaczy czytelnikowi"),
    ("ἀμήν", "amen", "od rdzenia aman (być pewnym) — pokrewne emet (prawda)"),
    ("υἱός", "bar enasz", '''Dn 7,13: „jakby syn człowieczy" na obłokach — tło J 1,51'''),
]

OCC2 = [
    ("μαρτυρέω", 15, "μαρτυρεῖ"), ("μαρτυρία", 19, "μαρτυρία"),
    ("μαρτυρέω", 32, "ἐμαρτύρησεν"), ("μαρτυρέω", 34, "μεμαρτύρηκα"),
    ("πλήρωμα", 16, "πληρώματος"), ("λαμβάνω", 16, "ἐλάβομεν"),
    ("χάρις", 16, "χάριν ἀντὶ χάριτος"), ("χάρις", 17, "χάρις"),
    ("ἀλήθεια", 17, "ἀλήθεια"), ("νόμος", 17, "νόμος"),
    ("γίνομαι", 17, "ἐγένετο"), ("μονογενής", 18, "μονογενής"),
    ("θεός", 18, "θεόν / θεός"), ("κόλπος", 18, "κόλπον"),
    ("ἐξηγέομαι", 18, "ἐξηγήσατο"),
    ("φωνή", 23, "φωνή"), ("βαπτίζω", 25, "βαπτίζεις"),
    ("βαπτίζω", 26, "βαπτίζω"), ("βαπτίζω", 33, "βαπτίζων"),
    ("ἀμνός", 29, "ἀμνός"), ("αἴρω", 29, "αἴρων"),
    ("ἁμαρτία", 29, "ἁμαρτίαν"), ("κόσμος", 29, "κόσμου"),
    ("πνεῦμα", 32, "πνεῦμα"), ("πνεῦμα", 33, "πνεύματι"),
    ("μένω", 32, "ἔμεινεν"), ("μένω", 33, "μένον"),
    ("θεάομαι", 32, "τεθέαμαι"), ("υἱός", 34, "υἱός"),
    ("ἀμνός", 36, "ἀμνός"), ("ἐμβλέπω", 36, "ἐμβλέψας"),
    ("ἀκολουθέω", 37, "ἠκολούθησαν"), ("ἀκολουθέω", 38, "ἀκολουθοῦντας"),
    ("θεάομαι", 38, "θεασάμενος"), ("ζητέω", 38, "ζητεῖτε"),
    ("ῥαββί", 38, "ῥαββί"), ("μένω", 38, "μένεις"),
    ("μένω", 39, "μένει / ἔμειναν"),
    ("ἀκολουθέω", 40, "ἀκολουθησάντων"), ("εὑρίσκω", 41, "εὑρίσκει / εὑρήκαμεν"),
    ("Μεσσίας", 41, "Μεσσίαν"), ("Χριστός", 41, "χριστός"),
    ("ἐμβλέπω", 42, "ἐμβλέψας"),
    ("εὑρίσκω", 43, "εὑρίσκει"), ("ἀκολουθέω", 43, "ἀκολούθει"),
    ("εὑρίσκω", 45, "εὑρίσκει / εὑρήκαμεν"), ("νόμος", 45, "νόμῳ"),
    ("δόλος", 47, "δόλος"), ("γινώσκω", 48, "γινώσκεις"),
    ("ῥαββί", 49, "ῥαββί"), ("υἱός", 49, "υἱός"),
    ("πιστεύω", 50, "πιστεύεις"), ("ἀμήν", 51, "ἀμὴν ἀμήν"),
    ("υἱός", 51, "υἱὸν τοῦ ἀνθρώπου"),
]

def _gk(a, b):
    return " ".join(VERSES2[v][0] for v in range(a, b + 1))
def _pl(a, b):
    return " ".join(VERSES2[v][1] for v in range(a, b + 1))

# ------------------------------------------------------------------
# PERYKOPA 2: J 1,15-18 — Dopełnienie Prologu
# ------------------------------------------------------------------
P2 = {
 "pericope": {"cs":1,"vs":15,"ce":1,"ve":18,"title":"Dopełnienie Prologu",
              "motto":"Gratia et veritas per Iesum Christum (Łaska i prawda przez Jezusa Chrystusa)",
              "status":"w_opracowaniu","position":2},
 "intro": "Wersety 15–18 domykają hymn: powraca świadectwo Chrzciciela (klamra z w. 6–8), a Prolog kończy się tam, gdzie się zaczął — przy Bogu, którego nikt nie widział, i przy Jednorodzonym, który Go opowiedział.",
 "blocks": [
 {"label":"w. 15","cs":1,"vs":15,"ce":1,"ve":15,"greek":VERSES2[15][0],"transl":VERSES2[15][1],
  "units":[
  ("κέκραγεν","wołał głośno (perfectum)",
"""Perfectum κέκραγεν (zawołał — i wołanie trwa) obok praesens μαρτυρεῖ (świadczy): świadectwo Jana nie jest epizodem z przeszłości, lecz głosem, który wciąż brzmi w Kościele — ewangelista celowo miesza czasy, jakby Chrzciciel wołał znad kart księgi. To samo perfectum opisze w w. 34 dopełnione świadectwo: μεμαρτύρηκα (zaświadczyłem — i świadectwo stoi)."""),
  ("πρῶτός μου ἦν","wcześniej ode mnie był",
"""Paradoks czasowy w jednym zdaniu: ὁ ὀπίσω μου ἐρχόμενος (przychodzący za mną — czyli późniejszy: młodszy kuzyn, uczeń idący za mistrzem) ἔμπροσθέν μου γέγονεν (stał się przede mną — wyprzedził mnie godnością), ὅτι πρῶτός μου ἦν (bo pierwszy ode mnie był). Racją pierwszeństwa nie jest kariera, lecz preegzystencja: wraca imperfectum ἦν (był) z w. 1. Chrzciciel — pierwszy egzegeta Prologu — wyprowadza hierarchię z metafizyki: kto był na początku, temu należy się pierwsze miejsce w historii."""),
  ]},
 {"label":"w. 16","cs":1,"vs":16,"ce":1,"ve":16,"greek":VERSES2[16][0],"transl":VERSES2[16][1],
  "units":[
  ("πλήρωμα","pełnia",
"""Πλήρωμα (pełnia) — słowo, które w II wieku gnostycy uczynią nazwą świata boskich eonów; Jan używa go wcześniej i prościej: w Chrystusie mieszka pełnia (por. Kol 1,19; 2,9), a my czerpiemy z niej jak ze źródła, które się nie umniejsza. Ἡμεῖς πάντες (my wszyscy) — pierwsza osoba liczby mnogiej włącza czytelnika: hymn przestaje opowiadać, a zaczyna wyznawać."""),
  ("χάριν ἀντὶ χάριτος","łaskę za łaską",
"""Przyimek ἀντί znaczy „w zamian za, w miejsce" — stąd dwie lektury: łaska *po* łasce (fala za falą, nieustanny przypływ) albo łaska *w miejsce* łaski (Nowe Przymierze w miejsce daru Starego — tak czytał już Chryzostom, a w. 17 tę lekturę wspiera). Obie prawdziwe i pewnie obie zamierzone: ekonomia zbawienia nie zna próżni — jedna łaska ustępuje tylko większej."""),
  ]},
 {"label":"w. 17","cs":1,"vs":17,"ce":1,"ve":17,"greek":VERSES2[17][0],"transl":VERSES2[17][1],
  "units":[
  ("ἐδόθη / ἐγένετο","zostało dane / stała się",
"""Precyzja czasowników: Prawo ἐδόθη (zostało dane) — przekazane przez pośrednika, jak paczka z rąk do rąk; łaska i prawda ἐγένετο (stała się) — wydarzyła się osobiście, przyszła sama w Tym, który jest πλήρης χάριτος καὶ ἀληθείας (pełen łaski i prawdy, w. 14). Jedyne miejsce Prologu, gdzie pada imię Ἰησοῦς Χριστός — hymn, który zaczął się od bezimiennego Λόγος (Słowa), kończy się imieniem własnym: metafizyka znalazła twarz. Zestawienie nie jest antytezą (Prawo też od Boga — „zostało dane"), lecz gradacją: sługa i Syn, zapowiedź i spełnienie."""),
  ]},
 {"label":"w. 18","cs":1,"vs":18,"ce":1,"ve":18,"greek":VERSES2[18][0],"transl":VERSES2[18][1],
  "units":[
  ("μονογενὴς θεός","Jednorodzony Bóg",
"""Najmocniejsza lekcja tekstu w całym Prologu: μονογενὴς θεός (Jednorodzony Bóg) — tak najstarsi i najlepsi świadkowie (P66, P75, Sinaiticus, Vaticanus); tradycja bizantyjska i łacińska czytają ὁ μονογενὴς υἱός (Jednorodzony Syn), stąd „Syn" w większości starych przekładów. NA28 przyjmuje lekcję trudniejszą — a ona domyka klamrę z w. 1: hymn otwiera θεὸς ἦν ὁ λόγος (Bogiem było Słowo) i zamyka μονογενὴς θεός (Jednorodzony Bóg). Prolog jest otoczony bóstwem Słowa jak nawiasem."""),
  ("ὁ ὢν εἰς τὸν κόλπον τοῦ πατρός","który jest w łonie Ojca",
"""Κόλπος (łono, pierś, zanadrze) — obraz z semickiej uczty: spoczywać u czyjegoś łona znaczy zajmować miejsce najbliższe, miejsce powiernika. Jan użyje tego samego słowa tylko raz jeszcze — o sobie: uczeń spoczywający ἐν τῷ κόλπῳ τοῦ Ἰησοῦ (na piersi Jezusa, J 13,23). Łańcuch bliskości jest zamierzony: Syn w łonie Ojca — uczeń na piersi Syna — czytelnik przy świadectwie ucznia. Participium ὁ ὤν (będący, Ten-który-jest) brzmi jak echo imienia Bożego z Wj 3,14 w LXX: ὁ ὤν (Jestem-który-Jestem)."""),
  ("ἐξηγήσατο","opowiedział, wyłożył",
"""Ostatnie słowo Prologu: ἐξηγήσατο — od ἐξηγέομαι (wyprowadzać na jaw, wykładać, opowiadać), skąd nasza „egzegeza". Termin techniczny: tak nazywano objaśnianie praw, misteriów i wyroczni. Boga nikt nigdy nie zobaczył — ale Jednorodzony Go *wyegzegezował*: całe życie Jezusa jest egzegezą Ojca. Zdanie to jest też najgłębszym uzasadnieniem niniejszej pracy: skoro Syn jest egzegetą Ojca, egzegeza Ewangelii jest czytaniem wykładu, nie zgadywaniem tajemnicy."""),
  ]},
 ],
 "sections": [
 {"type":"kontekst","title":"II. Kontekst historyczny, językowy, kulturowy i religijny","body":
"""Wersety 15–18 wykazują tę samą dwuwarstwowość co cały Prolog. **Pełnia i łaska.** Χάριν ἀντὶ χάριτος (łaskę za łaską) czytane na tle hebrajskim odsyła do chesed (łaski wiernej przymierzu) z Wj 34,6 — formuły przywołanej już w w. 14; w. 17 wymienia tę teofanię z imienia, zestawiając Mojżesza z Jezusem. **Nikt nie widział Boga.** To aksjomat Synaju: „nie może człowiek ujrzeć mojego oblicza i pozostać przy życiu" (Wj 33,20); judaizm Drugiej Świątyni obchodził go wizjami pośredniczącymi (anioł Pana, kawod — chwała, Memra — Słowo). Jan nie łagodzi aksjomatu — zaostrza go (οὐδεὶς πώποτε — nikt nigdy), by tym mocniej zabrzmiało wyłączne roszczenie: jedyny wykładowca Ojca jest w Jego łonie. **Polemika.** W. 17 nie jest antynomizmem (odrzuceniem Prawa): dla wspólnoty wyrzuconej z synagogi jest odpowiedzią na zarzut zdrady Tory — nie porzuciliśmy daru Mojżesza, przyjęliśmy Tego, ku któremu dar prowadził.""",
  "children":[]},
 {"type":"teologia","title":"III. Obserwacje teologiczne i filozoficzne w duchu tomistycznym","body":
"""**1. Pełnia jako źródło.** Tomasz rozróżnia pełnię *intensywną* (łaska Chrystusa co do istoty) i pełnię *sprawczą* (łaska głowy — *gratia capitis* — z której czerpią członki): w. 16 mówi o tej drugiej. Czerpanie z pełni nie umniejsza źródła, jak wiedza nauczyciela nie ubywa przez nauczanie — uczestnictwo (*participatio*) nie jest podziałem.

**2. Prawo i łaska.** Po tomistycznie w. 17 to nie opozycja, lecz porządek: Prawo poucza, czego unikać, ale nie daje sił (*lex vetus ostendit peccatum, non tollit* — Prawo stare pokazuje grzech, lecz go nie gładzi); łaska jest nowym Prawem wpisanym w serce — *lex nova est ipsa gratia Spiritus Sancti* (nowym Prawem jest sama łaska Ducha Świętego). Stąd ciągłość bez zrównania.

**3. Poznanie Boga.** „Boga nikt nigdy nie widział" — Tomasz doda: w tym życiu; wizja istoty Bożej (*visio essentiae*) przekracza siły natury, a jednak jest celem człowieka. W. 18 wskazuje jedyną drogę: Syn opowiada Ojca — objawienie nie zastępuje wizji, lecz ją zapowiada i do niej prowadzi; wiara jest zaczątkiem widzenia (*fides est inchoatio visionis*).""",
  "children":[]},
 {"type":"autor_ludzki","title":"IV. Autor ludzki: kim jest i co chce przekazać","body":
"""Ewangelista wykonuje tu ruch redaktorski o dużej samoświadomości: wplata głos Chrzciciela (w. 15) w sam środek hymnu i przechodzi z „on" na „my" (w. 16) — świadectwo jednostki staje się wyznaniem wspólnoty, a wspólnota wciąga czytelnika. Zamknięcie na ἐξηγήσατο (opowiedział) jest programowe: cała księga, która teraz nastąpi, będzie tym opowiadaniem — od Kany po pusty grób. Prolog okazuje się spisem treści napisanym językiem hymnu.""",
  "children":[]},
 {"type":"autor_bozy","title":"V. Autor Boży: co Duch Święty chce przekazać","body":
"""Duch Święty domyka objawienie trynitarne Prologu: w. 18 odsłania, że wieczne πρὸς τὸν θεόν (ku Bogu) z w. 1 jest relacją synowską — łonem Ojca. Zarazem ustanawia zasadę wszelkiej teologii: o Bogu prawdziwie mówi tylko to, co opowiedział Jednorodzony; każda inna mowa o Bogu jest domysłem albo echem. Sens dla czytelnika: nie musisz zdobywać Niewidzialnego — masz Jego egzegezę; przyjmij wykład, a Wykładający wprowadzi cię tam, skąd mówi.""",
  "children":[]},
 {"type":"odniesienia","title":"VI. Sieć odniesień biblijnych","body":
"""**Wj 33,18–23; 34,6 → w. 17–18.** Mojżesz prosił o widzenie chwały i usłyszał imię „bogaty w łaskę i wierność" — nie widząc oblicza. Prolog dopowiada obie połowy: łaska i prawda *stały się*, a Niewidzialnego *opowiedział* Ten, który Go widzi odwiecznie.

**Kol 1,19; 2,9 → w. 16.** Pawłowe „w Nim mieszka cała pełnia" — niezależne poświadczenie tej samej wiary w πλήρωμα (pełnię) Chrystusa.

**Wj 3,14 (LXX) → w. 18.** Ὁ ὤν (Będący) — participium z imienia Bożego powraca w opisie Syna „będącego w łonie Ojca".

**J 13,23 → w. 18.** Κόλπος (łono): jedyne dwa użycia w Ewangelii wiążą Syna z Ojcem i ucznia z Jezusem — łańcuch przekazu objawienia.

**Mt 11,27 → w. 18.** „Nikt nie zna Ojca, tylko Syn i ten, komu Syn zechce objawić" — synoptyczna paralela Janowego roszczenia wyłączności.""",
  "children":[]},
 {"type":"recepcja","title":"VII. Znaczenie w historii i liturgii Kościoła","body":
"""W sporach IV wieku w. 18 był tekstem rozstrzygającym po obu stronach — dlatego historia jego lekcji (μονογενὴς θεός / ὁ μονογενὴς υἱός) jest sama kartą historii dogmatu; formuła nicejska „Bóg z Boga" brzmi jak jego parafraza. Liturgicznie w. 15–18 żyją w pełnej formie Ewangelii Bożego Narodzenia: Msza w dzień dopuszcza J 1,1–18, a II Niedziela po Narodzeniu Pańskim czyta cały Prolog z w. 18 jako puentą. Χάριν ἀντὶ χάριτος (łaska za łaską) weszło do języka duchowości jako opis życia sakramentalnego — nieustannej wymiany darów.""",
  "children":[]},
 {"type":"patrystyka","title":"VIII. Komentarze Ojców Kościoła (catena patrum)","body":
"""Katena do dopełnienia Prologu — trzy głosy o pełni, łasce i łonie Ojca.""",
  "children":[]},
 ],
 "refs": [
 (("pericope",), "Wj", 33, 18, 33, 23, "Wj 33,18–23", "kontrast", "Mojżeszowi odmówiono widzenia — w. 18 ogłasza Widzącego odwiecznie"),
 (("pericope",), "Wj", 34, 6, 34, 6, "Wj 34,6", "aluzja", "chesed we'emet — łaska i prawda, teraz z imieniem Jezusa Chrystusa (w. 17)"),
 (("pericope",), "Wj", 3, 14, 3, 14, "Wj 3,14", "aluzja", "ὁ ὤν (Będący) — participium imienia Bożego w opisie Syna"),
 (("pericope",), "Kol", 1, 19, 1, 19, "Kol 1,19", "paralela", "w Nim mieszka cała pełnia (πλήρωμα)"),
 (("pericope",), "J", 13, 23, 13, 23, "J 13,23", "paralela", "uczeń na piersi Jezusa — drugie i ostatnie κόλπος Ewangelii"),
 (("pericope",), "Mt", 11, 27, 11, 27, "Mt 11,27", "paralela", "nikt nie zna Ojca, tylko Syn — synoptyczne echo w. 18"),
 (("unit","w. 16",1), "J", 21, 25, 21, 25, "J 21,25", "por", "niewyczerpalność: świat nie pomieściłby ksiąg"),
 ],
 "patristic": [
 ("w. 16", "św. Jan Chryzostom", "Homilie na Ewangelię Jana", "Hom. in Io. 14",
"""Pełnia jest jak źródło: my czerpiemy strumieniami, źródło pozostaje pełne. Chryzostom podkreśla różnicę uczestnictwa: prorocy mieli dary — On ma pełnię; oni otrzymali miarę — z Niego miara płynie dla wszystkich. „Łaskę za łaską" czyta jako wymianę Przymierzy: otrzymaliśmy Nowe w miejsce Starego — a i Stare było łaską, bo od tego samego Boga; różnica nie biegnie między gniewem a miłością, lecz między zadatkiem a dziedzictwem."""),
 ("w. 17", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 3,8–10",
"""*Gratia pro gratia* (łaska za łaskę): Augustyn pyta — jaka za jaką? I odpowiada: za łaskę wiary, którą teraz żyjemy, otrzymamy łaskę życia wiecznego; nawet zasługa jest łaską ukoronowaną łaską, bo Bóg „wieńczy w nas własne dary". Prawo zostało dane przez sługę i uczyniło winnych; łaska przyszła przez Króla i winnych uwolniła — Prawo groziło, nie leczyło; przyszedł Lekarz i chorego, którego litera oskarżała, duch ożywił."""),
 ("w. 18", "św. Cyryl Aleksandryjski", "Commentarii in Ioannem", "In Io., ks. I",
"""Κόλπος (łono) czyta Cyryl ontologicznie: być w łonie Ojca to być z Jego istoty — obraz mówi o współistotności, nie o miejscu. Dlatego tylko Ten może „opowiedzieć" Boga: egzegeta Ojca musi być tym, co wykłada; stworzenie opowiadałoby ze słyszenia, Syn opowiada z widzenia — a raczej z bycia. Objawienie chrześcijańskie nie jest raportem o Bogu, lecz samoudzieleniem się Boga w Tym, który z Jego łona nigdy nie wyszedł, choć do nas przyszedł."""),
 ],
 "liturgy": [
 ("rzymski", "Ewangelia Mszy w dzień Narodzenia Pańskiego (forma pełna) i II Niedzieli po Narodzeniu", "J 1,1–18",
  "Wersety 15–18 wieńczą uroczystą proklamację Prologu; w. 18 jest liturgiczną puentą tajemnicy Narodzenia."),
 ],
 "textual": [
 (18, "μονογενὴς θεός", "wariant lekcji",
  "μονογενὴς θεός: P66, P75, ℵ, B (aleksandryjskie, najstarsze); ὁ μονογενὴς υἱός: A, tradycja bizantyjska, Wulgata i przekłady zależne.",
  "NA28 przyjmuje μονογενὴς θεός jako lekcję najlepiej poświadczoną i trudniejszą; domyka ona inkluzję z w. 1c (θεὸς ἦν ὁ λόγος)."),
 ],
 "themes": [
 ("ἦν / ἐγένετο — trwanie a stawanie się", ("block","w. 17")),
 ("Szechina — zamieszkanie Boga", ("block","w. 18")),
 ],
}

# ------------------------------------------------------------------
# PERYKOPA 3: J 1,19-28 — Świadectwo Jana Chrzciciela
# ------------------------------------------------------------------
P3 = {
 "pericope": {"cs":1,"vs":19,"ce":1,"ve":28,"title":"Świadectwo Jana Chrzciciela",
              "motto":"Vox clamantis in deserto (Głos wołającego na pustyni)",
              "status":"w_opracowaniu","position":3},
 "intro": "Kończy się hymn, zaczyna narracja — i to od razu językiem procesu: oficjalna delegacja, przesłuchanie, protokół pytań i odpowiedzi. Wielki proces o tożsamość Jezusa otwiera przesłuchanie świadka.",
 "blocks": [
 {"label":"w. 19–21","cs":1,"vs":19,"ce":1,"ve":21,"greek":_gk(19,21),"transl":_pl(19,21),
  "units":[
  ("ὡμολόγησεν καὶ οὐκ ἠρνήσατο","wyznał, a nie zaprzeczył",
"""Uroczysta, niemal notarialna formuła: ὡμολόγησεν (wyznał) — οὐκ ἠρνήσατο (nie zaprzeczył) — ὡμολόγησεν (wyznał). Podwójne „wyznał" obejmuje przeczenie jak rama: paradoksalnie treścią wyznania Jana jest zaprzeczenie sobie. Ὁμολογέω (wyznawać) to później techniczny czasownik wyznania wiary (stąd „homologia" — wyznanie); pierwszym wyznaniem czwartej Ewangelii jest pokorne „nie jestem". Trzykrotne przeczenie Chrzciciela (nie Mesjasz, nie Eliasz, nie Prorok) ustawi się w pamięci czytelnika naprzeciw trzykrotnego zaparcia Piotra (J 18) — i trzykrotnego wyznania miłości (J 21)."""),
  ("Ἠλίας / ὁ προφήτης","Eliasz / Prorok",
"""Katalog oczekiwań mesjańskich epoki w trzech pytaniach. Eliasz — wzięty do nieba, miał wrócić przed dniem Pańskim (Ml 3,23); Jan zaprzecza, choć synoptycy widzą w nim Eliasza „w duchu i mocy" — nie jest Eliaszem redivivus (powróconym osobiście), jest Eliaszem typologicznie. Ὁ προφήτης (Prorok — z rodzajnikiem): obiecany w Pwt 18,15 prorok „jak Mojżesz" (ha-nawi), którego wyglądano osobno obok Mesjasza (por. reguły z Qumran wymieniające proroka i dwóch pomazańców). Jan odsuwa od siebie wszystkie trzy szaty — by wszystkie trzy mogły spocząć na Tym, który nadchodzi."""),
  ]},
 {"label":"w. 22–23","cs":1,"vs":22,"ce":1,"ve":23,"greek":_gk(22,23),"transl":_pl(22,23),
  "units":[
  ("φωνή","głos",
"""Zapytany wprost, Jan definiuje się jednym rzeczownikiem bez rodzajnika: φωνή (głos) — cytatem z Iz 40,3. Zestawienie z Prologiem jest zamierzone i olśniewające: Jezus jest λόγος (Słowem), Jan — φωνή (głosem). Głos poprzedza słowo w uszach, choć słowo poprzedza głos w sercu; głos przebrzmiewa, gdy słowo zostało przekazane. Cała teologia przepowiadania mieści się w tej parze: każdy głoszący jest głosem cudzego Słowa. U Iz 40,3 głos woła: „przygotujcie drogę Pana" — Jan stosuje do Jezusa tekst mówiący o JHWH; najcichsza, a najdalej idąca chrystologia tej sceny."""),
  ]},
 {"label":"w. 24–27","cs":1,"vs":24,"ce":1,"ve":27,"greek":_gk(24,27),"transl":_pl(24,27),
  "units":[
  ("μέσος ὑμῶν ἕστηκεν","pośród was stoi",
"""Odpowiedź na pytanie o mandat chrztu jest odpowiedzią o obecność: pośród was *stoi* (perfectum ἕστηκεν — stanął i stoi) Ten, którego nie znacie. Mesjasz ukryty pośród ludu — motyw znany judaizmowi (Mesjasz obecny, lecz nierozpoznany aż do objawienia) — u Jana nabiera ironii teologicznej: badacze przyszli badać świadka, a Sędzia stał w tłumie. Zdanie do dziś czytane egzystencjalnie: Nieznajomy pośród nas."""),
  ("λύσω αὐτοῦ τὸν ἱμάντα","rozwiązać rzemień Jego sandała",
"""Rozwiązywanie sandałów to w ówczesnym obyczaju czynność tak niska, że — wedle późniejszej sentencji rabinackiej — uczeń winien mistrzowi wszystko, co niewolnik panu, *oprócz* rozwiązania sandała. Jan schodzi więc poniżej progu niewolnika: nie jestem godzien tego, czego nie wolno wymagać od nikogo. Możliwe drugie dno: zdjęcie sandała należy do prawa lewiratu (Pwt 25,9; Rt 4,7) — gestu ustąpienia prawa bliższemu krewnemu-wykupicielowi (goel); Oblubieniec jest jeden, przyjaciel oblubieńca nie sięga po jego prawo (por. J 3,29)."""),
  ]},
 {"label":"w. 28","cs":1,"vs":28,"ce":1,"ve":28,"greek":VERSES2[28][0],"transl":VERSES2[28][1],
  "units":[
  (None,None,
"""Notatka topograficzna: Betania za Jordanem (inna niż Betania Łazarza pod Jerozolimą). Ewangelista lokalizuje sceny z dokładnością naocznego świadka — a kłopot z odnalezieniem tej Betanii miał już Orygenes, który objeżdżając Palestynę zaproponował poprawkę na Betabara (zob. aparat). Miejsce jest teologicznie nieprzypadkowe: za Jordanem, czyli tam, skąd Izrael wchodził do Ziemi Obiecanej — nowy Jozue (Jezus: to samo imię) zaczyna od brzegu, od którego zaczęło się pierwsze wejście."""),
  ]},
 ],
 "sections": [
 {"type":"kontekst","title":"II. Kontekst historyczny, językowy, kulturowy i religijny","body":
"""**Delegacja.** Kapłani i lewici z Jerozolimy, dosłani ἐκ τῶν Φαρισαίων (spośród faryzeuszów) — sondaż władzy religijnej wobec ruchu chrzcielnego nad Jordanem; masowe obmycia budziły czujność (por. Józef Flawiusz o Janie: chrzest i tłumy jako powód niepokoju Heroda). **Chrzest Janowy.** Judaizm znał obmycia rytualne (mykwy, codzienne ablucje esseńczyków z Qumran); nowością Jana była jednorazowość i wezwanie całego Izraela do pokuty — gest prorocki, nie rutyna czystości. Pytanie „czemu chrzcisz?" jest więc pytaniem o mandat eschatologiczny: obmycie całego ludu zapowiadali prorocy na czasy ostateczne (Ez 36,25; Za 13,1). **Trzy postaci oczekiwania.** Mesjasz-król, Eliasz-poprzednik, Prorok-jak-Mojżesz: świadectwo, że mesjanizm epoki był wielopostaciowy; Jan po kolei gasi każdą projekcję, by oczekiwanie nie zatrzymało się na nim.""",
  "children":[]},
 {"type":"teologia","title":"III. Obserwacje teologiczne i filozoficzne w duchu tomistycznym","body":
"""**1. Pokora jako prawda.** Tomasz definiuje pokorę nie jako zaniżanie siebie, lecz jako prawdę o sobie wobec Boga; Jan jest jej wzorcem doskonałym — mówi o sobie dokładnie tyle, ile jest: głos, nie Słowo; przyjaciel, nie Oblubieniec. Pokora okazuje się warunkiem poznania: kto zawyża siebie, zasłania sobie Tego, który stoi pośród nas.

**2. Posłannictwo i sakrament.** Chrzest Janowy — mówi Tomasz — przygotowywał, nie sprawiał: był sakramentalium zapowiedzi, nie sakramentem łaski; dyspozycją, nie przyczyną. Rozróżnienie wody i Ducha (w. 26.33) stanie się osią teologii sakramentu: znak bez mocy własnej czeka na Tego, który mocą napełnia znaki.

**3. Świadectwo a poznanie wiary.** Wiara rodzi się ze słyszenia świadka, nie z widzenia dowodu; scena przesłuchania pokazuje strukturę aktu wiary: pytanie o tożsamość, świadectwo, decyzja. Rozum bada świadka (i słusznie — delegacja pyta rzetelnie), lecz ostatni krok jest zawierzeniem osobie.""",
  "children":[]},
 {"type":"autor_ludzki","title":"IV. Autor ludzki: kim jest i co chce przekazać","body":
"""Ewangelista otwiera narrację formułą „takie jest świadectwo Jana" — jakby wciągał do akt pierwszy protokół procesu, który będzie się toczył przez całą księgę. Konstrukcja sceny jest prawnicza: pytania oficjalne, odpowiedzi pod przysięgą, ustalenie miejsca (w. 28 jak adnotacja o miejscu czynności). Zarazem trwa polemika środowiskowa znana z w. 6–8: wobec grup ceniących Chrzciciela ponad miarę (Efez, por. Dz 19,1–7) ewangelista oddaje głos samemu Janowi — niech najwyższy autorytet tych grup własnymi ustami wskaże Większego.""",
  "children":[]},
 {"type":"autor_bozy","title":"V. Autor Boży: co Duch Święty chce przekazać","body":
"""Duch Święty uczy tu gramatyki powołania: każdy posłany jest głosem, nie Słowem; światłem zapalonym, nie Światłością. Kto głosi, staje w miejscu Chrzciciela — i podlega jego regule: „nie jestem". Zarazem w. 26 niesie obietnicę stałą jak obecność: pośród was stoi Ten, którego nie znacie — zdanie prawdziwe w każdym pokoleniu Kościoła, w każdej liturgii, w każdym ubogim (por. Mt 25). Duch nie pozwala czytelnikowi zostać widzem przesłuchania: pytanie „ty kim jesteś?" wraca do każdego, kto czyta.""",
  "children":[]},
 {"type":"odniesienia","title":"VI. Sieć odniesień biblijnych","body":
"""**Iz 40,3 → w. 23.** Głos wołającego na pustyni — u Izajasza otwiera Księgę Pocieszenia i powrót z wygnania; wszyscy czterej ewangeliści czytają go o Janie, ale tylko czwarta Ewangelia wkłada go w usta samego Jana jako samookreślenie.

**Ml 3,1.23 → w. 21.** Posłaniec przygotowujący drogę i Eliasz posłany przed dniem Pańskim — tło pytania o Eliasza.

**Pwt 18,15.18 → w. 21.25.** Prorok jak Mojżesz (ha-nawi — ów Prorok): trzecia figura oczekiwania; powróci w J 6,14 i 7,40.

**Mk 1,2–8 (par.) → w. 19–28.** Synoptyczna wersja świadectwa: te same elementy (Izajasz, sandały, woda–Duch), inna optyka — Jan czwartej Ewangelii nie chrzci Jezusa na scenie, lecz o Nim zeznaje.

**Pwt 25,9; Rt 4,7 → w. 27.** Zzuwanie sandała w prawie wykupiciela (goel) — możliwe tło gestu ustąpienia prawa Oblubieńcowi (por. J 3,29).

**J 3,25–30 → całość.** Dalszy ciąg świadectwa: „On ma wzrastać, ja się umniejszać" — puenta duchowa tej sceny.""",
  "children":[]},
 {"type":"recepcja","title":"VII. Znaczenie w historii i liturgii Kościoła","body":
"""Kościół czyta tę perykopę w Adwencie: III Niedziela Adwentu roku B (Gaudete — Radujcie się) łączy J 1,6–8 z 1,19–28, czyniąc z Chrzciciela ikonę adwentowego oczekiwania; „prostujcie drogę Pana" stało się hasłem całego okresu. W ikonografii Jan wskazujący palcem (Izenheim!) z podpisem *illum oportet crescere* (por. J 3,30: trzeba, by On wzrastał) jest wizualną egzegezą w. 19–28. Patrystyka uczyniła z pary φωνή–λόγος (głos–Słowo) klasyczny temat kazań na Narodzenie Jana Chrzciciela (24 VI) — święto, które liturgia ustawiła naprzeciw Narodzenia Pańskiego (24 VI / 25 XII: od przesilenia dni maleją — „ja się umniejszać" — i rosną — „On ma wzrastać").""",
  "children":[]},
 {"type":"patrystyka","title":"VIII. Komentarze Ojców Kościoła (catena patrum)","body":
"""Katena do świadectwa: głos i Słowo, pokora wyznania, geografia Orygenesa.""",
  "children":[]},
 ],
 "refs": [
 (("pericope",), "Iz", 40, 3, 40, 3, "Iz 40,3", "cytat", "Głos wołającego na pustyni — samookreślenie Jana"),
 (("pericope",), "Ml", 3, 1, 3, 1, "Ml 3,1", "tlo", "posłaniec przygotowujący drogę"),
 (("pericope",), "Ml", 3, 23, 3, 24, "Ml 3,23–24", "tlo", "Eliasz posłany przed dniem Pańskim"),
 (("pericope",), "Pwt", 18, 15, 18, 18, "Pwt 18,15.18", "tlo", "Prorok jak Mojżesz — trzecia figura oczekiwania"),
 (("pericope",), "Mk", 1, 2, 1, 8, "Mk 1,2–8", "paralela", "synoptyczne świadectwo Chrzciciela"),
 (("pericope",), "Pwt", 25, 9, 25, 9, "Pwt 25,9", "tlo", "zzucie sandała w prawie wykupiciela (goel)"),
 (("pericope",), "J", 3, 25, 3, 30, "J 3,25–30", "rozwiniecie", "przyjaciel oblubieńca; On ma wzrastać"),
 (("unit","w. 24–27",0), "Mt", 25, 31, 25, 46, "Mt 25,31–46", "por", "Nieznajomy pośród nas — obecność nierozpoznana"),
 ],
 "patristic": [
 ("w. 22–23", "św. Augustyn", "Sermones", "Sermo 293,3 (por. Tract. in Io. 4)",
"""Najsłynniejsza patrystyczna para pojęć tej sceny: *vox et verbum* (głos i słowo). Słowo mieszka w sercu, zanim głos je poniesie; głos brzmi, przemija i milknie — słowo, które przekazał, zostaje w słuchającym. Jan jest głosem na czas, Chrystus Słowem od początku: dlatego Jan maleje, a Chrystus rośnie — głos wypełnia się w tym, że staje się zbędny. Augustyn dodaje puentę duszpasterską: jeśli głoszę, a słowo nie dociera do serca, byłem hałasem; głosem jestem tylko wtedy, gdy niosę Słowo."""),
 ("w. 19–21", "św. Jan Chryzostom", "Homilie na Ewangelię Jana", "Hom. in Io. 16",
"""Chryzostom zatrzymuje się nad formułą „wyznał, a nie zaprzeczył": największą pokusą posłanego jest przywłaszczyć sobie chwałę Posyłającego — Jan miał ku temu wszystko: tłumy, pustynię, sławę proroka; wyznaniem jego wierności było przeczenie. Kaznodzieja widzi tu lustro dla kleru: godność, której sobie nie przypisujesz, świeci; przypisana — gaśnie. A pytającym z Jerozolimy oddaje sprawiedliwość: pytali rzetelnie i po kolei — niewiara zaczyna się nie od pytań, lecz od niesłuchania odpowiedzi."""),
 ("w. 28", "Orygenes", "Komentarz do Ewangelii Jana", "Comm. in Io. VI,40",
"""Najstarszy przypadek biblijnej krytyki geograficznej: Orygenes, znający Palestynę z autopsji, nie umiał znaleźć Betanii za Jordanem — znał tylko Betanię Łazarza pod Jerozolimą — i zaproponował lekcję Βηθαβαρά (Betabara, „dom przeprawy"), którą znalazł w części rękopisów i w tradycji miejscowej. Poprawka weszła do wielu kodeksów i starych przekładów. Dziś krytyka wraca do Betanii (lekcja najlepiej poświadczona), a przypadek pozostaje pouczający: już w III wieku egzegeta ważył rękopisy, geografię i tradycję — i bywał od nas odważniejszy w emendacjach."""),
 ],
 "liturgy": [
 ("rzymski", "III Niedziela Adwentu, rok B (Gaudete)", "J 1,6–8.19–28",
  '''Chrzciciel jako ikona adwentowego oczekiwania; „prostujcie drogę Pana" hasłem okresu.'''),
 ("rzymski", "Uroczystość Narodzenia św. Jana Chrzciciela (24 VI) — tło kaznodziejskie", "J 1,19–28",
  "Klasyczny materiał homilii o parze głos–Słowo; kalendarz ustawia narodziny Jana naprzeciw Narodzenia Pańskiego."),
 ],
 "textual": [
 (28, "Βηθανίᾳ / Βηθαβαρᾷ", "wariant lekcji",
  "Βηθανίᾳ: P66, P75, ℵ*, B — lekcja najlepiej poświadczona; Βηθαβαρᾷ: koniektura Orygenesa przyjęta przez część tradycji (C2, bizantyjskie, syryjskie).",
  "NA28 utrzymuje Betanię; Betabara jest cennym świadectwem starożytnej krytyki geograficznej, nie pierwotnym tekstem."),
 ],
 "themes": [
 ("świadectwo (μαρτυρία)", ("pericope",)),
 ("vox et verbum — głos a Słowo", ("block","w. 22–23")),
 ],
}

# ------------------------------------------------------------------
# PERYKOPA 4: J 1,29-34 — Baranek Boży
# ------------------------------------------------------------------
P4 = {
 "pericope": {"cs":1,"vs":29,"ce":1,"ve":34,"title":"Baranek Boży",
              "motto":"Ecce Agnus Dei (Oto Baranek Boży)",
              "status":"w_opracowaniu","position":4},
 "intro": '''Τῇ ἐπαύριον (nazajutrz) — zaczyna się odliczanie dni, które doprowadzi do „dnia trzeciego" w Kanie: nowy tydzień stworzenia. Dziś, w dniu drugim, świadek wskazuje palcem i nadaje Jezusowi tytuł, który liturgia będzie powtarzać do końca świata.''',
 "blocks": [
 {"label":"w. 29","cs":1,"vs":29,"ce":1,"ve":29,"greek":VERSES2[29][0],"transl":VERSES2[29][1],
  "units":[
  ("ὁ ἀμνὸς τοῦ θεοῦ","Baranek Boży",
"""Tytuł bez precedensu w tej formie — i o czterech dnach naraz. (1) Baranek paschalny (Wj 12): zabijany w Jerozolimie, gdy Jezus umiera (J 19,14: przygotowanie Paschy), któremu „kości nie łamią" (J 19,36 = Wj 12,46). (2) Sługa Pański z Iz 53,7: „jak baranek na rzeź prowadzony" — dźwigający grzechy wielu; po aramejsku talja znaczy zarazem „baranek" i „sługa": jedno słowo Chrzciciela mogło nieść oba sensy. (3) Baranek ofiary ustawicznej (tamid — codziennej, rano i wieczorem, Wj 29,38–42): czas teraźniejszy ὁ αἴρων (dźwigający — stale). (4) Baranek-zwycięzca apokaliptyki (por. Ap 5–7.17): paradoks mocy w słabości. Genetivus τοῦ θεοῦ (Boży): baranek, którego — jak w odpowiedzi Abrahama synowi — „Bóg sam sobie upatrzy" (Rdz 22,8)."""),
  ("ὁ αἴρων τὴν ἁμαρτίαν","który dźwiga/usuwa grzech",
"""Αἴρω znaczy i „podnosić, brać na siebie", i „usuwać, znosić" — dwuznaczność jest teologią: Baranek usuwa grzech właśnie przez to, że go dźwiga (por. Iz 53,4.11–12: on nosił nasze choroby; hebr. nasa — nieść i odpuszczać zarazem!). Τὴν ἁμαρτίαν (grzech) — liczba pojedyncza: nie inwentarz uczynków, lecz grzech świata jako jedna zwarta rzeczywistość odłączenia; κόσμου (świata) — zasięg bez granic, ten sam „świat", który „Go nie poznał" (w. 10)."""),
  ]},
 {"label":"w. 30–31","cs":1,"vs":30,"ce":1,"ve":31,"greek":_gk(30,31),"transl":_pl(30,31),
  "units":[
  ("κἀγὼ οὐκ ᾔδειν αὐτόν","i ja Go nie znałem",
"""Dwukrotne (w. 31.33) wyznanie niewiedzy świadka — zaskakujące u krewnego (Łk 1). Sens jest teologiczny, nie biograficzny: Jan nie znał Jezusa *jako Tego, którym jest* — mesjańska tożsamość nie jest wiedzą rodzinną ani ludzką przenikliwością, lecz objawieniem z góry, związanym ze znakiem (w. 33). Świadek wiarygodny to taki, który zeznaje nie swoje domysły, lecz to, co mu pokazano; cała wartość chrztu Janowego okazuje się służebna: „po to przyszedłem chrzcząc, aby został objawiony Izraelowi"."""),
  ]},
 {"label":"w. 32–33","cs":1,"vs":32,"ce":1,"ve":33,"greek":_gk(32,33),"transl":_pl(32,33),
  "units":[
  ("καταβαῖνον ὡς περιστερὰν ... καὶ ἔμεινεν","zstępującego jak gołębica ... i pozostał",
"""Dwa obrazy z pierwszych kart Rdz spotykają się nad Jordanem: Duch (ruach — tchnienie) unoszący się nad wodami pierwszego stworzenia (Rdz 1,2 — Ojcowie i midrasz porównują to unoszenie do ptaka nad gniazdem) i gołębica Noego szukająca miejsca spocznienia po potopie (Rdz 8,8–12). Nad wodami Jordanu gołębica wreszcie *znalazła* miejsce: ἔμεινεν ἐπ᾿ αὐτόν (pozostał na Nim). Czasownik μένω (pozostawać, trwać) — od tej sceny wielkie słowo czwartej Ewangelii (aż po „trwajcie we Mnie", J 15) — odróżnia Jezusa od proroków: na nich Duch zstępował chwilowo, w Nim mieszka. Kryterium rozpoznania Mesjasza jest więc *trwanie* Ducha."""),
  ("ὁ βαπτίζων ἐν πνεύματι ἁγίῳ","chrzczący w Duchu Świętym",
"""Definitywna różnica posłannictw: Jan zanurza w wodzie (znak), Ten — w Duchu Świętym (rzeczywistość). Participium praesentis ὁ βαπτίζων (Chrzczący — stale): to tytuł, nie epizod; Jezus pozostaje Chrzczącym w każdym chrzcie Kościoła. Woda i Duch spotkają się w rozmowie z Nikodemem (J 3,5) i w wodzie z boku (J 19,34) — Jan buduje łuk sakramentalny od pierwszej sceny."""),
  ]},
 {"label":"w. 34","cs":1,"vs":34,"ce":1,"ve":34,"greek":VERSES2[34][0],"transl":VERSES2[34][1],
  "units":[
  ("ἑώρακα καὶ μεμαρτύρηκα","zobaczyłem i zaświadczyłem",
"""Podwójne perfectum: zobaczyłem (i widzenie trwa), zaświadczyłem (i świadectwo stoi) — formuła zeznania zamkniętego, prawnie ważnego. Przedmiot: οὗτός ἐστιν ὁ υἱὸς τοῦ θεοῦ (Ten jest Synem Bożym). Część najstarszych świadków czyta tu ὁ ἐκλεκτός (Wybrany Boży) — echo Iz 42,1 („mój Wybrany, złożyłem na nim Ducha") i naturalne dopełnienie sceny z Duchem; zob. aparat. Tak czy owak świadectwo Chrzciciela osiąga szczyt: od „nie jestem" doszedł do „Ten jest"."""),
  ]},
 ],
 "sections": [
 {"type":"kontekst","title":"II. Kontekst historyczny, językowy, kulturowy i religijny","body":
"""**Baranek w wyobraźni Izraela.** Pascha była pamięcią założycielską (baranek, którego krew osłania), tamid — codziennym pulsem świątyni (dwa baranki dziennie), Iz 53 — najgłębszą zagadką proroków (Sługa cierpiący za wielu; targum czytał ten tekst mesjańsko, choć cierpienie przenosił z Mesjasza na lud). Aramejskie tło (talja: baranek/sługa/dziecko) pozwala usłyszeć w jednym zdaniu Chrzciciela całą tę polifonię. **Duch nad wodą.** Obraz ptaka nad wodami łączył Rdz 1,2 z nadzieją nowego stworzenia; w Qumran oczekiwano oczyszczenia „duchem świętości jak wodą oczyszczenia". **Chrzest Mesjasza Duchem** — z Ez 36,25–27 i Jl 3,1: wylanie Ducha na wszelkie ciało jako znak czasów ostatecznych. Scena nad Jordanem ogłasza: te czasy stoją w wodzie pośród was.""",
  "children":[]},
 {"type":"teologia","title":"III. Obserwacje teologiczne i filozoficzne w duchu tomistycznym","body":
"""**1. Ofiara i zadośćuczynienie.** „Dźwiga grzech świata" — Tomasz wyjaśni: Chrystus zadośćuczynił nie przez równoważność bólu, lecz przez przewyższającą miłość (*satisfactio ex caritate* — zadośćuczynienie z miłości); baranek nie jest piorunochronem gniewu, lecz osobą, której miłość waży więcej niż grzech świata. Liczba pojedyncza ἁμαρτία potwierdza: usuwana jest sama zasada odłączenia, nie tylko jej epizody.

**2. Duch spoczywający.** Trwanie Ducha na Jezusie to po tomistycznie pełnia łaski w Głowie (*gratia capitis*), z której — jak z namaszczonej głowy Aarona na całą szatę (Ps 133,2) — łaska spływa na członki. Dlatego „chrzczący w Duchu" jest tytułem stałym: sakramenty są kanałami tej jednej pełni.

**3. Poznanie przez znak.** „Nie znałem Go... ale Ten, który mnie posłał, powiedział mi: na kogo zobaczysz..." — struktura poznania wiary: obietnica, znak, rozpoznanie, świadectwo. Znak nie zastępuje słowa, słowo nie obywa się bez znaku; Tomasz nazwie to drogą stosowną dla człowieka, który poznaje duchowe przez zmysłowe.""",
  "children":[]},
 {"type":"autor_ludzki","title":"IV. Autor ludzki: kim jest i co chce przekazać","body":
"""Ewangelista nie opisuje chrztu Jezusa — zakłada, że czytelnik zna scenę (synoptycy), i podaje samo jądro: zeznanie świadka o tym, co chrzest objawił. To świadomy wybór gatunku: nie kronika, lecz proces — liczy się nie zdarzenie, lecz jego poświadczona treść. Odliczanie dni (nazajutrz... nazajutrz... dnia trzeciego, 1,29.35.43; 2,1) buduje tydzień inauguracji zamknięty godami w Kanie: autor komponuje pierwszy tydzień nowego stworzenia, w którym dzień Baranka jest dniem wskazania Ofiary — od początku wesele i krzyż są w jednym rytmie.""",
  "children":[]},
 {"type":"autor_bozy","title":"V. Autor Boży: co Duch Święty chce przekazać","body":
"""Duch Święty jest w tej perykopie i treścią, i Autorem: objawia siebie jako Tego, który *pozostaje* — i tego samego uczy czytelnika o sobie. Sens dla Kościoła każdego czasu: rozpoznawaj Mesjasza po trwaniu Ducha, nie po błysku; i wiedz, że każdy chrzest, którego udziela Kościół, jest chrztem, w którym Chrzczącym pozostaje Ten sam. A tytuł „Baranek" Duch umieścił na progu Ewangelii po to, by żadna dalsza chwała — znaki, tłumy, Tabor Janowy w mowach — nie przesłoniła kierunku: ta historia idzie ku ofierze.""",
  "children":[]},
 {"type":"odniesienia","title":"VI. Sieć odniesień biblijnych","body":
"""**Wj 12 → w. 29.** Baranek paschalny; Jan dopnie klamrę w J 19,14.36 (godzina zabijania baranków; kości nie złamane).

**Iz 53,4–12 → w. 29.** Sługa dźwigający grzechy wielu; hebr. nasa (nieść/odpuszczać) odpowiada dwuznaczności αἴρω.

**Rdz 22,7–8 → w. 29.** „Bóg sam sobie upatrzy baranka" — odpowiedź Abrahama spełniona; łączy się z μονογενής (Jednorodzonym) z 1,14.18.

**Rdz 1,2; 8,8–12 → w. 32.** Duch nad wodami i gołębica Noego: nowe stworzenie i koniec potopu gniewu.

**Iz 42,1 → w. 34.** „Mój Wybrany, złożyłem na nim Ducha" — tło lekcji ὁ ἐκλεκτός (Wybrany).

**Ez 36,25–27 → w. 33.** Woda czysta i nowy Duch — obietnica, którą chrzest w Duchu wypełnia.

**Ap 5,6–14 → w. 29.** Baranek zabity, a stojący — dopełnienie tytułu w corpus Joanneum (pismach Janowych).

**1 P 1,18–19 → w. 29.** Baranek bez skazy — niezależne echo tej samej katechezy chrzcielnej.""",
  "children":[]},
 {"type":"recepcja","title":"VII. Znaczenie w historii i liturgii Kościoła","body":
"""Żaden werset Janowy nie wszedł do liturgii głębiej niż 1,29: *Ecce Agnus Dei, ecce qui tollit peccata mundi* (Oto Baranek Boży, oto Ten, który gładzi grzechy świata) — kapłan powtarza słowa Chrzciciela przed każdą Komunią, czyniąc z całego Kościoła wspólnotę wskazywanych i wskazujących; śpiew *Agnus Dei* (Baranku Boży) wprowadził do Mszy rzymskiej papież Sergiusz I (koniec VII w.), a Gloria woła do Baranka od starożytności. Ikonografia zna Baranka z chorągwią (zwycięstwo przez ofiarę) i Chrzciciela z palcem wyciągniętym — u Grünewalda palec ten jest nienaturalnie długi, bo taka jest cała funkcja Jana. Czytania: II Niedziela zwykła roku A (J 1,29–34); Wschód wspomina scenę w ramach święta Teofanii (Objawienia — Chrztu Pańskiego, 6 I).""",
  "children":[]},
 {"type":"patrystyka","title":"VIII. Komentarze Ojców Kościoła (catena patrum)","body":
"""Katena do Baranka: teraźniejszość dźwigania, gołębica jedności, Duch, który pozostał.""",
  "children":[]},
 ],
 "refs": [
 (("pericope",), "Wj", 12, 1, 12, 46, "Wj 12", "typologia", "baranek paschalny; klamra w J 19,14.36"),
 (("pericope",), "Iz", 53, 4, 53, 12, "Iz 53,4–12", "typologia", "Sługa dźwigający grzechy wielu (nasa = αἴρω)"),
 (("pericope",), "Rdz", 22, 7, 22, 8, "Rdz 22,7–8", "typologia", "Bóg sam sobie upatrzy baranka"),
 (("pericope",), "Rdz", 1, 2, 1, 2, "Rdz 1,2", "aluzja", "Duch nad wodami — nowe stworzenie"),
 (("pericope",), "Rdz", 8, 8, 8, 12, "Rdz 8,8–12", "aluzja", "gołębica Noego — koniec potopu, znalezione spocznienie"),
 (("pericope",), "Iz", 42, 1, 42, 1, "Iz 42,1", "tlo", "mój Wybrany, złożyłem na nim Ducha — tło wariantu ὁ ἐκλεκτός"),
 (("pericope",), "Ap", 5, 6, 5, 14, "Ap 5,6–14", "rozwiniecie", "Baranek zabity, a stojący — liturgia nieba"),
 (("pericope",), "1 P", 1, 18, 1, 19, "1 P 1,18–19", "paralela", "baranek bez skazy — wspólna katecheza chrzcielna"),
 (("unit","w. 32–33",1), "J", 3, 5, 3, 5, "J 3,5", "rozwiniecie", "narodzenie z wody i Ducha"),
 (("unit","w. 29",0), "J", 19, 36, 19, 36, "J 19,36", "rozwiniecie", "kości Mu nie złamano — Pascha spełniona"),
 ],
 "patristic": [
 ("w. 29", "św. Jan Chryzostom", "Homilie na Ewangelię Jana", "Hom. in Io. 17–18",
"""Chryzostom wskazuje czas teraźniejszy: nie „który poniósł" ani „poniesie", lecz ὁ αἴρων — dźwigający zawsze; ofiara złożona raz działa nieustannie, jak źródło raz otwarte płynie ciągle. I liczbę: „grzech", nie „grzechy" — Baranek uderza w korzeń, nie obrywa liści. Kaznodzieja słyszy też pokorę tytułu: Chrzciciel nie mówi „oto Król" (choć powie to Natanael) — zaczyna od ofiary, aby nikt nie budował mesjanizmu z pominięciem krzyża."""),
 ("w. 32–33", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 5–6",
"""Augustyn, spierając się z donatystami o ważność chrztu, znajduje w tej scenie swój najmocniejszy argument: Jan poznał po gołębicy Tego, który chrzci w Duchu — a więc mocą każdego chrztu jest Chrystus, nie szafarz; „Piotr chrzci — On chrzci; Judasz chrzci — On chrzci". Gołębica zaś jest znakiem tych, którzy chrzest mają owocnie: bez żółci, bez pazurów, wzdychająca zamiast śpiewu — prostota, łagodność, jedność (gołębica jest jedna, jak jedna jest oblubienica z Pnp 6,9). Chrzest ważny może mieć i kruk; owocny — tylko gołębica."""),
 ("w. 32–33", "św. Cyryl Aleksandryjski", "Commentarii in Ioannem", "In Io., ks. II",
"""Dlaczego Duch zstępuje na Tego, który od wieczności Go posiada? Cyryl: nie dla Niego — dla nas. Adam otrzymał tchnienie i przez grzech utracił stałość daru; w Chrystusie, nowym Adamie, Duch *pozostał* — powrócił do natury ludzkiej jak do siedziby, z której już nie odleci, aby z Niego, jako z korzenia rodu, rozlać się na całe człowieczeństwo. Namaszczenie Głowy jest namaszczeniem ciała: co spoczęło na Nim nad Jordanem, spływa na nas w chrzcie."""),
 ],
 "liturgy": [
 ("rzymski", "Ecce Agnus Dei przed Komunią świętą — każda Msza", "J 1,29",
  "Kapłan powtarza gest i słowa Chrzciciela; wierni odpowiadają słowami setnika (Mt 8,8)."),
 ("rzymski", "Śpiew Agnus Dei podczas łamania Chleba (od Sergiusza I, k. VII w.)", "J 1,29",
  "Potrójne wezwanie Baranka gładzącego grzechy świata; także w Gloria i litaniach."),
 ("rzymski", "II Niedziela zwykła, rok A", "J 1,29–34",
  "Świadectwo Chrzciciela jako przedłużenie objawień epifanijnych."),
 ("bizantyjski", "Teofania (Chrzest Pański, 6 I) — tło hymnografii", "J 1,29–34",
  "Trójca objawiona nad Jordanem; troparion święta opiewa głos Ojca i Ducha w postaci gołębicy."),
 ],
 "textual": [
 (34, "ὁ υἱός / ὁ ἐκλεκτός", "wariant lekcji",
  "ὁ υἱὸς τοῦ θεοῦ: P66, P75, A, B, tradycja większościowa; ὁ ἐκλεκτὸς τοῦ θεοῦ (Wybrany Boży): P5vid, ℵ*, stare łacińskie, syro-synajski.",
  '''NA28 utrzymuje „Syn"; lekcja „Wybrany" — trudniejsza i zgodna z Iz 42,1 — ma poważnych obrońców; obie prawowierne, wybór wpływa na siłę aluzji do Pieśni Sługi.'''),
 ],
 "themes": [
 ("świadectwo (μαρτυρία)", ("block","w. 34")),
 ("Baranek Boży", ("block","w. 29")),
 ("μένειν — trwać, pozostawać", ("block","w. 32–33")),
 ("nowy tydzień stworzenia (J 1,19–2,11)", ("pericope",)),
 ],
}

# ------------------------------------------------------------------
# PERYKOPA 5: J 1,35-42 — Pierwsi uczniowie
# ------------------------------------------------------------------
P5 = {
 "pericope": {"cs":1,"vs":35,"ce":1,"ve":42,"title":"Pierwsi uczniowie",
              "motto":"Magister, ubi habitas? (Nauczycielu, gdzie mieszkasz?)",
              "status":"w_opracowaniu","position":5},
 "intro": "Dzień trzeci tygodnia inauguracji: świadectwo wydaje owoc. Dwóch uczniów odchodzi od Jana ku Jezusowi — i zaczyna się łańcuch, który nie urwał się do dziś: usłyszeć, pójść, zamieszkać, znaleźć brata.",
 "blocks": [
 {"label":"w. 35–37","cs":1,"vs":35,"ce":1,"ve":37,"greek":_gk(35,37),"transl":_pl(35,37),
  "units":[
  ("ἠκολούθησαν τῷ Ἰησοῦ","poszli za Jezusem",
"""Największa godzina Chrzciciela: mówi „oto Baranek Boży" — i traci dwóch najlepszych uczniów. Ἀκολουθέω (iść za) to techniczne słowo uczniostwa: chodzić za rabbim, wstępować w jego ślady, dosłownie i duchowo. Jan nie zatrzymuje nikogo przy sobie — świadectwo, które gromadzi wokół świadka, jest zdradą świadectwa. Zwięzłość sceny jest jej teologią: usłyszeli — poszli; między słowem świadka a krokiem ucznia nie ma nic, żadnej agitacji, żadnego cudu."""),
  ]},
 {"label":"w. 38–39","cs":1,"vs":38,"ce":1,"ve":39,"greek":_gk(38,39),"transl":_pl(38,39),
  "units":[
  ("τί ζητεῖτε;","czego szukacie?",
"""Pierwsze słowa Jezusa w czwartej Ewangelii — i jest to pytanie. Nie manifest, nie nauka: pytanie o pragnienie. Τί ζητεῖτε (czego szukacie?) sięga dna woli — Ewangelia zacznie się od zbadania tęsknoty, a zamknie podobnym pytaniem do Magdaleny: τίνα ζητεῖς (kogo szukasz? J 20,15) — od „czego" do „kogo": oto droga ucznia. Odpowiedź uczniów też jest pytaniem: ποῦ μένεις (gdzie mieszkasz/trwasz?) — chcą nie informacji, lecz przebywania; pytają o adres, a pytają o komunię."""),
  ("ἔρχεσθε καὶ ὄψεσθε","przyjdźcie, a zobaczycie",
"""Metoda Jezusowa w trzech słowach: nie wykład, lecz zaproszenie do doświadczenia; poznanie przychodzi po przyjściu (tę samą formułę powtórzy Filip Natanaelowi, w. 46). Ἔμειναν παρ᾿ αὐτῷ (pozostali u Niego) — znów μένω (trwać): zamieszkanie u Jezusa jest pierwszą lekcją, zanim padnie jakakolwiek nauka. Ὥρα ἦν ὡς δεκάτη (była około godziny dziesiątej — ok. 16:00): szczegół bez funkcji fabularnej, za to z funkcją świadka — tak pamięta się godzinę, która przełamała życie. Jeśli narratorem jest drugi z uczniów (bezimienny — umiłowany?), to jest to godzina jego własnego początku."""),
  ]},
 {"label":"w. 40–42","cs":1,"vs":40,"ce":1,"ve":42,"greek":_gk(40,42),"transl":_pl(40,42),
  "units":[
  ("εὑρήκαμεν τὸν Μεσσίαν","znaleźliśmy Mesjasza",
"""Pierwszy owoc zamieszkania: misja. Andrzej „znajduje najpierw brata" — apostolat zaczyna się od najbliższych i od czasownika εὑρίσκω (znajdować), który w tej scenie i następnej tworzy łańcuch: znalazł Andrzej, znajdzie Filip, „znaleźliśmy" powie o Prawie i Prorokach. Kto szukał (ζητεῖτε), ten znalazł — i odtąd sam jest znajdującym. Μεσσίας — surowa semicka forma (masziach — pomazaniec) zachowana w greckim tekście tylko tu i w J 4,25 w całym NT: skamielina aramejskiego języka pierwszej godziny, którą ewangelista od razu tłumaczy czytelnikowi (χριστός — Chrystus)."""),
  ("σὺ κληθήσῃ Κηφᾶς","ty będziesz nazwany Kefas",
"""Jezus ἐμβλέψας (wpatrzywszy się — spojrzeniem, które czyta wnętrze, tym samym co w w. 36 u Chrzciciela) dokonuje aktu władzy biblijnej: zmiany imienia. Nadanie imienia to w Biblii wytyczenie przeznaczenia — Abram stał się Abrahamem, Jakub Izraelem; Szymon będzie Kefasem (aram. kefa — skała; gr. Πέτρος). Czas przyszły κληθήσῃ (będziesz nazwany) czyni z imienia proroctwo: nie opis obecnego charakteru (Szymon okaże się chwiejny), lecz zapowiedź tego, czym uczyni go łaska. Jan zakłada u czytelnika znajomość dalszego ciągu (Mt 16,18) — i pokazuje jego początek: skała zaczęła się od spojrzenia."""),
  ]},
 ],
 "sections": [
 {"type":"kontekst","title":"II. Kontekst historyczny, językowy, kulturowy i religijny","body":
"""**Rabbi i uczniowie.** Ῥαββί (hebr. rabbi — „mój wielki", mistrzu) — tytuł nauczycielski, który Jan konsekwentnie tłumaczy greckim czytelnikom (διδάσκαλε — nauczycielu): ślad środowiska dwujęzycznego. W zwyczajnej relacji rabinackiej to uczeń wybierał mistrza i prosił o przyjęcie; tutaj porządek jest odwrócony w połowie — uczniowie przychodzą od Jana, ale to Jezus pierwszy się odwraca, pyta i zaprasza (a Filipa po prostu powoła: „pójdź za Mną"). **Godziny.** Liczenie od świtu: godzina dziesiąta ≈ 16:00 — pora zbyt późna na powrót, naturalnie tłumaczy nocleg; pamięć konkretu wskazuje na wspomnienie uczestnika. **Imiona.** Andrzej i Filip noszą imiona greckie (Betsaida — pogranicze kultur); Kefas jest aramejski: pierwsza wspólnota od początku mówi dwoma językami, a ewangelista jest jej tłumaczem.""",
  "children":[]},
 {"type":"teologia","title":"III. Obserwacje teologiczne i filozoficzne w duchu tomistycznym","body":
"""**1. Pragnienie i łaska.** „Czego szukacie?" — łaska nie wchodzi w człowieka obok jego pragnień, lecz przez nie: Tomasz uczy, że łaska zakłada naturę i ją doskonali (*gratia non tollit naturam, sed perficit* — łaska nie znosi natury, lecz ją doskonali); pierwsze słowo Zbawiciela bada więc naturę — jej głód — zanim poda pokarm.

**2. Poznanie przez zamieszkanie.** „Przyjdźcie, a zobaczycie": poznanie rzeczy Bożych jest poznaniem przez współnaturalność (*per connaturalitatem*) — smakuje się je, przebywając; stąd pierwszą katechezą jest wspólny wieczór, nie traktat. Wiedza o Bogu z samego słyszenia ma się do wiedzy z zamieszkania jak mapa do kraju.

**3. Imię i przeznaczenie.** Zmiana imienia to po tomistycznie znak wybrania do urzędu: łaska uzdalnia do tego, co przekracza naturę — Szymon z natury trzcina, z łaski skała. Predestynacja urzędu nie gwałci wolności: „będziesz nazwany" zostawia całą drogę (i upadki) między obietnicą a spełnieniem.""",
  "children":[]},
 {"type":"autor_ludzki","title":"IV. Autor ludzki: kim jest i co chce przekazać","body":
"""Scena nosi znamiona wspomnienia osobistego: bezimienny drugi uczeń, zapamiętana godzina, brak jakiejkolwiek treści wieczornej rozmowy (świadek nie zmyśla tego, czego nie wolno mu powtórzyć albo czego nie potrzeba). Jeśli — jak chce tradycja — tym drugim jest sam autor, to w. 39 jest jego podpisem złożonym w rogu obrazu. Zamysł literacki: powołanie pokazane jako łańcuch osobistych spotkań i „znalezień", bez tłumów i cudów — wzór ewangelizacji, w którym każde ogniwo mówi tylko jedno zdanie i prowadzi do Osoby.""",
  "children":[]},
 {"type":"autor_bozy","title":"V. Autor Boży: co Duch Święty chce przekazać","body":
"""Duch Święty kreśli w tej scenie stały porządek nawrócenia: świadectwo → pójście → pytanie o pragnienie → zamieszkanie → wyznanie → misja. Żaden etap nie jest ozdobny i żaden nie bywa pomijany bezkarnie: wiara bez zamieszkania jest pogłoską, zamieszkanie bez misji — przytulnością. Pytanie „czego szukacie?" Duch kieruje do czytelnika każdej epoki jako pierwsze słowo Chrystusa także do niego; a przez zapamiętaną godzinę dziesiątą przypomina, że zbawienie dzieje się w konkrecie: ma datę, adres i porę dnia.""",
  "children":[]},
 {"type":"odniesienia","title":"VI. Sieć odniesień biblijnych","body":
"""**Pnp 3,1–4 → w. 38–39.** Szukanie Umiłowanego („szukałam tego, którego miłuje dusza moja... znalazłam") — oblubieńcza matryca pary ζητέω–εὑρίσκω (szukać–znaleźć); mistyka od Orygenesa czyta powołanie uczniów tym kluczem.

**J 20,15–16 → w. 38.** „Kogo szukasz?... Rabbuni!" — inkluzja z Magdaleną: pierwsze i wielkanocne pytanie Jezusa spina księgę.

**Mt 16,17–18 → w. 42.** „Ty jesteś Piotr-Skała" — synoptyczne dopełnienie obietnicy imienia; Jan pokazuje zasiew, Mateusz żniwo.

**Rdz 17,5; 32,29 → w. 42.** Abram→Abraham, Jakub→Izrael: biblijna gramatyka zmiany imienia jako zmiany przeznaczenia.

**Mk 1,16–20 → całość.** Powołanie nad jeziorem — inna tradycja tej samej rzeczywistości: tam zerwanie z sieciami, tu dojrzewanie od świadectwa; harmonizacja klasyczna widzi w J 1 pierwsze spotkanie, u synoptyków — definitywne wezwanie.""",
  "children":[]},
 {"type":"recepcja","title":"VII. Znaczenie w historii i liturgii Kościoła","body":
"""Kościół czyta tę perykopę na II Niedzielę zwykłą roku B oraz — w części o Andrzeju — w święto Apostoła (30 XI); Wschód czci Andrzeja jako Πρωτόκλητος (Protokletos — Pierwszy Powołany), a scena z J 1 jest fundamentem tego tytułu i duchowego prymatu Konstantynopola („stolica Pierwszego Powołanego"). „Przyjdź i zobacz" stało się nazwą metody duszpasterskiej i rekolekcyjnej; ποῦ μένεις (gdzie mieszkasz?) — pytaniem mistyki o zamieszkanie w Chrystusie, rozwiniętym w J 15 (trwajcie we Mnie) i w tradycji monastycznej. Godzina dziesiąta bywała w komentarzach obrazem późnej pory świata: nigdy nie jest za późno pójść za Barankiem.""",
  "children":[]},
 {"type":"patrystyka","title":"VIII. Komentarze Ojców Kościoła (catena patrum)","body":
"""Katena do powołania: pytanie o pragnienie, wieczór u Jezusa, brat prowadzący brata, imię-skała.""",
  "children":[]},
 ],
 "refs": [
 (("pericope",), "Pnp", 3, 1, 3, 4, "Pnp 3,1–4", "typologia", "szukanie i znalezienie Umiłowanego — matryca oblubieńcza"),
 (("pericope",), "J", 20, 15, 20, 16, "J 20,15–16", "paralela", "kogo szukasz? Rabbuni — wielkanocna inkluzja"),
 (("pericope",), "Mt", 16, 17, 16, 18, "Mt 16,17–18", "paralela", "Ty jesteś Piotr — dopełnienie obietnicy Kefasa"),
 (("pericope",), "Rdz", 17, 5, 17, 5, "Rdz 17,5", "tlo", "Abram→Abraham: zmiana imienia jako przeznaczenie"),
 (("pericope",), "Rdz", 32, 29, 32, 29, "Rdz 32,29", "tlo", "Jakub→Izrael"),
 (("pericope",), "Mk", 1, 16, 1, 20, "Mk 1,16–20", "kontrast", "powołanie nad jeziorem — inna tradycja, ta sama rzeczywistość"),
 (("unit","w. 38–39",1), "J", 15, 4, 15, 4, "J 15,4", "rozwiniecie", "trwajcie we Mnie — dojrzała forma ποῦ μένεις"),
 ],
 "patristic": [
 ("w. 38–39", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 7,9",
"""„Gdzie mieszkasz?" — „Przyjdźcie, a zobaczycie". Augustyn czyta to jako regułę poznania Boga: przyjdź przez wiarę, zobaczysz przez doświadczenie — *crede ut intelligas* (uwierz, abyś zrozumiał); mieszkania Chrystusowego nie ogląda się z ulicy. Zbudowali sobie tamtego wieczoru dom w Nim, o którym nic nam nie powiedziano — i słusznie, mówi Augustyn: co się dzieje, gdy człowiek zamieszka u Jezusa, każdy ma poznać nie z cudzej relacji, lecz z własnego wieczoru."""),
 ("w. 40–42", "św. Jan Chryzostom", "Homilie na Ewangelię Jana", "Hom. in Io. 18–19",
"""Chryzostom podziwia Andrzeja podwójnie. Najpierw za pamięć godziny: tak zeznaje naoczny świadek, nie kompilator. Potem za pierwszy odruch znalazcy: nie zatrzymał skarbu — pobiegł do brata; „znaleźliśmy" mówi ten, kto szukał razem z całym Izraelem i wie, że znalezisko jest wspólne. Apostolat rodzi się przy rodzinnym stole, zanim stanie na areopagach; a największym dziełem Andrzeja — dodaje złotousty kaznodzieja — było przyprowadzenie Piotra: czasem powołaniem jest przyprowadzić większego od siebie."""),
 ("w. 40–42", "św. Jan Chryzostom", "Homilie na Ewangelię Jana", "Hom. in Io. 19",
"""Zmiana imienia jest u Chryzostoma dowodem Boskiej władzy i wiedzy: imiona nadaje ten, kto jest panem nazywanego i zna jego przyszłość — jak Bóg Abrahamowi. Jezus nazywa Szymona skałą, zanim ten cokolwiek zbudował i zanim trzykrotnie się zachwieje: imię nie jest dyplomem za osiągnięcia, lecz kredytem łaski. Chryzostom każe słuchaczom nosić własne imię chrzcielne tak samo: jako zadane, nie zdobyte."""),
 ],
 "liturgy": [
 ("rzymski", "II Niedziela zwykła, rok B", "J 1,35–42",
  "Powołanie pierwszych uczniów jako przedłużenie objawień epifanijnych."),
 ("bizantyjski", "Św. Andrzeja Pierwszego Powołanego (30 XI)", "J 1,35–42",
  "Tytuł Protokletos (Pierwszy Powołany) wyrasta wprost z tej perykopy."),
 ],
 "textual": [],
 "themes": [
 ("Baranek Boży", ("block","w. 35–37")),
 ("μένειν — trwać, pozostawać", ("block","w. 38–39")),
 ("nowy tydzień stworzenia (J 1,19–2,11)", ("pericope",)),
 ],
}

# ------------------------------------------------------------------
# PERYKOPA 6: J 1,43-51 — Powołanie Filipa i Natanaela
# ------------------------------------------------------------------
P6 = {
 "pericope": {"cs":1,"vs":43,"ce":1,"ve":51,"title":"Powołanie Filipa i Natanaela",
              "motto":"Rabbi, tu es Filius Dei (Rabbi, Ty jesteś Syn Boży)",
              "status":"w_opracowaniu","position":6},
 "intro": '''Czwarty dzień tygodnia inauguracji i ostatnia scena rozdziału: łańcuch „znalezień" sięga sceptyka, a rozdział tytułów chrystologicznych zamyka się obietnicą otwartego nieba. Od „czego szukacie" doszliśmy do „większe od tych rzeczy zobaczysz".''',
 "blocks": [
 {"label":"w. 43–44","cs":1,"vs":43,"ce":1,"ve":44,"greek":_gk(43,44),"transl":_pl(43,44),
  "units":[
  ("ἀκολούθει μοι","pójdź za Mną",
'''Jedyne w tym rozdziale powołanie wprost z ust Jezusa — bez pośrednika, bez świadectwa, dwa słowa rozkazu: ἀκολούθει μοι (pójdź za Mną; imperativus praesentis — „idź za Mną i nie przestawaj iść"). Ewangelista pokazuje całą paletę dróg do wiary: przez świadka (Andrzej i towarzysz), przez brata (Szymon), przez bezpośrednie wezwanie (Filip), przez przyjaciela i własne zmaganie (Natanael) — żadna nie jest jedynie słuszna. Betsaida (dosł. „dom rybaka") — miasteczko na pograniczu, z greckimi imionami mieszkańców: Ewangelia od pierwszych kroków stoi jedną nogą w świecie pogan, do którego ci ludzie kiedyś pójdą (por. J 12,20–22, gdzie Grecy szukają Jezusa właśnie przez Filipa i Andrzeja).'''),
  ]},
 {"label":"w. 45–46","cs":1,"vs":45,"ce":1,"ve":46,"greek":_gk(45,46),"transl":_pl(45,46),
  "units":[
  ("ὃν ἔγραψεν Μωϋσῆς ἐν τῷ νόμῳ καὶ οἱ προφῆται","o którym pisał Mojżesz w Prawie i Prorocy",
'''Wyznanie Filipa to cała hermeneutyka biblijna pierwszego Kościoła w jednym zdaniu: Pisma — Prawo i Prorocy — są o Kimś, i ten Ktoś da się znaleźć. Εὑρήκαμεν (znaleźliśmy) — trzecie ogniwo łańcucha znalezień. Zarazem Filip mówi o Znalezionym językiem najzwyklejszej metryki: „Jezus, syn Józefa, z Nazaretu" — czytelnik, który zna Prolog, słyszy przepaść między tym, co Filip mówi, a Tym, o kim mówi; Ewangelia celowo pokazuje, że wiara zaczyna od danych z dowodu osobistego, a kończy na „Pan mój i Bóg mój" (J 20,28).'''),
  ("ἔρχου καὶ ἴδε","przyjdź i zobacz",
'''Na szyderstwo Natanaela („z Nazaretu może być coś dobrego?" — Nazaret: wioska bez jednej wzmianki w ST, Talmudzie i u Flawiusza; prowincjonalna duma Kany, rodzinnego miasteczka Natanaela wedle J 21,2, też mogła grać rolę) Filip nie odpowiada argumentem, lecz metodą swojego Mistrza: ἔρχου καὶ ἴδε (przyjdź i zobacz) — dokładnie tą formułą, którą sam usłyszał pośrednio dzień wcześniej (w. 39). Apologetyka Janowa w pigułce: nie wygrywaj sporu — doprowadź do spotkania. Uprzedzenie nie ustępuje przed sylogizmem; ustępuje przed doświadczeniem.'''),
  ]},
 {"label":"w. 47–48","cs":1,"vs":47,"ce":1,"ve":48,"greek":_gk(47,48),"transl":_pl(47,48),
  "units":[
  ("ἀληθῶς Ἰσραηλίτης ἐν ᾧ δόλος οὐκ ἔστιν","prawdziwie Izraelita, w którym nie ma podstępu",
'''Zdanie z kluczem w Księdze Rodzaju: praojciec Izrael — Jakub — zdobył błogosławieństwo δόλῳ (podstępem; tak LXX w Rdz 27,35: „przyszedł twój brat podstępnie"). Natanael jest więc „prawdziwie Izraelitą" — anty-Jakubem: nosicielem obietnicy bez rodowej skazy oszustwa; Izraelem, jakim Izrael miał być (por. Ps 32,2: błogosławiony człowiek, w którego duchu nie ma podstępu — remija). Pochwała jest zarazem programem: do takiego Izraelity należy wizja, którą Jakub oglądał we śnie (w. 51). Szczerość — także szorstka szczerość sceptyka sprzed chwili — okazuje się glebą objawienia.'''),
  ("ὄντα ὑπὸ τὴν συκῆν εἶδόν σε","widziałem cię pod figowcem",
'''Co robił Natanael pod figowcem — tekst milczy, i to milczenie jest wymowne: wiedzą tylko oni dwaj, i właśnie ta prywatność wiedzy łamie opór Natanaela. Tło podwójne: w tradycji rabinackiej cień figowca to klasyczne miejsce studiowania Tory (uczeni „siedzący pod figowcem" nad Pismem), a „siedzieć pod swoją winoroślą i swoim figowcem" to prorocki obraz pokoju mesjańskiego (Mi 4,4; Za 3,10 — „w owym dniu będziecie się wzajemnie zapraszać pod winorośl i pod figowiec"). Jezus widzi więc Natanaela w miejscu jego najgłębszej tęsknoty — nad Pismem, w oczekiwaniu pokoju — zanim ktokolwiek go zawołał: πρὸ τοῦ σε Φίλιππον φωνῆσαι (zanim cię Filip zawołał). Łaska uprzedza pośrednika.'''),
  ]},
 {"label":"w. 49–51","cs":1,"vs":49,"ce":1,"ve":51,"greek":_gk(49,51),"transl":_pl(49,51),
  "units":[
  ("σὺ εἶ ὁ υἱὸς τοῦ θεοῦ, σὺ βασιλεὺς εἶ τοῦ Ἰσραήλ","Ty jesteś Synem Bożym, Ty jesteś Królem Izraela",
'''Wyznanie Natanaela domyka katalog tytułów rozdziału pierwszego — najgęstszej chrystologicznej litanii NT: Słowo, Bóg, Światłość, Jednorodzony, Mesjasz-Chrystus, Baranek Boży, Syn Boży, Rabbi, Król Izraela, Syn Człowieczy. „Król Izraela" (por. So 3,15: „Król Izraela, Pan, jest pośród ciebie") to tytuł, który powróci ironicznie w Męce — na ustach tłumu (J 12,13) i na tabliczce Piłata (J 19,19): to, co Natanael wyznał pod figowcem, Rzym przybije nad krzyżem w trzech językach.'''),
  ("ἀμὴν ἀμὴν λέγω ὑμῖν","amen, amen, mówię wam",
'''Pierwsze z dwudziestu pięciu Janowych podwójnych amen (hebr. amen — „niech się stanie", od rdzenia aman: być pewnym, wiernym; pokrewne emet — prawda). U synoptyków pojedyncze, u Jana zawsze zdwojone i zawsze otwierające (nie zamykające!) wypowiedź: Jezus nie potwierdza cudzych słów — uwierzytelnia własne, sam będąc Amen (por. Ap 3,14: „To mówi Amen, Świadek wierny"). Zauważmy przejście z liczby pojedynczej na mnogą: „mówię wam" — obietnica przekracza Natanaela i obejmuje wszystkich uczniów, z czytelnikiem włącznie.'''),
  ("τοὺς ἀγγέλους ... ἀναβαίνοντας καὶ καταβαίνοντας ἐπὶ τὸν υἱὸν τοῦ ἀνθρώπου","aniołów wstępujących i zstępujących na Syna Człowieczego",
'''Jawna typologia snu Jakuba (Rdz 28,12): drabina oparta o ziemię, sięgająca nieba, aniołowie wstępujący i zstępujący (ta sama kolejność — najpierw w górę, jakby ruch zaczynał się od ziemi). Jakub zbudził się i nazwał to miejsce Betel — dom Boga, brama nieba. Jezus podstawia siebie w miejsce drabiny: Syn Człowieczy JEST miejscem, w którym niebo i ziemia są połączone — nowym Betel, prawdziwym domem Boga; to samo, co ogłosiło ἐσκήνωσεν (rozbił namiot) w 1,14, powiedziane językiem wizji. Tytuł ὁ υἱὸς τοῦ ἀνθρώπου (Syn Człowieczy; aram. bar enasz — Dn 7,13: „jakby syn człowieczy" przychodzący na obłokach, któremu dana jest władza wieczna) — jedyny tytuł, którego Jezus używa sam o sobie — koryguje entuzjazm Natanaela: tak, Król, ale królestwo przyjdzie drogą Dn 7 czytaną przez Iz 53. „Większe od tych rzeczy zobaczysz": wiara z małego znaku otwiera oczy na znaki większe — zaczynając od Kany, „trzeciego dnia".'''),
  ]},
 ],
 "sections": [
 {"type":"kontekst","title":"II. Kontekst historyczny, językowy, kulturowy i religijny","body":
'''**Natanael.** Imię znaczy „Bóg dał" (netan-El); wymieniony tylko u Jana (tu i 21,2 — z Kany Galilejskiej); tradycja od średniowiecza utożsamia go z Bartłomiejem synoptyków (Bar-Tolmaj — syn Tolmaja: patronimik, nie imię własne; listy apostołów stawiają Bartłomieja obok Filipa). **Nazaret.** Osada tak podrzędna, że milczą o niej wszystkie źródła żydowskie epoki; wzgarda Natanaela to wzgarda Galilejczyka wobec sąsiedniej wioski — tym mocniej brzmi Janowy paradoks wybrania tego, co wzgardzone. **Figowiec.** Splot dwóch skojarzeń — studium Tory w cieniu drzewa i mesjański pokój „pod winoroślą i figowcem" (Mi 4,4; Za 3,10) — czynił z figowca niemal techniczny obraz pobożnego oczekiwania Izraela. **Drabina Jakubowa.** Rdz 28 czytano w synagodze z targumicznymi rozwinięciami (aniołowie oglądający oblicze śpiącego Jakuba wyryte w niebie); wizja należała do żelaznego repertuaru nadziei — Jezus sięga po obraz, który każdy słuchacz nosił w wyobraźni.''',
  "children":[]},
 {"type":"teologia","title":"III. Obserwacje teologiczne i filozoficzne w duchu tomistycznym","body":
'''**1. Wiedza Chrystusa.** „Widziałem cię pod figowcem" — Tomasz rozróżnia w Chrystusie wiedzę Boską, wiedzę błogosławionych i wiedzę nabytą; to widzenie na odległość, przenikające serce (por. J 2,25: sam wiedział, co jest w człowieku), przypisze poznaniu przekraczającemu naturę. Dla Natanaela znak jest mały; wystarcza, bo trafia w to, co najintymniejsze — Bóg przekonuje każdego tym, co tylko On o nim wie.

**2. Wiara i jej wzrost.** „Wierzysz? Większe zobaczysz" — wiara nie jest stanem, lecz drogą rosnącą: *fides quaerens intellectum* (wiara szukająca zrozumienia) i widzenia. Tomasz: łaska pomnaża się przez akty; kto uwierzył z małego, temu obiecane większe — zasada całej pedagogii znaków w czwartej Ewangelii.

**3. Pośrednictwo Chrystusa.** Drabina to obraz, który Tomasz czyta wprost: Chrystus jako jedyny pośrednik (*unus mediator*, 1 Tm 2,5) — w dół zstępuje łaska, w górę wstępuje modlitwa i natura ludzka; aniołowie „na Synu Człowieczym" oznaczają, że wszelka służba nieba przechodzi odtąd przez Wcielonego. Zjednoczenie hipostatyczne jest ontologiczną drabiną: w jednej Osobie ziemia dotyka nieba.''',
  "children":[]},
 {"type":"autor_ludzki","title":"IV. Autor ludzki: kim jest i co chce przekazać","body":
'''Ewangelista komponuje finał rozdziału jak jubiler: w czterech scenach tygodnia inauguracji rozmieścił wszystkie tytuły mesjańskie, by w ostatniej dołożyć zwieńczenie — tytuł, który Jezus wybiera sam. Portret Natanaela jest małym arcydziełem charakterologii: sceptyk uczciwy, którego opór nie jest cynizmem, lecz wiernością Pismu („czy z Nazaretu...?" to pytanie człowieka, który zna proroctwa o Betlejem) — autor pokazuje, że droga do wiary wiedzie także przez rzetelną wątpliwość. A obietnicą w. 51, sformułowaną w liczbie mnogiej i czasie przyszłym, ewangelista przerzuca most nad całą księgą: czytelniku, to, co teraz nastąpi — znaki, godzina, wywyższenie — jest tym otwartym niebem.''',
  "children":[]},
 {"type":"autor_bozy","title":"V. Autor Boży: co Duch Święty chce przekazać","body":
'''Duch Święty domyka rozdział lekcją o widzeniu: Jezus „zobaczył" Natanaela, zanim ten zobaczył Jezusa — każde nasze szukanie jest wtórne wobec bycia znalezionym; łaska uprzedzająca (gratia praeveniens) ma tu swoją ikonę. Zarazem Duch koryguje każdą wiarę, która chciałaby się zatrzymać na własnym wyznaniu: nawet pełna litania tytułów nie jest metą — „większe zobaczysz". I zostawia obietnicę eklezjalną: odkąd Słowo rozbiło namiot, dom Boga i brama nieba nie są miejscem na mapie, lecz Osobą — a przez Nią wspólnotą, w której ta Osoba trwa.''',
  "children":[]},
 {"type":"odniesienia","title":"VI. Sieć odniesień biblijnych","body":
'''**Rdz 28,10–19 → w. 51.** Sen Jakuba: drabina, aniołowie, Betel — dom Boga i brama nieba; Syn Człowieczy jako nowe Betel.

**Rdz 27,35 → w. 47.** Jakub zdobywa błogosławieństwo podstępem (LXX: μετὰ δόλου) — Natanael jest Izraelitą bez δόλος: anty-Jakub.

**Ps 32,2 → w. 47.** Błogosławiony, w którego duchu nie ma podstępu (remija) — psalmiczne tło pochwały.

**Mi 4,4; Za 3,10 → w. 48.** Pokój mesjański „pod winoroślą i figowcem" — figowiec jako miejsce tęsknoty za owym dniem.

**Pwt 18,15 → w. 45.** „Pisał Mojżesz" — obietnica Proroka; z Prorokami razem: cała hermeneutyka chrystologiczna Starego Testamentu.

**So 3,15 → w. 49.** „Król Izraela, Pan, jest pośród ciebie" — prorocki adres tytułu Natanaela.

**Dn 7,13–14 → w. 51.** Syn Człowieczy na obłokach, władza wieczna — tło jedynego autotytułu Jezusa.

**J 12,13; 19,19 → w. 49.** Król Izraela w Męce: hosanna tłumu i titulus (napis) Piłata — ironiczne dopełnienie wyznania.''',
  "children":[]},
 {"type":"recepcja","title":"VII. Znaczenie w historii i liturgii Kościoła","body":
'''Liturgia rzymska czyta w. 47–51 w święto Świętych Archaniołów Michała, Gabriela i Rafała (29 IX) — aniołowie wstępujący i zstępujący na Syna Człowieczego jako Ewangelia dnia aniołów; sam Natanael czczony jest — za utożsamieniem z Bartłomiejem — 24 VIII. „Przyjdź i zobacz" oraz „widziałem cię pod figowcem" weszły do języka kierownictwa duchowego jako formuły łaski uprzedzającej i osobistego wybrania; w tradycji monastycznej figowiec Natanaela bywał obrazem lectio divina (Bożego czytania) — miejsca, w którym Pan zastaje człowieka nad Pismem. Drabina Jakubowa odczytana chrystologicznie przez w. 51 zapłodniła i ikonografię (drabina do nieba), i duchowość (Reguła św. Benedykta, rozdz. 7: drabina pokory), i hymnografię maryjną Wschodu (Maryja „drabiną, po której zstąpił Bóg" — bo przez Nią przyszedł Ten, który sam jest drabiną).''',
  "children":[]},
 {"type":"patrystyka","title":"VIII. Komentarze Ojców Kościoła (catena patrum)","body":
'''Katena do finału rozdziału: figowiec i liście grzechu, sceptyk pochwalony, drabina zjednoczenia.''',
  "children":[]},
 ],
 "refs": [
 (("pericope",), "Rdz", 28, 10, 28, 19, "Rdz 28,10–19", "typologia", "drabina Jakubowa i Betel — Syn Człowieczy nowym domem Boga"),
 (("pericope",), "Rdz", 27, 35, 27, 35, "Rdz 27,35", "kontrast", "Jakub-podstęp (δόλος) — Natanael anty-Jakubem"),
 (("pericope",), "Ps", 32, 2, 32, 2, "Ps 32,2", "aluzja", "błogosławiony, w którego duchu nie ma podstępu"),
 (("pericope",), "Mi", 4, 4, 4, 4, "Mi 4,4", "tlo", "pokój pod winoroślą i figowcem"),
 (("pericope",), "Za", 3, 10, 3, 10, "Za 3,10", "tlo", "w owym dniu — zapraszanie pod figowiec"),
 (("pericope",), "Pwt", 18, 15, 18, 15, "Pwt 18,15", "aluzja", "pisał Mojżesz — obietnica Proroka"),
 (("pericope",), "So", 3, 15, 3, 15, "So 3,15", "tlo", "Król Izraela pośród ciebie"),
 (("pericope",), "Dn", 7, 13, 7, 14, "Dn 7,13–14", "tlo", "Syn Człowieczy na obłokach — bar enasz"),
 (("unit","w. 49–51",0), "J", 19, 19, 19, 19, "J 19,19", "rozwiniecie", "titulus Piłata: Król Żydów nad krzyżem"),
 (("unit","w. 45–46",1), "J", 4, 29, 4, 29, "J 4,29", "paralela", "Samarytanka: chodźcie, zobaczcie — ta sama metoda"),
 ],
 "patristic": [
 ("w. 47–48", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 7,21",
'''Augustyn pyta, czemu właśnie „pod figowcem" — i odpowiada obrazem z Rdz 3,7: liśćmi figowymi okryli się pierwsi rodzice po grzechu; figowiec jest cieniem śmiertelności, kondycją Adamową. „Widziałem cię pod figowcem" znaczy więc: ujrzałem cię w cieniu grzechu — i uprzedziłem cię miłosierdziem, zanim cię ktokolwiek zawołał. Jak Bóg w raju wołał „Adamie, gdzie jesteś?", tak tu Nowy Adam znajduje człowieka pod tym samym drzewem wstydu — ale już nie po to, by wyganiać, lecz by powołać. Łaska widzi nas wcześniej, niż my ją zobaczymy.'''),
 ("w. 45–46", "św. Jan Chryzostom", "Homilie na Ewangelię Jana", "Hom. in Io. 20–21",
'''Chryzostom broni Natanaela przed zarzutem małostkowości: jego „czy z Nazaretu może być coś dobrego?" to nie przewrotność, lecz dociekliwość człowieka biegłego w Pismach — wiedział, że Mesjasz ma przyjść z Betlejem, i nie dał się porwać entuzjazmowi przyjaciela bez sprawdzenia. Dlatego Chrystus chwali go, zanim ten uwierzył: prawda nie boi się badania, boi się tylko obojętności. A obietnica „większe zobaczysz" jest u Chryzostoma prawem duchowego wzrostu: Bóg odmierza objawienie wedle pojemności — kto wiernie przyjął krople, temu otworzy morze.'''),
 ("w. 49–51", "św. Cyryl Aleksandryjski", "Commentarii in Ioannem", "In Io., ks. II",
'''Drabinę Jakubową czyta Cyryl jako proroctwo zjednoczenia natur: aniołowie wstępują i zstępują „na Syna Człowieczego", bo w Nim otwarła się wymiana między niebem a ziemią — służą Temu, który będąc Bogiem, stał się człowiekiem, i w tej służbie łączą oba końce drabiny. Odtąd nie ma innej drogi ani w górę, ani w dół: modlitwa wstępuje przez Niego, łaska zstępuje przez Niego. Niebo „otwarte" (perfectum ἀνεῳγότα — otwarte i pozostające otwarte) to skutek Wcielenia, którego nic już nie cofnie.'''),
 ],
 "liturgy": [
 ("rzymski", "Święto Świętych Archaniołów (29 IX)", "J 1,47–51",
  "Aniołowie wstępujący i zstępujący na Syna Człowieczego — Ewangelia dnia aniołów."),
 ("rzymski", "Święto św. Bartłomieja Apostoła (24 VIII) — za utożsamieniem z Natanaelem", "J 1,45–51",
  "Tradycja od średniowiecza łączy Natanaela z Bartłomiejem list apostolskich."),
 ],
 "textual": [],
 "themes": [
 ("tytuły chrystologiczne J 1", ("block","w. 49–51")),
 ("nowy tydzień stworzenia (J 1,19–2,11)", ("pericope",)),
 ("Szechina — zamieszkanie Boga", ("block","w. 49–51")),
 ],
}

CONT = [P2, P3, P4, P5, P6]

# nowe motywy przekrojowe (INSERT OR IGNORE po nazwie; opisy)
THEMES2 = [
 ("Baranek Boży",
  "Tytuł z J 1,29.36 o czterech tłach (Pascha, Sługa z Iz 53, tamid, Baranek apokaliptyczny); oś liturgii eucharystycznej."),
 ("μένειν — trwać, pozostawać",
  '''Wielkie słowo Janowe: od Ducha, który pozostał (1,32-33), przez „gdzie mieszkasz" (1,38-39), po „trwajcie we Mnie" (15,4).'''),
 ("vox et verbum — głos a Słowo",
  "Para Chrzciciel-Chrystus (1,23 wobec 1,1); patrystyczna teologia przepowiadania (Augustyn, Sermo 293)."),
 ("nowy tydzień stworzenia (J 1,19–2,11)",
  "Odliczanie dni (nazajutrz... nazajutrz... trzeciego dnia) buduje tydzień inauguracji zamknięty godami w Kanie — nowe stworzenie kończy się weselem."),
 ("tytuły chrystologiczne J 1",
  "Katalog rozdziału pierwszego: Słowo, Bóg, Światłość, Jednorodzony, Mesjasz, Baranek, Syn Boży, Rabbi, Król Izraela, Syn Człowieczy."),
]

# ------------------------------------------------------------------
# 18. ROZSZERZENIE BAZY O J 1,15-51
# ------------------------------------------------------------------
def extend():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    cur = con.cursor()

    def book_of(ab):
        r = cur.execute("SELECT id FROM book WHERE abbrev_pl=?", (ab,)).fetchone()
        if r: return r[0]
        raise KeyError(ab)
    for ab, nm, tst, ordn in BOOKS2:
        cur.execute("INSERT OR IGNORE INTO book(abbrev_pl, name_pl, testament, canon_order) VALUES (?,?,?,?)",
                    (ab, nm, tst, ordn))
    bid_J = book_of("J")

    # wersety 15-51
    verse_id = {}
    for vn, (gk, pl) in VERSES2.items():
        cur.execute("INSERT INTO verse(book_id, chapter, verse_num, text_greek, text_working_pl) VALUES (?,?,?,?,?)",
                    (bid_J, 1, vn, gk, pl))
        verse_id[vn] = cur.lastrowid

    # leksemy / terminy semickie / powiązania / wystąpienia
    def lex_of(lemma):
        return cur.execute("SELECT id FROM lexeme WHERE lemma=?", (lemma,)).fetchone()[0]
    for lemma, tr, pos_, gl in LEXEMES2:
        cur.execute("INSERT OR IGNORE INTO lexeme(lemma, translit, pos, gloss_pl) VALUES (?,?,?,?)",
                    (lemma, tr, pos_, gl))
    def sem_of(tr):
        return cur.execute("SELECT id FROM semitic_term WHERE translit=?", (tr,)).fetchone()[0]
    for term, tr, lang, gl in SEMITIC2:
        cur.execute("INSERT OR IGNORE INTO semitic_term(term, translit, lang, gloss_pl) VALUES (?,?,?,?)",
                    (term, tr, lang, gl))
    for lemma, sem_tr, note in LEXSEM2:
        cur.execute("INSERT OR IGNORE INTO lexeme_semitic(lexeme_id, semitic_id, relation_note) VALUES (?,?,?)",
                    (lex_of(lemma), sem_of(sem_tr), note))
    for lemma, vn, form in OCC2:
        cur.execute("INSERT INTO lexeme_occurrence(lexeme_id, verse_id, form_in_text) VALUES (?,?,?)",
                    (lex_of(lemma), verse_id[vn], form))

    # dzieła (nowe w katenie kontynuacji)
    cur.execute("""INSERT OR IGNORE INTO work(author, title, title_pl, century, tradition)
                   VALUES ('św. Augustyn','Sermones','Kazania','IV/V','patrystyka')""")
    def work_of(author, title):
        return cur.execute("SELECT id FROM work WHERE author=? AND title=?", (author, title)).fetchone()[0]

    # motywy
    for name, desc in THEMES2:
        cur.execute("INSERT OR IGNORE INTO theme(name, description_md) VALUES (?,?)", (name, desc))
    def theme_of(name):
        return cur.execute("SELECT id FROM theme WHERE name=?", (name,)).fetchone()[0]

    # perykopy
    for P in CONT:
        pd = P["pericope"]
        cur.execute("""INSERT INTO pericope(book_id, chapter_start, verse_start, chapter_end, verse_end,
                       title, motto, status, position) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (bid_J, pd["cs"], pd["vs"], pd["ce"], pd["ve"],
                     pd["title"], pd["motto"], pd["status"], pd["position"]))
        pid = cur.lastrowid

        section_id, block_id, unit_id = {}, {}, {}
        def add_section(stype, title, body, parent, pos):
            cur.execute("""INSERT INTO section(pericope_id, parent_id, section_type, title, body_md, position)
                           VALUES (?,?,?,?,?,?)""", (pid, parent, stype, title, body, pos))
            section_id[title] = cur.lastrowid
            return cur.lastrowid

        sec1 = add_section("filologia",
                           "I. Tekst grecki (Nestle-Aland, wyd. 28) z przekładem roboczym i analizą filologiczną",
                           P["intro"], None, 1)
        for bpos, b in enumerate(P["blocks"], start=1):
            cur.execute("""INSERT INTO commentary_block(section_id, chapter_start, verse_start, chapter_end,
                           verse_end, label, greek_text, working_translation_pl, position)
                           VALUES (?,?,?,?,?,?,?,?,?)""",
                        (sec1, b["cs"], b["vs"], b["ce"], b["ve"], b["label"], b["greek"], b["transl"], bpos))
            block_id[b["label"]] = cur.lastrowid
            for upos, (phr, phr_pl, body) in enumerate(b["units"]):
                cur.execute("""INSERT INTO analysis_unit(block_id, phrase_greek, phrase_translation_pl, body_md, position)
                               VALUES (?,?,?,?,?)""",
                            (block_id[b["label"]], phr, phr_pl, body.strip(), upos))
                unit_id[(b["label"], upos)] = cur.lastrowid

        for spos, s in enumerate(P["sections"], start=2):
            top = add_section(s["type"], s["title"], s["body"], None, spos)
            for cpos, (ct, cb) in enumerate(s["children"], start=1):
                add_section(s["type"], ct, cb.strip(), top, cpos)

        def source_cols(src):
            if src[0] == "pericope": return pid, None, None
            if src[0] == "section":  return None, section_id[src[1]], None
            if src[0] == "unit":     return None, None, unit_id[(src[1], src[2])]
            raise ValueError(src)

        for src, tb, cs, vs, ce, ve, label, rel, note in P["refs"]:
            sp, ss, su = source_cols(src)
            cur.execute("""INSERT INTO scripture_ref(pericope_id, section_id, analysis_unit_id,
                           target_book_id, target_chapter_start, target_verse_start,
                           target_chapter_end, target_verse_end, target_label, relation, note_md)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (sp, ss, su, book_of(tb), cs, vs, ce, ve, label, rel, note))

        pos_per_block = {}
        for blabel, author, wtitle, locus, body in P["patristic"]:
            pos_per_block[blabel] = pos_per_block.get(blabel, 0) + 1
            cur.execute("""INSERT INTO patristic_comment(work_id, block_id, locus, body_md, position)
                           VALUES (?,?,?,?,?)""",
                        (work_of(author, wtitle), block_id[blabel], locus, body.strip(),
                         pos_per_block[blabel]))

        for rite, occ, passage, desc in P["liturgy"]:
            cur.execute("""INSERT INTO liturgical_use(pericope_id, rite, occasion, passage, description_md)
                           VALUES (?,?,?,?,?)""", (pid, rite, occ, passage, desc))

        for vn, lemma, issue, readings, assessment in P["textual"]:
            cur.execute("""INSERT INTO textual_note(verse_id, lemma_text, issue, readings_md, assessment_md)
                           VALUES (?,?,?,?,?)""", (verse_id[vn], lemma, issue, readings, assessment))

        for name, link in P["themes"]:
            tid = theme_of(name)
            cols = {"pericope_id": None, "section_id": None, "block_id": None, "analysis_unit_id": None}
            if link[0] == "pericope":  cols["pericope_id"] = pid
            elif link[0] == "section": cols["section_id"] = section_id[link[1]]
            elif link[0] == "block":   cols["block_id"] = block_id[link[1]]
            elif link[0] == "unit":    cols["analysis_unit_id"] = unit_id[(link[1], link[2])]
            cur.execute("""INSERT INTO theme_link(theme_id, pericope_id, section_id, block_id, analysis_unit_id)
                           VALUES (?,?,?,?,?)""",
                        (tid, cols["pericope_id"], cols["section_id"], cols["block_id"], cols["analysis_unit_id"]))

        cur.execute("INSERT INTO revision_log(entity, entity_id, note) VALUES (?,?,?)",
                    ("pericope", pid, f"Dodano perykopę {pd['title']} (J {pd['cs']},{pd['vs']}-{pd['ve']}) z kateną"))

    con.commit()
    n = cur.execute("SELECT count(*) FROM pericope").fetchone()[0]
    print(f"extend OK — perykop w bazie: {n}")
    con.close()


# ------------------------------------------------------------------
# 19. PERYKOPA 7: J 2,1-11 — Wesele w Kanie Galilejskiej
# ------------------------------------------------------------------
VERSES3 = {
    1: ("Καὶ τῇ ἡμέρᾳ τῇ τρίτῃ γάμος ἐγένετο ἐν Κανὰ τῆς Γαλιλαίας, καὶ ἦν ἡ μήτηρ τοῦ Ἰησοῦ ἐκεῖ·",
        "A trzeciego dnia odbyło się wesele w Kanie Galilejskiej i była tam matka Jezusa."),
    2: ("ἐκλήθη δὲ καὶ ὁ Ἰησοῦς καὶ οἱ μαθηταὶ αὐτοῦ εἰς τὸν γάμον.",
        "Zaproszony był też na wesele Jezus i Jego uczniowie."),
    3: ("καὶ ὑστερήσαντος οἴνου λέγει ἡ μήτηρ τοῦ Ἰησοῦ πρὸς αὐτόν· οἶνον οὐκ ἔχουσιν.",
        "A gdy zabrakło wina, mówi matka Jezusa do Niego: Wina nie mają."),
    4: ("[καὶ] λέγει αὐτῇ ὁ Ἰησοῦς· τί ἐμοὶ καὶ σοί, γύναι; οὔπω ἥκει ἡ ὥρα μου.",
        "[I] mówi jej Jezus: Co Mnie i tobie, niewiasto? Jeszcze nie nadeszła godzina moja."),
    5: ("λέγει ἡ μήτηρ αὐτοῦ τοῖς διακόνοις· ὅ τι ἂν λέγῃ ὑμῖν ποιήσατε.",
        "Mówi Jego matka sługom: Cokolwiek wam powie, czyńcie."),
    6: ("ἦσαν δὲ ἐκεῖ λίθιναι ὑδρίαι ἓξ κατὰ τὸν καθαρισμὸν τῶν Ἰουδαίων κείμεναι, χωροῦσαι ἀνὰ μετρητὰς δύο ἢ τρεῖς.",
        "A stało tam sześć kamiennych stągwi, ustawionych do żydowskiego oczyszczenia, mieszczących po dwie lub trzy miary."),
    7: ("λέγει αὐτοῖς ὁ Ἰησοῦς· γεμίσατε τὰς ὑδρίας ὕδατος. καὶ ἐγέμισαν αὐτὰς ἕως ἄνω.",
        "Mówi im Jezus: Napełnijcie stągwie wodą. I napełnili je aż po brzegi."),
    8: ("καὶ λέγει αὐτοῖς· ἀντλήσατε νῦν καὶ φέρετε τῷ ἀρχιτρικλίνῳ· οἱ δὲ ἤνεγκαν.",
        "I mówi im: Zaczerpnijcie teraz i zanieście staroście weselnemu. Oni zaś zanieśli."),
    9: ("ὡς δὲ ἐγεύσατο ὁ ἀρχιτρίκλινος τὸ ὕδωρ οἶνον γεγενημένον καὶ οὐκ ᾔδει πόθεν ἐστίν, οἱ δὲ διάκονοι ᾔδεισαν οἱ ἠντληκότες τὸ ὕδωρ, φωνεῖ τὸν νυμφίον ὁ ἀρχιτρίκλινος",
        "A gdy starosta skosztował wody, która stała się winem — a nie wiedział, skąd jest; słudzy zaś, którzy zaczerpnęli wody, wiedzieli — woła starosta pana młodego"),
    10: ("καὶ λέγει αὐτῷ· πᾶς ἄνθρωπος πρῶτον τὸν καλὸν οἶνον τίθησιν καὶ ὅταν μεθυσθῶσιν τὸν ἐλάσσω· σὺ τετήρηκας τὸν καλὸν οἶνον ἕως ἄρτι.",
        "i mówi mu: Każdy człowiek stawia najpierw dobre wino, a gdy sobie podpiją — gorsze; ty zachowałeś dobre wino aż dotąd."),
    11: ("Ταύτην ἐποίησεν ἀρχὴν τῶν σημείων ὁ Ἰησοῦς ἐν Κανὰ τῆς Γαλιλαίας καὶ ἐφανέρωσεν τὴν δόξαν αὐτοῦ, καὶ ἐπίστευσαν εἰς αὐτὸν οἱ μαθηταὶ αὐτοῦ.",
        "Ten początek znaków uczynił Jezus w Kanie Galilejskiej i objawił swoją chwałę, i uwierzyli w Niego Jego uczniowie."),
}

def _gk3(a, b):
    return " ".join(VERSES3[v][0] for v in range(a, b + 1))
def _pl3(a, b):
    return " ".join(VERSES3[v][1] for v in range(a, b + 1))

BOOKS3 = [
    ("Am", "Księga Amosa", "ST", 37),
]

LEXEMES3 = [
    ("γάμος", "gamos", "rzeczownik", "wesele, gody (mesjańska uczta weselna)"),
    ("οἶνος", "oinos", "rzeczownik", "wino — biblijny znak radości i czasów mesjańskich"),
    ("ὥρα", "hora", "rzeczownik", "godzina — u Jana: wyznaczony czas uwielbienia przez krzyż (2,4; 7,30; 12,23; 13,1; 17,1)"),
    ("γυνή", "gyne", "rzeczownik", "kobieta, niewiasta — u Jana tytuł teologiczny (2,4; 19,26)"),
    ("σημεῖον", "semeion", "rzeczownik", "znak — Janowe słowo na cud: wskazuje poza siebie (nie θαῦμα — dziw)"),
    ("φανερόω", "phaneroo", "czasownik", "objawić, uczynić jawnym"),
    ("ὑδρία", "hydria", "rzeczownik", "stągiew na wodę"),
    ("καθαρισμός", "katharismos", "rzeczownik", "oczyszczenie (rytualne)"),
    ("διάκονος", "diakonos", "rzeczownik", "sługa, usługujący (stąd diakon)"),
    ("νυμφίος", "nymphios", "rzeczownik", "pan młody, oblubieniec"),
]

SEMITIC3 = [
    ("מַה־לִּי וָלָךְ", "ma-li wa-lach", "hbr",
     "co mnie i tobie — idiom dystansu wobec wtrącenia (Sdz 11,12; 1 Krl 17,18); tło τί ἐμοὶ καὶ σοί w 2,4"),
]

OCC3 = [
    ("γάμος", 1, "γάμος"), ("γάμος", 2, "γάμον"),
    ("γίνομαι", 1, "ἐγένετο"),
    ("οἶνος", 3, "οἴνου / οἶνον"), ("οἶνος", 9, "οἶνον"), ("οἶνος", 10, "οἶνον"),
    ("γυνή", 4, "γύναι"), ("ὥρα", 4, "ὥρα"),
    ("διάκονος", 5, "διακόνοις"), ("διάκονος", 9, "διάκονοι"),
    ("ὑδρία", 6, "ὑδρίαι"), ("ὑδρία", 7, "ὑδρίας"),
    ("καθαρισμός", 6, "καθαρισμόν"),
    ("γίνομαι", 9, "γεγενημένον"),
    ("νυμφίος", 9, "νυμφίον"),
    ("ἀρχή", 11, "ἀρχήν"), ("σημεῖον", 11, "σημείων"),
    ("φανερόω", 11, "ἐφανέρωσεν"), ("δόξα", 11, "δόξαν"),
    ("πιστεύω", 11, "ἐπίστευσαν"),
]

P7 = {
 "pericope": {"cs":2,"vs":1,"ce":2,"ve":11,"title":"Wesele w Kanie Galilejskiej",
              "motto":"Quodcumque dixerit vobis, facite (Cokolwiek wam powie, czyńcie)",
              "status":"w_opracowaniu","position":7},
 "intro": '''„Trzeciego dnia" — tydzień inauguracji dobiega szczytu. Nowe stworzenie, odliczane dzień po dniu od J 1,19, kończy się nie kazaniem, lecz weselem: pierwszy znak Jezusa jest znakiem nadmiaru radości. W jedenastu wersetach spinają się wszystkie nici rozdziału pierwszego: ἀρχή (początek) wraca z 1,1, δόξα (chwała) z 1,14, wiara uczniów z 1,50 — a nad wszystkim po raz pierwszy pada słowo, które poprowadzi księgę do końca: godzina.''',
 "blocks": [
 {"label":"w. 1–2","cs":2,"vs":1,"ce":2,"ve":2,"greek":_gk3(1,2),"transl":_pl3(1,2),
  "units":[
  ("τῇ ἡμέρᾳ τῇ τρίτῃ","trzeciego dnia",
'''Rachuba jest podwójna i obie warstwy są zamierzone. (1) Trzeci dzień od powołania Natanaela zamyka tydzień inauguracji (J 1,19–2,11): dzień pierwszy — przesłuchanie, „nazajutrz" — Baranek, „nazajutrz" — pierwsi uczniowie, „nazajutrz" — Filip i Natanael, „trzeciego dnia" — Kana; nowy tydzień stworzenia kończy się godami, jak pierwszy kończył się szabatem. (2) „Trzeciego dnia" to w Biblii dzień teofanii i ocalenia: trzeciego dnia Pan zstąpił na Synaj (Wj 19,11.16), trzeciego dnia Bóg wskrzesza (Oz 6,2) — a chrześcijańskie ucho słyszy tu przede wszystkim zapowiedź Zmartwychwstania. Pierwsze objawienie chwały nosi datę ostatniego.'''),
  ("ἡ μήτηρ τοῦ Ἰησοῦ","matka Jezusa",
'''Czwarta Ewangelia nigdy nie nazywa Maryi po imieniu — zawsze „matka Jezusa" albo „niewiasta": nie z chłodu, lecz z typologii; jak „uczeń, którego Jezus miłował", jest postacią, w której czytelnik ma zobaczyć więcej niż jednostkę. Występuje w tej księdze dokładnie dwa razy: na początku znaków (Kana) i w godzinie krzyża (J 19,25–27) — klamra zamierzona, bo oba razy pada to samo słowo γύναι (niewiasto) i oba razy chodzi o godzinę.'''),
  ]},
 {"label":"w. 3–5","cs":2,"vs":3,"ce":2,"ve":5,"greek":_gk3(3,5),"transl":_pl3(3,5),
  "units":[
  ("οἶνον οὐκ ἔχουσιν","wina nie mają",
'''Modlitwa wstawiennicza w trzech słowach: bez prośby, bez instrukcji — samo przedstawienie braku. Na weselu żydowskim, trwającym do siedmiu dni, wino było obowiązkiem gościnności; jego brak okrywał rodzinę wstydem na lata. Ale zdanie niesie więcej niż towarzyską katastrofę: wino to w Biblii radość (Ps 104,15: wino rozwesela serce człowieka) i znak czasów mesjańskich (Am 9,13: góry ociekać będą moszczem; Iz 25,6: uczta z wystałych win). „Wina nie mają" — diagnoza Izraela i ludzkości u progu Ewangelii: skończyła się radość pierwszego przymierza; stągwie oczyszczeń stoją pełne wody, a wesele umiera.'''),
  ("τί ἐμοὶ καὶ σοί, γύναι;","co Mnie i tobie, niewiasto?",
'''Semityzm ma-li wa-lach (co mnie i tobie — Sdz 11,12; 1 Krl 17,18): idiom zaznaczający dystans wobec wtrącenia — nie obelga, lecz sygnał innego porządku: między prośbą matki a działaniem Syna staje wola Ojca i „godzina". Γύναι (niewiasto) — wołacz uprzejmy, ale w ustach syna do matki bezprecedensowy; Jan używa go celowo i powtórzy pod krzyżem (19,26). Od Ojców po współczesnych egzegetów czytano tu Niewiastę z Rdz 3,15 — nową Ewę przy nowym Adamie: w Kanie zaczyna się scena, którą dokończy Golgota, gdzie Niewiasta otrzyma macierzyństwo wobec ucznia. Ἡ ὥρα μου (godzina moja) — pierwsze uderzenie zegara czwartej Ewangelii: „godzina" będzie wracać (7,30; 8,20: jeszcze nie nadeszła; 12,23; 13,1; 17,1: nadeszła) i zawsze znaczy jedno — uwielbienie przez krzyż. Prośba o wino dotknęła, nie wiedząc, sprężyny całej księgi: dać wino naprawdę znaczy wydać krew.'''),
  ("ὅ τι ἂν λέγῃ ὑμῖν ποιήσατε","cokolwiek wam powie, czyńcie",
'''Ostatnie zdanie Maryi zapisane w Ewangeliach — i doskonały testament: nie „zróbcie, co mówię", lecz „czyńcie, cokolwiek On powie". Fraza jest niemal cytatem z Rdz 41,55: faraon odsyła głodny Egipt do Józefa słowami „co wam powie, czyńcie" — Maryja staje w roli faraona wskazującego nowego Józefa, szafarza w czasie braku. Zauważmy logikę wiary: po odpowiedzi, która brzmiała jak odmowa, matka nie wycofuje prośby, lecz przygotowuje posłuszeństwo — wierzy w „tak" ukryte w „jeszcze nie". To pierwszy akt wiary Nowego Testamentu wobec słowa Jezusa, złożony zanim jakikolwiek znak się dokonał.'''),
  ]},
 {"label":"w. 6–8","cs":2,"vs":6,"ce":2,"ve":8,"greek":_gk3(6,8),"transl":_pl3(6,8),
  "units":[
  ("λίθιναι ὑδρίαι ἓξ","sześć kamiennych stągwi",
'''Każde słowo pracuje. Kamienne — bo według halachy (prawa) naczynia kamienne nie przyjmują nieczystości rytualnej (archeologia Galilei I wieku potwierdza masową produkcję naczyń kamiennych); to sprzęt religijny, nie kuchenny. Sześć — liczba o jeden mniejsza od pełni siódemki: system oczyszczeń dobry, lecz niepełny, czekający. Κατὰ τὸν καθαρισμὸν τῶν Ἰουδαίων (do żydowskiego oczyszczenia) — woda obmyć rytualnych stanie się winem wesela: nie zniesienie Prawa, lecz jego przemiana w radość (dokładnie logika 1,17). Pojemność: μετρητής (miara) ≈ 39 litrów; dwie–trzy miary na stągiew × sześć stągwi ≈ 500–700 litrów. Nadmiar jest skandaliczny i celowy: tak wygląda mesjańska obfitość — Bóg nie odmierza łaski aptekarską miarką.'''),
  ("γεμίσατε ... ἕως ἄνω","napełnijcie ... aż po brzegi",
'''Cud potrzebuje posłuszeństwa bez zrozumienia: słudzy noszą setki litrów wody, nie wiedząc po co — i napełniają ἕως ἄνω (aż po brzegi), z gorliwością przekraczającą polecenie. Jan zapisuje tę nadgorliwość z czułością: pełnia cudu odpowiada pełni posłuszeństwa; kto napełnia do połowy, do połowy zobaczy. Sekwencja „napełnijcie — zaczerpnijcie — zanieście" jest też liturgią w zalążku: ludzkie ręce podają materię, Pan daje przemianę, a droga wiedzie od posługi do stołu.'''),
  ]},
 {"label":"w. 9–10","cs":2,"vs":9,"ce":2,"ve":10,"greek":_gk3(9,10),"transl":_pl3(9,10),
  "units":[
  ("τὸ ὕδωρ οἶνον γεγενημένον","wodę, która stała się winem",
'''Participium perfecti od γίνομαι (stawać się) — czasownika, który w Prologu opisywał stworzenie (πάντα δι᾿ αὐτοῦ ἐγένετο — wszystko przez Nie się stało) i Wcielenie (ὁ λόγος σὰρξ ἐγένετο — Słowo ciałem się stało): ten sam Sprawca, ten sam czasownik, ta sama dyskrecja. Sam moment przemiany nie jest opisany — Jan nie pokazuje „jak", pokazuje „skąd i dokąd": nikt nie widzi cudu, wszyscy widzą skutek. Ironia wiedzy: starosta, ekspert od wina, nie wie πόθεν (skąd); słudzy, którzy nosili wodę, wiedzą — u Jana wiedza o pochodzeniu darów należy do tych, którzy służą (πόθεν powróci jako pytanie o samego Jezusa: 7,27n; 19,9).'''),
  ("σὺ τετήρηκας τὸν καλὸν οἶνον ἕως ἄρτι","ty zachowałeś dobre wino aż dotąd",
'''Starosta wygłasza — nieświadomie — teologię historii zbawienia: świat daje najpierw dobre, potem gorsze (młodość, potem osad); Bóg odwrotnie — najlepsze zachował na koniec. Καλός (dobry, piękny, szlachetny — to samo słowo, którym Jezus nazwie się Dobrym Pasterzem, 10,11): nowe wino przymierza nie jest tańszym zamiennikiem, lecz winem lepszym od wszystkiego, co podano dotąd. Ἕως ἄρτι (aż dotąd) — „teraz" Ewangelii: czytelnik stoi przy stole, na który właśnie wjechało to wino.'''),
  ]},
 {"label":"w. 11","cs":2,"vs":11,"ce":2,"ve":11,"greek":VERSES3[11][0],"transl":VERSES3[11][1],
  "units":[
  ("ἀρχὴν τῶν σημείων","początek znaków",
'''Ἀρχή (początek) — ostatni raz padło w 1,1: ἐν ἀρχῇ ἦν ὁ λόγος (na początku było Słowo). Nowy „początek" jest więc początkiem w mocnym sensie: nie pierwszym numerem na liście cudów, lecz zasadą i wzorem wszystkich znaków — każdy następny (jest ich w księdze siedem) będzie wariacją Kany: materia, brak, słowo, przemiana, chwała, wiara. Σημεῖον (znak): Jan nigdy nie mówi o „cudach" językiem zdumienia (θαύματα — dziwy) ani mocy (δυνάμεις — dzieła mocy, jak synoptycy) — znak jest strzałką: wart tyle, ile wskazuje; kto zatrzymał się na winie, nie zobaczył nic.'''),
  ("ἐφανέρωσεν τὴν δόξαν αὐτοῦ","objawił swoją chwałę",
'''Spłata obietnicy z Prologu: ἐθεασάμεθα τὴν δόξαν αὐτοῦ (oglądaliśmy chwałę Jego, 1,14) — oto pierwsza rata tego oglądania; i obietnicy sprzed czterech dni: μείζω τούτων ὄψῃ (większe zobaczysz, 1,50). Chwała (δόξα — kawod, obecność) objawia się nie w błyskawicy, lecz w uratowanym weselu ubogiej rodziny: styl Boga Janowego. Καὶ ἐπίστευσαν εἰς αὐτὸν οἱ μαθηταὶ αὐτοῦ (i uwierzyli w Niego Jego uczniowie) — cel całej księgi (J 20,31: abyście wierzyli) osiągnięty po raz pierwszy; wiara z rozdziału 1, zrodzona ze świadectwa, tu dojrzewa przez widzenie znaku. Struktura „znak → chwała → wiara" będzie odtąd metrum Ewangelii.'''),
  ]},
 ],
 "sections": [
 {"type":"kontekst","title":"II. Kontekst historyczny, językowy, kulturowy i religijny","body":
'''**Wesele galilejskie.** Uroczystość do siedmiu dni (por. Rdz 29,27; Sdz 14,12), z procesją, ucztą i winem jako rdzeniem gościnności; za zapasy odpowiadał pan młody (stąd pretensja starosty w w. 10 idzie do niego). Brak wina to kompromitacja rodziny wobec całej wioski — Kana leżała kilka–kilkanaście kilometrów od Nazaretu (dziś wskazywana Chirbet Kana lub Kefr Kenna), zaproszenie Maryi i Jezusa sugeruje więzi rodzinne lub sąsiedzkie (Natanael był z Kany, J 21,2). **Naczynia kamienne.** Halacha czystości uznawała kamień za nieprzyjmujący nieczystości (por. Kpł 11,33 o naczyniach glinianych, które trzeba tłuc); wykopaliska w Galilei (Jerozolima, Reina k. Nazaretu — warsztaty!) potwierdzają boom produkcji naczyń kamiennych w I wieku: detal Janowy jest archeologicznie precyzyjny. **Wino czasów ostatecznych.** Prorocy malują erę mesjańską obfitością wina: Am 9,13–14, Jl 4,18 (góry moczem opływać będą), Iz 25,6 (uczta z wystałych win na górze Syjon); apokaliptyka (2 Ba 29,5) liczy grona ery mesjańskiej w tysiącach. Pierwszy znak mówi więc językiem, który każdy Żyd rozumiał bez słownika: zaczęły się gody mesjańskie. **Trzeci dzień.** Wj 19,10–11.16: „na trzeci dzień Pan zstąpi na oczach całego ludu na górę Synaj" — objawienie chwały trzeciego dnia po dniach przygotowania; tradycja żydowska łączyła trzeci dzień z ocaleniem (Rdz 22,4; Oz 6,2; Jon 2,1).''',
  "children":[]},
 {"type":"teologia","title":"III. Obserwacje teologiczne i filozoficzne w duchu tomistycznym","body":
'''**1. Cud a natura.** Tomasz definiuje cud jako dzieło dokonane przez Boga poza porządkiem całej natury stworzonej (*praeter ordinem totius naturae creatae*); Kana jest wzorcowa: woda staje się winem co roku — w winorośli, przez deszcz, glebę i słońce; tu Stwórca skraca drogę własnego stworzenia, niczego nie gwałcąc. Cud nie jest wyjątkiem od rozumności świata, lecz podpisem Autora złożonym Jego zwykłym charakterem pisma, tylko szybciej.

**2. Wstawiennictwo i pośrednictwo.** Prośba Maryi jest przyczyną wstawienniczą, nie sprawczą: nie czyni cudu, lecz uprasza go u Tego, który czyni — wzór wszelkiego pośrednictwa świętych *w* jedynym Pośredniku (1 Tm 2,5), nie obok Niego. Tomistyczna zasada: Bóg chce udzielać darów także przez porządek próśb, aby stworzenia miały godność przyczyn — Kana jest jej ewangelicznym paradygmatem.

**3. Małżeństwo uświęcone.** Obecność Chrystusa na godach Ojcowie i scholastyka czytają jako uświęcenie małżeństwa u progu Nowego Przymierza: to, co było „wielką tajemnicą" stworzenia (Rdz 2,24), staje się znakiem oblubieńczej miłości Chrystusa i Kościoła (Ef 5,32); Tomasz umieści małżeństwo wśród siedmiu sakramentów jako znak tej właśnie unii. Pierwszy cud Jezusa jest prezentem ślubnym — teologia ciała zaczyna się od uratowanego wesela.

**4. Znak i akt wiary.** Σημεῖον prowadzi od widzialnego do niewidzialnego jak przesłanka do wniosku — ale wiara nie jest wnioskiem koniecznym: starosta skosztował tego samego wina i nie uwierzył, bo nie zapytał „skąd". Tomasz: do wiary trzeba i znaku zewnętrznego, i wewnętrznego pociągnięcia łaski (*instinctus interior*); Kana pokazuje oba — i wolność, która może zatrzymać się na smaku.''',
  "children":[]},
 {"type":"autor_ludzki","title":"IV. Autor ludzki: kim jest i co chce przekazać","body":
'''Kompozycja zdradza rękę mistrza: tydzień inauguracji domknięty „trzecim dniem"; inkluzja dwóch znaków w Kanie (2,1–11 i 4,46–54 — „drugi znak", jakby autor odhaczał ramę); klamra „matka Jezusa — godzina — niewiasta" zarzucona aż po 19,25–27. Szczegóły mają fakturę naocznego wspomnienia: liczba i tworzywo stągwi, ich pojemność, tytuł ἀρχιτρίκλινος (starosta weselny), przytoczona dosłownie rubaszna maksyma o kolejności win. Zarazem autor pisze z dyskrecją teologa: sam cud dzieje się poza kadrem, między w. 8 a 9 — bo nie mechanika przemiany jest tematem, lecz jej sens. I rys polemiczny à rebours: pierwszy znak Mesjasza nie dzieje się w Świątyni ani na pustyni, lecz w kuchni wiejskiego wesela — przeciw każdej religijności, która szuka Boga tylko w sacrum wydzielonym.''',
  "children":[]},
 {"type":"autor_bozy","title":"V. Autor Boży: co Duch Święty chce przekazać","body":
'''Duch Święty ustanawia w Kanie gramatykę znaków, którą czytelnik ma stosować do końca księgi — i do własnego życia: brak przedstawiony w modlitwie, słowo przyjęte w posłuszeństwie, materia podana ludzkimi rękami, przemiana dokonana dyskretnie, chwała objawiona, wiara pogłębiona. Ta sekwencja jest matrycą sakramentalną: Kościół od starożytności widział w wodzie przemienionej w wino zapowiedź Eucharystii (a w „godzinie" — Krzyż, z którego ona wypływa). Duch zostawia też lekcję o Maryi: jej ostatnie słowo w Piśmie — „cokolwiek wam powie, czyńcie" — jest całym jej orędziem; prawdziwa pobożność maryjna kończy się zawsze posłuszeństwem Jezusowi. I lekcję o Bogu: który na początek znaków wybrał ratowanie ludzkiej radości — nie nasze łzy są Mu potrzebne, lecz nasze wesele.''',
  "children":[]},
 {"type":"odniesienia","title":"VI. Sieć odniesień biblijnych","body":
'''**Rdz 41,55 → w. 5.** „Co wam powie, czyńcie" — faraon o Józefie w czasie głodu; Maryja wskazuje nowego Józefa, szafarza w czasie braku.

**Wj 19,10–11.16 → w. 1.** Trzeciego dnia Pan zstępuje na Synaj w chwale — trzeci dzień jako dzień teofanii; por. Oz 6,2 (trzeciego dnia nas wskrzesi).

**Ps 104,15 → w. 3.** Wino rozwesela serce człowieka — antropologia daru.

**Iz 25,6; Am 9,13–14 → w. 3.6–10.** Uczta z wystałych win i góry ociekające moszczem — obfitość wina znakiem ery mesjańskiej; stąd wymowa 500–700 litrów.

**Pnp 1,2; 2,4 → całość.** Miłość lepsza niż wino; dom wina — oblubieńcze tło godów; mistyka czyta Kanę kluczem Pieśni.

**Rdz 3,15 → w. 4.** Niewiasta i jej potomstwo — protoewangelia; γύναι w 2,4 i 19,26 jako klamra nowej Ewy.

**Mk 2,19–22 → całość.** Oblubieniec, nowe wino i stare bukłaki — synoptyczna paralela tej samej teologii nowości.

**J 4,46–54 → całość.** „Drugi znak" w Kanie — inkluzja spinająca sekcję znaków galilejskich.

**J 19,25–27 → w. 4.** Niewiasta pod krzyżem w godzinie — dokończenie sceny z Kany.

**Ap 19,7–9 → w. 1–2.** Gody Baranka — wesele, ku któremu wskazuje pierwszy znak.''',
  "children":[]},
 {"type":"recepcja","title":"VII. Znaczenie w historii i liturgii Kościoła","body":
'''Starożytna liturgia związała Kanę z Epifanią (Objawieniem Pańskim): antyfona nieszporów śpiewa o dniu „ozdobionym trzema cudami" (*tribus miraculis ornatum diem colimus*) — pokłon Magów, chrzest w Jordanie i woda przemieniona w wino to trzy odsłony jednego objawienia chwały; Wschód do dziś trzyma ten splot w hymnografii Teofanii. W lekcjonarzu rzymskim J 2,1–11 czyta się w II Niedzielę zwykłą roku C — tuż po święcie Chrztu Pańskiego, zgodnie ze starą logiką epifanijną — oraz z upodobaniem na Mszach ślubnych: Kana jest biblijną ikoną sakramentu małżeństwa. Jan Paweł II, dodając w 2002 r. tajemnice światła do różańca (*Rosarium Virginis Mariae*), uczynił Kanę drugą z nich: „objawienie siebie na weselu w Kanie". „Zróbcie wszystko, cokolwiek wam powie" stało się osią teologii maryjnej (per Mariam ad Iesum — przez Maryję do Jezusa) i mott niezliczonych sanktuariów. W ikonografii scena należy do kanonu od katakumb (Kana obok rozmnożenia chleba — para eucharystyczna) po Giotta i monumentalne płótno Veronesego; w polskiej wyobraźni utrwaliła ją kolęda i kazania godowe. Duchowość zapamiętała z Kany dwie reguły: przedstawiaj Bogu brak, nie instrukcję; i napełniaj stągwie po brzegi — resztę zostaw Jemu.''',
  "children":[]},
 {"type":"patrystyka","title":"VIII. Komentarze Ojców Kościoła (catena patrum)","body":
'''Katena do pierwszego znaku: cud jako przyspieszona natura, sześć stągwi i epoki świata, godzina i posłuszeństwo Matki, gody uświęcone.''',
  "children":[]},
 ],
 "refs": [
 (("pericope",), "Rdz", 41, 55, 41, 55, "Rdz 41,55", "aluzja", "co wam powie, czyńcie — faraon o Józefie; Maryja wskazuje nowego szafarza"),
 (("pericope",), "Wj", 19, 10, 19, 16, "Wj 19,10–16", "typologia", "trzeciego dnia teofania na Synaju — chwała objawiona trzeciego dnia"),
 (("pericope",), "Ps", 104, 15, 104, 15, "Ps 104,15", "tlo", "wino rozwesela serce człowieka"),
 (("pericope",), "Iz", 25, 6, 25, 6, "Iz 25,6", "tlo", "uczta z wystałych win — obfitość mesjańska"),
 (("pericope",), "Am", 9, 13, 9, 14, "Am 9,13–14", "tlo", "góry ociekające moszczem — wino czasów ostatecznych"),
 (("pericope",), "Pnp", 1, 2, 1, 2, "Pnp 1,2", "typologia", "miłość lepsza niż wino — oblubieńczy klucz Kany"),
 (("pericope",), "Rdz", 3, 15, 3, 15, "Rdz 3,15", "typologia", "Niewiasta i potomstwo — protoewangelia za tytułem γύναι"),
 (("pericope",), "Mk", 2, 19, 2, 22, "Mk 2,19–22", "paralela", "oblubieniec i nowe wino — synoptyczna teologia nowości"),
 (("pericope",), "J", 4, 46, 4, 54, "J 4,46–54", "rozwiniecie", "drugi znak w Kanie — inkluzja"),
 (("pericope",), "J", 19, 25, 19, 27, "J 19,25–27", "rozwiniecie", "Niewiasta pod krzyżem — dokończenie Kany w godzinie"),
 (("pericope",), "Ap", 19, 7, 19, 9, "Ap 19,7–9", "rozwiniecie", "gody Baranka — cel, ku któremu wskazuje znak"),
 (("unit","w. 3–5",1), "J", 7, 30, 7, 30, "J 7,30", "rozwiniecie", "godzina jeszcze nie nadeszła — kolejne uderzenia zegara"),
 (("unit","w. 9–10",0), "J", 19, 34, 19, 34, "J 19,34", "rozwiniecie", "krew i woda z boku — wino godziny wydane do końca"),
 ],
 "patristic": [
 ("w. 9–10", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 8,1",
'''Cud Kany Augustyn wpisuje w większy cud, którego nie podziwiamy tylko dlatego, że jest codzienny: „ten, który owego dnia uczynił wino w stągwiach, czyni je co roku w winnicach — lecz tamto nikogo nie dziwi, bo dzieje się stale". Woda z deszczu przechodzi przez winorośl i staje się winem: rzecz nie mniej cudowna, tylko rozłożona w czasie. Znaki są po to, by obudzić śpiące zdumienie: kto przez Kanę nauczy się dziwić winnicy, ten w całym świecie zobaczy nieustanny cud Słowa, przez które wszystko się stało.'''),
 ("w. 6–8", "św. Augustyn", "In Iohannis Evangelium tractatus", "Tract. in Io. 9",
'''Sześć stągwi czyta Augustyn alegorycznie jako sześć epok dziejów (od Adama do Noego, do Abrahama, do Dawida, do niewoli, do Jana Chrzciciela, do końca): w każdej epoce stoi woda proroctwa — dobra, lecz bez smaku, dopóki czyta się ją bez Chrystusa. Pan nie wylewa wody i nie tłucze stągwi: każe je napełnić po brzegi i przemienia — tak Stary Testament, czytany w Chrystusie, nie zostaje odrzucony, lecz zaczyna smakować jak wino. Kto czyta Pisma i nie znajduje w nich Chrystusa, stoi przy stągwiach z wodą; kto znalazł — pije.'''),
 ("w. 3–5", "św. Jan Chryzostom", "Homilie na Ewangelię Jana", "Hom. in Io. 21–22",
'''Chryzostom broni w. 4 przed zgorszeniem: odpowiedź Jezusa nie jest wzgardą wobec Matki — jest lekcją porządku: w sprawach znaków i godziny nie więzy krwi decydują, lecz wola Ojca; a że czci Matkę, pokazał czynem — bo prośbę ostatecznie spełnił, i to z naddatkiem. Wielkość Maryi kaznodzieja widzi w jej reakcji: nie obraziła się, nie nalegała — przygotowała sługi; wiara, która po pozornej odmowie mówi „czyńcie, cokolwiek powie", jest większa niż wiara po cudzie. Słudzy zaś, którzy napełnili stągwie po brzegi, uczą współpracy z łaską: Bóg mógł stworzyć wino z niczego — wolał je uczynić z wody, którą przynieśli ludzie.'''),
 ("w. 1–2", "św. Cyryl Aleksandryjski", "Commentarii in Ioannem", "In Io., ks. II",
'''Dlaczego początek znaków na weselu? Cyryl: bo tam, gdzie grzech zaczął się od niewiasty i zatruł źródła życia, tam Chrystus — przyszedłszy z Matką-Niewiastą — uświęca sam początek ludzkich początków: małżeństwo i rodzenie. Przekleństwo ciążące na Ewie (w bólu rodzić będziesz) zostaje wzięte w nawias błogosławieństwa: Pan zasiada na godach jako gość, by okazać się Oblubieńcem. A przemiana wody w wino jest u Cyryla figurą przejścia od litery do Ducha: Prawo miało wodę oczyszczeń, Ewangelia ma wino wesela — natura nie zostaje zniszczona, lecz podniesiona ku lepszemu, jak woda, która nie przestała być darem, stając się winem.'''),
 ],
 "liturgy": [
 ("rzymski", "Epifania — antyfona Tribus miraculis (nieszpory Objawienia Pańskiego)", "J 2,1–11",
  "Trzy cuda jednego objawienia: Magowie, Jordan, Kana — starożytny splot epifanijny."),
 ("rzymski", "II Niedziela zwykła, rok C", "J 2,1–11",
  "Kana tuż po święcie Chrztu Pańskiego — kontynuacja logiki epifanijnej lekcjonarza."),
 ("rzymski", "Msza obrzędowa za nowożeńców (czytania ślubne)", "J 2,1–11",
  "Biblijna ikona sakramentu małżeństwa: Chrystus gościem i dawcą radości godów."),
 ("pobożność", "Różaniec — II tajemnica światła (od 2002, Rosarium Virginis Mariae)", "J 2,1–11",
  '''Objawienie siebie na weselu w Kanie; oś maryjnej drogi „czyńcie, cokolwiek wam powie".'''),
 ],
 "textual": [
 (3, "ὑστερήσαντος οἴνου", "wariant lekcji",
  "Tekst krótki (NA28): ὑστερήσαντος οἴνου (gdy zabrakło wina). Lekcja rozszerzona (ℵ*, część starołacińskich): οἶνον οὐκ εἶχον, ὅτι συνετελέσθη ὁ οἶνος τοῦ γάμου (wina nie mieli, bo wyczerpało się wino wesela) — z dopiskiem o wcześniejszym spożyciu.",
  "Lekcja dłuższa wygląda na wczesną glosę narracyjną (wyjaśnienie przyczyny braku); NA28 słusznie zachowuje tekst zwięzły. Wariant cenny jako świadek żywego, gawędziarskiego obiegu perykopy w II wieku."),
 ],
 "themes": [
 ("nowy tydzień stworzenia (J 1,19–2,11)", ("pericope",)),
 ("ἦν / ἐγένετο — trwanie a stawanie się", ("block","w. 9–10")),
 ("godzina Jezusa (ἡ ὥρα)", ("block","w. 3–5")),
 ("znaki (σημεῖα) i wiara", ("block","w. 11")),
 ("tytuły chrystologiczne J 1", ("block","w. 1–2")),
 ],
}

THEMES3 = [
 ("godzina Jezusa (ἡ ὥρα)",
  "Wyznaczony czas uwielbienia przez krzyż: 2,4 (jeszcze nie) — 7,30; 8,20 — 12,23; 13,1; 17,1 (nadeszła). Zegar całej księgi uruchomiony w Kanie."),
 ("znaki (σημεῖα) i wiara",
  "Siedem znaków księgi znaków (J 2–11); struktura znak → chwała → wiara ustanowiona w 2,11; znak jako strzałka wskazująca poza siebie (por. 20,30-31)."),
]

# ------------------------------------------------------------------
# 20. ROZSZERZENIE BAZY O J 2,1-11
# ------------------------------------------------------------------
def extend_kana():
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    cur = con.cursor()

    def book_of(ab):
        return cur.execute("SELECT id FROM book WHERE abbrev_pl=?", (ab,)).fetchone()[0]
    for ab, nm, tst, ordn in BOOKS3:
        cur.execute("INSERT OR IGNORE INTO book(abbrev_pl, name_pl, testament, canon_order) VALUES (?,?,?,?)",
                    (ab, nm, tst, ordn))
    bid_J = book_of("J")

    # wersety J 2,1-11
    verse_id = {}
    for vn, (gk, pl) in VERSES3.items():
        cur.execute("INSERT INTO verse(book_id, chapter, verse_num, text_greek, text_working_pl) VALUES (?,?,?,?,?)",
                    (bid_J, 2, vn, gk, pl))
        verse_id[vn] = cur.lastrowid

    def lex_of(lemma):
        return cur.execute("SELECT id FROM lexeme WHERE lemma=?", (lemma,)).fetchone()[0]
    for lemma, tr, pos_, gl in LEXEMES3:
        cur.execute("INSERT OR IGNORE INTO lexeme(lemma, translit, pos, gloss_pl) VALUES (?,?,?,?)",
                    (lemma, tr, pos_, gl))
    for term, tr, lang, gl in SEMITIC3:
        cur.execute("INSERT OR IGNORE INTO semitic_term(term, translit, lang, gloss_pl) VALUES (?,?,?,?)",
                    (term, tr, lang, gl))
    for lemma, vn, form in OCC3:
        cur.execute("INSERT INTO lexeme_occurrence(lexeme_id, verse_id, form_in_text) VALUES (?,?,?)",
                    (lex_of(lemma), verse_id[vn], form))

    def work_of(author, title):
        return cur.execute("SELECT id FROM work WHERE author=? AND title=?", (author, title)).fetchone()[0]
    for name, desc in THEMES3:
        cur.execute("INSERT OR IGNORE INTO theme(name, description_md) VALUES (?,?)", (name, desc))
    def theme_of(name):
        return cur.execute("SELECT id FROM theme WHERE name=?", (name,)).fetchone()[0]

    P = P7
    pd = P["pericope"]
    cur.execute("""INSERT INTO pericope(book_id, chapter_start, verse_start, chapter_end, verse_end,
                   title, motto, status, position) VALUES (?,?,?,?,?,?,?,?,?)""",
                (bid_J, pd["cs"], pd["vs"], pd["ce"], pd["ve"],
                 pd["title"], pd["motto"], pd["status"], pd["position"]))
    pid = cur.lastrowid

    section_id, block_id, unit_id = {}, {}, {}
    def add_section(stype, title, body, parent, pos):
        cur.execute("""INSERT INTO section(pericope_id, parent_id, section_type, title, body_md, position)
                       VALUES (?,?,?,?,?,?)""", (pid, parent, stype, title, body, pos))
        section_id[title] = cur.lastrowid
        return cur.lastrowid

    sec1 = add_section("filologia",
                       "I. Tekst grecki (Nestle-Aland, wyd. 28) z przekładem roboczym i analizą filologiczną",
                       P["intro"], None, 1)
    for bpos, b in enumerate(P["blocks"], start=1):
        cur.execute("""INSERT INTO commentary_block(section_id, chapter_start, verse_start, chapter_end,
                       verse_end, label, greek_text, working_translation_pl, position)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (sec1, b["cs"], b["vs"], b["ce"], b["ve"], b["label"], b["greek"], b["transl"], bpos))
        block_id[b["label"]] = cur.lastrowid
        for upos, (phr, phr_pl, body) in enumerate(b["units"]):
            cur.execute("""INSERT INTO analysis_unit(block_id, phrase_greek, phrase_translation_pl, body_md, position)
                           VALUES (?,?,?,?,?)""",
                        (block_id[b["label"]], phr, phr_pl, body.strip(), upos))
            unit_id[(b["label"], upos)] = cur.lastrowid

    for spos, s in enumerate(P["sections"], start=2):
        top = add_section(s["type"], s["title"], s["body"], None, spos)
        for cpos, (ct, cb) in enumerate(s["children"], start=1):
            add_section(s["type"], ct, cb.strip(), top, cpos)

    def source_cols(src):
        if src[0] == "pericope": return pid, None, None
        if src[0] == "section":  return None, section_id[src[1]], None
        if src[0] == "unit":     return None, None, unit_id[(src[1], src[2])]
        raise ValueError(src)

    for src, tb, cs, vs, ce, ve, label, rel, note in P["refs"]:
        sp, ss, su = source_cols(src)
        cur.execute("""INSERT INTO scripture_ref(pericope_id, section_id, analysis_unit_id,
                       target_book_id, target_chapter_start, target_verse_start,
                       target_chapter_end, target_verse_end, target_label, relation, note_md)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (sp, ss, su, book_of(tb), cs, vs, ce, ve, label, rel, note))

    pos_per_block = {}
    for blabel, author, wtitle, locus, body in P["patristic"]:
        pos_per_block[blabel] = pos_per_block.get(blabel, 0) + 1
        cur.execute("""INSERT INTO patristic_comment(work_id, block_id, locus, body_md, position)
                       VALUES (?,?,?,?,?)""",
                    (work_of(author, wtitle), block_id[blabel], locus, body.strip(),
                     pos_per_block[blabel]))

    for rite, occ, passage, desc in P["liturgy"]:
        cur.execute("""INSERT INTO liturgical_use(pericope_id, rite, occasion, passage, description_md)
                       VALUES (?,?,?,?,?)""", (pid, rite, occ, passage, desc))

    for vn, lemma, issue, readings, assessment in P["textual"]:
        cur.execute("""INSERT INTO textual_note(verse_id, lemma_text, issue, readings_md, assessment_md)
                       VALUES (?,?,?,?,?)""", (verse_id[vn], lemma, issue, readings, assessment))

    for name, link in P["themes"]:
        tid = theme_of(name)
        cols = {"pericope_id": None, "section_id": None, "block_id": None, "analysis_unit_id": None}
        if link[0] == "pericope":  cols["pericope_id"] = pid
        elif link[0] == "section": cols["section_id"] = section_id[link[1]]
        elif link[0] == "block":   cols["block_id"] = block_id[link[1]]
        elif link[0] == "unit":    cols["analysis_unit_id"] = unit_id[(link[1], link[2])]
        cur.execute("""INSERT INTO theme_link(theme_id, pericope_id, section_id, block_id, analysis_unit_id)
                       VALUES (?,?,?,?,?)""",
                    (tid, cols["pericope_id"], cols["section_id"], cols["block_id"], cols["analysis_unit_id"]))

    cur.execute("INSERT INTO revision_log(entity, entity_id, note) VALUES (?,?,?)",
                ("pericope", pid, "Dodano perykopę Wesele w Kanie Galilejskiej (J 2,1-11) z kateną"))

    con.commit()
    n = cur.execute("SELECT count(*) FROM pericope").fetchone()[0]
    print(f"extend_kana OK — perykop w bazie: {n}")
    con.close()


if __name__ == "__main__":
    main()          # baza od zera: schemat + Prolog + katena
    extend()        # J 1,15-51: pięć perykop
    extend_kana()   # J 2,1-11: Wesele w Kanie
