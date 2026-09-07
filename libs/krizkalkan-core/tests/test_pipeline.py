"""Analiz boru hattının davranış testleri.

Bu testler rapordaki taahhütleri koda bağlar: Kural 0, silme yetkisinin
bulunmaması, çekinme yeteneği ve altı sınıflı taksonomi.
"""

from __future__ import annotations

import pytest
from krizkalkan_core.fusion.calibration import calibrate, expected_calibration_error
from krizkalkan_core.pipeline import AnalysisPipeline
from krizkalkan_core.taxonomy import (
    HELP_CALL_THRESHOLD,
    InterventionLevel,
    KnowledgeVerdict,
    Verdict,
)


@pytest.fixture
def pipeline() -> AnalysisPipeline:
    return AnalysisPipeline()


# ─────────────────────────── Kural 0 ───────────────────────────


def test_yardim_cagrisi_hicbir_mudahale_almaz(pipeline: AnalysisPipeline) -> None:
    """Kural 0: yardım çağrısı diğer tüm sinyalleri geçersiz kılar."""
    result = pipeline.analyse(
        body=(
            "ACİL! Kardeşim enkaz altında, hâlâ ses geliyor. "
            "Adres: Bahçelievler Mah. Yardım edin, ekip gönderin!"
        )
    )
    assert result.intervention.protected_by_rule_zero is True
    assert result.intervention.level is InterventionLevel.NONE
    assert result.verdict is Verdict.TEMIZ


def test_panik_dili_iceren_yardim_cagrisi_da_korunur(pipeline: AnalysisPipeline) -> None:
    """Yüzeysel olarak panik gibi görünen yardım çağrısı yine korunur."""
    result = pipeline.analyse(
        body="YARDIM EDİN!! Enkaz altındayız, durum çok vahim, acilen ekip gönderin!"
    )
    assert result.intervention.protected_by_rule_zero is True


def test_yardim_cagrisi_esigi_dusuk_tutulmus() -> None:
    """Eşik duyarlılık lehine asimetriktir."""
    assert HELP_CALL_THRESHOLD <= 0.40


# ─────────────────────── Silme yetkisi yoktur ───────────────────────


@pytest.mark.parametrize(
    "body,media,fingerprint",
    [
        (
            "Şanlıurfa'da az önce çekildi! Bina yıkıldı, hemen paylaşın!",
            "video",
            "deprem-yikim-hatay-2023",
        ),
        ("AFAD açıkladı: ikinci büyük deprem bekleniyor. Kesin bilgi!", "yok", None),
        ("Vali konuşma yaptı, şehir tahliye ediliyor.", "video", "ai-klon-yetkili-ses"),
        ("Sorumlular hesap versin, hepimiz sokağa dökülelim!", "yok", None),
        ("Bölgede arama kurtarma çalışmaları sürüyor.", "yok", None),
    ],
)
def test_hicbir_yolda_icerik_kaldirilmaz(
    pipeline: AnalysisPipeline, body: str, media: str, fingerprint: str | None
) -> None:
    """Sistemin silme yetkisi yoktur; hiçbir girdi bunu değiştiremez."""
    result = pipeline.analyse(body=body, media_kind=media, media_fingerprint=fingerprint)
    assert result.intervention.content_removed is False
    assert result.intervention.level is not InterventionLevel.HUMAN_REVIEW or (
        result.intervention.automatic is False
    )


# ─────────────────────────── Taksonomi ───────────────────────────


def test_eski_goruntu_yanlis_baglam_olarak_siniflanir(pipeline: AnalysisPipeline) -> None:
    result = pipeline.analyse(
        body="Şanlıurfa'da az önce çekildi! Bina tamamen yıkıldı.",
        media_kind="video",
        media_fingerprint="deprem-yikim-hatay-2023",
    )
    assert result.verdict is Verdict.YANLIS_BAGLAM
    assert result.provenance is not None
    assert result.provenance.matched is True
    assert result.provenance.first_published == "08.02.2023"


def test_koken_kesinse_pahali_moduller_atlanir(pipeline: AnalysisPipeline) -> None:
    """Kademeli işlem: köken kesin sonuç verdiğinde M2 ve M4 çalışmaz."""
    result = pipeline.analyse(
        body="Az önce çekildi!",
        media_kind="video",
        media_fingerprint="deprem-yikim-hatay-2023",
    )
    assert "M2" in result.modules_skipped
    assert "M4" in result.modules_skipped
    assert result.skip_reason is not None


def test_sentetik_medya_siniflanir(pipeline: AnalysisPipeline) -> None:
    result = pipeline.analyse(
        body="Vali konuşma yaptı.",
        media_kind="video",
        media_fingerprint="ai-klon-yetkili-ses",
    )
    assert result.verdict is Verdict.SENTETIK_MEDYA


def test_resmi_kaynakla_celisen_iddia(pipeline: AnalysisPipeline) -> None:
    result = pipeline.analyse(body="AFAD açıkladı: ikinci büyük deprem bekleniyor.")
    assert result.verdict is Verdict.DOGRULANMAMIS_IDDIA
    assert result.knowledge is not None
    assert result.knowledge.verdict is KnowledgeVerdict.CELISIYOR


def test_resmi_kaynak_sessizligi_yalan_degildir(pipeline: AnalysisPipeline) -> None:
    """Kayıtta karşılığı olmayan iddia otomatik olarak yalan sayılmaz."""
    result = pipeline.analyse(body="Merhaba, bugün hava çok güzel.")
    assert result.verdict in (Verdict.TEMIZ, Verdict.YETERSIZ_KANIT)
    assert result.intervention.level is InterventionLevel.NONE


def test_provokatif_cerceveleme(pipeline: AnalysisPipeline) -> None:
    result = pipeline.analyse(
        body="Sorumlular hesap versin, hepimiz sokağa dökülelim! Gerçekleri saklıyorlar."
    )
    assert result.verdict is Verdict.PROVOKATIF_CERCEVELEME


# ─────────────────────── Çekinme (abstention) ───────────────────────


def test_dagilim_disi_medyada_cekinilir(pipeline: AnalysisPipeline) -> None:
    """M4 karar veremiyorsa sistem 'bilmiyorum' der, 'temiz' demez."""
    result = pipeline.analyse(
        body="Bir şeyler oluyor galiba.",
        media_kind="video",
        media_fingerprint="dusuk-cozunurluk-kisa-klip",
    )
    assert result.verdict is Verdict.YETERSIZ_KANIT
    assert any(s.abstained for s in result.signals)


def test_cekinen_sinyaller_kanit_panelinde_gosterilir(pipeline: AnalysisPipeline) -> None:
    result = pipeline.analyse(body="Kısa bir not.")
    assert any(s.abstained and s.abstain_reason for s in result.signals)


# ─────────────────── Yalanlama (debunk) çerçevesi ───────────────────


def test_tekzip_metni_dezenformasyon_sayilmaz(pipeline: AnalysisPipeline) -> None:
    """Bilinen hata modu: yalanlama metni, yalanladığı iddia sanılmamalı."""
    result = pipeline.analyse(
        body=(
            "Baraj yıkıldı iddiası gerçeği yansıtmamaktadır. DSİ ve Valilik, "
            "barajlarda yapısal hasar bulunmadığını bildirmiştir."
        )
    )
    assert result.verdict is not Verdict.DOGRULANMAMIS_IDDIA
    assert result.intervention.level is InterventionLevel.NONE


# ─────────────────────────── Kalibrasyon ───────────────────────────


def test_kalibrasyon_monoton_artan() -> None:
    """Ham skor arttıkça kalibre olasılık azalmamalıdır."""
    for key in ("provenance.match", "synthetic.video", "text.manipulative"):
        values = [calibrate(key, raw / 20) for raw in range(21)]
        assert values == sorted(values), f"{key} monoton değil"


def test_ece_hesabi() -> None:
    mukemmel = [(1.0, True)] * 10 + [(0.0, False)] * 10
    assert expected_calibration_error(mukemmel) == pytest.approx(0.0, abs=1e-6)

    kotu = [(0.9, False)] * 10
    assert expected_calibration_error(kotu) > 0.5


# ─────────────────────────── Önbellek ───────────────────────────


def test_ayni_icerik_onbellekten_doner(pipeline: AnalysisPipeline) -> None:
    payload = {"body": "Aynı içerik", "media_kind": "yok"}
    first = pipeline.analyse(**payload)  # type: ignore[arg-type]
    second = pipeline.analyse(**payload)  # type: ignore[arg-type]
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.verdict is first.verdict
    assert pipeline.metrics.cache_hits == 1


def test_metrikler_toplaniyor(pipeline: AnalysisPipeline) -> None:
    pipeline.analyse(body="Bir gönderi")
    pipeline.analyse(body="Başka bir gönderi")
    assert pipeline.metrics.total_analyses == 2
    assert pipeline.metrics.p50_ms >= 0
    assert pipeline.metrics.removed_content == 0
