"""Gerçek görsel yükleme uçlarının testleri.

Etik protokolün KVKK taahhüdü burada kilitlenir: yüklenen görsel yalnızca
analiz süresince, sahibine özel izinlerle diskte durur ve sonra silinir.
"""

from __future__ import annotations

import io
import stat
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from krizkalkan_api import media
from krizkalkan_api.main import app
from krizkalkan_api.seed import seed
from krizkalkan_core.pipeline import pipeline


@pytest.fixture(autouse=True)
def _fresh_store() -> None:
    seed()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def temp_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Geçici dosyaları izlenebilir bir dizine yönlendirir."""
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path


def _png(size: int = 64) -> bytes:
    """Dokulu (gürültülü) bir görsel — düz görsel köken aramasından çekinir."""
    import random

    from PIL import Image

    rastgele = random.Random(0)
    image = Image.new("RGB", (size, size))
    image.putdata([tuple(rastgele.randrange(256) for _ in range(3)) for _ in range(size * size)])
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_gorsel_analizi_medya_modullerini_calistirir(client: TestClient) -> None:
    r = client.post(
        "/api/analyze/media",
        files={"file": ("deprem.png", _png(), "image/png")},
        data={"body": "Hatay'da deprem sonrası yıkım"},
    )
    assert r.status_code == 200
    # İndekste karşılığı olmayan görsel: köken kesin değil, pahalı medya
    # modülleri de gerçek dosya üzerinde çalışır.
    assert {"M1", "M2", "M4"} <= set(r.json()["modules_run"])


def test_gecici_dosya_yalnizca_analiz_suresince_var(
    client: TestClient, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gorulen: dict[str, object] = {}
    asil = pipeline.analyse

    def izleyen(**kwargs: object):  # type: ignore[no-untyped-def]
        yol = Path(str(kwargs["media_fingerprint"]))
        gorulen["vardi"] = yol.is_file()
        gorulen["izin"] = stat.S_IMODE(yol.stat().st_mode)
        gorulen["dizin"] = yol.parent
        return asil(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(pipeline, "analyse", izleyen)
    r = client.post("/api/analyze/media", files={"file": ("a.png", _png(), "image/png")})

    assert r.status_code == 200
    assert gorulen["vardi"] is True
    assert gorulen["izin"] == 0o600
    assert gorulen["dizin"] == temp_dir
    assert list(temp_dir.glob(f"{media.TEMP_PREFIX}*")) == []


def test_gorsel_olmayan_dosya_reddedilir(client: TestClient, temp_dir: Path) -> None:
    r = client.post(
        "/api/analyze/media",
        files={"file": ("sahte.jpg", b"bu bir goruntu degil", "image/jpeg")},
    )
    assert r.status_code == 415
    assert list(temp_dir.iterdir()) == []


def test_sinir_asan_dosya_reddedilir(
    client: TestClient, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(media, "MAX_BYTES", 100)
    r = client.post("/api/analyze/media", files={"file": ("buyuk.png", _png(), "image/png")})
    assert r.status_code == 413
    assert list(temp_dir.iterdir()) == []


def test_gorselli_gonderi_yayimlanir_ve_dosya_saklanmaz(client: TestClient, temp_dir: Path) -> None:
    r = client.post(
        "/api/posts/media",
        files={"file": ("ayse_yilmaz_evim.png", _png(), "image/png")},
        data={"body": "Mahallemizden görüntü", "audience": "herkes"},
    )
    assert r.status_code == 201
    post = r.json()
    assert post["media"]["uploaded"] is True
    assert post["media"]["kind"] == "image"
    assert post["analysis"]["intervention"]["content_removed"] is False
    # Dosya adı kişisel bilgi taşıyabilir; gönderiye hiçbir biçimde girmez.
    assert "ayse" not in r.text.casefold()
    assert list(temp_dir.glob(f"{media.TEMP_PREFIX}*")) == []

    akis = client.get("/api/posts").json()
    assert akis[0]["id"] == post["id"]


# ────────────────────────── video ──────────────────────────


def _mp4(kare: int = 40) -> bytes:
    """Hareketli bir kare içeren gerçek bir MP4."""
    cv2 = pytest.importorskip("cv2", reason="opencv kurulu değil")
    import numpy as np

    with tempfile.TemporaryDirectory() as dizin:
        yol = Path(dizin) / "v.mp4"
        yazici = cv2.VideoWriter(str(yol), cv2.VideoWriter_fourcc(*"mp4v"), 25.0, (160, 96))
        for i in range(kare):
            tuval = np.full((96, 160, 3), 40, np.uint8)
            tuval[30:50, (i * 3) % 140 : (i * 3) % 140 + 20] = (0, 200, 255)
            yazici.write(tuval)
        yazici.release()
        return yol.read_bytes()


def test_video_analizi_video_olarak_isler(client: TestClient, temp_dir: Path) -> None:
    video = _mp4()
    r = client.post(
        "/api/analyze/media",
        # İstemcinin bildirdiği tür ve ad yanlış: tür baytlardan tanınır.
        files={"file": ("dosya.bin", video, "application/octet-stream")},
        data={"body": "Deprem anı"},
    )
    assert r.status_code == 200
    sonuc = r.json()
    assert "video" in sonuc["modalities"]
    assert "M4" in sonuc["modules_run"]
    assert any(s["key"] == "synthetic.video_clip" for s in sonuc["signals"])
    # Ne video ne anahtar kare sunucuda kalır.
    assert list(temp_dir.iterdir()) == []


def test_videolu_gonderi_video_olarak_yayimlanir(client: TestClient, temp_dir: Path) -> None:
    r = client.post(
        "/api/posts/media",
        files={"file": ("ayse_yilmaz.mp4", _mp4(), "video/mp4")},
        data={"body": "Sel görüntüsü", "audience": "herkes"},
    )
    assert r.status_code == 201
    post = r.json()
    assert post["media"] == {**post["media"], "kind": "video", "uploaded": True}
    assert "ayse" not in r.text.casefold()
    assert list(temp_dir.iterdir()) == []


def test_heic_video_sanilmaz(client: TestClient, temp_dir: Path) -> None:
    """`ftyp` kutusu HEIC/AVIF görsellerde de var; bunlar video yoluna girmez."""
    heic = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 64
    r = client.post("/api/analyze/media", files={"file": ("a.heic", heic, "image/heic")})
    assert r.status_code == 415
    assert list(temp_dir.iterdir()) == []


#: Kapsayıcı başlığı geçerli (`ftyp` · mp42) ama tek bir kare bile taşımayan dosya.
_BOZUK_MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 256


def test_cozulemeyen_video_reddedilir(client: TestClient, temp_dir: Path) -> None:
    """Kare çözücü varken bozuk video analize hiç girmez."""
    pytest.importorskip("cv2", reason="opencv kurulu değil")
    r = client.post("/api/analyze/media", files={"file": ("a.mp4", _BOZUK_MP4, "video/mp4")})
    assert r.status_code == 415
    assert list(temp_dir.iterdir()) == []


def test_opencv_yoksa_video_kabul_edilir_ve_m4_cekinir(
    client: TestClient, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OpenCV'siz kurulumda (ör. yalnızca `[dev]`) video reddedilmez, sistem çökmez.

    Dosyanın çözülüp çözülemediği bilinemez; karar analize bırakılır ve M4
    "bilmiyorum" der. Bu, model katmanı kapalıyken kural yoluna düşmenin
    video karşılığıdır.
    """
    monkeypatch.setitem(sys.modules, "cv2", None)  # import cv2 → ImportError
    r = client.post("/api/analyze/media", files={"file": ("a.mp4", _BOZUK_MP4, "video/mp4")})

    assert r.status_code == 200
    klip = next(s for s in r.json()["signals"] if s["key"] == "synthetic.video_clip")
    assert klip["abstained"] is True
    assert list(temp_dir.iterdir()) == []


def test_sinir_asan_video_reddedilir(
    client: TestClient, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Boyut, çözme denemesinden ÖNCE denetlenir: OpenCV gerekmez.
    monkeypatch.setattr(media, "MAX_VIDEO_BYTES", 100)
    r = client.post("/api/analyze/media", files={"file": ("a.mp4", _BOZUK_MP4, "video/mp4")})
    assert r.status_code == 413
    assert list(temp_dir.iterdir()) == []
