from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class WeakTopic(BaseModel):
    tema: str
    fallos: int
    intentos: int


class RankSummary(BaseModel):
    rank: str
    best_level: str
    score: int
    by_level: dict[str, dict[str, int]]


class WordCard(BaseModel):
    id: int
    lemma: str
    word: str
    pos: str
    topic: str
    translation: str
    example_en: str
    example_es: str
    ease: float
    interval: int
    reps: int
    lapses: int
    due: date | None
    status: str


class ReviewPayload(BaseModel):
    word_id: int
    rating: int = Field(ge=1, le=4)


class GrammarQuizItem(BaseModel):
    id: int
    title: str
    prompt: str
    options: list[str]
    answer_index: int
    level: str
    description: str


class GrammarReviewPayload(BaseModel):
    item_id: int
    rating: int = Field(ge=1, le=4)
    correct: bool


class ContentItemSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    record_key: str
    source: str
    kind: str
    language: str
    asr_model: str
    source_path: str
    created_at: datetime
    text_preview: str
    text_en_length: int
    text_en: str
    text_es: str
    media_url: str = ""
    vtt_url: str = ""
    source_metadata: dict = Field(default_factory=dict)


class ContentProcessRequest(BaseModel):
    topic: str = ""
    import_vocab: bool = True
    import_grammar: bool = True
    llm_model: str = ""


class GraphIndexRequest(BaseModel):
    content_ids: list[int]
    llm_model: str = ""


class GraphQueryRequest(BaseModel):
    question: str
    llm_model: str = ""
    hops: int = Field(default=1, ge=1, le=3)


class GraphResponse(BaseModel):
    answer: str


class GraphStats(BaseModel):
    nodes: int
    edges: int


class DashboardSummary(BaseModel):
    word_counts: dict[str, int]
    grammar_counts: dict[str, int]
    rank: RankSummary
    weak_topics: list[WeakTopic]
    weak_grammar_topics: list[WeakTopic]
    graph: GraphStats


class ModelCatalogItem(BaseModel):
    id: str
    label: str
    vram_gb: int
    installed: bool


class AsrCatalogItem(BaseModel):
    id: str
    label: str
    backend: str


class ModelCatalogResponse(BaseModel):
    preferred_llm: str
    installed_llms: list[str]
    catalog: list[ModelCatalogItem]
    asr_catalog: list[AsrCatalogItem]


class MediaAssetResponse(BaseModel):
    asset_id: str
    source_name: str
    media_kind: str
    media_url: str
    metadata: dict
    last_asr_key: str = ""
    last_vtt_url: str = ""
    transcript_text: str = ""
    segments: list[dict] = Field(default_factory=list)


class MediaUploadResponse(BaseModel):
    message: str
    asset: MediaAssetResponse


class ExistingMediaItem(BaseModel):
    media_id: str
    source_name: str
    media_kind: str
    category: str
    media_url: str
    paired_video_name: str = ""
    size_bytes: int
    created_at: datetime
    transcript_saved: bool = False


class ExistingMediaSelectRequest(BaseModel):
    media_id: str


class YouTubeDownloadRequest(BaseModel):
    url: str
    audio_only: bool = False


class MediaTranscribeRequest(BaseModel):
    asset_id: str
    asr_key: str
    language: str = "en"


class MediaSaveRequest(BaseModel):
    asset_id: str
    llm_model: str = ""
    translate: bool = True


class MediaPreviewRequest(BaseModel):
    asset_id: str
    llm_model: str = ""
    translate: bool = True


class MediaSegmentUpdate(BaseModel):
    index: int
    text_en: str = ""
    text_es: str = ""


class MediaCorrectionsRequest(BaseModel):
    asset_id: str
    segments: list[MediaSegmentUpdate]


class DocumentImportResponse(BaseModel):
    message: str


class MessageResponse(BaseModel):
    message: str
