"""
content.py - Ingesta, persistencia y lectura de contenido de estudio.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import re
import shutil
import subprocess
import uuid

import models as M


DATA_DIR = Path("data")
UPLOADS_DIR = DATA_DIR / "uploads"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
LIBRARY_DIR = DATA_DIR / "library"
OBSIDIAN_DIR = DATA_DIR / "obsidian"
MEDIA_LIBRARY_DIR = DATA_DIR / "media_library"
CORRECTIONS_DIR = DATA_DIR / "corrections"
TRANSLATION_MEMORY_PATH = CORRECTIONS_DIR / "translation_memory.jsonl"
WORKSPACE_DIR = DATA_DIR / "workspace"
PENDING_ASSETS_DIR = WORKSPACE_DIR / "pending"
LIBRARY_ASSETS_DIR = WORKSPACE_DIR / "library"
DOCUMENT_ASSETS_DIR = WORKSPACE_DIR / "documents"

VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
TEXT_EXTS = {".txt", ".md"}
PDF_EXTS = {".pdf"}
YOUTUBE_SUBTITLE_PRIORITY = {
    "en": ["en", "en-US", "en-GB", "en-CA", "en-AU"],
    "es": ["es", "es-419", "es-MX", "es-ES"],
}


def ensure_dirs():
    for path in [
        DATA_DIR,
        UPLOADS_DIR,
        TRANSCRIPTS_DIR,
        LIBRARY_DIR,
        OBSIDIAN_DIR,
        MEDIA_LIBRARY_DIR,
        CORRECTIONS_DIR,
        WORKSPACE_DIR,
        PENDING_ASSETS_DIR,
        LIBRARY_ASSETS_DIR,
        DOCUMENT_ASSETS_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip().lower())
    value = value.strip("._-")
    return value or "item"


def is_video(path: str | Path) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTS


def is_audio(path: str | Path) -> bool:
    return Path(path).suffix.lower() in AUDIO_EXTS


def is_media(path: str | Path) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in VIDEO_EXTS or suffix in AUDIO_EXTS


def save_upload_bytes(name: str, raw: bytes) -> Path:
    ensure_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = UPLOADS_DIR / f"{stamp}_{slugify(Path(name).name)}"
    path.write_bytes(raw)
    return path


def new_asset_id() -> str:
    return uuid.uuid4().hex


def asset_dir(asset_id: str, *, library: bool = False) -> Path:
    ensure_dirs()
    return (LIBRARY_ASSETS_DIR if library else PENDING_ASSETS_DIR) / asset_id


def asset_manifest_path(asset_id: str, *, library: bool = False) -> Path:
    return asset_dir(asset_id, library=library) / "manifest.json"


def write_asset_manifest(asset_id: str, payload: dict, *, library: bool = False) -> Path:
    directory = asset_dir(asset_id, library=library)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "manifest.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_asset_manifest(asset_id: str, *, library: bool = False) -> dict:
    return json.loads(asset_manifest_path(asset_id, library=library).read_text(encoding="utf-8"))


def save_asset_upload(asset_id: str, name: str, raw: bytes) -> Path:
    directory = asset_dir(asset_id)
    media_dir = directory / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    path = media_dir / slugify(Path(name).name)
    path.write_bytes(raw)
    return path


def promote_asset_directory(asset_id: str) -> Path:
    pending = asset_dir(asset_id)
    library = asset_dir(asset_id, library=True)
    library.parent.mkdir(parents=True, exist_ok=True)
    if library.exists():
        shutil.rmtree(library)
    if pending.exists():
        pending.replace(library)
    return library


def delete_asset_directory(asset_id: str, *, library: bool | None = None) -> int:
    roots = []
    if library is None:
        roots = [asset_dir(asset_id), asset_dir(asset_id, library=True)]
    else:
        roots = [asset_dir(asset_id, library=library)]
    deleted = 0
    for root in roots:
        if root.exists() and root.is_dir():
            shutil.rmtree(root)
            deleted += 1
    return deleted


def workspace_relative(path: str | Path) -> str:
    local = Path(path).resolve()
    return local.relative_to(DATA_DIR.resolve()).as_posix()


def _unique_path(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        other = directory / f"{stem}_{index}{suffix}"
        if not other.exists():
            return other
        index += 1


def move_media_to_library(source_path: str | Path, source_name: str = "") -> Path:
    """Mueve un medio aprobado a la biblioteca permanente."""
    ensure_dirs()
    src = Path(source_path)
    if not src.exists():
        return src
    target_name = slugify(source_name or src.name)
    if not Path(target_name).suffix:
        target_name += src.suffix
    dest = _unique_path(MEDIA_LIBRARY_DIR, target_name)
    src.replace(dest)
    return dest


def delete_path(path: str | Path) -> bool:
    target = Path(path)
    if not target.exists():
        return False
    if target.is_file():
        target.unlink()
        return True
    return False


def _subtitle_target_path(media_path: Path, lang: str) -> Path:
    return media_path.with_name(f"{media_path.stem}.{lang}.vtt")


def _strip_timestamp_prefix(stem: str) -> str:
    return re.sub(r"^\d{8}_\d{6}_", "", stem)


def _strip_subtitle_language_suffix(stem: str) -> str:
    for variants in YOUTUBE_SUBTITLE_PRIORITY.values():
        for variant in variants:
            suffix = f".{variant}"
            if stem.endswith(suffix):
                return stem[: -len(suffix)]
    return stem


def _subtitle_candidates_by_title(path: str | Path) -> list[Path]:
    media_path = Path(path)
    title_key = slugify(_strip_timestamp_prefix(media_path.stem))
    if not title_key:
        return []

    candidates = []
    for directory in [UPLOADS_DIR, MEDIA_LIBRARY_DIR]:
        if not directory.exists():
            continue
        for candidate in directory.glob("*.vtt"):
            candidate_key = slugify(
                _strip_timestamp_prefix(
                    _strip_subtitle_language_suffix(candidate.stem)
                )
            )
            if candidate_key == title_key:
                candidates.append(candidate)
    return candidates


def find_media_sidecar_subtitles(path: str | Path) -> dict[str, Path]:
    media_path = Path(path)
    found: dict[str, Path] = {}
    candidates = list(media_path.parent.glob(f"{media_path.stem}.*.vtt"))
    candidates.extend(_subtitle_candidates_by_title(media_path))
    by_lang: dict[str, dict[str, Path]] = {"en": {}, "es": {}}
    for candidate in candidates:
        suffixes = candidate.suffixes
        if len(suffixes) < 2 or suffixes[-1] != ".vtt":
            continue
        raw_lang = suffixes[-2].lstrip(".")
        for canonical, priority in YOUTUBE_SUBTITLE_PRIORITY.items():
            if raw_lang in priority:
                by_lang[canonical][raw_lang] = candidate
                break

    for canonical, priority in YOUTUBE_SUBTITLE_PRIORITY.items():
        for variant in priority:
            candidate = by_lang[canonical].get(variant)
            if candidate is not None:
                found[canonical] = candidate
                break
    return found


def find_all_media_sidecar_subtitles(path: str | Path) -> list[Path]:
    media_path = Path(path)
    candidates = list(media_path.parent.glob(f"{media_path.stem}.*.vtt"))
    candidates.extend(_subtitle_candidates_by_title(media_path))
    seen = set()
    out = []
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.exists():
            out.append(candidate)
    return out


def _with_subtitle_urls(metadata: dict | None) -> dict:
    out = dict(metadata or {})
    subtitle_paths = out.get("youtube_subtitles") or {}
    subtitle_urls = {}
    for lang, path in subtitle_paths.items():
        local = Path(path)
        if local.exists():
            try:
                relative = local.resolve().relative_to(DATA_DIR.resolve()).as_posix()
                subtitle_urls[lang] = f"/files/{relative}"
            except ValueError:
                continue
    if subtitle_urls:
        out["youtube_subtitle_urls"] = subtitle_urls
    return out


def move_media_sidecar_subtitles(source_path: str | Path, dest_path: str | Path, metadata: dict | None = None) -> dict:
    src = Path(source_path)
    dest = Path(dest_path)
    updated = dict(metadata or {})
    found = find_media_sidecar_subtitles(src)
    if not found:
        return updated

    moved = {}
    for lang, subtitle_path in found.items():
        target = _subtitle_target_path(dest, lang)
        subtitle_path.replace(target)
        moved[lang] = str(target)
    if moved:
        updated["youtube_subtitles"] = moved
    return updated


def delete_media_with_sidecars(path: str | Path) -> bool:
    target = Path(path)
    subtitle_paths = find_all_media_sidecar_subtitles(target)
    deleted = delete_path(target)
    for subtitle_path in subtitle_paths:
        delete_path(subtitle_path)
    return deleted


def delete_metadata_subtitles(metadata: dict | None) -> int:
    deleted = 0
    subtitle_paths = (metadata or {}).get("youtube_subtitles") or {}
    for path in subtitle_paths.values():
        if delete_path(path):
            deleted += 1
    return deleted


def _youtube_download_options(
    output_template: str,
    *,
    audio_only: bool,
    progress_callback=None,
    with_subtitles: bool = True,
) -> dict:
    options = {
        "outtmpl": output_template,
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    if with_subtitles:
        options.update(
            {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": sorted({lang for langs in YOUTUBE_SUBTITLE_PRIORITY.values() for lang in langs}),
                "subtitlesformat": "vtt/best",
            }
        )
    if audio_only:
        options["format"] = "bestaudio/best"
    else:
        options["format"] = "bestvideo+bestaudio/best"
        options["merge_output_format"] = "mp4"
    if progress_callback is not None:
        options["progress_hooks"] = [progress_callback]
    return options


def _is_youtube_subtitle_error(exc: Exception) -> bool:
    message = str(exc).lower()
    markers = ("subtitle", "subtitles", "caption", "captions", "429", "too many requests")
    return any(marker in message for marker in markers)


def download_youtube_media(
    url: str,
    *,
    audio_only: bool = False,
    progress_callback=None,
    asset_id: str | None = None,
) -> tuple[Path, dict]:
    """Descarga un video o audio de YouTube usando yt-dlp."""
    ensure_dirs()
    try:
        import yt_dlp
    except Exception as exc:
        raise RuntimeError("Falta instalar yt-dlp para descargar contenido desde URL.") from exc

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    download_dir = asset_dir(asset_id) / "media" if asset_id else UPLOADS_DIR
    download_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(download_dir / f"{stamp}_%(title).120s.%(ext)s")
    info = {}
    warning = ""
    final_path = Path()
    try:
        with yt_dlp.YoutubeDL(
            _youtube_download_options(
                output_template,
                audio_only=audio_only,
                progress_callback=progress_callback,
                with_subtitles=True,
            )
        ) as ydl:
            info = ydl.extract_info(url, download=True)
            final_path = Path(ydl.prepare_filename(info))
    except Exception as exc:
        if not _is_youtube_subtitle_error(exc):
            raise
        warning = "YouTube bloqueo o no entrego algunos subtitulos; se guardo solo el medio."
        with yt_dlp.YoutubeDL(
            _youtube_download_options(
                output_template,
                audio_only=audio_only,
                progress_callback=progress_callback,
                with_subtitles=False,
            )
        ) as ydl:
            info = ydl.extract_info(url, download=True)
            final_path = Path(ydl.prepare_filename(info))

    requested = info.get("requested_downloads") or []
    filepath = requested[0].get("filepath") if requested and isinstance(requested[0], dict) else ""
    if filepath:
        final_path = Path(filepath)

    if not final_path.exists():
        candidates = sorted(download_dir.glob(f"{stamp}_*"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not candidates:
            raise RuntimeError("yt-dlp no devolvio un archivo descargado.")
        final_path = candidates[0]

    subtitle_paths = {
        lang: str(path)
        for lang, path in find_media_sidecar_subtitles(final_path).items()
    }

    metadata = {
        "url": url,
        "title": info.get("title", final_path.name),
        "webpage_url": info.get("webpage_url", url),
        "duration": info.get("duration"),
        "channel": info.get("channel"),
        "audio_only": audio_only,
        "youtube_subtitles": subtitle_paths,
    }
    if warning:
        metadata["youtube_subtitles_warning"] = warning
    return final_path, _with_subtitle_urls(metadata)


def read_text_file(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def extract_pdf_text(path: str | Path) -> str:
    p = Path(path)
    try:
        import fitz

        doc = fitz.open(p)
        text = "\n".join(page.get_text("text") for page in doc)
        if text.strip():
            return text
    except Exception:
        pass

    try:
        import pdfplumber

        with pdfplumber.open(p) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages).strip()
    except Exception as exc:
        raise RuntimeError(f"No se pudo extraer texto de PDF: {p.name}") from exc


def extract_document_text(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in TEXT_EXTS:
        return read_text_file(path)
    if suffix in PDF_EXTS:
        return extract_pdf_text(path)
    raise ValueError(f"Tipo de documento no soportado: {suffix}")


def record_filename(source_name: str, kind: str) -> str:
    stem = slugify(Path(source_name).stem)
    return f"{stem}.{kind}.json"


def save_record(record: dict, directory: Path) -> Path:
    ensure_dirs()
    path = directory / record_filename(record["source"], record.get("kind", "content"))
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def save_record_at(record: dict, path: str | Path) -> Path:
    ensure_dirs()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def write_record(path: str | Path, record: dict) -> Path:
    target = Path(path)
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def record_translation_corrections(entries: list[dict], *, source: str = "") -> None:
    clean_entries = []
    for entry in entries:
        text_en = str(entry.get("text_en", "")).strip()
        text_es = str(entry.get("text_es", "")).strip()
        if not text_en or not text_es:
            continue
        clean_entries.append(
            {
                "source": source,
                "text_en": text_en,
                "text_es": text_es,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
    if not clean_entries:
        return

    ensure_dirs()
    with TRANSLATION_MEMORY_PATH.open("a", encoding="utf-8") as handle:
        for entry in clean_entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def build_record(
    source_name: str,
    kind: str,
    text_en: str,
    text_es: str = "",
    *,
    asr_model: str = "",
    language: str = "en",
    source_path: str = "",
    segments: list[dict] | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "source": source_name,
        "kind": kind,
        "language": language,
        "asr_model": asr_model,
        "text_en": text_en.strip(),
        "text_es": text_es.strip(),
        "segments": segments or [],
        "source_path": source_path,
        "metadata": metadata or {},
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def enrich_record_with_segment_translations(record: dict, llm_model: str = "") -> tuple[dict, bool]:
    segments = record.get("segments") or []
    if not segments:
        return record, False

    metadata = dict(record.get("metadata") or {})
    translated = metadata.get("translated_segments_es")
    if isinstance(translated, list) and len(translated) == len(segments):
        return record, False

    segment_texts = [str(segment.get("text", "")).strip() for segment in segments]
    translated_segments = M.translate_segments(segment_texts, llm_model=llm_model)
    if not any(text.strip() for text in translated_segments):
        return record, False

    metadata["translated_segments_es"] = translated_segments
    record["metadata"] = metadata
    if not str(record.get("text_es", "")).strip():
        record["text_es"] = " ".join(text for text in translated_segments if text.strip())
    return record, True


def save_transcript_record(
    source_name: str,
    segments: list[M.Segment],
    *,
    asr_model: str,
    llm_model: str = "",
    kind: str = "video",
    source_path: str = "",
    translate: bool = True,
    metadata: dict | None = None,
    asset_id: str = "",
) -> Path:
    text_en = " ".join(segment.text for segment in segments).strip()
    text_es = M.translate_text(text_en, llm_model=llm_model) if translate else ""
    metadata = dict(metadata or {})
    if translate:
        translated_segments = M.translate_segments([segment.text for segment in segments], llm_model=llm_model)
        if any(text.strip() for text in translated_segments):
            metadata["translated_segments_es"] = translated_segments
            if not text_es.strip():
                text_es = " ".join(text for text in translated_segments if text.strip())
    if asset_id:
        promote_asset_directory(asset_id)
        media_path = Path(source_path)
        metadata["asset_id"] = asset_id
        metadata = _with_subtitle_urls(metadata)
    else:
        media_path = move_media_to_library(source_path, source_name) if source_path else ""
        if source_path and media_path:
            metadata = move_media_sidecar_subtitles(source_path, media_path, metadata)
            metadata = _with_subtitle_urls(metadata)
    record = build_record(
        source_name,
        kind,
        text_en,
        text_es=text_es,
        asr_model=asr_model,
        source_path=str(media_path) if media_path else source_path,
        segments=[segment.__dict__ for segment in segments],
        metadata=metadata,
    )
    if asset_id:
        record_path = asset_dir(asset_id, library=True) / "records" / record_filename(source_name, kind)
        return save_record_at(record, record_path)
    return save_record(record, TRANSCRIPTS_DIR)


def import_document(
    source_name: str,
    raw: bytes,
    *,
    llm_model: str = "",
    translate: bool = True,
    asset_id: str = "",
) -> Path:
    if asset_id:
        source_path = save_asset_upload(asset_id, source_name, raw)
    else:
        source_path = save_upload_bytes(source_name, raw)
    text_en = extract_document_text(source_path)
    text_es = M.translate_text(text_en, llm_model=llm_model) if translate else ""
    kind = "pdf" if source_path.suffix.lower() in PDF_EXTS else "text"
    record = build_record(
        source_name,
        kind,
        text_en,
        text_es=text_es,
        source_path=str(source_path),
        metadata={"uploaded_name": source_name, "asset_id": asset_id} if asset_id else {"uploaded_name": source_name},
    )
    if asset_id:
        promote_asset_directory(asset_id)
        record_path = asset_dir(asset_id, library=True) / "records" / record_filename(source_name, kind)
        return save_record_at(record, record_path)
    return save_record(record, LIBRARY_DIR)


def list_records() -> list[Path]:
    ensure_dirs()
    records = list(TRANSCRIPTS_DIR.glob("*.json")) + list(LIBRARY_DIR.glob("*.json"))
    records += list(LIBRARY_ASSETS_DIR.glob("*/records/*.json"))
    return sorted(records, key=lambda path: path.stat().st_mtime, reverse=True)


def load_record(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def display_name(record: dict) -> str:
    meta = record.get("metadata", {})
    return meta.get("title") or record.get("source") or "sin_nombre"


def list_pending_media_uploads() -> list[Path]:
    """Medios en uploads aun no promovidos a la biblioteca."""
    ensure_dirs()
    referenced = set()
    for record_path in TRANSCRIPTS_DIR.glob("*.json"):
        try:
            record = load_record(record_path)
        except Exception:
            continue
        source_path = record.get("source_path")
        if source_path:
            referenced.add(str(Path(source_path).resolve()))
    uploads = []
    for path in UPLOADS_DIR.iterdir():
        if not path.is_file() or not is_media(path):
            continue
        if str(path.resolve()) not in referenced:
            uploads.append(path)
    return sorted(uploads, key=lambda item: item.stat().st_mtime, reverse=True)


def cleanup_orphan_files(*, dry_run: bool = False) -> dict:
    ensure_dirs()
    referenced = set()
    for record_path in list_records():
        try:
            record = load_record(record_path)
        except Exception:
            continue
        for value in [
            record.get("source_path", ""),
            *((record.get("metadata") or {}).get("youtube_subtitles") or {}).values(),
        ]:
            if value:
                referenced.add(str(Path(value).resolve()))

    pending_media = {str(path.resolve()) for path in list_pending_media_uploads()}
    deleted = []

    for path in UPLOADS_DIR.glob("*.vtt"):
        resolved = str(path.resolve())
        if resolved not in referenced and resolved not in pending_media:
            deleted.append(str(path))
            if not dry_run:
                delete_path(path)

    for tmp_file in DATA_DIR.joinpath("tmp_ingest").glob("content_*.vtt"):
        deleted.append(str(tmp_file))
        if not dry_run:
            delete_path(tmp_file)

    for root in [PENDING_ASSETS_DIR, LIBRARY_ASSETS_DIR, DOCUMENT_ASSETS_DIR]:
        if not root.exists():
            continue
        for directory in root.iterdir():
            if directory.is_dir() and not (directory / "manifest.json").exists():
                deleted.append(str(directory))
                if not dry_run:
                    shutil.rmtree(directory)

    return {"deleted": deleted, "count": len(deleted), "dry_run": dry_run}


def list_media_records() -> list[Path]:
    return [
        path
        for path in list_records()
        if load_record(path).get("kind") in {"video", "audio"}
    ]


def delete_record(record_path: str | Path, *, delete_source: bool = True) -> bool:
    path = Path(record_path)
    if not path.exists():
        return False
    record = load_record(path)
    source_path = record.get("source_path", "")
    if delete_source and source_path:
        delete_media_with_sidecars(source_path)
        delete_metadata_subtitles(record.get("metadata") or {})
    path.unlink()
    return True
