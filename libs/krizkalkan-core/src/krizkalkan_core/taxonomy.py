"""Altı sınıflı kriz içeriği taksonomisi ve kademeli müdahale merdiveni.

Rapor Bölüm 2.2 ve 3.1 (M7) ile birebir uyumludur. Bu modül sistemin
sözleşmesidir: sınıf adları, müdahale seviyeleri ve Kural 0 eşiği burada
tanımlanır; başka hiçbir yerde sabit kodlanmaz.
"""

from __future__ import annotations

from enum import StrEnum


class Verdict(StrEnum):
    """İçeriğin hangi anlamda sorunlu olduğunu ayıran altı sınıf."""

    SENTETIK_MEDYA = "SENTETİK_MEDYA"
    MANIPULE_MEDYA = "MANİPÜLE_MEDYA"
    YANLIS_BAGLAM = "YANLIŞ_BAĞLAM"
    DOGRULANMAMIS_IDDIA = "DOĞRULANMAMIŞ_İDDİA"
    PROVOKATIF_CERCEVELEME = "PROVOKATİF_ÇERÇEVELEME"
    TEMIZ = "TEMİZ"
    YETERSIZ_KANIT = "YETERSİZ_KANIT"


#: Kullanıcıya gösterilen kısa açıklamalar (rapor 2.2 tablosu).
VERDICT_MEANING: dict[Verdict, str] = {
    Verdict.SENTETIK_MEDYA: "İçerik yapay zekâ ile üretilmiş",
    Verdict.MANIPULE_MEDYA: "Gerçek medya değiştirilmiş",
    Verdict.YANLIS_BAGLAM: "Medya gerçek, bağlamı yanlış",
    Verdict.DOGRULANMAMIS_IDDIA: "Resmî kaynakla teyit edilmemiş",
    Verdict.PROVOKATIF_CERCEVELEME: "İçerik doğru, sunum manipülatif",
    Verdict.TEMIZ: "Sorun tespit edilmedi",
    Verdict.YETERSIZ_KANIT: "Karar verilemiyor",
}


class InterventionLevel(StrEnum):
    """Kademeli müdahale merdiveni (rapor 3.1 · M7).

    Seviye 5 bilinçli olarak tanımsızdır: sistemde içerik silme yetkisi yoktur.
    """

    NONE = "SEVIYE_0"
    FOOTNOTE = "SEVIYE_1"
    CONTEXT_CARD = "SEVIYE_2"
    FRICTION = "SEVIYE_3"
    HUMAN_REVIEW = "SEVIYE_4"


INTERVENTION_LABEL: dict[InterventionLevel, str] = {
    InterventionLevel.NONE: "Eylem yok",
    InterventionLevel.FOOTNOTE: "Alt bilgi + resmî kaynak bağlantısı",
    InterventionLevel.CONTEXT_CARD: "Bağlam kartı + kanıt paneli",
    InterventionLevel.FRICTION: "Paylaşım öncesi sürtünme ekranı",
    InterventionLevel.HUMAN_REVIEW: "İnsan moderatöre öncelikli yönlendirme",
}

INTERVENTION_AUTOMATIC: dict[InterventionLevel, bool] = {
    InterventionLevel.NONE: True,
    InterventionLevel.FOOTNOTE: True,
    InterventionLevel.CONTEXT_CARD: True,
    InterventionLevel.FRICTION: True,
    InterventionLevel.HUMAN_REVIEW: False,  # karar insanındır
}

#: Sınıf → varsayılan müdahale seviyesi eşlemesi (rapor 3.1 merdiveni).
VERDICT_INTERVENTION: dict[Verdict, InterventionLevel] = {
    Verdict.TEMIZ: InterventionLevel.NONE,
    Verdict.YETERSIZ_KANIT: InterventionLevel.NONE,
    Verdict.DOGRULANMAMIS_IDDIA: InterventionLevel.FOOTNOTE,
    Verdict.YANLIS_BAGLAM: InterventionLevel.CONTEXT_CARD,
    Verdict.PROVOKATIF_CERCEVELEME: InterventionLevel.CONTEXT_CARD,
    Verdict.SENTETIK_MEDYA: InterventionLevel.FRICTION,
    Verdict.MANIPULE_MEDYA: InterventionLevel.FRICTION,
}


class ManipulationLabel(StrEnum):
    """Görev B1 — manipülatif söylem, sekiz etiket (rapor 3.1 · M3)."""

    PANIK_YAYMA = "panik_yayma"
    KAYNAKSIZ_ACIL_CAGRI = "kaynaksız_acil_çağrı"
    KURUM_TAKLIDI = "kurum_taklidi"
    YANLIS_KESINLIK = "yanlış_kesinlik"
    TOPLUMSAL_KISKIRTMA = "toplumsal_kışkırtma"
    ACILIYET_BASKISI = "aciliyet_baskısı"
    KOMPLO_CERCEVESI = "komplo_çerçevesi"
    NOTR_BILGILENDIRME = "nötr_bilgilendirme"


class KnowledgeVerdict(StrEnum):
    """M5 bilgi havuzu çıktısı (rapor 3.1 · M5).

    RESMÎ_KAYNAK_SESSİZ, YALAN ile eş anlamlı DEĞİLDİR; kriz saatlerinin
    başında resmî kaynak henüz konuşmamış olabilir.
    """

    DESTEKLIYOR = "DESTEKLİYOR"
    CELISIYOR = "ÇELİŞİYOR"
    ILGISIZ = "İLGİSİZ"
    KAYNAK_SESSIZ = "RESMÎ_KAYNAK_SESSİZ"


class ClaimType(StrEnum):
    """Görev A — iddia çıkarımı türleri."""

    ALTYAPI_HASARI = "altyapı_hasarı"
    IKINCIL_AFET_UYARISI = "ikincil_afet_uyarısı"
    TAHLIYE = "tahliye"
    CAN_KAYBI = "can_kaybı"
    RESMI_ACIKLAMA = "resmî_açıklama"
    YARDIM_CAGRISI = "yardım_çağrısı"
    BELIRSIZ = "belirsiz"


class Certainty(StrEnum):
    MUTLAK = "mutlak"
    OLASILIKSAL = "olasılıksal"
    SOYLENTI = "söylenti"


# ─────────────────────────── Kural 0 ───────────────────────────

#: Yardım çağrısı koruma eşiği. Kasten düşük tutulmuştur: birkaç dezenformasyon
#: içeriğinin etiketsiz geçmesi, bir yardım çağrısının engellenmesine tercih
#: edilmiştir (rapor 2.2 · Y3).
HELP_CALL_THRESHOLD = 0.35

#: Sentetik/manipüle medya için "yüksek güven" eşiği — Seviye 3'ü tetikler.
HIGH_CONFIDENCE_THRESHOLD = 0.70

#: Belirsizlik bandının üst sınırı — bu değerin altındaki zayıf sinyaller tek
#: başına karar vermeye yetmez (rapor 2.2 · Y2).
ABSTENTION_THRESHOLD = 0.45

#: Belirsizlik bandının alt sınırı. Bunun da altındaki skorlar "sorun yok"
#: anlamına gelir; kararsızlık değil, temiz içerik göstergesidir.
ABSTENTION_FLOOR = 0.30

#: Seviye 4 (insan moderatör) için gereken yayılım hızı eşiği (paylaşım/dakika).
HUMAN_REVIEW_SPREAD_THRESHOLD = 40.0
