from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.utcnow()


class Base(DeclarativeBase):
    pass


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lemma: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    word: Mapped[str] = mapped_column(String(255), default="")
    pos: Mapped[str] = mapped_column(String(64), default="")
    topic: Mapped[str] = mapped_column(String(255), default="")
    translation: Mapped[str] = mapped_column(Text, default="")
    example_en: Mapped[str] = mapped_column(Text, default="")
    example_es: Mapped[str] = mapped_column(Text, default="")
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    reviews: Mapped[list["WordReview"]] = relationship(back_populates="word", cascade="all, delete-orphan")


class WordReview(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    word: Mapped[Word] = relationship(back_populates="reviews")


class GrammarItem(Base):
    __tablename__ = "grammar_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    topic: Mapped[str] = mapped_column(String(255), default="")
    level: Mapped[str] = mapped_column(String(8), default="A1")
    description: Mapped[str] = mapped_column(Text, default="")
    example_en: Mapped[str] = mapped_column(Text, default="")
    example_es: Mapped[str] = mapped_column(Text, default="")
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    interval: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[int] = mapped_column(Integer, default=0)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    due: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    reviews: Mapped[list["GrammarReview"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
    )


class GrammarReview(Base):
    __tablename__ = "grammar_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("grammar_items.id", ondelete="CASCADE"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    correct: Mapped[bool] = mapped_column(default=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    item: Mapped[GrammarItem] = relationship(back_populates="reviews")


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32), default="content")
    language: Mapped[str] = mapped_column(String(16), default="en")
    asr_model: Mapped[str] = mapped_column(String(128), default="")
    text_en: Mapped[str] = mapped_column(Text, default="")
    text_es: Mapped[str] = mapped_column(Text, default="")
    source_path: Mapped[str] = mapped_column(Text, default="")
    segments: Mapped[list[dict]] = mapped_column(JSON, default=list)
    source_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    synced_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
