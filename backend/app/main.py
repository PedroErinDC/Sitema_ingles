from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import content as legacy_content
import models as legacy_models

from .config import settings
from .db import SessionLocal, get_db, init_db
from .schemas import (
    AsrCatalogItem,
    ContentItemSummary,
    ContentProcessRequest,
    DashboardSummary,
    DocumentImportResponse,
    ExistingMediaItem,
    ExistingMediaSelectRequest,
    GrammarQuizItem,
    GrammarReviewPayload,
    GraphIndexRequest,
    GraphResponse,
    GraphStats,
    GraphQueryRequest,
    MediaAssetResponse,
    MediaCorrectionsRequest,
    MediaPreviewRequest,
    MediaSaveRequest,
    MediaTranscribeRequest,
    MediaUploadResponse,
    MessageResponse,
    ModelCatalogItem,
    ModelCatalogResponse,
    ReviewPayload,
    YouTubeDownloadRequest,
    WordCard,
)
from .services import content_service, graph_service, learning_service
from .services.bootstrap_service import bootstrap_data
from .services import ingest_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    with SessionLocal() as session:
        bootstrap_data(session)
    yield


app = FastAPI(
    title="API de Portafolio para Aprendizaje de Inglés",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/files", StaticFiles(directory=settings.data_dir), name="files")


@app.get("/api/health", response_model=MessageResponse)
def health() -> MessageResponse:
    return MessageResponse(message="ok")


@app.get("/api/models", response_model=ModelCatalogResponse)
def list_models() -> ModelCatalogResponse:
    installed = legacy_models.llm_installed()
    catalog = [
        ModelCatalogItem(
            id=model_id,
            label=meta["label"],
            vram_gb=meta["vram_gb"],
            installed=model_id in installed,
        )
        for model_id, meta in legacy_models.LLM_CATALOG.items()
    ]
    asr_catalog = [
        AsrCatalogItem(
            id=model_id,
            label=meta["label"],
            backend=meta["backend"],
        )
        for model_id, meta in legacy_models.ASR_CATALOG.items()
    ]
    return ModelCatalogResponse(
        preferred_llm=legacy_models.preferred_llm(),
        installed_llms=installed,
        catalog=catalog,
        asr_catalog=asr_catalog,
    )


@app.get("/api/media/library", response_model=list[ExistingMediaItem])
def media_library(db: Session = Depends(get_db)) -> list[ExistingMediaItem]:
    return [ExistingMediaItem(**item) for item in ingest_service.list_existing_media(db)]


@app.delete("/api/media/library/{media_id}", response_model=MessageResponse)
def delete_pending_media(media_id: str) -> MessageResponse:
    try:
        message = ingest_service.delete_pending_media(media_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(message=message)


@app.post("/api/ingest/media/upload", response_model=MediaUploadResponse)
async def upload_media(file: UploadFile = File(...)) -> MediaUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Archivo no válido.")
    raw = await file.read()
    try:
        asset = ingest_service.create_uploaded_media_asset(file.filename, raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaUploadResponse(message="Archivo cargado para validación", asset=MediaAssetResponse(**asset))


@app.post("/api/ingest/media/youtube", response_model=MediaUploadResponse)
def download_youtube_media(payload: YouTubeDownloadRequest) -> MediaUploadResponse:
    try:
        asset = ingest_service.create_youtube_media_asset(payload.url, audio_only=payload.audio_only)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    warning = (asset.get("metadata") or {}).get("youtube_subtitles_warning", "")
    message = "Contenido descargado para validación"
    if warning:
        message = f"{message}. {warning}"
    return MediaUploadResponse(message=message, asset=MediaAssetResponse(**asset))


@app.post("/api/ingest/media/library", response_model=MediaUploadResponse)
def load_existing_media(payload: ExistingMediaSelectRequest, db: Session = Depends(get_db)) -> MediaUploadResponse:
    try:
        asset = ingest_service.create_existing_media_asset(db, payload.media_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaUploadResponse(message="Archivo existente cargado para validación", asset=MediaAssetResponse(**asset))


@app.post("/api/ingest/media/transcribe", response_model=MediaUploadResponse)
def transcribe_media(payload: MediaTranscribeRequest) -> MediaUploadResponse:
    try:
        asset = ingest_service.transcribe_asset(payload.asset_id, payload.asr_key, language=payload.language)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaUploadResponse(message="Transcripción generada", asset=MediaAssetResponse(**asset))


@app.post("/api/ingest/media/preview", response_model=MediaUploadResponse)
def preview_media(payload: MediaPreviewRequest) -> MediaUploadResponse:
    try:
        asset = ingest_service.preview_transcript_asset(
            payload.asset_id,
            llm_model=payload.llm_model,
            translate=payload.translate,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaUploadResponse(message="Previsualización bilingüe generada", asset=MediaAssetResponse(**asset))


@app.post("/api/ingest/media/corrections", response_model=MediaUploadResponse)
def update_media_corrections(payload: MediaCorrectionsRequest) -> MediaUploadResponse:
    try:
        asset = ingest_service.update_transcript_corrections(
            payload.asset_id,
            [segment.model_dump() for segment in payload.segments],
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MediaUploadResponse(message="Correcciones aplicadas", asset=MediaAssetResponse(**asset))


@app.post("/api/ingest/media/save", response_model=MessageResponse)
def save_media(payload: MediaSaveRequest, db: Session = Depends(get_db)) -> MessageResponse:
    try:
        result = ingest_service.save_transcript_asset(
            db,
            payload.asset_id,
            llm_model=payload.llm_model,
            translate=payload.translate,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(message=result)


@app.post("/api/ingest/document", response_model=DocumentImportResponse)
async def upload_document(
    file: UploadFile = File(...),
    llm_model: str = Form(default=""),
    translate: bool = Form(default=True),
    db: Session = Depends(get_db),
) -> DocumentImportResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Documento no válido.")
    raw = await file.read()
    try:
        result = ingest_service.import_document_asset(
            db,
            file.filename,
            raw,
            llm_model=llm_model,
            translate=translate,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DocumentImportResponse(message=result)


@app.get("/api/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)) -> DashboardSummary:
    return DashboardSummary(
        word_counts=learning_service.status_counts(db),
        grammar_counts=learning_service.grammar_status_counts(db),
        rank=learning_service.grammar_rank_summary(db),
        weak_topics=learning_service.weak_topics(db),
        weak_grammar_topics=learning_service.weak_grammar_topics(db),
        graph=GraphStats(**graph_service.graph_stats()),
    )


@app.get("/api/study/queue", response_model=list[WordCard])
def study_queue(limit: int = 20, db: Session = Depends(get_db)) -> list[WordCard]:
    return [WordCard(**item) for item in learning_service.due_today(db, limit=limit)]


@app.post("/api/study/review", response_model=WordCard)
def review_word(payload: ReviewPayload, db: Session = Depends(get_db)) -> WordCard:
    item = learning_service.review_word(db, payload.word_id, payload.rating)
    if item is None:
        raise HTTPException(status_code=404, detail="Palabra no encontrada.")
    return WordCard(**item)


@app.get("/api/grammar/quiz", response_model=list[GrammarQuizItem])
def grammar_quiz(limit: int = 5, db: Session = Depends(get_db)) -> list[GrammarQuizItem]:
    return [GrammarQuizItem(**item) for item in learning_service.build_grammar_quiz_session(db, limit=limit)]


@app.post("/api/grammar/review", response_model=MessageResponse)
def review_grammar(payload: GrammarReviewPayload, db: Session = Depends(get_db)) -> MessageResponse:
    item = learning_service.review_grammar(db, payload.item_id, payload.rating, payload.correct)
    if item is None:
        raise HTTPException(status_code=404, detail="Elemento de gramática no encontrado.")
    return MessageResponse(message="Revisión de gramática guardada")


@app.get("/api/content", response_model=list[ContentItemSummary])
def list_content(db: Session = Depends(get_db)) -> list[ContentItemSummary]:
    items = content_service.list_content_items(db)
    return [
        ContentItemSummary(
            id=item.id,
            record_key=item.record_key,
            source=item.source,
            kind=item.kind,
            language=item.language,
            asr_model=item.asr_model,
            source_path=item.source_path,
            created_at=item.created_at,
            text_preview=(item.text_en[:240] + "...") if len(item.text_en) > 240 else item.text_en,
            text_en_length=len(item.text_en),
            text_en=item.text_en,
            text_es=item.text_es,
            media_url=content_service._to_relative_url(item.source_path),
            vtt_url=content_service._build_vtt_for_item(item),
            source_metadata=legacy_content._with_subtitle_urls(item.source_metadata or {}),
        )
        for item in items
    ]


@app.post("/api/content/sync", response_model=MessageResponse)
def sync_content(db: Session = Depends(get_db)) -> MessageResponse:
    result = content_service.sync_content_records(db)
    return MessageResponse(
        message=f"Sincronización completa: {result['inserted']} insertados, {result['updated']} actualizados"
    )


@app.post("/api/content/cleanup", response_model=MessageResponse)
def cleanup_content_files(db: Session = Depends(get_db)) -> MessageResponse:
    try:
        result = legacy_content.cleanup_orphan_files(dry_run=False)
        sync_result = content_service.sync_content_records(db)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(
        message=(
            f"Limpieza completa: {result['count']} residuos eliminados. "
            f"Biblioteca sincronizada: {sync_result['total']} registros."
        )
    )


@app.delete("/api/content/{content_id}", response_model=MessageResponse)
def delete_content(content_id: int, db: Session = Depends(get_db)) -> MessageResponse:
    try:
        message = content_service.delete_content_item(db, content_id, delete_source=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(message=message)


@app.post("/api/content/{content_id}/process", response_model=MessageResponse)
def process_content(
    content_id: int,
    payload: ContentProcessRequest,
    db: Session = Depends(get_db),
) -> MessageResponse:
    item = content_service.get_content_item(db, content_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Contenido no encontrado.")

    vocab_count = 0
    grammar_count = 0
    if payload.import_vocab:
        vocab_count = learning_service.add_words_from_text(
            db,
            item.text_en,
            topic=payload.topic,
            llm_model=payload.llm_model,
        )
    if payload.import_grammar:
        grammar_count = learning_service.import_grammar_points(
            db,
            item.text_en,
            topic=payload.topic,
            llm_model=payload.llm_model,
        )
    return MessageResponse(
        message=f"Contenido procesado: {vocab_count} elementos de vocabulario, {grammar_count} puntos de gramática"
    )


@app.get("/api/graph/stats", response_model=GraphStats)
def get_graph_stats() -> GraphStats:
    return GraphStats(**graph_service.graph_stats())


@app.post("/api/graph/index", response_model=MessageResponse)
def index_graph(payload: GraphIndexRequest, db: Session = Depends(get_db)) -> MessageResponse:
    stats = graph_service.index_content(db, payload.content_ids, payload.llm_model)
    return MessageResponse(
        message=f"Grafo actualizado: {stats['indexed']} elementos, {stats['nodes']} nodos, {stats['edges']} relaciones"
    )


@app.post("/api/graph/query", response_model=GraphResponse)
def query_graph(payload: GraphQueryRequest) -> GraphResponse:
    return GraphResponse(
        answer=graph_service.query_graph(payload.question, payload.llm_model, payload.hops)
    )
