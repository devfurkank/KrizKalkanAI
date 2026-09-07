"""Bellek içi veri deposu.

Demo ve geliştirme için varsayılan depodur; PostgreSQL bağlantısı
yapılandırıldığında aynı arayüz SQLAlchemy repository'siyle değiştirilir
(rapor 3.1 · veritabanı katmanı). Süreç ömrü boyunca yaşar, dış bağımlılığı
yoktur — bu sayede sunum ortamında tek komutla ayağa kalkar.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from threading import RLock

from krizkalkan_core.schemas import (
    AnalysisResult,
    Appeal,
    AuditEntry,
    Post,
)


def _now() -> datetime:
    return datetime.now(UTC)


class Store:
    """İş parçacığı güvenli, süreç ömürlü depo."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.posts: dict[str, Post] = {}
        self.analyses: dict[str, AnalysisResult] = {}
        self.appeals: dict[str, Appeal] = {}
        self.audit: list[AuditEntry] = []
        #: Gönderi kimliği → dakikadaki paylaşım hızı (Kriz Radar ve Seviye 4 için).
        self.spread: dict[str, float] = {}

    # ────────────────────────── gönderiler ──────────────────────────

    def add_post(self, post: Post, spread_per_minute: float = 0.0) -> Post:
        with self._lock:
            self.posts[post.id] = post
            self.spread[post.id] = spread_per_minute
            if post.analysis:
                self.analyses[post.analysis.analysis_id] = post.analysis
            return post

    def list_posts(self) -> list[Post]:
        with self._lock:
            return sorted(self.posts.values(), key=lambda p: p.created_at, reverse=True)

    def get_post(self, post_id: str) -> Post | None:
        with self._lock:
            return self.posts.get(post_id)

    # ────────────────────────── analizler ──────────────────────────

    def add_analysis(self, analysis: AnalysisResult) -> AnalysisResult:
        with self._lock:
            self.analyses[analysis.analysis_id] = analysis
            return analysis

    def get_analysis(self, analysis_id: str) -> AnalysisResult | None:
        with self._lock:
            return self.analyses.get(analysis_id)

    def list_analyses(self) -> list[AnalysisResult]:
        with self._lock:
            return list(self.analyses.values())

    # ────────────────────────── itirazlar ──────────────────────────

    def add_appeal(self, post_id: str, analysis_id: str, reason: str, note: str | None) -> Appeal:
        with self._lock:
            appeal = Appeal(
                id=f"itiraz_{uuid.uuid4().hex[:8]}",
                post_id=post_id,
                analysis_id=analysis_id,
                reason=reason,
                note=note,
                created_at=_now(),
            )
            self.appeals[appeal.id] = appeal
            return appeal

    def list_appeals(self) -> list[Appeal]:
        with self._lock:
            return sorted(self.appeals.values(), key=lambda a: a.created_at, reverse=True)

    def resolve_appeal(self, appeal_id: str, accepted: bool, note: str | None) -> Appeal | None:
        with self._lock:
            appeal = self.appeals.get(appeal_id)
            if appeal is None:
                return None
            appeal.status = "kabul" if accepted else "ret"
            appeal.resolved_at = _now()
            appeal.moderator_note = note
            return appeal

    def appeal_for_post(self, post_id: str) -> Appeal | None:
        with self._lock:
            return next(
                (
                    a
                    for a in self.appeals.values()
                    if a.post_id == post_id and a.status == "bekliyor"
                ),
                None,
            )

    # ────────────────────────── denetim kaydı ──────────────────────────

    def log(
        self,
        action: str,
        *,
        actor: str = "sistem",
        post_id: str | None = None,
        detail: str | None = None,
    ) -> AuditEntry:
        with self._lock:
            entry = AuditEntry(
                id=f"log_{uuid.uuid4().hex[:8]}",
                at=_now(),
                actor=actor,  # type: ignore[arg-type]
                action=action,
                post_id=post_id,
                detail=detail,
            )
            self.audit.append(entry)
            return entry

    def list_audit(self, limit: int = 100) -> list[AuditEntry]:
        with self._lock:
            return list(reversed(self.audit[-limit:]))

    # ────────────────────────── bakım ──────────────────────────

    def clear(self) -> None:
        with self._lock:
            self.posts.clear()
            self.analyses.clear()
            self.appeals.clear()
            self.audit.clear()
            self.spread.clear()


#: Uygulama genelinde paylaşılan tek depo.
store = Store()
