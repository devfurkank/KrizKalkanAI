"""Paylaşılan Pydantic şemaları.

TypeScript eşleniği: apps/web/src/lib/types.ts
Bu şemalar API sözleşmesidir; arayüz doğrudan bunlara göre çizer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from krizkalkan_core.taxonomy import (
    Certainty,
    ClaimType,
    InterventionLevel,
    KnowledgeVerdict,
    ManipulationLabel,
    Verdict,
)

Modality = Literal["metin", "görsel", "video", "ses"]
ModuleCode = Literal["M1", "M2", "M3", "M4", "M5", "M6", "M7"]


# ─────────────────────────── Kanıt ───────────────────────────


class Evidence(BaseModel):
    """Bir sinyalin işaret ettiği somut kanıt.

    Açıklama skordan değil, bu nesnelerden üretilir (rapor 2.2 · Y5).
    """

    kind: Literal["kare", "zaman_araligi", "metin_araligi", "kayit", "ustveri"]
    label: str = Field(description="Kullanıcıya gösterilen kısa açıklama")
    locator: str | None = Field(
        default=None, description="Kare no, 00:00–00:14, karakter aralığı vb."
    )
    detail: str | None = None
    url: str | None = None


class Signal(BaseModel):
    """Tek bir modül sinyali.

    `abstained` True ise skor anlamlı değildir; modül karar vermeyi reddetmiştir.
    """

    module: ModuleCode
    key: str
    label: str
    score: float = Field(ge=0.0, le=1.0, description="Kalibre edilmiş olasılık")
    raw_score: float = Field(ge=0.0, le=1.0, description="Kalibrasyon öncesi ham skor")
    abstained: bool = False
    abstain_reason: str | None = None
    evidence: list[Evidence] = Field(default_factory=list)


# ─────────────────────────── Modül çıktıları ───────────────────────────


class ProvenanceMatch(BaseModel):
    """M1 — köken eşleşmesi."""

    matched: bool
    similarity: float = 0.0
    first_published: str | None = None
    source: str | None = None
    original_event: str | None = None
    original_location: str | None = None
    matched_frame: str | None = None
    corpus_id: str | None = None


class ExtractedClaim(BaseModel):
    """Görev A — iddia çıkarımı."""

    claim_type: ClaimType
    text: str
    location: str | None = None
    magnitude: str | None = None
    time_expr: str | None = None
    alleged_source: str | None = None
    certainty: Certainty


class TextAnalysis(BaseModel):
    """M3 çıktısı."""

    claims: list[ExtractedClaim] = Field(default_factory=list)
    labels: dict[ManipulationLabel, float] = Field(default_factory=dict)
    dominant_label: ManipulationLabel = ManipulationLabel.NOTR_BILGILENDIRME
    help_call_score: float = 0.0
    #: Metin bir iddiayı öne sürmüyor, yalanlıyor/düzeltiyorsa > 0.
    debunk_score: float = 0.0


class KnowledgeMatch(BaseModel):
    """M5 çıktısı."""

    verdict: KnowledgeVerdict
    matched_claim: str | None = None
    official_statement: str | None = None
    source: str | None = None
    published_at: str | None = None
    similarity: float = 0.0


# ─────────────────────────── Politika ───────────────────────────


class Intervention(BaseModel):
    """M7 politika motoru kararı."""

    level: InterventionLevel
    label: str
    automatic: bool
    headline: str = Field(description="Kullanıcıya gösterilen tek cümlelik özet")
    detail: str | None = None
    #: Kural 0 devreye girdiyse True — diğer tüm sinyaller geçersiz kılınmıştır.
    protected_by_rule_zero: bool = False
    #: Sistem hiçbir koşulda içerik silmez; bu alan her zaman False'tur.
    content_removed: bool = False


# ─────────────────────────── Analiz ───────────────────────────


class AnalysisResult(BaseModel):
    """Uçtan uca analiz çıktısı — arayüzün analiz kartını çizdiği nesne."""

    analysis_id: str
    content_id: str
    verdict: Verdict
    verdict_meaning: str
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_label: Literal["düşük", "orta", "yüksek"]
    intervention: Intervention

    signals: list[Signal] = Field(default_factory=list)
    provenance: ProvenanceMatch | None = None
    text: TextAnalysis | None = None
    knowledge: KnowledgeMatch | None = None

    modalities: list[Modality] = Field(default_factory=list)
    modules_run: list[ModuleCode] = Field(default_factory=list)
    modules_skipped: list[ModuleCode] = Field(default_factory=list)
    skip_reason: str | None = None

    latency_ms: float = 0.0
    cache_hit: bool = False
    created_at: datetime


# ─────────────────────────── Platform ───────────────────────────


class Author(BaseModel):
    handle: str
    name: str
    verified: bool = False
    avatar: str = "from-slate-400 to-slate-600"


class MediaRef(BaseModel):
    kind: Literal["grid", "video", "image"]
    tiles: list[str] = Field(default_factory=list)
    poster: str | None = None
    label: str | None = None


class Post(BaseModel):
    id: str
    author: Author
    body: str
    created_at: datetime
    audience: Literal["herkes", "takipciler", "belirli"] = "herkes"
    media: MediaRef | None = None
    stats: dict[str, int] = Field(default_factory=dict)
    analysis: AnalysisResult | None = None
    #: Kullanıcı sürtünme ekranını görüp yine de paylaştıysa True.
    shared_despite_warning: bool = False


class CreatePostRequest(BaseModel):
    body: str = Field(max_length=10_000)
    audience: Literal["herkes", "takipciler", "belirli"] = "herkes"
    media_kind: Literal["yok", "grid", "video", "image"] = "yok"
    #: Demo senaryolarını tetiklemek için isteğe bağlı içerik parmak izi.
    media_fingerprint: str | None = None


class AnalyzeRequest(BaseModel):
    body: str = Field(default="", max_length=10_000)
    media_kind: Literal["yok", "grid", "video", "image"] = "yok"
    media_fingerprint: str | None = None
    duration_seconds: float | None = None


# ─────────────────────────── Moderasyon ───────────────────────────


class Appeal(BaseModel):
    id: str
    post_id: str
    analysis_id: str
    reason: str
    note: str | None = None
    status: Literal["bekliyor", "kabul", "ret"] = "bekliyor"
    created_at: datetime
    resolved_at: datetime | None = None
    moderator_note: str | None = None


class CreateAppealRequest(BaseModel):
    post_id: str
    reason: str
    note: str | None = None


class ModerationItem(BaseModel):
    """Moderatör triyaj kuyruğu satırı — yayılım hızına göre sıralanır."""

    post_id: str
    analysis_id: str
    verdict: Verdict
    confidence: float
    spread_per_minute: float
    body_preview: str
    created_at: datetime
    appeal_id: str | None = None


class ModerationDecision(BaseModel):
    post_id: str
    decision: Literal["onayla", "baglam_ekle", "mercie_bildir"]
    note: str | None = None


class AuditEntry(BaseModel):
    """Denetim kaydı — her politika kararı buraya yazılır."""

    id: str
    at: datetime
    actor: Literal["sistem", "moderatör", "kullanıcı"]
    action: str
    post_id: str | None = None
    detail: str | None = None


# ─────────────────────────── Kriz Radar (M8) ───────────────────────────


class ClaimCluster(BaseModel):
    id: str
    claim: str
    post_count: int
    spread_per_minute: float
    acceleration: float
    verdict: Verdict
    official_status: KnowledgeVerdict
    locations: list[str] = Field(default_factory=list)


class RadarSnapshot(BaseModel):
    window_minutes: int
    analyzed_count: int
    labelled_count: int
    high_confidence_synthetic: int
    wrong_context: int
    unverified: int
    #: Kural 0 ile korunan yardım çağrısı sayısı — panelde sürekli görünür.
    protected_help_calls: int
    #: Her zaman 0 — sistemin yetki sınırını hatırlatır.
    removed_content: int = 0
    clusters: list[ClaimCluster] = Field(default_factory=list)
    generated_at: datetime


# ─────────────────────────── Metrikler ───────────────────────────


class SystemMetrics(BaseModel):
    total_analyses: int
    cache_hits: int
    cache_hit_rate: float
    latency_p50_ms: float
    latency_p95_ms: float
    throughput_per_minute: float
    human_review_rate: float
    protected_help_calls: int
    removed_content: int = 0
    uptime_seconds: float
