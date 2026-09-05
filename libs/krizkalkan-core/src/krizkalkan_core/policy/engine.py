"""M7 — Kademeli müdahale politikası.

İki kuralla tanımlıdır (rapor 2.2 · Y3):

    1. Sistem hiçbir içeriği silme yetkisine sahip değildir. Uygulayabileceği
       azami otomatik eylem, bir bağlam kartı ve paylaşım öncesi sürtünme
       ekranıdır.
    2. Kural 0: yardım_çağrısı sınıflandırıcısı diğer TÜM sinyalleri geçersiz
       kılar. Eşik kasten düşüktür (0,35) — birkaç dezenformasyon içeriğinin
       etiketsiz geçmesi, bir yardım çağrısının engellenmesine tercih edilmiştir.

Bu katman modelden ayrıktır ve kural tabanlıdır: model güncellendiğinde politika
değişmez, politika değiştiğinde model yeniden eğitilmez (rapor 4.3).
"""

from __future__ import annotations

from krizkalkan_core.schemas import Intervention
from krizkalkan_core.taxonomy import (
    HELP_CALL_THRESHOLD,
    HIGH_CONFIDENCE_THRESHOLD,
    HUMAN_REVIEW_SPREAD_THRESHOLD,
    INTERVENTION_AUTOMATIC,
    INTERVENTION_LABEL,
    VERDICT_INTERVENTION,
    InterventionLevel,
    Verdict,
)

#: Sınıf → kullanıcıya gösterilen tek cümlelik özet.
#: Kriz stresinde okuma kapasitesi düştüğü için cümleler kısadır (rapor 3.3).
HEADLINES: dict[Verdict, str] = {
    Verdict.TEMIZ: "Bu içerikte sorun tespit edilmedi.",
    Verdict.YETERSIZ_KANIT: "Bu içerik hakkında karar verilemedi.",
    Verdict.DOGRULANMAMIS_IDDIA: "Resmî kaynaklarda bu iddia teyit edilmiyor.",
    Verdict.YANLIS_BAGLAM: "Bu görüntü gerçek, ancak güncel olaya ait değil.",
    Verdict.PROVOKATIF_CERCEVELEME: "Bu içerik manipülatif bir dille sunulmuş.",
    Verdict.SENTETIK_MEDYA: "Bu içerik yapay zekâ ile üretilmiş olabilir.",
    Verdict.MANIPULE_MEDYA: "Bu içeriğin değiştirilmiş olma olasılığı yüksek.",
}

DETAILS: dict[Verdict, str] = {
    Verdict.DOGRULANMAMIS_IDDIA: (
        "İddia resmî kurum kayıtlarıyla eşleştirildi ve karşılık bulunamadı. "
        "Paylaşmadan önce resmî kaynakları inceleyebilirsiniz."
    ),
    Verdict.YANLIS_BAGLAM: (
        "İçeriğin ilk yayın tarihi ve kaynağı kanıt panelinde gösterilmektedir. "
        "İçerik kaldırılmadı."
    ),
    Verdict.PROVOKATIF_CERCEVELEME: (
        "İçeriğin kendisi doğru olabilir; sunum dili panik veya kışkırtma işaretleri taşıyor."
    ),
    Verdict.SENTETIK_MEDYA: (
        "Paylaşmadan önce kanıtları inceleyiniz. Karar sizindir; içerik kaldırılmadı."
    ),
    Verdict.MANIPULE_MEDYA: (
        "Ses ve görüntü arasında tutarsızlık işaretleri bulundu. Karar sizindir; "
        "içerik kaldırılmadı."
    ),
}

#: Kural 0 tetiklendiğinde denetim kaydına yazılan sabit ifade.
RULE_ZERO_AUDIT = "koruma_kuralı_uygulandı"


def decide(
    verdict: Verdict,
    confidence: float,
    help_call_score: float,
    spread_per_minute: float = 0.0,
) -> Intervention:
    """Sınıf ve sinyallerden müdahale kararı üretir.

    Kural 0 her şeyden önce değerlendirilir ve geçersiz kılınamaz.
    """
    # ─────────────── Kural 0 ───────────────
    if help_call_score > HELP_CALL_THRESHOLD:
        return Intervention(
            level=InterventionLevel.NONE,
            label=INTERVENTION_LABEL[InterventionLevel.NONE],
            automatic=True,
            headline="Bu içerik bir yardım çağrısı olarak sınıflandırıldı.",
            detail=(
                "Kural 0 gereği hiçbir etiket, sürtünme veya yavaşlatma "
                "uygulanmadı. Denetim kaydına "
                f"“{RULE_ZERO_AUDIT}” yazıldı."
            ),
            protected_by_rule_zero=True,
            content_removed=False,
        )

    level = VERDICT_INTERVENTION[verdict]

    # Sentetik/manipüle medyada sürtünme yalnızca yüksek güvende uygulanır;
    # aksi hâlde bir alt basamağa, bağlam kartına düşülür.
    if level is InterventionLevel.FRICTION and confidence < HIGH_CONFIDENCE_THRESHOLD:
        level = InterventionLevel.CONTEXT_CARD

    # Yüksek yayılım + yüksek güven → insan moderatöre yönlendirme.
    # Bu, otomatik bir kısıtlama değildir; yalnızca kuyruk önceliğidir.
    if (
        spread_per_minute >= HUMAN_REVIEW_SPREAD_THRESHOLD
        and confidence >= HIGH_CONFIDENCE_THRESHOLD
        and verdict not in (Verdict.TEMIZ, Verdict.YETERSIZ_KANIT)
    ):
        level = InterventionLevel.HUMAN_REVIEW

    return Intervention(
        level=level,
        label=INTERVENTION_LABEL[level],
        automatic=INTERVENTION_AUTOMATIC[level],
        headline=HEADLINES[verdict],
        detail=DETAILS.get(verdict),
        protected_by_rule_zero=False,
        # Sistemde içerik silme yetkisi yoktur — bu alan hiçbir yolda True olmaz.
        content_removed=False,
    )
