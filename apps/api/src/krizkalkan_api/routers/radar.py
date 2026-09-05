"""M8 — Kriz Radar uç noktası."""

from __future__ import annotations

from fastapi import APIRouter
from krizkalkan_core.radar import build_snapshot
from krizkalkan_core.schemas import RadarSnapshot

from krizkalkan_api.store import store

router = APIRouter(prefix="/api/radar", tags=["kriz radar"])


@router.get("", response_model=RadarSnapshot)
def snapshot(window_minutes: int = 30) -> RadarSnapshot:
    """Kurumsal karar destek panelinin görüntüsü (Akış 5)."""
    analyses = [p.analysis for p in store.list_posts() if p.analysis is not None]
    protected = sum(1 for a in analyses if a.intervention.protected_by_rule_zero)
    return build_snapshot(analyses, window_minutes=window_minutes, protected_help_calls=protected)
