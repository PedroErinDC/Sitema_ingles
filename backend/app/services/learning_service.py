from __future__ import annotations

from datetime import date, timedelta
import json
import random
import re

from sqlalchemy import Float, cast, case, desc, func, or_, select
from sqlalchemy.orm import Session

import models as legacy_models

from ..db_models import GrammarItem, GrammarReview, Word, WordReview


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


def _slug(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return text.strip("-") or "item"


def _sm2(ease: float, interval: int, reps: int, rating: int) -> tuple[float, int, int, bool]:
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


def serialize_word(word: Word) -> dict:
    return {
        "id": word.id,
        "lemma": word.lemma,
        "word": word.word,
        "pos": word.pos or "",
        "topic": word.topic or "",
        "translation": word.translation or "",
        "example_en": word.example_en or "",
        "example_es": word.example_es or "",
        "ease": word.ease,
        "interval": word.interval,
        "reps": word.reps,
        "lapses": word.lapses,
        "due": word.due,
        "status": status_of(word.interval, word.reps),
    }


def _extract_vocab_candidates(text_en: str, min_len: int = 3) -> list[dict]:
    import spacy

    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text_en)
    sentences = list(doc.sents)
    seen: dict[str, dict] = {}
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


def add_words_from_text(session: Session, text_en: str, topic: str = "", min_len: int = 3, llm_model: str = "") -> int:
    entries = _extract_vocab_candidates(text_en, min_len=min_len)
    translations = legacy_models.translate_terms([entry["lemma"] for entry in entries], llm_model=llm_model)
    inserted = 0

    for entry in entries:
        lemma = entry["lemma"].strip().lower()
        word = session.scalar(select(Word).where(Word.lemma == lemma))
        if word is None:
            word = Word(
                lemma=lemma,
                word=entry["word"] or lemma,
                pos=entry["pos"] or "",
                topic=topic,
                translation=translations.get(lemma, ""),
                example_en=entry["example_en"] or "",
                due=date.today(),
            )
            session.add(word)
            inserted += 1
            continue

        if topic and not word.topic:
            word.topic = topic
        if not word.translation:
            word.translation = translations.get(lemma, "")
        if not word.example_en:
            word.example_en = entry["example_en"] or ""
        if not word.pos:
            word.pos = entry["pos"] or ""

    session.commit()
    return inserted


def review_word(session: Session, word_id: int, rating: int) -> dict | None:
    word = session.get(Word, word_id)
    if word is None:
        return None

    ease, interval, reps, lapse = _sm2(word.ease, word.interval, word.reps, rating)
    word.ease = ease
    word.interval = interval
    word.reps = reps
    word.lapses += 1 if lapse else 0
    word.due = date.today() + timedelta(days=interval)
    session.add(WordReview(word_id=word_id, rating=rating))
    session.commit()
    session.refresh(word)
    return serialize_word(word)


def due_today(session: Session, limit: int = 20) -> list[dict]:
    stmt = (
        select(Word)
        .where(or_(Word.due.is_(None), Word.due <= date.today()))
        .order_by(case((Word.reps == 0, 1), else_=0).desc(), Word.lapses.desc(), Word.interval.asc())
        .limit(limit)
    )
    return [serialize_word(word) for word in session.scalars(stmt).all()]


def status_counts(session: Session) -> dict[str, int]:
    counts = {"nueva": 0, "aprendiendo": 0, "mas_o_menos": 0, "dominada": 0}
    for interval, reps in session.execute(select(Word.interval, Word.reps)).all():
        counts[status_of(interval, reps)] += 1
    return counts


def weak_topics(session: Session, limit: int = 5) -> list[dict]:
    topic_expr = func.coalesce(func.nullif(Word.topic, ""), func.nullif(Word.pos, ""), "sin_tema")
    fail_expr = func.sum(case((WordReview.rating == 1, 1), else_=0))
    stmt = (
        select(
            topic_expr.label("tema"),
            fail_expr.label("fallos"),
            func.count(WordReview.id).label("intentos"),
        )
        .join(WordReview, WordReview.word_id == Word.id)
        .group_by(topic_expr)
        .having(func.count(WordReview.id) > 0)
        .order_by(
            desc(fail_expr),
            desc(cast(fail_expr, Float) / func.count(WordReview.id)),
        )
        .limit(limit)
    )
    return [dict(row._mapping) for row in session.execute(stmt).all()]


def add_grammar_item(
    session: Session,
    title: str,
    *,
    topic: str = "",
    level: str = "A1",
    description: str = "",
    example_en: str = "",
    example_es: str = "",
) -> bool:
    slug = _slug(title)
    item = session.scalar(select(GrammarItem).where(GrammarItem.slug == slug))
    if item is not None:
        if topic and not item.topic:
            item.topic = topic
        if description and not item.description:
            item.description = description
        if example_en and not item.example_en:
            item.example_en = example_en
        if example_es and not item.example_es:
            item.example_es = example_es
        return False

    session.add(
        GrammarItem(
            slug=slug,
            title=title.strip(),
            topic=topic.strip(),
            level=level if level in LEVEL_ORDER else _infer_level(title),
            description=description.strip(),
            example_en=example_en.strip(),
            example_es=example_es.strip(),
            due=date.today(),
        )
    )
    return True


def import_grammar_points(session: Session, text_en: str, topic: str = "", llm_model: str = "", limit: int = 8) -> int:
    items = []
    snippet = text_en[:5000]
    if llm_model:
        try:
            raw = legacy_models.llm_chat(
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
        if add_grammar_item(
            session,
            title,
            topic=item.get("topic", topic),
            level=item.get("level", _infer_level(title)),
            description=item.get("description", ""),
            example_en=item.get("example_en", ""),
            example_es=item.get("example_es", ""),
        ):
            inserted += 1

    session.commit()
    return inserted


def grammar_due_today(session: Session, limit: int = 10) -> list[GrammarItem]:
    stmt = (
        select(GrammarItem)
        .where(or_(GrammarItem.due.is_(None), GrammarItem.due <= date.today()))
        .order_by(case((GrammarItem.reps == 0, 1), else_=0).desc(), GrammarItem.lapses.desc(), GrammarItem.interval.asc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def review_grammar(session: Session, item_id: int, rating: int, correct: bool) -> GrammarItem | None:
    item = session.get(GrammarItem, item_id)
    if item is None:
        return None

    ease, interval, reps, lapse = _sm2(item.ease, item.interval, item.reps, rating)
    item.ease = ease
    item.interval = interval
    item.reps = reps
    item.lapses += 1 if lapse else 0
    item.due = date.today() + timedelta(days=interval)
    session.add(GrammarReview(item_id=item_id, rating=rating, correct=correct))
    session.commit()
    session.refresh(item)
    return item


def grammar_status_counts(session: Session) -> dict[str, int]:
    counts = {"nueva": 0, "aprendiendo": 0, "mas_o_menos": 0, "dominada": 0}
    for interval, reps in session.execute(select(GrammarItem.interval, GrammarItem.reps)).all():
        counts[status_of(interval, reps)] += 1
    return counts


def grammar_rank_summary(session: Session) -> dict:
    rows = session.execute(select(GrammarItem.level, GrammarItem.interval, GrammarItem.reps)).all()
    by_level = {level: {"total": 0, "mastered": 0} for level in LEVEL_ORDER}
    score = 0
    for level, interval, reps in rows:
        safe_level = level if level in LEVEL_ORDER else "A1"
        by_level[safe_level]["total"] += 1
        if status_of(interval, reps) == "dominada":
            by_level[safe_level]["mastered"] += 1
            score += LEVEL_WEIGHT[safe_level]

    best_level = "A0"
    for level in LEVEL_ORDER:
        if by_level[level]["mastered"] > 0:
            best_level = level

    if score >= 30:
        rank = "Experto"
    elif score >= 18:
        rank = "Avanzado"
    elif score >= 9:
        rank = "Intermedio"
    elif score >= 3:
        rank = "Fundamentos"
    else:
        rank = "Inicial"

    return {"rank": rank, "best_level": best_level, "score": score, "by_level": by_level}


def weak_grammar_topics(session: Session, limit: int = 5) -> list[dict]:
    topic_expr = func.coalesce(func.nullif(GrammarItem.topic, ""), GrammarItem.title)
    fail_expr = func.sum(case((GrammarReview.correct.is_(False), 1), else_=0))
    stmt = (
        select(
            topic_expr.label("tema"),
            fail_expr.label("fallos"),
            func.count(GrammarReview.id).label("intentos"),
        )
        .join(GrammarReview, GrammarReview.item_id == GrammarItem.id)
        .group_by(topic_expr)
        .having(func.count(GrammarReview.id) > 0)
        .order_by(
            desc(fail_expr),
            desc(cast(fail_expr, Float) / func.count(GrammarReview.id)),
        )
        .limit(limit)
    )
    return [dict(row._mapping) for row in session.execute(stmt).all()]


def build_grammar_quiz_session(session: Session, limit: int = 5) -> list[dict]:
    items = grammar_due_today(session, limit=limit)
    if not items:
        return []

    pool = list(session.scalars(select(GrammarItem).order_by(GrammarItem.title)).all())
    quizzes = []
    for item in items:
        distractors = [candidate.title for candidate in pool if candidate.id != item.id]
        random.shuffle(distractors)
        options = [item.title] + distractors[:3]
        options = list(dict.fromkeys(options))
        while len(options) < min(4, len(pool)):
            filler = next(
                (
                    candidate.title
                    for candidate in pool
                    if candidate.title not in options and candidate.id != item.id
                ),
                None,
            )
            if not filler:
                break
            options.append(filler)
        random.shuffle(options)
        quizzes.append(
            {
                "id": item.id,
                "title": item.title,
                "prompt": item.example_en or item.description or item.title,
                "options": options,
                "answer_index": options.index(item.title),
                "level": item.level,
                "description": item.description or "",
            }
        )
    return quizzes
