"""M5 — Doğrulanmış kriz bilgi havuzu.

Çıkarılan iddia, havuz kayıtlarıyla doğal dil çıkarımı (NLI) yoluyla eşleştirilir
ve dört durumdan biri döndürülür (rapor 3.1 · M5).

Kritik tasarım ayrımı: RESMÎ_KAYNAK_SESSİZ, YALAN ile eş anlamlı değildir.
Kriz saatlerinin başında resmî kaynak henüz konuşmamış olabilir; bu ayrım
yapılmazsa sistem doğru erken uyarıları bastırır.
"""

from __future__ import annotations

from dataclasses import dataclass

from krizkalkan_core.knowledge import corpus, nli, retriever
from krizkalkan_core.knowledge.corpus import KnowledgeRecord
from krizkalkan_core.schemas import Evidence, ExtractedClaim, KnowledgeMatch, Signal
from krizkalkan_core.taxonomy import KnowledgeVerdict
from krizkalkan_core.text.lexicon import normalize

#: Bu benzerliğin altındaki eşleşmeler kayıtla ilişkilendirilmez (sözlük yolu).
MATCH_THRESHOLD = 0.34

#: Çıkarım katmanına kaç aday gönderilir. Geri getirme Recall@5 = 0,964
#: ölçtüğü için beş aday pratikte doğru kaydı içeriyor; daha fazlası yalnızca
#: çıkarım maliyetini artırır (docs/metrikler/m5.md).
ADAY_SAYISI = 5


@dataclass(slots=True)
class _Eslesme:
    """Karar katmanının çıktısı — hangi yolla bulunduğu dahil."""

    record: KnowledgeRecord | None
    benzerlik: float
    verdict: KnowledgeVerdict
    guven: float
    yol: str


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


#: Kaynak derecesi → sistem kararı. Anahtarlar `normalize()` çıktısı biçiminde
#: tutulur; karşılaştırma da normalize üzerinden yapılır.
#:
#: Neden casefold() değil: DMM verisi "Yanlış", tohum kayıtlar "YANLIŞ" yazar.
#: Python'da "YANLIŞ".casefold() → "yanliş" üretir (noktasız I, noktalı i'ye
#: katlanır) ve "yanlış" ile eşleşmez. Türkçe metinde büyük/küçük harf
#: karşılaştırması yalnızca projenin katlama işleviyle güvenlidir.
_RATING_VERDICT: dict[str, KnowledgeVerdict] = {
    "yanlis": KnowledgeVerdict.CELISIYOR,
    "dogru": KnowledgeVerdict.DESTEKLIYOR,
}


def _verdict_of(record: KnowledgeRecord) -> KnowledgeVerdict:
    """Kaydın derecesini sistem kararına çevirir."""
    return _RATING_VERDICT.get(normalize(record.rating_label), KnowledgeVerdict.ILGISIZ)


def _sozluk_yolu(claim_text: str) -> _Eslesme:
    """Anahtar terim örtüşmesi — modeller yokken kullanılan yol."""
    scored = [(record, _overlap(claim_text, record)) for record in corpus.records()]
    best, similarity = max(scored, key=lambda pair: pair[1])
    if similarity < MATCH_THRESHOLD:
        return _Eslesme(None, similarity, KnowledgeVerdict.KAYNAK_SESSIZ, 0.0, "sozluk")
    return _Eslesme(best, similarity, _verdict_of(best), similarity, "sozluk")


def _iki_asamali_yol(claim_text: str, arayici, cikarimci) -> _Eslesme:
    """Geri getirme → çıkarım. Kararı benzerlik değil, çıkarım modeli verir.

    Benzerliğin tek başına karar verdiremediği ölçülmüştür: konu olarak
    havuza benzeyen resmî duyurular, tekziplerle aynı skor bandına düşüyor
    (docs/metrikler/m5.md · ayrım analizi).
    """
    adaylar = arayici.ara(claim_text, k=ADAY_SAYISI)
    if not adaylar:
        return _Eslesme(None, 0.0, KnowledgeVerdict.KAYNAK_SESSIZ, 0.0, "iki_asamali")

    kayitlar = {k.record_id: k for k in corpus.records()}
    secilen = [(a, kayitlar[a.record_id]) for a in adaylar if a.record_id in kayitlar]
    cikarimlar = cikarimci.siniflandir([(kayit.claim, claim_text) for _, kayit in secilen])

    for (aday, kayit), cikarim in zip(secilen, cikarimlar, strict=True):
        if cikarim.ayni_iddia:
            # Aynı iddia: kaydın derecesi doğrudan karara dönüşür.
            return _Eslesme(
                kayit, aday.benzerlik, _verdict_of(kayit), cikarim.olasilik, "iki_asamali"
            )
        if cikarim.tersini_soyluyor and _verdict_of(kayit) is KnowledgeVerdict.CELISIYOR:
            # Kullanıcı yalanlanan iddianın TERSİNİ söylüyor: tekzibi paylaşıyor
            # olabilir. Bu içerik dezenformasyon değildir; kayıt onu destekler.
            return _Eslesme(
                kayit, aday.benzerlik, KnowledgeVerdict.DESTEKLIYOR, cikarim.olasilik, "iki_asamali"
            )

    return _Eslesme(None, adaylar[0].benzerlik, KnowledgeVerdict.KAYNAK_SESSIZ, 0.0, "iki_asamali")


def _eslestir(claim_text: str) -> _Eslesme:
    """İki aşamalı yol kullanılabilirse onu, değilse sözlük yolunu seçer."""
    arayici, cikarimci = retriever.get(), nli.get()
    if arayici is not None and cikarimci is not None:
        return _iki_asamali_yol(claim_text, arayici, cikarimci)
    return _sozluk_yolu(claim_text)


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
    eslesme = _eslestir(claim_text)
    best, similarity = eslesme.record, eslesme.benzerlik

    # ── Resmî kaynak sessiz ──
    if best is None:
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

    verdict = eslesme.verdict
    match = KnowledgeMatch(
        verdict=verdict,
        matched_claim=best.claim,
        official_statement=best.fact_check,
        source=best.source,
        published_at=best.date_published,
        similarity=similarity,
    )

    # Sözlük yolunda skor sınıfa bağlı sabittir; iki aşamalı yolda çıkarım
    # modelinin güveni kullanılır — M6 kalibrasyonunun anlamlı çalışabilmesi
    # için ham skorun ayrışan bir büyüklük olması gerekir.
    if eslesme.yol == "iki_asamali" and verdict is KnowledgeVerdict.CELISIYOR:
        score = eslesme.guven
    else:
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
                    locator=(
                        f"{best.source} · {best.date_published} · {best.record_id}"
                        + (
                            f" · çıkarım güveni {eslesme.guven:.2f}"
                            if eslesme.yol == "iki_asamali"
                            else ""
                        )
                    ),
                )
            ],
        )
    ]
