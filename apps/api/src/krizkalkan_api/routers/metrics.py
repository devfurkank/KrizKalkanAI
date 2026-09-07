"""Sistem metrikleri (rapor 4.1 · ölçülebilir etkinlik göstergeleri)."""

from __future__ import annotations

from fastapi import APIRouter
from krizkalkan_core.pipeline import pipeline
from krizkalkan_core.schemas import SystemMetrics

router = APIRouter(prefix="/api/metrics", tags=["metrikler"])


@router.get("", response_model=SystemMetrics)
def metrics() -> SystemMetrics:
    m = pipeline.metrics
    return SystemMetrics(
        total_analyses=m.total_analyses,
        cache_hits=m.cache_hits,
        cache_hit_rate=m.cache_hit_rate,
        latency_p50_ms=m.p50_ms,
        latency_p95_ms=m.p95_ms,
        throughput_per_minute=m.throughput_per_minute,
        human_review_rate=m.human_review_rate,
        protected_help_calls=m.protected_help_calls,
        removed_content=0,
        uptime_seconds=m.uptime_seconds,
    )
