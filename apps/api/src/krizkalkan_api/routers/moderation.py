"""Moderatör triyajı, itiraz akışı ve denetim kaydı."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from krizkalkan_core.schemas import (
    Appeal,
    AuditEntry,
    CreateAppealRequest,
    ModerationDecision,
    ModerationItem,
)
from krizkalkan_core.taxonomy import Verdict

from krizkalkan_api.store import store

router = APIRouter(prefix="/api/moderation", tags=["moderasyon"])


@router.get("/queue", response_model=list[ModerationItem])
def queue() -> list[ModerationItem]:
    """Triyaj kuyruğu — yayılım hızına göre sıralı (Akış 4)."""
    items: list[ModerationItem] = []
    for post in store.list_posts():
        analysis = post.analysis
        if analysis is None:
            continue
        # Korunan yardım çağrıları kuyruğa hiç girmez.
        if analysis.intervention.protected_by_rule_zero:
            continue
        if analysis.verdict in (Verdict.TEMIZ, Verdict.YETERSIZ_KANIT):
            continue
        appeal = store.appeal_for_post(post.id)
        items.append(
            ModerationItem(
                post_id=post.id,
                analysis_id=analysis.analysis_id,
                verdict=analysis.verdict,
                confidence=analysis.confidence,
                spread_per_minute=store.spread.get(post.id, 0.0),
                body_preview=post.body[:160],
                created_at=post.created_at,
                appeal_id=appeal.id if appeal else None,
            )
        )
    return sorted(items, key=lambda i: i.spread_per_minute, reverse=True)


@router.post("/decide", response_model=AuditEntry)
def decide(payload: ModerationDecision) -> AuditEntry:
    """Moderatör kararı. Karar insanındır; sistem yalnızca kaydeder."""
    post = store.get_post(payload.post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Gönderi bulunamadı")

    labels = {
        "onayla": "moderatör_onayladı",
        "baglam_ekle": "moderatör_bağlam_ekledi",
        "mercie_bildir": "yetkili_mercie_bildirildi",
    }
    return store.log(
        labels[payload.decision],
        actor="moderatör",
        post_id=payload.post_id,
        detail=payload.note or "Not girilmedi. İçerik kaldırılmadı.",
    )


@router.get("/appeals", response_model=list[Appeal])
def appeals() -> list[Appeal]:
    return store.list_appeals()


@router.post("/appeals", response_model=Appeal, status_code=201)
def create_appeal(payload: CreateAppealRequest) -> Appeal:
    """Kullanıcı itirazı (Akış 3)."""
    post = store.get_post(payload.post_id)
    if post is None or post.analysis is None:
        raise HTTPException(status_code=404, detail="Gönderi veya analiz bulunamadı")

    appeal = store.add_appeal(
        post_id=payload.post_id,
        analysis_id=post.analysis.analysis_id,
        reason=payload.reason,
        note=payload.note,
    )
    store.log(
        "itiraz_alındı",
        actor="kullanıcı",
        post_id=payload.post_id,
        detail=f"{payload.reason} · moderatör kuyruğuna eklendi",
    )
    return appeal


@router.post("/appeals/{appeal_id}/resolve", response_model=Appeal)
def resolve_appeal(appeal_id: str, accepted: bool, note: str | None = None) -> Appeal:
    """İtirazı sonuçlandırır; karar aktif öğrenmeye beslenir."""
    appeal = store.resolve_appeal(appeal_id, accepted, note)
    if appeal is None:
        raise HTTPException(status_code=404, detail="İtiraz bulunamadı")
    store.log(
        "itiraz_sonuçlandı",
        actor="moderatör",
        post_id=appeal.post_id,
        detail=f"{'kabul' if accepted else 'ret'} · aktif öğrenmeye beslendi",
    )
    return appeal


@router.get("/audit", response_model=list[AuditEntry])
def audit(limit: int = 50) -> list[AuditEntry]:
    """Denetim kaydı — her politika kararı buraya yazılır."""
    return store.list_audit(limit)
