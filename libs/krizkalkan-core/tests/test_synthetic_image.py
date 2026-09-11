"""M4 · sentetik görüntü detektörü — yedek yol, çekinme ve sözleşme.

Bu testler ağırlık gerektirmez ve gerektirmemelidir: sürekli tümleştirmede
`models/` dizini boştur. Korudukları davranış şudur — **ağırlık yokken modül
bugünkü sözlük yoluyla eksiksiz çalışır, ağırlık varken sözleşme değişmez.**

Model yolu, sözleşmeye uyan sahte bir detektörle sınanır. Ağırlığın kendisinin
ne kadar iyi olduğu burada değil `scripts/eval/m4_synthetic.py` içinde ölçülür;
testin işi doğruluk değil, davranıştır.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from krizkalkan_core.synthetic import engine as synthetic
from krizkalkan_core.synthetic import image
from krizkalkan_core.synthetic.image import (
    ASGARI_BAYT_PIKSEL,
    ASGARI_KENAR,
    GoruntuSonucu,
    SentetikGoruntuModeli,
)

PIL = pytest.importorskip("PIL", reason="pillow kurulu değil")


def _anahtarlar(sinyaller) -> set[str]:
    return {s.key for s in sinyaller}


def _sinyal(sinyaller, anahtar):
    return next((s for s in sinyaller if s.key == anahtar), None)


def _goruntu_yaz(yol: Path, kenar: int = 640, kalite: int = 92) -> Path:
    """Gerçek bir JPEG üretir — sıkıştırma oranı ölçümü gerçek dosya ister."""
    from PIL import Image

    rastgele = __import__("random").Random(0)
    goruntu = Image.new("RGB", (kenar, kenar))
    goruntu.putdata(
        [(rastgele.randrange(256), rastgele.randrange(256), 0) for _ in range(kenar**2)]
    )
    goruntu.save(yol, format="JPEG", quality=kalite)
    return yol


# ────────────────────────── yedek yol ──────────────────────────


def test_agirlik_yokken_sozluk_yolu_calisir(monkeypatch) -> None:
    """Ağırlık yoksa modül çökmez; bugünkü davranışını aynen sürdürür."""
    monkeypatch.setattr(image, "get", lambda: None)

    sinyaller = synthetic.analyse("ai-uretilmis-deprem-videosu", "video", has_audio=True)

    assert "synthetic.video" in _anahtarlar(sinyaller)
    video = _sinyal(sinyaller, "synthetic.video")
    assert video is not None and not video.abstained
    # Sözlük yolu "ai-" işaretini görüp yüksek skor üretmeli — eski davranış.
    assert video.score >= 0.7


def test_demo_parmak_izi_modelden_etkilenmez(monkeypatch) -> None:
    """Demo senaryoları dosya değildir; model yüklü olsa bile sözlükten geçer."""

    class PatlayanModel:
        def incele(self, yol):  # pragma: no cover — çağrılmamalı
            raise AssertionError("demo parmak izi için model çağrılmamalıydı")

    monkeypatch.setattr(image, "get", lambda: PatlayanModel())

    sinyaller = synthetic.analyse("c2pa-ai-imzali-gorsel", "image", has_audio=False)
    assert "synthetic.video" in _anahtarlar(sinyaller)


def test_ood_isaretinde_cekinilir(monkeypatch) -> None:
    monkeypatch.setattr(image, "get", lambda: None)

    sinyaller = synthetic.analyse("dusuk-cozunurluk-klip", "video", has_audio=False)

    video = _sinyal(sinyaller, "synthetic.video")
    assert video is not None and video.abstained
    assert "Yetersiz kanıt" in (video.abstain_reason or "")


# ────────────────────────── model yolu ──────────────────────────


@dataclass
class SahteModel:
    """Sözleşmeye uyan sahte detektör."""

    sonuc: GoruntuSonucu

    def incele(self, yol: Path) -> GoruntuSonucu:
        return self.sonuc


def test_model_yolu_iki_sinyal_uretir(monkeypatch, tmp_path: Path) -> None:
    """Üretim ve tür sinyalleri AYRI taşınır: tek skor taksonomiyi taşıyamaz."""
    dosya = _goruntu_yaz(tmp_path / "ornek.jpg")
    monkeypatch.setattr(
        image,
        "get",
        lambda: SahteModel(
            GoruntuSonucu(
                uretim_skoru=0.91,
                tur="sentetik",
                tur_skorlari={"sentetik": 0.88, "manipüle": 0.07, "gerçek": 0.05},
                genislik=640,
                yukseklik=640,
                bayt_piksel=0.4,
            )
        ),
    )

    sinyaller = synthetic.analyse(str(dosya), "image", has_audio=False)

    assert {"synthetic.video", "synthetic.manipulation"} <= _anahtarlar(sinyaller)
    video = _sinyal(sinyaller, "synthetic.video")
    assert video is not None and video.score == pytest.approx(0.91)
    assert not video.abstained
    assert video.evidence and video.evidence[0].detail is not None

    tur = _sinyal(sinyaller, "synthetic.manipulation")
    assert tur is not None and tur.score == pytest.approx(0.07)


def test_model_cekinirse_sinyal_cekinir(monkeypatch, tmp_path: Path) -> None:
    dosya = _goruntu_yaz(tmp_path / "ornek.jpg")
    monkeypatch.setattr(
        image,
        "get",
        lambda: SahteModel(GoruntuSonucu(cekinme_nedeni="çözünürlük çalışma aralığının altında")),
    )

    sinyaller = synthetic.analyse(str(dosya), "image", has_audio=False)

    video = _sinyal(sinyaller, "synthetic.video")
    assert video is not None and video.abstained
    assert video.score == 0.0
    # Çekinirken tür sinyali hiç üretilmez: bilinmeyen bir şeyin türü olmaz.
    assert "synthetic.manipulation" not in _anahtarlar(sinyaller)


def test_okunamayan_dosyada_sozluge_dusulmez(monkeypatch, tmp_path: Path) -> None:
    """Gerçek dosya çözümlenemiyorsa dosya ADINDA kelime aranmaz, çekinilir.

    Sözlük yolu yalnızca demo tanımlayıcıları için anlamlıdır. Gerçek bir medya
    dosyasının adına bakıp "sentetik" demek, uydurma bir cevaptır.
    """
    bozuk = tmp_path / "ai-uretilmis.mp4"
    bozuk.write_bytes(b"bu bir video degil")

    class PatlayanModel:
        def incele(self, yol):
            raise OSError("görüntü olarak açılamadı")

    monkeypatch.setattr(image, "get", lambda: PatlayanModel())

    sinyaller = synthetic.analyse(str(bozuk), "video", has_audio=False)

    video = _sinyal(sinyaller, "synthetic.video")
    assert video is not None and video.abstained
    assert "ffmpeg" in (video.abstain_reason or "")


# ────────────────────────── çekinme mantığı ──────────────────────────


def _cikarim_modeli() -> SentetikGoruntuModeli:
    """ONNX oturumu olmadan yalnızca çekinme dallarını sınamak için örnek.

    Dağılım dışı kontrolleri modelden ÖNCE çalışır; bu yüzden oturumlara hiç
    dokunulmadan sınanabilirler. Bu, testin ağırlık gerektirmemesinin sebebidir.
    """
    import numpy as np

    model = SentetikGoruntuModeli.__new__(SentetikGoruntuModeli)
    model._np = np
    model._onisleme = {}
    return model


def test_dusuk_cozunurlukte_model_calistirilmaz(tmp_path: Path) -> None:
    kucuk = _goruntu_yaz(tmp_path / "kucuk.jpg", kenar=ASGARI_KENAR - 32)

    sonuc = _cikarim_modeli().incele(kucuk)

    assert sonuc.cekindi
    assert "çözünürlük" in (sonuc.cekinme_nedeni or "")
    assert sonuc.uretim_skoru == 0.0


def test_asiri_sikistirmada_model_calistirilmaz(tmp_path: Path) -> None:
    """Tek renkli, ağır sıkıştırılmış bir görüntü çok düşük bayt/piksel verir."""
    from PIL import Image

    yol = tmp_path / "duz.jpg"
    Image.new("RGB", (1024, 1024), (128, 128, 128)).save(yol, format="JPEG", quality=5)
    assert yol.stat().st_size / (1024 * 1024) < ASGARI_BAYT_PIKSEL

    sonuc = _cikarim_modeli().incele(yol)

    assert sonuc.cekindi
    assert "sıkıştırma" in (sonuc.cekinme_nedeni or "")


def test_cekinilen_sonucta_tur_skorlari_sifirlanir() -> None:
    """Çekinme hâlinde hiçbir skor karara sızmamalı."""
    sonuc = GoruntuSonucu(
        uretim_skoru=0.95,
        tur="manipüle",
        tur_skorlari={"sentetik": 0.1, "manipüle": 0.85, "gerçek": 0.05},
        cekinme_nedeni="iki detektör çelişti",
        uyusmazlik=True,
    )

    assert sonuc.cekindi
    assert sonuc.manipulasyon_skoru == 0.0
    assert sonuc.sentetik_skoru == 0.0


# ────────────────────────── füzyon sözleşmesi ──────────────────────────


def test_tur_sinyali_tek_basina_sinif_kurmaz() -> None:
    """`synthetic.manipulation` kanıttır, karar değildir.

    Ölçüldü (docs/metrikler/m4.md · bölüm 4): üç sınıflı detektör tamamı gerçek
    olan kümelerde de üretilmiş sınıflarından birini seçiyor ve "gerçek"
    sınıfına ortalama 0,001–0,004 olasılık veriyor. Bu sinyal karara katılırsa
    gerçek afet fotoğrafları sentetik/manipüle sınıflanır.

    Test bu kararı kilitler: sinyal yükselse bile tek başına sınıf kurmamalı.
    """
    from krizkalkan_core.fusion import engine as fusion
    from krizkalkan_core.schemas import Signal
    from krizkalkan_core.taxonomy import Verdict

    sinyaller = [
        Signal(
            module="M4",
            key="synthetic.manipulation",
            label="Gerçek içerik üzerinde oynama izi",
            score=0.99,
            raw_score=0.99,
        ),
        Signal(
            module="M4",
            key="synthetic.video",
            label="Görüntüde sentetik üretim izi",
            score=0.05,
            raw_score=0.05,
        ),
    ]

    sinif, _, _ = fusion.fuse(sinyaller, None, None, None)

    assert sinif not in (Verdict.SENTETIK_MEDYA, Verdict.MANIPULE_MEDYA)
