"""
learning.py - Motor adaptativo para vocabulario y gramatica sobre SQLite.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import json
import random
import re
import sqlite3


DB = Path("data/ingles.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS words (
    id          INTEGER PRIMARY KEY,
    lemma       TEXT UNIQUE NOT NULL,
    word        TEXT,
    pos         TEXT,
    topic       TEXT,
    translation TEXT,
    example_en  TEXT,
    example_es  TEXT,
    ease        REAL DEFAULT 2.5,
    interval    INTEGER DEFAULT 0,
    reps        INTEGER DEFAULT 0,
    lapses      INTEGER DEFAULT 0,
    due         TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY,
    word_id INTEGER REFERENCES words(id),
    rating INTEGER,
    reviewed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS grammar_items (
    id          INTEGER PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,
    title       TEXT NOT NULL,
    topic       TEXT,
    level       TEXT DEFAULT 'A1',
    description TEXT,
    example_en  TEXT,
    example_es  TEXT,
    ease        REAL DEFAULT 2.5,
    interval    INTEGER DEFAULT 0,
    reps        INTEGER DEFAULT 0,
    lapses      INTEGER DEFAULT 0,
    due         TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS grammar_reviews (
    id INTEGER PRIMARY KEY,
    item_id INTEGER REFERENCES grammar_items(id),
    rating INTEGER,
    correct INTEGER DEFAULT 0,
    reviewed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

LEARNING_MAX = 7
KNOWN_MIN = 30
LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1"]
LEVEL_WEIGHT = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5}


GRAMMAR_EXTRACT_PROMPT = """Analiza este material para un estudiante de ingles y extrae
hasta {limit} puntos gramaticales utiles para estudiar.

Devuelve solo JSON valido con esta forma:
{{"items":[{{"title":"...","topic":"...","level":"A1|A2|B1|B2|C1",
"description":"explicacion corta en espanol","example_en":"frase de ejemplo"}}]}}

MATERIAL:
\"\"\"{text}\"\"\"
"""


def connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect() as con:
        con.executescript(SCHEMA)


def _slug(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    text = text.strip("-")
    return text or "item"


def _sm2(ease: float, interval: int, reps: int, rating: int):
    quality = {1: 1, 2: 3, 3: 4, 4: 5}[rating]
    lapse = quality < 3
    if lapse:
        reps, interval = 0, 1
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(1, round(interval * ease))
        reps += 1
    ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    return ease, interval, reps, lapse


def status_of(interval: int, reps: int) -> str:
    if reps == 0:
        return "nueva"
    if interval < LEARNING_MAX:
        return "aprendiendo"
    if interval < KNOWN_MIN:
        return "mas_o_menos"
    return "dominada"


def add_word(
    lemma: str,
    translation: str = "",
    topic: str = "",
    pos: str = "",
    word: str = "",
    example_en: str = "",
    example_es: str = "",
):
    with connect() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO words
                (lemma, word, pos, topic, translation, example_en, example_es, due)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                lemma.lower().strip(),
                word or lemma,
                pos,
                topic,
                translation,
                example_en,
                example_es,
                date.today().isoformat(),
            ),
        )


def _extract_vocab_candidates(text_en: str, min_len: int = 3):
    import spacy

    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text_en)
    seen = {}
    sentences = list(doc.sents)
    for token in doc:
        if not (token.is_alpha and not token.is_stop and token.pos_ in {"NOUN", "VERB", "ADJ", "ADV"}):
            continue
        lemma = token.lemma_.lower()
        if len(lemma) < min_len or lemma in seen:
            continue
        example_en = ""
        for sent in sentences:
            if token.text in sent.text or lemma in sent.text.lower():
                example_en = sent.text.strip()
                break
        seen[lemma] = {
            "lemma": lemma,
            "word": token.text,
            "pos": token.pos_,
            "example_en": example_en,
        }
    return list(seen.values())


def add_words_from_text(
    text_en: str,
    topic: str = "",
    min_len: int = 3,
    llm_model: str = "",
):
    import models as M

    entries = _extract_vocab_candidates(text_en, min_len=min_len)
    translations = M.translate_terms([entry["lemma"] for entry in entries], llm_model=llm_model)
    for entry in entries:
        add_word(
            entry["lemma"],
            translation=translations.get(entry["lemma"], ""),
            topic=topic,
            pos=entry["pos"],
            word=entry["word"],
            example_en=entry["example_en"],
        )
    return len(entries)


def review_word(word_id: int, rating: int):
    with connect() as con:
        row = con.execute(
            "SELECT ease, interval, reps, lapses FROM words WHERE id=?",
            (word_id,),
        ).fetchone()
        if not row:
            return
        ease, interval, reps, lapse = _sm2(row["ease"], row["interval"], row["reps"], rating)
        lapses = row["lapses"] + (1 if lapse else 0)
        due = (date.today() + timedelta(days=interval)).isoformat()
        con.execute(
            "UPDATE words SET ease=?, interval=?, reps=?, lapses=?, due=? WHERE id=?",
            (ease, interval, reps, lapses, due, word_id),
        )
        con.execute("INSERT INTO reviews (word_id, rating) VALUES (?,?)", (word_id, rating))


def due_today(limit: int = 20) -> list[dict]:
    today = date.today().isoformat()
    with connect() as con:
        rows = con.execute(
            """
            SELECT * FROM words
            WHERE due IS NULL OR due <= ?
            ORDER BY (reps = 0) DESC, lapses DESC, interval ASC
            LIMIT ?
            """,
            (today, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def status_counts() -> dict:
    out = {"nueva": 0, "aprendiendo": 0, "mas_o_menos": 0, "dominada": 0}
    with connect() as con:
        for row in con.execute("SELECT interval, reps FROM words"):
            out[status_of(row["interval"], row["reps"])] += 1
    return out


def weak_topics(limit: int = 5) -> list[dict]:
    with connect() as con:
        rows = con.execute(
            """
            SELECT COALESCE(NULLIF(w.topic, ''), w.pos, 'sin_tema') AS tema,
                   SUM(CASE WHEN r.rating = 1 THEN 1 ELSE 0 END) AS fallos,
                   COUNT(*) AS intentos
            FROM reviews r
            JOIN words w ON w.id = r.word_id
            GROUP BY tema
            HAVING intentos > 0
            ORDER BY fallos DESC,
                     (CAST(SUM(CASE WHEN r.rating = 1 THEN 1 ELSE 0 END) AS REAL) / COUNT(*)) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _first_sentence(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return sentences[0].strip() if sentences and sentences[0].strip() else text[:160].strip()


def _infer_level(title: str) -> str:
    lowered = title.lower()
    rules = [
        ("present simple", "A1"),
        ("past simple", "A1"),
        ("future simple", "A1"),
        ("there is", "A1"),
        ("comparative", "A2"),
        ("superlative", "A2"),
        ("present perfect", "B1"),
        ("modal", "B1"),
        ("passive", "B1"),
        ("past perfect", "B2"),
        ("conditional", "B2"),
        ("reported speech", "B2"),
        ("subjunctive", "C1"),
    ]
    for pattern, level in rules:
        if pattern in lowered:
            return level
    return "A2"


def add_grammar_item(
    title: str,
    *,
    topic: str = "",
    level: str = "A1",
    description: str = "",
    example_en: str = "",
    example_es: str = "",
):
    slug = _slug(title)
    with connect() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO grammar_items
                (slug, title, topic, level, description, example_en, example_es, due)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                slug,
                title.strip(),
                topic.strip(),
                level if level in LEVEL_ORDER else _infer_level(title),
                description.strip(),
                example_en.strip(),
                example_es.strip(),
                date.today().isoformat(),
            ),
        )


def _heuristic_grammar_points(text_en: str, topic: str = "") -> list[dict]:
    points = []
    rules = [
        (r"\b(have|has)\s+\w+ed\b", "present perfect"),
        (r"\bhad\s+\w+ed\b", "past perfect"),
        (r"\bif\b.+\bwould\b", "conditional"),
        (r"\b(will|going to)\b", "future simple"),
        (r"\b(can|could|should|must|might)\b", "modal verbs"),
        (r"\bmore\s+\w+\s+than\b|\b\w+er\s+than\b", "comparatives"),
        (r"\bthe\s+\w+est\b|\bmost\s+\w+\b", "superlatives"),
        (r"\bup\b|\bout\b|\boff\b|\bon\b", "phrasal verbs"),
    ]
    for pattern, title in rules:
        match = re.search(pattern, text_en, flags=re.I | re.S)
        if match:
            points.append(
                {
                    "title": title.title(),
                    "topic": topic or title,
                    "level": _infer_level(title),
                    "description": f"Punto detectado automaticamente: {title}.",
                    "example_en": _first_sentence(text_en),
                }
            )
    if not points and topic:
        points.append(
            {
                "title": topic.title(),
                "topic": topic,
                "level": _infer_level(topic),
                "description": "Tema importado desde material del usuario.",
                "example_en": _first_sentence(text_en),
            }
        )
    return points


def import_grammar_points(text_en: str, topic: str = "", llm_model: str = "", limit: int = 8) -> int:
    import models as M

    items = []
    snippet = text_en[:5000]
    if llm_model:
        try:
            raw = M.llm_chat(
                llm_model,
                GRAMMAR_EXTRACT_PROMPT.format(limit=limit, text=snippet),
                system="Responde unicamente con JSON valido.",
            )
            match = re.search(r"\{.*\}", raw, flags=re.S)
            data = json.loads(match.group(0) if match else raw)
            items = data.get("items", [])
        except Exception:
            items = []
    if not items:
        items = _heuristic_grammar_points(text_en, topic=topic)

    inserted = 0
    for item in items[:limit]:
        title = item.get("title", "").strip()
        if not title:
            continue
        before = grammar_item_by_slug(_slug(title))
        add_grammar_item(
            title,
            topic=item.get("topic", topic),
            level=item.get("level", _infer_level(title)),
            description=item.get("description", ""),
            example_en=item.get("example_en", ""),
            example_es=item.get("example_es", ""),
        )
        after = grammar_item_by_slug(_slug(title))
        if not before and after:
            inserted += 1
    return inserted


def grammar_item_by_slug(slug: str) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT * FROM grammar_items WHERE slug=?", (slug,)).fetchone()
    return dict(row) if row else None


def grammar_due_today(limit: int = 10) -> list[dict]:
    today = date.today().isoformat()
    with connect() as con:
        rows = con.execute(
            """
            SELECT * FROM grammar_items
            WHERE due IS NULL OR due <= ?
            ORDER BY (reps = 0) DESC, lapses DESC, interval ASC
            LIMIT ?
            """,
            (today, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def review_grammar(item_id: int, rating: int, correct: bool):
    with connect() as con:
        row = con.execute(
            "SELECT ease, interval, reps, lapses FROM grammar_items WHERE id=?",
            (item_id,),
        ).fetchone()
        if not row:
            return
        ease, interval, reps, lapse = _sm2(row["ease"], row["interval"], row["reps"], rating)
        lapses = row["lapses"] + (1 if lapse else 0)
        due = (date.today() + timedelta(days=interval)).isoformat()
        con.execute(
            "UPDATE grammar_items SET ease=?, interval=?, reps=?, lapses=?, due=? WHERE id=?",
            (ease, interval, reps, lapses, due, item_id),
        )
        con.execute(
            "INSERT INTO grammar_reviews (item_id, rating, correct) VALUES (?,?,?)",
            (item_id, rating, int(correct)),
        )


def grammar_status_counts() -> dict:
    out = {"nueva": 0, "aprendiendo": 0, "mas_o_menos": 0, "dominada": 0}
    with connect() as con:
        for row in con.execute("SELECT interval, reps FROM grammar_items"):
            out[status_of(row["interval"], row["reps"])] += 1
    return out


def grammar_rank_summary() -> dict:
    with connect() as con:
        rows = con.execute("SELECT level, interval, reps FROM grammar_items").fetchall()

    by_level = {level: {"total": 0, "mastered": 0} for level in LEVEL_ORDER}
    score = 0
    for row in rows:
        level = row["level"] if row["level"] in LEVEL_ORDER else "A1"
        by_level[level]["total"] += 1
        if status_of(row["interval"], row["reps"]) == "dominada":
            by_level[level]["mastered"] += 1
            score += LEVEL_WEIGHT[level]

    best_level = "A0"
    for level in LEVEL_ORDER:
        if by_level[level]["mastered"] > 0:
            best_level = level

    if score >= 30:
        rank = "Expert"
    elif score >= 18:
        rank = "Advanced"
    elif score >= 9:
        rank = "Intermediate"
    elif score >= 3:
        rank = "Foundation"
    else:
        rank = "Starter"

    return {"rank": rank, "best_level": best_level, "score": score, "by_level": by_level}


def weak_grammar_topics(limit: int = 5) -> list[dict]:
    with connect() as con:
        rows = con.execute(
            """
            SELECT COALESCE(NULLIF(g.topic, ''), g.title) AS tema,
                   SUM(CASE WHEN r.correct = 0 THEN 1 ELSE 0 END) AS fallos,
                   COUNT(*) AS intentos
            FROM grammar_reviews r
            JOIN grammar_items g ON g.id = r.item_id
            GROUP BY tema
            HAVING intentos > 0
            ORDER BY fallos DESC,
                     (CAST(SUM(CASE WHEN r.correct = 0 THEN 1 ELSE 0 END) AS REAL) / COUNT(*)) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def build_grammar_quiz_session(limit: int = 5) -> list[dict]:
    items = grammar_due_today(limit=limit)
    if not items:
        return []

    with connect() as con:
        pool = [dict(row) for row in con.execute("SELECT id, title FROM grammar_items").fetchall()]

    quizzes = []
    for item in items:
        distractors = [candidate["title"] for candidate in pool if candidate["id"] != item["id"]]
        random.shuffle(distractors)
        options = [item["title"]] + distractors[:3]
        options = list(dict.fromkeys(options))
        while len(options) < min(4, len(pool)):
            filler = next(
                (candidate["title"] for candidate in pool if candidate["title"] not in options and candidate["id"] != item["id"]),
                None,
            )
            if not filler:
                break
            options.append(filler)
        random.shuffle(options)
        answer_index = options.index(item["title"])
        prompt = item["example_en"] or item["description"] or item["title"]
        quizzes.append(
            {
                "id": item["id"],
                "title": item["title"],
                "prompt": prompt,
                "options": options,
                "answer_index": answer_index,
                "level": item["level"],
                "description": item["description"],
            }
        )
    return quizzes
