"""Gerçek görsel yükleme uçlarının testleri.

Etik protokolün KVKK taahhüdü burada kilitlenir: yüklenen görsel yalnızca
analiz süresince, sahibine özel izinlerle diskte durur ve sonra silinir.
"""

from __future__ import annotations

import io
import stat
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
