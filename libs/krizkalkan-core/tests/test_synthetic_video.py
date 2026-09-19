"""M4 · sentetik video — kare seçimi, çekinme ve sözleşme.

Ağırlık gerektirmez: sürekli tümleştirmede `models/` dizini boştur. Model yolu
sözleşmeye uyan sahte bir detektörle sınanır; ağırlığın ne kadar iyi olduğu
`scripts/eval/m4_video.py` içinde ölçülür. Tek istisna en alttaki test: ağırlık
diskteyse uçtan uca çıkarımı sınar, yoksa atlanır.

OpenCV `[models]` ekindedir ve CI yalnızca `[dev]` kurar. Bu yüzden OpenCV
YALNIZCA gerçekten video çözen testlerde istenir; motor sözleşmesi ve füzyon
testleri onsuz da çalışır ve CI'da atlanmaz.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from krizkalkan_core import medya
from krizkalkan_core.fusion.engine import SENTETIK_KANIT_ESIGI, apply_calibration, fuse
from krizkalkan_core.models.runtime import model_root
from krizkalkan_core.multimodal import engine as multimodal
from krizkalkan_core.pipeline import AnalysisPipeline
from krizkalkan_core.schemas import Signal
from krizkalkan_core.synthetic import engine as synthetic
from krizkalkan_core.synthetic import video
from krizkalkan_core.synthetic.engine import VIDEO_KLIP_ANAHTARI
from krizkalkan_core.synthetic.video import KareOrnekleyici, VideoSonucu
from krizkalkan_core.taxonomy import Verdict

AYAR = {
    "kare_sayisi": 32,
    "boyut": 224,
    "akis_boyutu": 112,
    "hareket_ornekleme": True,
    "farneback": [0.5, 3, 15, 3, 5, 1.2, 0],
}


def _video_yaz(yol: Path, kare: int = 60, genislik: int = 160, yukseklik: int = 96) -> Path:
    """Hareketli bir kare içeren gerçek bir MP4 üretir; OpenCV yoksa testi atlar."""
    cv2 = pytest.importorskip("cv2", reason="opencv kurulu değil")
    np = pytest.importorskip("numpy", reason="numpy kurulu değil")
    yazici = cv2.VideoWriter(str(yol), cv2.VideoWriter_fourcc(*"mp4v"), 25.0, (genislik, yukseklik))
    for i in range(kare):
        tuval = np.full((yukseklik, genislik, 3), 40, np.uint8)
        x = (i * 3) % (genislik - 20)
        tuval[30:50, x : x + 20] = (0, 200, 255)
        yazici.write(tuval)
    yazici.release()
    return yol


def _dosya(yol: Path) -> Path:
    """Video uzantılı gerçek bir dosya — içeriği çözülmez, yalnızca yolu sınanır.

    Motor sözleşmesi testleri sahte detektör kullanır; dosyanın yalnızca diskte
    var olması gerekir. Böylece OpenCV'siz kurulumda da çalışırlar.
    """
    yol.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    return yol


def _sinyal(sinyaller, anahtar):
    return next((s for s in sinyaller if s.key == anahtar), None)


class SahteVideoModeli:
    """`SentetikVideoModeli` sözleşmesine uyan, ağırlıksız detektör."""

    def __init__(self, sonuc: VideoSonucu) -> None:
        self.sonuc = sonuc
        self.cagrilar: list[Path] = []

    def incele(self, yol):
        self.cagrilar.append(Path(yol))
        return self.sonuc


# ────────────────────────── kare seçimi ──────────────────────────


def test_hareket_duyarli_secim_32_sirali_kare_verir(tmp_path: Path) -> None:
    yol = _video_yaz(tmp_path / "a.mp4", kare=90)
    secilen = KareOrnekleyici(AYAR).sec(yol, 90)

    assert len(secilen) == 32
    assert secilen == sorted(secilen)
    assert all(0 <= i < 90 for i in secilen)


def test_kisa_videoda_son_kare_tekrarlanir(tmp_path: Path) -> None:
    """32'den az kareli videoda eğitimdeki gibi son kare tekrarlanır."""
    yol = _video_yaz(tmp_path / "kisa.mp4", kare=10)
    secilen = KareOrnekleyici(AYAR).sec(yol, 10)

    assert secilen == [*range(10), *([9] * 22)]


def test_okunan_tensor_modelin_girisine_uyar(tmp_path: Path) -> None:
    """[0,1] aralığı, RGB, 224×224 — ResNet normalizasyonu modelin içindedir."""
    yol = _video_yaz(tmp_path / "a.mp4")
    import numpy as np

    ornekleyici = KareOrnekleyici(AYAR)
    kareler = ornekleyici.oku(yol, ornekleyici.sec(yol, 60))

    assert kareler.shape == (32, 224, 224, 3)
    assert kareler.dtype == np.float32
    assert float(kareler.min()) >= 0.0 and float(kareler.max()) <= 1.0
    # Hareketli kare BGR (0,200,255) yazıldı → RGB'de kırmızı kanal baskın.
    parlak = kareler[kareler.sum(axis=-1) > 1.5]
    assert parlak.size and float(parlak[:, 0].mean()) > float(parlak[:, 2].mean())


# ────────────────────────── M4 motoru ──────────────────────────


def test_video_dosyasi_video_modeline_gider(monkeypatch, tmp_path: Path) -> None:
    yol = _dosya(tmp_path / "klip.mp4")
    sahte = SahteVideoModeli(VideoSonucu(uretim_skoru=0.93, secilen_kareler=list(range(32))))
    monkeypatch.setattr(video, "get", lambda: sahte)

    sinyaller = synthetic.analyse(str(yol), "video", has_audio=False)

    klip = _sinyal(sinyaller, VIDEO_KLIP_ANAHTARI)
    assert sahte.cagrilar == [yol]
    assert klip is not None and not klip.abstained
    assert klip.raw_score == 0.93
    assert "üretim izi bulundu" in klip.evidence[0].label
    # Görüntü detektörü videoya hiç sorulmaz.
    assert _sinyal(sinyaller, "synthetic.video") is None


def test_model_yoksa_sozluge_dusulmez_cekinilir(monkeypatch, tmp_path: Path) -> None:
    """Dosya adındaki 'ai-uretilmis' gerçek bir dosyada hiçbir skora dönüşmez."""
    yol = _dosya(tmp_path / "ai-uretilmis-deepfake.mp4")
    monkeypatch.setattr(video, "get", lambda: None)

    sinyaller = synthetic.analyse(str(yol), "video", has_audio=True)

    klip = _sinyal(sinyaller, VIDEO_KLIP_ANAHTARI)
    assert klip is not None and klip.abstained
    assert "Video modeli kullanılamıyor" in (klip.abstain_reason or "")
    assert all(s.abstained or s.raw_score == 0.0 for s in sinyaller)


def test_cekinen_model_skor_uretmez(monkeypatch, tmp_path: Path) -> None:
    yol = _dosya(tmp_path / "uzun.mp4")
    sahte = SahteVideoModeli(
        VideoSonucu(cekinme_nedeni="video süresi modelin çalışma aralığının dışında")
    )
    monkeypatch.setattr(video, "get", lambda: sahte)

    klip = _sinyal(synthetic.analyse(str(yol), "video", False), VIDEO_KLIP_ANAHTARI)

    assert klip.abstained and klip.score == 0.0
    assert "çalışma aralığının dışında" in (klip.abstain_reason or "")


def test_gercek_dosyada_ses_ve_ustveri_uydurulmaz(monkeypatch, tmp_path: Path) -> None:
    """Ses modeli yok ve üstveri tarayıcısı videoda ölçülmedi: ikisi de çekinir."""
    yol = _dosya(tmp_path / "klon-sentetik-ses.mp4")
    monkeypatch.setattr(video, "get", lambda: None)

    sinyaller = synthetic.analyse(str(yol), "video", has_audio=True)

    ses = _sinyal(sinyaller, "synthetic.audio")
    ustveri = _sinyal(sinyaller, "synthetic.metadata")
    assert ses.abstained and "kurulmadı" in (ses.abstain_reason or "")
    assert ustveri.abstained and "okunmuyor" in (ustveri.abstain_reason or "")


def test_gercek_dosyada_dudak_ses_uyumu_uydurulmaz(tmp_path: Path) -> None:
    yol = _dosya(tmp_path / "senkronsuz.mp4")

    sinyaller = multimodal.analyse(str(yol), "video", True, [], "")

    av = _sinyal(sinyaller, "multimodal.av_sync")
    assert av is not None and av.abstained
    assert _sinyal(sinyaller, "multimodal.speaker_face") is None


def test_bozuk_video_gercek_modelde_cekinir(tmp_path: Path) -> None:
    """Çözülemeyen dosyada ağ hiç çalıştırılmaz — oturum gerekmez."""
    pytest.importorskip("cv2", reason="opencv kurulu değil")
    bozuk = tmp_path / "bozuk.mp4"
    bozuk.write_bytes(b"\x00\x00\x00\x18ftypmp42 bu bir video degil")
    model = video.SentetikVideoModeli.__new__(video.SentetikVideoModeli)
    model.karar_esigi = 0.55

    sonuc = model.incele(bozuk)

    assert sonuc.cekindi and "çözümlenemedi" in (sonuc.cekinme_nedeni or "")


def test_sure_siniri_asilinca_cekinilir(monkeypatch, tmp_path: Path) -> None:
    yol = _video_yaz(tmp_path / "a.mp4", kare=60)  # 2,4 sn
    monkeypatch.setattr(video, "AZAMI_SURE_SN", 1.0)
    model = video.SentetikVideoModeli.__new__(video.SentetikVideoModeli)
    model.karar_esigi = 0.55

    sonuc = model.incele(yol)

    assert sonuc.cekindi and "çalışma aralığının dışında" in (sonuc.cekinme_nedeni or "")


def test_opencv_yoksa_bozuk_dosya_denmez(monkeypatch, tmp_path: Path) -> None:
    """Kurulum eksiği kullanıcının dosyasına yüklenmez."""
    yol = _dosya(tmp_path / "klip.mp4")

    class OpenCVsizModel:
        def incele(self, yol):
            raise ModuleNotFoundError("No module named 'cv2'")

    monkeypatch.setattr(video, "get", lambda: OpenCVsizModel())

    klip = _sinyal(synthetic.analyse(str(yol), "video", False), VIDEO_KLIP_ANAHTARI)

    assert klip.abstained
    assert "OpenCV" in (klip.abstain_reason or "")
    assert "bozuk" not in (klip.abstain_reason or "")


# ────────────────────────── füzyon ──────────────────────────


def _klip(ham: float) -> Signal:
    return Signal(module="M4", key=VIDEO_KLIP_ANAHTARI, label="v", score=ham, raw_score=ham)


def test_model_esiginin_ustu_sentetik_medya_kurar() -> None:
    """Kalibrasyon modelin kendi eşiğini (P(üretilmiş) > 0,55) korur."""
    sinyaller = apply_calibration([_klip(0.60)])
    assert sinyaller[0].score >= SENTETIK_KANIT_ESIGI

    karar, _, katkilar = fuse(sinyaller, None, None, None)
    assert karar is Verdict.SENTETIK_MEDYA
    assert [s.key for s in katkilar] == [VIDEO_KLIP_ANAHTARI]


def test_model_esiginin_alti_sentetik_demez() -> None:
    sinyaller = apply_calibration([_klip(0.40)])
    assert sinyaller[0].score < SENTETIK_KANIT_ESIGI

    karar, _, _ = fuse(sinyaller, None, None, None)
    assert karar is not Verdict.SENTETIK_MEDYA


# ────────────────────────── boru hattı ──────────────────────────


def test_boru_hatti_goruntu_modullerine_anahtar_kare_verir(monkeypatch, tmp_path: Path) -> None:
    """M1/M2 videonun anahtar karesini, M4 videonun kendisini görür; kare silinir."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    yol = _video_yaz(tmp_path / "klip.mp4")
    gorulen: dict[str, str | None] = {}

    from krizkalkan_core.provenance import engine as provenance

    asil_m1 = provenance.analyse

    def izleyen_m1(parmak, konum=None):
        gorulen["m1"] = parmak
        gorulen["m1_vardi"] = str(Path(parmak).is_file())
        return asil_m1(parmak, konum)

    sahte = SahteVideoModeli(VideoSonucu(uretim_skoru=0.10, secilen_kareler=list(range(32))))
    monkeypatch.setattr(provenance, "analyse", izleyen_m1)
    monkeypatch.setattr(video, "get", lambda: sahte)

    sonuc = AnalysisPipeline().analyse(
        body="Deprem bölgesinden görüntü", media_kind="video", media_fingerprint=str(yol)
    )

    assert Path(gorulen["m1"]).name.startswith(medya.KARE_ONEKI)
    assert gorulen["m1_vardi"] == "True"
    assert sahte.cagrilar == [yol]
    assert "M4" in sonuc.modules_run
    assert list(tmp_path.glob(f"{medya.KARE_ONEKI}*")) == []


# ────────────────────────── gerçek ağırlık (varsa) ──────────────────────────


@pytest.mark.skipif(
    not (model_root() / video.MODEL_ADI / "model.onnx").exists(),
    reason="M4 video ağırlığı yok (models/m4_video)",
)
def test_gercek_agirlikla_uctan_uca_cikarim(tmp_path: Path) -> None:
    yol = _video_yaz(tmp_path / "a.mp4", kare=90, genislik=320, yukseklik=180)
    model = video.SentetikVideoModeli(model_root() / video.MODEL_ADI)

    sonuc = model.incele(yol)

    assert not sonuc.cekindi
    assert 0.0 <= sonuc.uretim_skoru <= 1.0
    assert len(sonuc.secilen_kareler) == 32
    assert (sonuc.genislik, sonuc.yukseklik, sonuc.kare_sayisi) == (320, 180, 90)
