"""M5 — Doğrulanmış kriz bilgi havuzu.

Çıkarılan iddia, havuz kayıtlarıyla doğal dil çıkarımı (NLI) yoluyla eşleştirilir
ve dört durumdan biri döndürülür (rapor 3.1 · M5).

Kritik tasarım ayrımı: RESMÎ_KAYNAK_SESSİZ, YALAN ile eş anlamlı değildir.
Kriz saatlerinin başında resmî kaynak henüz konuşmamış olabilir; bu ayrım
yapılmazsa sistem doğru erken uyarıları bastırır.
"""

from __future__ import annotations

from dataclasses import dataclass

# nli içe aktarımı korunuyor: `_cikarim_yolu` devre dışı olsa da testler ve
# gelecekteki yeniden değerlendirme onu bu ad üzerinden çözüyor.
from krizkalkan_core.knowledge import corpus, nli, retriever  # noqa: F401
from krizkalkan_core.knowledge.corpus import KnowledgeRecord
from krizkalkan_core.schemas import Evidence, ExtractedClaim, KnowledgeMatch, Signal
from krizkalkan_core.taxonomy import KnowledgeVerdict
from krizkalkan_core.text.lexicon import normalize

#: Sözlük tek başına çalışırken eşik. Yüksek tutulur: geri getirici yokken
#: yanlış eşleşmeyi engelleyecek tek mekanizma budur.
MATCH_THRESHOLD = 0.34

#: Geri getirici veto olarak devredeyken kullanılabilecek DÜŞÜK eşik.
#:
#: Ölçüldü (docs/metrikler/m5.md): 0,34'te 3/28 doğru · 0 zararlı; 0,25'te
#: 8/28 doğru · 1 zararlı. Tek başına 0,25'e inmek zararlı eşleşme getiriyor,
#: ama zararlı örnek geri getiricinin ilk 20'sinde bile yok (sıra 99), doğru
#: eşleşmelerin tamamı ilk 3'te. Veto bu yüzden düşük eşiği güvenli kılıyor.
DOGRULANMIS_MATCH_THRESHOLD = 0.25

#: Adayın geri getiricinin ilk kaçında bulunması gerekir.
VETO_SIRA = 5

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


def _en_iyi_ortusme(claim_text: str) -> tuple[KnowledgeRecord | None, float]:
    """Havuzdaki en yüksek örtüşme skorlu kayıt."""
    scored = [(record, _overlap(claim_text, record)) for record in corpus.records()]
    best, similarity = max(scored, key=lambda pair: pair[1])
    return best, similarity


def _sozluk_yolu(claim_text: str) -> _Eslesme:
    """Anahtar terim örtüşmesi — geri getirici yokken kullanılan yol."""
    best, similarity = _en_iyi_ortusme(claim_text)
    if similarity < MATCH_THRESHOLD:
        return _Eslesme(None, similarity, KnowledgeVerdict.KAYNAK_SESSIZ, 0.0, "sozluk")
    return _Eslesme(best, similarity, _verdict_of(best), similarity, "sozluk")


def _dogrulanmis_yol(claim_text: str, arayici) -> _Eslesme:
    """Sözlük önerir, geri getirici doğrular.

    İki katmanın güçlü yanları farklı: sözlük skoru ayırt edici terim
    örtüşmesini ölçer (yüksek kesinlik, düşük duyarlılık), gömme ise anlamsal
    yakınlığı (yüksek duyarlılık, karar verdiremeyecek kadar sıkışık dağılım).
    Biri aday üretir, diğeri vetolar.

    Ölçüm (docs/metrikler/m5.md · n=28):

        sözlük tek başına, eşik 0,34   3 doğru · 0 zararlı
        sözlük tek başına, eşik 0,25   8 doğru · 1 zararlı
        çıkarım (NLI) katmanı          1 doğru · 5 zararlı
        sözlük 0,25 + geri getirme veto  8 doğru · 0 zararlı

    Zararlı örnek geri getiricinin ilk 20'sinde bile yoktu; doğru eşleşmelerin
    tamamı ilk 3'teydi. Ayrım keskin olduğu için veto düşük eşiği güvenli kılar.
    """
    aday, skor = _en_iyi_ortusme(claim_text)
    if aday is None or skor < DOGRULANMIS_MATCH_THRESHOLD:
        return _Eslesme(None, skor, KnowledgeVerdict.KAYNAK_SESSIZ, 0.0, "dogrulanmis")

    ilk_siradakiler = {a.record_id for a in arayici.ara(claim_text, k=VETO_SIRA)}
    if aday.record_id not in ilk_siradakiler:
        # Sözlük eşleşti ama anlamsal olarak uzak: kayıt reddedilir.
        return _Eslesme(None, skor, KnowledgeVerdict.KAYNAK_SESSIZ, 0.0, "dogrulanmis")

    return _Eslesme(aday, skor, _verdict_of(aday), skor, "dogrulanmis")


def _cikarim_yolu(claim_text: str, arayici, cikarimci) -> _Eslesme:
    """Geri getirme → NLI çıkarımı. **Şu an devrede DEĞİL.**

    Ölçüldü ve reddedildi: SNLI-TR ile eğitilen çıkarım modeli kendi kümesinde
    0,8181 doğruluk alıyor ama kriz alanında çalışmıyor — 28 sorguda 1 doğru,
    5 ZARARLI eşleşme üretti (sözlük yolu aynı kümede 3 doğru, 0 zararlı).

    Sebep görev uyumsuzluğu: SNLI'ın "öncül varsayımı ima ediyor mu?" sorusu,
    bizim "bu iki metin aynı iddiayı mı öne sürüyor?" sorumuz değildir. Ayrıca
    SNLI-TR makine çevirisi kısa altyazılardan oluşur; kriz iddiaları uzun ve
    kurumsaldır.

    Fonksiyon ve testleri korunuyor: gerçek bir iddia eşleştirme kümesiyle
    eğitilmiş model geldiğinde karar ölçümle yeniden ele alınacak.
    """
    adaylar = arayici.ara(claim_text, k=ADAY_SAYISI)
    if not adaylar:
        return _Eslesme(None, 0.0, KnowledgeVerdict.KAYNAK_SESSIZ, 0.0, "cikarim")

    kayitlar = {k.record_id: k for k in corpus.records()}
    secilen = [(a, kayitlar[a.record_id]) for a in adaylar if a.record_id in kayitlar]
    cikarimlar = cikarimci.siniflandir([(kayit.claim, claim_text) for _, kayit in secilen])

    for (aday, kayit), cikarim in zip(secilen, cikarimlar, strict=True):
        if cikarim.ayni_iddia:
            # Aynı iddia: kaydın derecesi doğrudan karara dönüşür.
            return _Eslesme(kayit, aday.benzerlik, _verdict_of(kayit), cikarim.olasilik, "cikarim")
        if cikarim.tersini_soyluyor and _verdict_of(kayit) is KnowledgeVerdict.CELISIYOR:
            # Kullanıcı yalanlanan iddianın TERSİNİ söylüyor: tekzibi paylaşıyor
            # olabilir. Bu içerik dezenformasyon değildir; kayıt onu destekler.
            return _Eslesme(
                kayit, aday.benzerlik, KnowledgeVerdict.DESTEKLIYOR, cikarim.olasilik, "cikarim"
            )

    return _Eslesme(None, adaylar[0].benzerlik, KnowledgeVerdict.KAYNAK_SESSIZ, 0.0, "cikarim")


def _eslestir(claim_text: str) -> _Eslesme:
    """Geri getirici varsa doğrulanmış yolu, yoksa sözlük yolunu seçer.

    Çıkarım (NLI) yolu bilinçli olarak seçilmez; gerekçesi `_cikarim_yolu`
    docstring'inde ölçümüyle birlikte yazılıdır.
    """
    arayici = retriever.get()
    if arayici is not None:
        return _dogrulanmis_yol(claim_text, arayici)
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
    if eslesme.yol == "cikarim" and verdict is KnowledgeVerdict.CELISIYOR:
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
