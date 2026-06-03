from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

import content as legacy_content
import models as legacy_models

from ..config import settings
from ..db_models import ContentItem


def _record_key(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(settings.project_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.utcnow()


def _to_relative_url(path: str | Path) -> str:
    if not path:
        return ""
    local_path = Path(path)
    if not local_path.exists():
        return ""
    resolved = local_path.resolve()
    relative = resolved.relative_to(settings.data_dir.resolve()).as_posix()
    return f"/files/{relative}"


def _build_vtt_for_item(item: ContentItem) -> str:
    if item.kind not in {"video", "audio"} or not item.segments:
        return ""
    translated_segments = item.source_metadata.get("translated_segments_es", []) if item.source_metadata else []
    digest_source = json.dumps(
        {
            "key": item.record_key,
            "segments": len(item.segments),
            "translated": translated_segments,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    digest = hashlib.md5(digest_source.encode("utf-8")).hexdigest()
    out = settings.tmp_ingest_dir / f"content_{item.id}_{digest}.vtt"
    if not out.exists():
        settings.tmp_ingest_dir.mkdir(parents=True, exist_ok=True)
        segments = [
            legacy_models.Segment(
                start=float(segment.get("start", 0.0)),
                end=float(segment.get("end", 0.0)),
                text="\n".join(
                    part
                    for part in [
                        segment.get("text", "").strip(),
                        translated_segments[index].strip()
                        if isinstance(translated_segments, list) and index < len(translated_segments)
                        else "",
                    ]
                    if part
                ),
            )
            for index, segment in enumerate(item.segments)
        ]
        legacy_models.write_vtt(segments, str(out))
    return _to_relative_url(out)


def sync_content_records(session: Session) -> dict[str, int]:
    legacy_content.ensure_dirs()
    paths = legacy_content.list_records()
    existing = {
        item.record_key: item
        for item in session.scalars(select(ContentItem)).all()
    }

    inserted = 0
    updated = 0
    for path in paths:
        record = legacy_content.load_record(path)
        key = _record_key(path)
        payload = {
            "source": record.get("source", path.stem),
            "kind": record.get("kind", "content"),
            "language": record.get("language", "en"),
            "asr_model": record.get("asr_model", ""),
            "text_en": record.get("text_en", ""),
            "text_es": record.get("text_es", ""),
            "source_path": record.get("source_path", ""),
            "segments": record.get("segments") or [],
            "source_metadata": record.get("metadata") or {},
            "created_at": _parse_datetime(record.get("created_at")),
        }

        item = existing.get(key)
        if item is None:
            session.add(ContentItem(record_key=key, **payload))
            inserted += 1
            continue

        changed = False
        for field, value in payload.items():
            if field == "created_at":
                continue
            if getattr(item, field) != value:
                setattr(item, field, value)
                changed = True
        if changed:
            updated += 1

    session.commit()
    total = session.scalar(select(func.count()).select_from(ContentItem)) or 0
    return {"inserted": inserted, "updated": updated, "total": total}


def list_content_items(session: Session) -> list[ContentItem]:
    sync_content_records(session)
    stmt = select(ContentItem).order_by(ContentItem.created_at.desc())
    return list(session.scalars(stmt).all())


def get_content_item(session: Session, content_id: int) -> ContentItem | None:
    return session.get(ContentItem, content_id)


def _safe_data_path(path: str | Path) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = settings.project_root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(settings.data_dir.resolve())
    except ValueError:
        return None
    return resolved


def delete_content_item(session: Session, content_id: int, *, delete_source: bool = True) -> str:
    item = session.get(ContentItem, content_id)
    if item is None:
        raise ValueError("Contenido no encontrado.")

    record_path = _safe_data_path(item.record_key)
    source_path = _safe_data_path(item.source_path)
    source_name = item.source

    if delete_source and source_path is not None:
        legacy_content.delete_media_with_sidecars(source_path)
        legacy_content.delete_metadata_subtitles(item.source_metadata or {})

    if record_path is not None and record_path.exists():
        legacy_content.delete_path(record_path)

    asset_id = (item.source_metadata or {}).get("asset_id", "")
    if asset_id:
        legacy_content.delete_asset_directory(asset_id)

    session.delete(item)
    session.commit()
    return f"Contenido eliminado: {source_name}"
