
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

-- Wprowadzenie do całej księgi (nie-perykopa): drzewo sekcji jak w section,
-- lecz bez zakotwiczenia w pericope. Tytuł/motto/akapit wiodący — w meta
-- (intro_title, intro_motto, intro_lead).
CREATE TABLE intro_section (
    id        INTEGER PRIMARY KEY,
    parent_id INTEGER REFERENCES intro_section(id) ON DELETE CASCADE,
    title     TEXT,
    body_md   TEXT,
    position  INTEGER NOT NULL DEFAULT 0
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

