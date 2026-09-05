"""Analiz boru hattı — modüllerin orkestrasyonu.

Zincir (rapor 1.2):

    içerik alımı → modalite ayrıştırma → modüllerin çalıştırılması →
    sinyallerin kalibrasyonu → yorumlanabilir sınıflandırma → politika motoru

İki tasarım tercihi burada uygulanır:

* **Köken önceliği** — M1 önce çalışır; kesin kanıt üretirse pahalı sentetik
  medya analizi hiç çalıştırılmaz.
* **Kademeli işlem** — ucuz modüller (M1, M3) önce; M2 ve M4 yalnızca gerektiğinde.

Ayrıca algısal karma tabanlı bir önbellek katmanı vardır: daha önce analiz
edilmiş içerik yeniden yüklendiğinde boru hattı baştan çalıştırılmaz
(rapor 4.1 · maliyet verimliliği).
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from krizkalkan_core.fusion import engine as fusion
from krizkalkan_core.knowledge import engine as knowledge
from krizkalkan_core.metrics import MetricsCollector
from krizkalkan_core.multimodal import engine as multimodal
from krizkalkan_core.policy import engine as policy
from krizkalkan_core.provenance import engine as provenance
from krizkalkan_core.provenance.hashing import perceptual_hash
from krizkalkan_core.schemas import AnalysisResult, Modality, ModuleCode, Signal
from krizkalkan_core.synthetic import engine as synthetic
from krizkalkan_core.taxonomy import HELP_CALL_THRESHOLD, InterventionLevel, Verdict
from krizkalkan_core.text import engine as text_engine

#: Köken eşleşmesi bu güvenin üzerindeyse pahalı modüller atlanır.
PROVENANCE_CONCLUSIVE = 0.88


class AnalysisPipeline:
    """Durumsuz analiz motoru + süreç ömürlü önbellek ve metrikler."""

    def __init__(self) -> None:
        self._cache: dict[str, AnalysisResult] = {}
        self.metrics = MetricsCollector()

    # ────────────────────────── yardımcılar ──────────────────────────

    @staticmethod
    def _modalities(body: str, media_kind: str, has_audio: bool) -> list[Modality]:
        mods: list[Modality] = []
        if body.strip():
            mods.append("metin")
        if media_kind == "image":
            mods.append("görsel")
        elif media_kind in ("video", "grid"):
            mods.append("video")
        if has_audio:
            mods.append("ses")
        return mods

    @staticmethod
    def _cache_key(body: str, media_kind: str, fingerprint: str | None) -> str:
        return f"{perceptual_hash(f'{body}|{media_kind}|{fingerprint or ""}'):016x}"

    # ────────────────────────── ana akış ──────────────────────────

    def analyse(
        self,
        *,
        body: str = "",
        media_kind: str = "yok",
        media_fingerprint: str | None = None,
        duration_seconds: float | None = None,
        content_id: str | None = None,
        spread_per_minute: float = 0.0,
    ) -> AnalysisResult:
        started = time.perf_counter()
        content_id = content_id or f"c_{uuid.uuid4().hex[:10]}"
        cache_key = self._cache_key(body, media_kind, media_fingerprint)

        # ── Önbellek ──
        if cached := self._cache.get(cache_key):
            latency = (time.perf_counter() - started) * 1000
            self.metrics.record(
                latency,
                cache_hit=True,
                human_review=cached.intervention.level is InterventionLevel.HUMAN_REVIEW,
                rule_zero=cached.intervention.protected_by_rule_zero,
            )
            return cached.model_copy(
                update={
                    "analysis_id": f"a_{uuid.uuid4().hex[:10]}",
                    "content_id": content_id,
                    "cache_hit": True,
                    "latency_ms": round(latency, 2),
                    "created_at": datetime.now(UTC),
                }
            )

        has_audio = media_kind in ("video", "grid") and (
            media_fingerprint is not None and "sessiz" not in media_fingerprint.casefold()
        )
        signals: list[Signal] = []
        modules_run: list[ModuleCode] = []
        modules_skipped: list[ModuleCode] = []
        skip_reason: str | None = None

        # ── M3: Türkçe kriz metin motoru (ucuz, önce çalışır) ──
        text_analysis = None
        if body.strip():
            text_analysis, text_signals = text_engine.analyse(body)
            signals.extend(text_signals)
            modules_run.append("M3")
        else:
            modules_skipped.append("M3")

        claims = text_analysis.claims if text_analysis else []
        claimed_location = next((c.location for c in claims if c.location), None)

        # ── M1: Köken (ucuz, kesin kanıt üretebilir) ──
        prov_match, prov_signals = provenance.analyse(media_fingerprint, claimed_location)
        signals.extend(prov_signals)
        modules_run.append("M1")

        provenance_conclusive = bool(
            prov_match and prov_match.matched and prov_match.similarity >= PROVENANCE_CONCLUSIVE
        )

        # ── M5: Bilgi havuzu (ucuz) ──
        know_match, know_signals = knowledge.analyse(claims)
        signals.extend(know_signals)
        modules_run.append("M5")

        # ── M2 / M4: pahalı modüller — kademeli işlem ──
        if provenance_conclusive:
            modules_skipped.extend(["M2", "M4"])
            skip_reason = (
                "Köken eşleşmesi kesin sonuç ürettiği için pahalı sentetik medya ve "
                "çok modlu analiz çalıştırılmadı (kademeli işlem)."
            )
        elif media_kind == "yok":
            modules_skipped.extend(["M2", "M4"])
            skip_reason = "İçerikte medya bulunmadığı için medya modülleri atlandı."
        else:
            signals.extend(multimodal.analyse(media_fingerprint, media_kind, has_audio, claims))
            modules_run.append("M2")
            signals.extend(synthetic.analyse(media_fingerprint, media_kind, has_audio))
            modules_run.append("M4")

        # ── M6: kalibrasyon + füzyon ──
        fusion.apply_calibration(signals)
        verdict, confidence, contributing = fusion.fuse(
            signals, prov_match, text_analysis, know_match
        )
        modules_run.append("M6")

        # ── M7: politika ──
        help_score = text_analysis.help_call_score if text_analysis else 0.0
        intervention = policy.decide(
            verdict, confidence, help_score, spread_per_minute=spread_per_minute
        )
        modules_run.append("M7")

        # Kural 0 devredeyse sınıf korunur ama hiçbir müdahale uygulanmaz;
        # kullanıcıya gösterilen sınıf da nötrlenir.
        if intervention.protected_by_rule_zero:
            verdict = Verdict.TEMIZ
            confidence = max(confidence, help_score)

        latency = (time.perf_counter() - started) * 1000
        result = AnalysisResult(
            analysis_id=f"a_{uuid.uuid4().hex[:10]}",
            content_id=content_id,
            verdict=verdict,
            verdict_meaning=fusion.describe(verdict),
            confidence=round(min(max(confidence, 0.0), 1.0), 4),
            confidence_label=fusion.confidence_label(confidence),  # type: ignore[arg-type]
            intervention=intervention,
            signals=contributing if contributing else [s for s in signals if not s.abstained],
            provenance=prov_match,
            text=text_analysis,
            knowledge=know_match,
            modalities=self._modalities(body, media_kind, has_audio),
            modules_run=modules_run,
            modules_skipped=modules_skipped,
            skip_reason=skip_reason,
            latency_ms=round(latency, 2),
            cache_hit=False,
            created_at=datetime.now(UTC),
        )

        # Çekinilen sinyaller de kanıt panelinde gösterilir: sistemin neyi
        # bilmediği, ne bildiği kadar önemlidir (rapor 2.2 · Y2).
        abstained = [s for s in signals if s.abstained]
        seen = {s.key for s in result.signals}
        result.signals.extend(s for s in abstained if s.key not in seen)

        self._cache[cache_key] = result
        self.metrics.record(
            latency,
            cache_hit=False,
            human_review=intervention.level is InterventionLevel.HUMAN_REVIEW,
            rule_zero=intervention.protected_by_rule_zero,
        )
        return result

    # ────────────────────────── yönetim ──────────────────────────

    @property
    def help_call_threshold(self) -> float:
        return HELP_CALL_THRESHOLD

    def clear_cache(self) -> None:
        self._cache.clear()


#: Uygulama genelinde paylaşılan tek örnek.
pipeline = AnalysisPipeline()
