"""Gerçek dosya yolunun davranışı.

Kullanıcı yüklemesi açıldığında boru hattı ilk kez keyfi görüntüler görür.
Bu testler iki hatayı kilitler: gerçek dosyanın demo sözlük yoluna düşüp dosya
adından skor üretmesi ve bilgi taşımayan bir karmanın indekste eşleşmesi.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from krizkalkan_core.models import runtime
from krizkalkan_core.models.registry import registry
from krizkalkan_core.multimodal import engine as multimodal
from krizkalkan_core.multimodal import scene
from krizkalkan_core.pipeline import pipeline
from krizkalkan_core.provenance import engine as provenance
from krizkalkan_core.provenance import index
from krizkalkan_core.provenance.index import _gorunen_metin
from krizkalkan_core.taxonomy import Verdict


@pytest.fixture
def duz_gorsel(tmp_path: Path) -> Path:
    image = pytest.importorskip("PIL.Image", reason="pillow kurulu değil")

    yol = tmp_path / "duz.png"
    image.new("RGB", (640, 480), (120, 90, 60)).save(yol)
    return yol


class _IzleyenIndeks:
    """Sorgulanıp sorgulanmadığını kaydeden sahte indeks."""

    def __init__(self) -> None:
        self.soruldu = False

    def __len__(self) -> int:
        return 1

    def ara(self, dhash: int, phash: int, k: int = 3) -> list[object]:
        self.soruldu = True
        return []


def test_duz_gorsel_indekste_aranmaz(duz_gorsel: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Karma hesaplanamazsa modül "okunamadı" diye çekinir; ölçülen şey o değil.
    pytest.importorskip("imagehash", reason="imagehash kurulu değil")
    sahte = _IzleyenIndeks()
    monkeypatch.setattr(index, "get", lambda: sahte)

    match, sinyaller = provenance.analyse(str(duz_gorsel), "Hatay")

    assert sahte.soruldu is False
    assert match is None
    assert sinyaller[0].abstained
    assert "ayırt edici" in (sinyaller[0].abstain_reason or "")


def test_indeks_yoksa_gercek_dosya_demo_korpusuna_dusmez(
    duz_gorsel: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(index, "get", lambda: None)
    match, sinyaller = provenance.analyse(str(duz_gorsel), None)
    assert match is None
    assert sinyaller[0].abstained
    assert "indeksi yüklü değil" in (sinyaller[0].abstain_reason or "")


def test_sahne_modeli_yoksa_gercek_dosya_cekinir(
    duz_gorsel: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sözlük yolu dosya adında dayanak bulamayınca 0,55–0,78 çelişki üretiyordu."""
    monkeypatch.setattr(scene, "get", lambda: None)
    sinyaller = multimodal.analyse(
        str(duz_gorsel), "image", False, [], "Hatay'da deprem sonrası yıkım"
    )
    sahne = [s for s in sinyaller if s.key == "multimodal.scene_claim"]
    assert len(sahne) == 1
    assert sahne[0].abstained
    assert sahne[0].raw_score == 0.0


@pytest.mark.parametrize("modeller", [True, False])
def test_duz_gorsel_yanlis_baglam_almaz(
    duz_gorsel: Path, modeller: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Ayarlar içe aktarılırken okunur; ortam değişkeni sonradan etkisizdir.
    monkeypatch.setattr(runtime.settings, "models", modeller)
    registry.reset()
    pipeline.clear_cache()
    try:
        sonuc = pipeline.analyse(
            body="Hatay'da deprem sonrası yıkım",
            media_kind="image",
            media_fingerprint=str(duz_gorsel),
        )
    finally:
        registry.reset()
        pipeline.clear_cache()
    assert sonuc.verdict is not Verdict.YANLIS_BAGLAM


@pytest.mark.parametrize(
    ("ham", "beklenen"),
    [
        ('20 March 1993<div style="display: none;"', "20 March 1993"),
        ("2023-02-06 04:17", "2023-02-06 04:17"),
        ("<span>gizli</span>", None),
        (None, None),
        ("", None),
    ],
)
def test_commons_tarihindeki_html_ayiklanir(ham: str | None, beklenen: str | None) -> None:
    assert _gorunen_metin(ham) == beklenen
