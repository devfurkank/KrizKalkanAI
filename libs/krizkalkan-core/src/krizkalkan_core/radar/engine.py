"""M8 — Kriz Radar kümeleme ve yayılım analizi.

Aynı iddianın farklı ifadelerini tek kümede toplar, yayılım hızını ve ivmesini
hesaplar. Panelin iki sayacı her zaman görünür kalır: Kural 0 ile korunan
yardım çağrısı sayısı ve kaldırılan içerik sayısı (her zaman sıfır).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from krizkalkan_core.schemas import AnalysisResult, ClaimCluster, RadarSnapshot
from krizkalkan_core.taxonomy import ClaimType, KnowledgeVerdict, Verdict
from krizkalkan_core.text.lexicon import normalize

#: Kümelemede kullanılan anahtar terim eşiği — bu orandan fazla örtüşen
#: iddialar aynı kümeye düşer. Gerçek sistemde cümle gömme + HDBSCAN.
CLUSTER_OVERLAP = 0.5

#: Kümeleme dışı bırakılan çok genel terimler.
_STOPWORDS = {
    "bir",
    "bu",
    "su",
    "ve",
    "ile",
    "icin",
    "gibi",
    "daha",
    "cok",
    "var",
    "yok",
    "olarak",
    "sonra",
    "once",
    "kadar",
    "ama",
    "ancak",
    "de",
    "da",
    "ki",
    "mi",
}


def _tokens(text: str) -> set[str]:
    return {w for w in normalize(text).split() if len(w) > 2 and w not in _STOPWORDS}


def _similar(a: set[str], b: set[str]) -> bool:
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) >= CLUSTER_OVERLAP


def build_snapshot(
    analyses: list[AnalysisResult],
    *,
    window_minutes: int = 30,
    protected_help_calls: int = 0,
) -> RadarSnapshot:
    """Analiz geçmişinden kurumsal panel görüntüsü üretir."""
    labelled = [
        a
        for a in analyses
        if a.verdict not in (Verdict.TEMIZ, Verdict.YETERSIZ_KANIT)
        and not a.intervention.protected_by_rule_zero
    ]

    # ── İddia kümeleme ──
    buckets: list[dict] = []
    for analysis in labelled:
        if not analysis.text or not analysis.text.claims:
            continue
        claim = next(
            (c for c in analysis.text.claims if c.claim_type is not ClaimType.BELIRSIZ),
            analysis.text.claims[0],
        )
        tokens = _tokens(claim.text)
        if not tokens:
            continue

        for bucket in buckets:
            if _similar(tokens, bucket["tokens"]):
                bucket["count"] += 1
                bucket["tokens"] |= tokens
                bucket["analyses"].append(analysis)
                if claim.location:
                    bucket["locations"].add(claim.location)
                break
        else:
            buckets.append(
                {
                    "claim": claim.text,
                    "tokens": tokens,
                    "count": 1,
                    "analyses": [analysis],
                    "locations": {claim.location} if claim.location else set(),
                }
            )

    clusters: list[ClaimCluster] = []
    for i, bucket in enumerate(sorted(buckets, key=lambda b: -b["count"])):
        members: list[AnalysisResult] = bucket["analyses"]
        spread = round(bucket["count"] / max(window_minutes, 1) * 60, 1)
        # İvme: kümenin son yarıdaki payı, ilk yarıya oranı.
        half = max(len(members) // 2, 1)
        acceleration = round(len(members[half:]) / half, 2) if len(members) > 1 else 1.0

        verdict_counts: dict[Verdict, int] = defaultdict(int)
        for m in members:
            verdict_counts[m.verdict] += 1
        dominant = max(verdict_counts, key=lambda k: verdict_counts[k])

        official = KnowledgeVerdict.KAYNAK_SESSIZ
        for m in members:
            if m.knowledge and m.knowledge.verdict is not KnowledgeVerdict.KAYNAK_SESSIZ:
                official = m.knowledge.verdict
                break

        clusters.append(
            ClaimCluster(
                id=f"kume_{i + 1:02d}",
                claim=bucket["claim"],
                post_count=bucket["count"],
                spread_per_minute=spread,
                acceleration=acceleration,
                verdict=dominant,
                official_status=official,
                locations=sorted(bucket["locations"]),
            )
        )

    return RadarSnapshot(
        window_minutes=window_minutes,
        analyzed_count=len(analyses),
        labelled_count=len(labelled),
        high_confidence_synthetic=sum(
            1
            for a in labelled
            if a.verdict in (Verdict.SENTETIK_MEDYA, Verdict.MANIPULE_MEDYA)
            and a.confidence >= 0.70
        ),
        wrong_context=sum(1 for a in labelled if a.verdict is Verdict.YANLIS_BAGLAM),
        unverified=sum(1 for a in labelled if a.verdict is Verdict.DOGRULANMAMIS_IDDIA),
        protected_help_calls=protected_help_calls,
        removed_content=0,
        clusters=clusters[:8],
        generated_at=datetime.now(UTC),
    )
