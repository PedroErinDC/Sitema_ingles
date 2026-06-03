from __future__ import annotations

from datetime import date, datetime
import sqlite3

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db_models import GrammarItem, GrammarReview, Word, WordReview
from .content_service import sync_content_records


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.utcnow()


def import_legacy_learning_data(session: Session) -> dict[str, int | bool]:
    if not settings.legacy_learning_db.exists():
        return {"migrated": False, "words": 0, "grammar_items": 0}

    word_count = session.scalar(select(Word.id).limit(1))
    grammar_count = session.scalar(select(GrammarItem.id).limit(1))
    if word_count or grammar_count:
        return {"migrated": False, "words": 0, "grammar_items": 0}

    con = sqlite3.connect(settings.legacy_learning_db)
    con.row_factory = sqlite3.Row
    migrated_words = 0
    migrated_grammar = 0
    try:
        for row in con.execute("SELECT * FROM words"):
            session.add(
                Word(
                    id=row["id"],
                    lemma=row["lemma"],
                    word=row["word"] or "",
                    pos=row["pos"] or "",
                    topic=row["topic"] or "",
                    translation=row["translation"] or "",
                    example_en=row["example_en"] or "",
                    example_es=row["example_es"] or "",
                    ease=row["ease"] or 2.5,
                    interval=row["interval"] or 0,
                    reps=row["reps"] or 0,
                    lapses=row["lapses"] or 0,
                    due=_parse_date(row["due"]),
                    created_at=_parse_datetime(row["created_at"]),
                )
            )
            migrated_words += 1

        for row in con.execute("SELECT * FROM reviews"):
            session.add(
                WordReview(
                    id=row["id"],
                    word_id=row["word_id"],
                    rating=row["rating"],
                    reviewed_at=_parse_datetime(row["reviewed_at"]),
                )
            )

        for row in con.execute("SELECT * FROM grammar_items"):
            session.add(
                GrammarItem(
                    id=row["id"],
                    slug=row["slug"],
                    title=row["title"],
                    topic=row["topic"] or "",
                    level=row["level"] or "A1",
                    description=row["description"] or "",
                    example_en=row["example_en"] or "",
                    example_es=row["example_es"] or "",
                    ease=row["ease"] or 2.5,
                    interval=row["interval"] or 0,
                    reps=row["reps"] or 0,
                    lapses=row["lapses"] or 0,
                    due=_parse_date(row["due"]),
                    created_at=_parse_datetime(row["created_at"]),
                )
            )
            migrated_grammar += 1

        for row in con.execute("SELECT * FROM grammar_reviews"):
            session.add(
                GrammarReview(
                    id=row["id"],
                    item_id=row["item_id"],
                    rating=row["rating"],
                    correct=bool(row["correct"]),
                    reviewed_at=_parse_datetime(row["reviewed_at"]),
                )
            )
    except sqlite3.OperationalError:
        session.rollback()
        return {"migrated": False, "words": 0, "grammar_items": 0}
    finally:
        con.close()

    session.commit()
    return {"migrated": True, "words": migrated_words, "grammar_items": migrated_grammar}


def bootstrap_data(session: Session) -> None:
    import_legacy_learning_data(session)
    sync_content_records(session)
