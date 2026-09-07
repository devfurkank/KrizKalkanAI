"""Çalışma anı metrik toplayıcı.

Rapor 4.1'de tanımlanan ölçülebilir etkinlik göstergelerini üretir: gecikme
yüzdelikleri, verim, önbellek isabet oranı, insan incelemesine yönlendirme
oranı ve Kural 0 koruma sayacı.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class MetricsCollector:
    """Süreç ömrü boyunca biriken sayaçlar."""

    started_at: float = field(default_factory=time.monotonic)
    latencies_ms: list[float] = field(default_factory=list)
    total_analyses: int = 0
    cache_hits: int = 0
    human_reviews: int = 0
    protected_help_calls: int = 0
    #: Sistem içerik silemez; sayaç kanıt olarak tutulur ve hep 0 kalır.
    removed_content: int = 0

    def record(
        self,
        latency_ms: float,
        *,
        cache_hit: bool = False,
        human_review: bool = False,
        rule_zero: bool = False,
    ) -> None:
        self.total_analyses += 1
        self.latencies_ms.append(latency_ms)
        if cache_hit:
            self.cache_hits += 1
        if human_review:
            self.human_reviews += 1
        if rule_zero:
            self.protected_help_calls += 1

    # ── Türetilmiş göstergeler ──

    def _percentile(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        ordered = sorted(self.latencies_ms)
        idx = min(len(ordered) - 1, round((len(ordered) - 1) * p))
        return round(ordered[idx], 2)

    @property
    def p50_ms(self) -> float:
        return self._percentile(0.50)

    @property
    def p95_ms(self) -> float:
        return self._percentile(0.95)

    @property
    def cache_hit_rate(self) -> float:
        if not self.total_analyses:
            return 0.0
        return round(self.cache_hits / self.total_analyses, 4)

    @property
    def human_review_rate(self) -> float:
        if not self.total_analyses:
            return 0.0
        return round(self.human_reviews / self.total_analyses, 4)

    @property
    def uptime_seconds(self) -> float:
        return round(time.monotonic() - self.started_at, 1)

    @property
    def throughput_per_minute(self) -> float:
        """Ortalama gecikmeden türetilen teorik verim (tek işçi)."""
        if not self.latencies_ms:
            return 0.0
        mean_ms = sum(self.latencies_ms) / len(self.latencies_ms)
        if mean_ms <= 0:
            return 0.0
        return round(60_000 / mean_ms, 1)

    def reset(self) -> None:
        self.latencies_ms.clear()
        self.total_analyses = 0
        self.cache_hits = 0
        self.human_reviews = 0
        self.protected_help_calls = 0
