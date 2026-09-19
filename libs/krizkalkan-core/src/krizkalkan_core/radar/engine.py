"""M8 — Kriz Radar kümeleme ve yayılım analizi.

Aynı iddianın farklı ifadelerini tek kümede toplar, yayılım hızını ve ivmesini
hesaplar. Panelin iki sayacı her zaman görünür kalır: Kural 0 ile korunan
yardım çağrısı sayısı ve kaldırılan içerik sayısı (her zaman sıfır).
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime

from krizkalkan_core.schemas import AnalysisResult, ClaimCluster, RadarSnapshot
from krizkalkan_core.taxonomy import ClaimType, KnowledgeVerdict, Verdict
from krizkalkan_core.text.lexicon import normalize

logger = logging.getLogger(__name__)

#: Anahtar terim örtüşme eşiği — gömme modeli yokken kullanılan yedek yol.
CLUSTER_OVERLAP = 0.5

#: HDBSCAN'in bir küme sayması için gereken asgari üye sayısı.
ASGARI_KUME = 2

#: Gömme tabanlı kümeleme için gereken asgari iddia sayısı. Altında HDBSCAN
#: her şeyi gürültü sayar ve sözlük yolu daha iyi davranır.
ASGARI_IDDIA = 6

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


def _token_kumeleri(metinler: list[str]) -> list[int]:
    """Anahtar terim örtüşmesiyle açgözlü kümeleme — yedek yol.

    Aynı iddianın farklı kelimelerle ifade edilmiş hâllerini yakalayamaz;
    gömme modeli yüklüyse `_gomme_kumeleri` tercih edilir.
    """
    kumeler: list[set[str]] = []
    etiketler: list[int] = []
    for metin in metinler:
        tokens = _tokens(metin)
        for i, mevcut in enumerate(kumeler):
            if _similar(tokens, mevcut):
                mevcut |= tokens
                etiketler.append(i)
                break
        else:
            kumeler.append(tokens)
            etiketler.append(len(kumeler) - 1)
    return etiketler


def _gomme_kumeleri(metinler: list[str], arayici) -> list[int] | None:
    """Cümle gömmesi + HDBSCAN.

    Aynı iddianın farklı ifadelerini kelime örtüşmesine bakmadan bir araya
    getirir — kriz dönemlerinde aynı yalan onlarca farklı cümleyle dolaştığı
    için asıl ihtiyaç budur.

    HDBSCAN'in gürültü olarak işaretlediği (-1) iddialar tek üyeli kümelere
    dönüştürülür: bir kez görülmüş iddia da bir iddiadır, atılamaz.
    """
    if len(metinler) < ASGARI_IDDIA:
        return None
    try:
        import numpy as np
        from sklearn.cluster import HDBSCAN
    except ImportError:
        logger.info("scikit-learn yok; sözlük tabanlı kümeleme kullanılıyor")
        return None

    try:
        gomme = np.asarray(arayici.kodla(metinler, sorgu=True))
    except Exception:  # kodlayıcı hatası panelin tamamını düşürmemeli
        logger.warning("Gömme hesaplanamadı; sözlük tabanlı kümelemeye düşülüyor")
        return None

    # copy=True bilinçli: girdi dizisi çağıranın olduğu için yerinde
    # değiştirilmemeli. (sklearn 1.10'da varsayılan olacak; şimdi açıkça verilir.)
    ham = HDBSCAN(min_cluster_size=ASGARI_KUME, metric="euclidean", copy=True).fit_predict(gomme)

    # Gürültü noktalarına yeni küme numaraları ver.
    etiketler: list[int] = []
    sonraki = int(ham.max()) + 1 if len(ham) and ham.max() >= 0 else 0
    for etiket in ham:
        if etiket < 0:
            etiketler.append(sonraki)
            sonraki += 1
        else:
            etiketler.append(int(etiket))
    return etiketler


def kumele(metinler: list[str]) -> tuple[list[int], str]:
    """İddia metinlerini kümeler; (etiketler, kullanılan yöntem) döndürür."""
    from krizkalkan_core.knowledge import retriever

    arayici = retriever.get()
    if arayici is not None and (etiketler := _gomme_kumeleri(metinler, arayici)) is not None:
        return etiketler, "gömme + HDBSCAN"
    return _token_kumeleri(metinler), "anahtar terim örtüşmesi"


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
    adaylar: list[tuple[str, str | None, AnalysisResult]] = []
    for analysis in labelled:
        if not analysis.text or not analysis.text.claims:
            continue
        claim = next(
            (c for c in analysis.text.claims if c.claim_type is not ClaimType.BELIRSIZ),
            analysis.text.claims[0],
        )
        if _tokens(claim.text):
            adaylar.append((claim.text, claim.location, analysis))

    etiketler, _yontem = kumele([m for m, _, _ in adaylar]) if adaylar else ([], "")

    gruplar: dict[int, dict] = {}
    for (metin, konum, analysis), etiket in zip(adaylar, etiketler, strict=True):
        grup = gruplar.setdefault(
            etiket, {"claim": metin, "count": 0, "analyses": [], "locations": set()}
        )
        grup["count"] += 1
        grup["analyses"].append(analysis)
        if konum:
            grup["locations"].add(konum)
    buckets = list(gruplar.values())

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
