from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import uuid

from sqlalchemy.orm import Session

import content as legacy_content
import models as legacy_models

from ..config import settings
from ..db_models import ContentItem
from .content_service import sync_content_records


def _ensure_tmp_dir() -> None:
    settings.tmp_ingest_dir.mkdir(parents=True, exist_ok=True)


def _asset_path(asset_id: str) -> Path:
    _ensure_tmp_dir()
    return settings.tmp_ingest_dir / f"{asset_id}.json"


def _asset_workspace_path(asset_id: str) -> Path:
    return legacy_content.asset_manifest_path(asset_id)


def _to_relative_url(path: str | Path) -> str:
    local_path = Path(path).resolve()
    relative = local_path.relative_to(settings.data_dir.resolve()).as_posix()
    return f"/files/{relative}"


def _load_asset_or_error(asset_id: str) -> dict:
    path = _asset_workspace_path(asset_id)
    if not path.exists():
        path = _asset_path(asset_id)
    if not path.exists():
        raise ValueError("No existe una sesión de validación para ese archivo.")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_asset(payload: dict) -> None:
    asset_id = payload["asset_id"]
    if payload.get("workspace_asset", False):
        legacy_content.write_asset_manifest(asset_id, payload)
    else:
        _asset_path(asset_id).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _serialize_asset(payload: dict) -> dict:
    transcription = payload.get("transcription") or {}
    segments = transcription.get("segments") or []
    transcript_text = " ".join(segment.get("text", "").strip() for segment in segments).strip()
    translated_segments = transcription.get("translated_segments_es") or []
    editable_segments = [
        {
            "index": index,
            "start": float(segment.get("start", 0.0)),
            "end": float(segment.get("end", 0.0)),
            "text_en": segment.get("text", "").strip(),
            "text_es": translated_segments[index].strip()
            if isinstance(translated_segments, list) and index < len(translated_segments)
            else "",
        }
        for index, segment in enumerate(segments)
    ]
    return {
        "asset_id": payload["asset_id"],
        "source_name": payload["source_name"],
        "media_kind": payload["media_kind"],
        "media_url": _to_relative_url(payload["media_path"]),
        "metadata": legacy_content._with_subtitle_urls(payload.get("metadata") or {}),
        "last_asr_key": transcription.get("asr_key", ""),
        "last_vtt_url": _to_relative_url(transcription["vtt_path"]) if transcription.get("vtt_path") else "",
        "transcript_text": transcript_text,
        "segments": editable_segments,
    }


def _scan_upload_media(session: Session) -> list[dict]:
    legacy_content.ensure_dirs()
    out = []
    for manifest_path in legacy_content.PENDING_ASSETS_DIR.glob("*/manifest.json"):
        try:
            asset = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        media_path = Path(asset.get("media_path", ""))
        if not media_path.exists():
            continue
        out.append(
            {
                "media_id": asset["asset_id"],
                "source_name": asset.get("source_name", media_path.name),
                "media_kind": asset.get("media_kind", "video" if legacy_content.is_video(media_path) else "audio"),
                "category": asset.get("origin", "workspace"),
                "media_url": _to_relative_url(media_path),
                "paired_video_name": "",
                "size_bytes": media_path.stat().st_size,
                "created_at": datetime.fromtimestamp(media_path.stat().st_mtime),
                "transcript_saved": False,
            }
        )

    files = legacy_content.list_pending_media_uploads()
    videos = {path.stem: path for path in files if legacy_content.is_video(path)}
    for path in files:
        if legacy_content.is_video(path):
            category = "video"
            paired_video_name = ""
            media_kind = "video"
        elif legacy_content.is_audio(path):
            paired_video = videos.get(path.stem)
            if paired_video is not None:
                category = "audio_extraido"
                paired_video_name = paired_video.name
            else:
                category = "audio_subido"
                paired_video_name = ""
            media_kind = "audio"
        else:
            continue

        out.append(
            {
                "media_id": path.name,
                "source_name": path.name,
                "media_kind": media_kind,
                "category": category,
                "media_url": _to_relative_url(path),
                "paired_video_name": paired_video_name,
                "size_bytes": path.stat().st_size,
                "created_at": datetime.fromtimestamp(path.stat().st_mtime),
                "transcript_saved": False,
            }
        )
    return out


def list_existing_media(session: Session) -> list[dict]:
    return _scan_upload_media(session)


def create_uploaded_media_asset(filename: str, raw: bytes) -> dict:
    legacy_content.ensure_dirs()
    asset_id = legacy_content.new_asset_id()
    source_path = legacy_content.save_asset_upload(asset_id, filename, raw)
    media_kind = "video" if legacy_content.is_video(source_path) else "audio"
    asset = {
        "asset_id": asset_id,
        "source_name": filename,
        "media_kind": media_kind,
        "media_path": str(source_path),
        "origin": "upload",
        "workspace_asset": True,
        "metadata": {"uploaded_name": filename},
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
        "transcription": {},
    }
    _save_asset(asset)
    return _serialize_asset(asset)


def create_existing_media_asset(session: Session, media_id: str) -> dict:
    workspace_manifest = legacy_content.asset_manifest_path(media_id)
    if workspace_manifest.exists():
        asset = json.loads(workspace_manifest.read_text(encoding="utf-8"))
        _save_asset(asset)
        return _serialize_asset(asset)

    items = {item["media_id"]: item for item in _scan_upload_media(session)}
    picked = items.get(media_id)
    if picked is None:
        raise ValueError("No existe ese archivo en la biblioteca de medios.")
    source_path = legacy_content.UPLOADS_DIR / media_id
    asset = {
        "asset_id": uuid.uuid4().hex,
        "source_name": picked["source_name"],
        "media_kind": picked["media_kind"],
        "media_path": str(source_path),
        "origin": "library",
        "metadata": {
            "category": picked["category"],
            "paired_video_name": picked.get("paired_video_name", ""),
        },
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
        "transcription": {},
    }
    _save_asset(asset)
    return _serialize_asset(asset)


def delete_pending_media(media_id: str) -> str:
    pending_asset = legacy_content.asset_dir(media_id)
    if pending_asset.exists():
        legacy_content.delete_asset_directory(media_id, library=False)
        return f"Archivo pendiente eliminado: {media_id}"

    target = legacy_content.UPLOADS_DIR / media_id
    if not target.exists():
        raise ValueError("No existe ese archivo pendiente.")
    legacy_content.delete_media_with_sidecars(target)
    return f"Archivo pendiente eliminado: {media_id}"


def create_youtube_media_asset(url: str, *, audio_only: bool = False) -> dict:
    legacy_content.ensure_dirs()
    asset_id = legacy_content.new_asset_id()
    source_path, info = legacy_content.download_youtube_media(url, audio_only=audio_only, asset_id=asset_id)
    media_kind = "audio" if audio_only or legacy_content.is_audio(source_path) else "video"
    asset = {
        "asset_id": asset_id,
        "source_name": source_path.name,
        "media_kind": media_kind,
        "media_path": str(source_path),
        "origin": "youtube",
        "workspace_asset": True,
        "metadata": info,
        "created_at": datetime.utcnow().isoformat(timespec="seconds"),
        "transcription": {},
    }
    _save_asset(asset)
    return _serialize_asset(asset)


def transcribe_asset(asset_id: str, asr_key: str, *, language: str = "en") -> dict:
    asset = _load_asset_or_error(asset_id)
    media_path = asset["media_path"]
    segments = legacy_models.transcribe_media(media_path, asr_key, language=language)
    if asset.get("workspace_asset"):
        vtt_path = legacy_content.asset_dir(asset_id) / "transcripts" / f"{asr_key}.vtt"
        vtt_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        vtt_path = settings.tmp_ingest_dir / f"{asset_id}.{asr_key}.vtt"
    legacy_models.write_vtt(segments, str(vtt_path))
    asset["transcription"] = {
        "asr_key": asr_key,
        "language": language,
        "segments": [segment.__dict__ for segment in segments],
        "vtt_path": str(vtt_path),
        "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
    }
    _save_asset(asset)
    return _serialize_asset(asset)


def _write_bilingual_preview_vtt(asset: dict) -> None:
    transcription = asset.get("transcription") or {}
    segments = transcription.get("segments") or []
    translated_segments = transcription.get("translated_segments_es") or []
    if not segments:
        return

    if asset.get("workspace_asset"):
        vtt_path = legacy_content.asset_dir(asset["asset_id"]) / "transcripts" / "preview.bilingual.vtt"
        vtt_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        vtt_path = settings.tmp_ingest_dir / f"{asset['asset_id']}.preview.vtt"
    preview_segments = []
    for index, segment in enumerate(segments):
        text_en = segment.get("text", "").strip()
        text_es = (
            translated_segments[index].strip()
            if isinstance(translated_segments, list) and index < len(translated_segments)
            else ""
        )
        preview_segments.append(
            legacy_models.Segment(
                start=float(segment.get("start", 0.0)),
                end=float(segment.get("end", 0.0)),
                text="\n".join(part for part in [text_en, text_es] if part),
            )
        )
    legacy_models.write_vtt(preview_segments, str(vtt_path))
    transcription["vtt_path"] = str(vtt_path)
    asset["transcription"] = transcription


def preview_transcript_asset(
    asset_id: str,
    *,
    llm_model: str = "",
    translate: bool = True,
) -> dict:
    asset = _load_asset_or_error(asset_id)
    transcription = asset.get("transcription") or {}
    segments = transcription.get("segments") or []
    if not segments:
        raise ValueError("Primero genera una transcripción.")

    translated_segments = transcription.get("translated_segments_es") or []
    if translate and len(translated_segments) != len(segments):
        translated_segments = legacy_models.translate_segments(
            [segment.get("text", "").strip() for segment in segments],
            llm_model=llm_model,
        )
        transcription["translated_segments_es"] = translated_segments
        asset["transcription"] = transcription

    _write_bilingual_preview_vtt(asset)
    _save_asset(asset)
    return _serialize_asset(asset)


def update_transcript_corrections(asset_id: str, updates: list[dict]) -> dict:
    asset = _load_asset_or_error(asset_id)
    transcription = asset.get("transcription") or {}
    segments = transcription.get("segments") or []
    if not segments:
        raise ValueError("Primero genera una transcripción.")

    translated_segments = transcription.get("translated_segments_es") or [""] * len(segments)
    if len(translated_segments) < len(segments):
        translated_segments = list(translated_segments) + [""] * (len(segments) - len(translated_segments))

    correction_log = transcription.get("corrections") or []
    translation_memory_entries = []
    for update in updates:
        index = int(update.get("index", -1))
        if index < 0 or index >= len(segments):
            continue
        old_en = segments[index].get("text", "")
        old_es = translated_segments[index]
        new_en = update.get("text_en", old_en).strip()
        new_es = update.get("text_es", old_es).strip()
        segments[index]["text"] = new_en
        translated_segments[index] = new_es
        if new_en != old_en or new_es != old_es:
            correction_log.append(
                {
                    "index": index,
                    "old_en": old_en,
                    "new_en": new_en,
                    "old_es": old_es,
                    "new_es": new_es,
                    "updated_at": datetime.utcnow().isoformat(timespec="seconds"),
                }
            )
            translation_memory_entries.append({"text_en": new_en, "text_es": new_es})

    transcription["segments"] = segments
    transcription["translated_segments_es"] = translated_segments
    transcription["corrections"] = correction_log
    transcription["updated_at"] = datetime.utcnow().isoformat(timespec="seconds")
    asset["transcription"] = transcription
    _write_bilingual_preview_vtt(asset)
    _save_asset(asset)
    legacy_content.record_translation_corrections(translation_memory_entries, source=asset.get("source_name", ""))
    return _serialize_asset(asset)


def save_transcript_asset(session: Session, asset_id: str, *, llm_model: str = "", translate: bool = True) -> str:
    asset = _load_asset_or_error(asset_id)
    transcription = asset.get("transcription") or {}
    if not transcription.get("segments"):
        raise ValueError("Primero genera y valida una transcripción.")

    segments = [
        legacy_models.Segment(
            start=float(item.get("start", 0.0)),
            end=float(item.get("end", 0.0)),
            text=item.get("text", "").strip(),
        )
        for item in transcription["segments"]
    ]
    metadata = asset.get("metadata") or {}
    translated_segments = transcription.get("translated_segments_es") or []
    if translated_segments:
        metadata = dict(metadata)
        metadata["translated_segments_es"] = translated_segments
    if transcription.get("corrections"):
        metadata = dict(metadata)
        metadata["corrections"] = transcription["corrections"]
    out_file = legacy_content.save_transcript_record(
        asset["source_name"],
        segments,
        asr_model=transcription["asr_key"],
        llm_model=llm_model,
        kind=asset["media_kind"],
        source_path=asset["media_path"],
        translate=translate and not translated_segments,
        metadata=metadata,
        asset_id=asset_id if asset.get("workspace_asset") else "",
    )
    sync_content_records(session)
    return f"Transcripción guardada en {out_file}"


def import_document_asset(
    session: Session,
    filename: str,
    raw: bytes,
    *,
    llm_model: str = "",
    translate: bool = True,
) -> str:
    out_file = legacy_content.import_document(filename, raw, llm_model=llm_model, translate=translate)
    sync_content_records(session)
    return f"Documento importado en {out_file}"
