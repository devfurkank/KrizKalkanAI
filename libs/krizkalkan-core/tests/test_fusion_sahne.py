"""Füzyon — sahne çelişkisi dalı ve dal sıralaması.

Sahne çelişkisi, "medya gerçek ama gösterdiği olay iddia edilenden başka"
bulgusudur. Bu dosya iki şeyi kilitler: dalın çalıştığını ve DAHA GÜÇLÜ
bulguları geçersiz kılmadığını.
"""

from __future__ import annotations

import pytest
from krizkalkan_core.fusion.engine import SAHNE_CELISKI_ESIGI, fuse
from krizkalkan_core.schemas import ProvenanceMatch, Signal
from krizkalkan_core.taxonomy import Verdict


def _sinyal(anahtar: str, skor: float) -> Signal:
    """Kalibrasyon uygulanmış bir sinyal (score alanı doğrudan okunur)."""
    return Signal(module="M2", key=anahtar, label=anahtar, score=skor, raw_score=skor)


def test_sahne_celiskisi_yanlis_baglam_kurar() -> None:
    verdict, guven, katkilar = fuse([_sinyal("multimodal.scene_claim", 0.85)], None, None, None)
    assert verdict is Verdict.YANLIS_BAGLAM
    assert guven > 0.5
    assert any(s.key == "multimodal.scene_claim" for s in katkilar)


def test_esigin_altinda_sahne_karar_vermez() -> None:
    verdict, _, _ = fuse(
        [_sinyal("multimodal.scene_claim", SAHNE_CELISKI_ESIGI - 0.01)], None, None, None
    )
    assert verdict is not Verdict.YANLIS_BAGLAM


def test_koken_dogruladiysa_sahne_gecersiz_kilamaz() -> None:
    """Kesin kanıt olasılıksal sinyalden önce gelir (rapor 1.2).

    Köken kaydı görüntünün gerçekten o olaya ait olduğunu söylüyorsa,
    görsel-dil modelinin ikinci tahmini bunu bozmamalıdır.
    """
    dogrulayan = ProvenanceMatch(
        matched=True, similarity=0.95, context_conflict=False, original_event="test olayı"
    )
    verdict, _, _ = fuse(
        [_sinyal("multimodal.scene_claim", 0.95), _sinyal("provenance.match", 0.95)],
        dogrulayan,
        None,
        None,
    )
    assert verdict is not Verdict.YANLIS_BAGLAM, "köken doğrulaması sahneyi bastırmalı"


def test_koken_celiskisi_sahneden_once_gelir() -> None:
    """Köken çelişkisi varsa sınıf ondan kurulur; sahne dalına düşülmez."""
    celisen = ProvenanceMatch(
        matched=True, similarity=0.95, context_conflict=True, original_location="Hatay"
    )
    verdict, _, katkilar = fuse(
        [_sinyal("provenance.match", 0.95), _sinyal("multimodal.scene_claim", 0.85)],
        celisen,
        None,
        None,
    )
    assert verdict is Verdict.YANLIS_BAGLAM
    assert any(s.key == "provenance.match" for s in katkilar), "kanıt kökenden gelmeli"


@pytest.mark.parametrize(
    ("anahtar", "beklenen"),
    [
        ("synthetic.video", Verdict.SENTETIK_MEDYA),
        ("multimodal.av_sync", Verdict.MANIPULE_MEDYA),
    ],
)
def test_daha_guclu_bulgular_sahneyi_gecer(anahtar: str, beklenen: Verdict) -> None:
    """ "İçerik üretilmiş/değiştirilmiş", "sahne uyuşmuyor"dan güçlüdür.

    Sıralama ilk sürümde tersti ve sentetik medya senaryosu YANLIŞ_BAĞLAM
    olarak sınıflanıyordu.
    """
    verdict, _, _ = fuse(
        [_sinyal(anahtar, 0.90), _sinyal("multimodal.scene_claim", 0.90)], None, None, None
    )
    assert verdict is beklenen
