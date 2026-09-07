"""M5 — Doğrulanmış kriz bilgi havuzu.

Çıkarılan iddia, havuz kayıtlarıyla doğal dil çıkarımı (NLI) yoluyla eşleştirilir
ve dört durumdan biri döndürülür (rapor 3.1 · M5).

Kritik tasarım ayrımı: RESMÎ_KAYNAK_SESSİZ, YALAN ile eş anlamlı değildir.
Kriz saatlerinin başında resmî kaynak henüz konuşmamış olabilir; bu ayrım
yapılmazsa sistem doğru erken uyarıları bastırır.
"""

from __future__ import annotations

from krizkalkan_core.knowledge import corpus
from krizkalkan_core.knowledge.corpus import KnowledgeRecord
from krizkalkan_core.schemas import Evidence, ExtractedClaim, KnowledgeMatch, Signal
from krizkalkan_core.taxonomy import KnowledgeVerdict
from krizkalkan_core.text.lexicon import normalize

#: Bu benzerliğin altındaki eşleşmeler kayıtla ilişkilendirilmez.
MATCH_THRESHOLD = 0.34


def _overlap(claim_text: str, record: KnowledgeRecord) -> float:
    """Anahtar terim örtüşmesine dayalı benzerlik.

    Önce çapa kontrolü yapılır: kaydın ayırt edici terimlerinden hiçbiri
    metinde geçmiyorsa eşleşme yoktur. Bu olmadan "yıkıldı" gibi genel bir
    terim, baraj tekzibini bina çökmesi haberine iliştirir.

    Gerçek sistemde bu adım NLI-TR üzerine eğitilmiş bir çıkarım modelidir;
    sözleşme (benzerlik + karar) aynıdır.
    """
    norm = normalize(claim_text)
    if not record.keywords:
        return 0.0
    if record.anchors and not any(a in norm for a in record.anchors):
        return 0.0
    hits = sum(1 for kw in record.keywords if kw in norm)
    return round(hits / len(record.keywords), 4)


def _verdict_of(record: KnowledgeRecord) -> KnowledgeVerdict:
    """Kaydın derecesini sistem kararına çevirir."""
    if record.rating_label == "YANLIŞ":
        return KnowledgeVerdict.CELISIYOR
    if record.rating_label == "DOĞRU":
        return KnowledgeVerdict.DESTEKLIYOR
    return KnowledgeVerdict.ILGISIZ


def analyse(claims: list[ExtractedClaim]) -> tuple[KnowledgeMatch | None, list[Signal]]:
    """İddiayı resmî kayıtlarla eşleştirir."""
    if not claims:
        return None, [
            Signal(
                module="M5",
                key="knowledge.verdict",
                label="Resmî kaynak doğrulaması",
                score=0.0,
                raw_score=0.0,
                abstained=True,
                abstain_reason="Metinden doğrulanabilir bir iddia çıkarılamadı",
            )
        ]

    claim_text = " ".join(c.text for c in claims)
    scored = [(record, _overlap(claim_text, record)) for record in corpus.RECORDS]
    best, similarity = max(scored, key=lambda pair: pair[1])

    # ── Resmî kaynak sessiz ──
    if similarity < MATCH_THRESHOLD:
        match = KnowledgeMatch(verdict=KnowledgeVerdict.KAYNAK_SESSIZ, similarity=similarity)
        return match, [
            Signal(
                module="M5",
                key="knowledge.verdict",
                label="Resmî kaynak doğrulaması",
                # Sessizlik yalan değildir: orta düzey, tek başına karar vermeyen skor.
                score=0.45,
                raw_score=0.45,
                evidence=[
                    Evidence(
                        kind="kayit",
                        label="Resmî kaynaklarda bu konuda henüz açıklama bulunmuyor",
                        detail=(
                            "Bu, iddianın yanlış olduğu anlamına gelmez; kriz "
                            "saatlerinin başında kaynaklar henüz konuşmamış olabilir."
                        ),
                    )
                ],
            )
        ]

    verdict = _verdict_of(best)
    match = KnowledgeMatch(
        verdict=verdict,
        matched_claim=best.claim,
        official_statement=best.fact_check,
        source=best.source,
        published_at=best.date_published,
        similarity=similarity,
    )

    score = {
        KnowledgeVerdict.CELISIYOR: 0.92,
        KnowledgeVerdict.DESTEKLIYOR: 0.05,
        KnowledgeVerdict.ILGISIZ: 0.30,
        KnowledgeVerdict.KAYNAK_SESSIZ: 0.45,
    }[verdict]

    headline = {
        KnowledgeVerdict.CELISIYOR: "Resmî kaynak bu iddiayı yalanlıyor",
        KnowledgeVerdict.DESTEKLIYOR: "Resmî kaynak bu iddiayı doğruluyor",
        KnowledgeVerdict.ILGISIZ: "Eşleşen kayıt iddiayla doğrudan ilgili değil",
        KnowledgeVerdict.KAYNAK_SESSIZ: "Resmî kaynaklarda henüz açıklama yok",
    }[verdict]

    return match, [
        Signal(
            module="M5",
            key="knowledge.verdict",
            label="Resmî kaynak doğrulaması",
            score=score,
            raw_score=score,
            evidence=[
                Evidence(
                    kind="kayit",
                    label=headline,
                    detail=best.fact_check,
                    locator=f"{best.source} · {best.date_published} · {best.record_id}",
                )
            ],
        )
    ]
