"""API uç noktalarının davranış testleri."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from krizkalkan_api.main import app
from krizkalkan_api.seed import seed


@pytest.fixture(autouse=True)
def _fresh_store() -> None:
    seed()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_saglik(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_akis_doldurulmus(client: TestClient) -> None:
    posts = client.get("/api/posts").json()
    assert len(posts) >= 10
    assert all(p["analysis"] is not None for p in posts)


def test_akista_hicbir_icerik_kaldirilmamis(client: TestClient) -> None:
    posts = client.get("/api/posts").json()
    assert all(p["analysis"]["intervention"]["content_removed"] is False for p in posts)


def test_akis_tum_mudahale_seviyelerini_kapsar(client: TestClient) -> None:
    """Demo akışı beş seviyenin tamamını ve Kural 0'ı göstermelidir."""
    posts = client.get("/api/posts").json()
    levels = {p["analysis"]["intervention"]["level"] for p in posts}
    assert {"SEVIYE_0", "SEVIYE_1", "SEVIYE_2", "SEVIYE_3", "SEVIYE_4"} <= levels
    assert any(p["analysis"]["intervention"]["protected_by_rule_zero"] for p in posts)


def test_analiz_ucnoktasi(client: TestClient) -> None:
    r = client.post(
        "/api/analyze",
        json={
            "body": "Şanlıurfa'da az önce çekildi! Bina yıkıldı.",
            "media_kind": "video",
            "media_fingerprint": "deprem-yikim-hatay-2023",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["verdict"] == "YANLIŞ_BAĞLAM"
    assert data["provenance"]["first_published"] == "08.02.2023"
    assert len(data["signals"]) > 0


def test_gonderi_olusturma_engellenmez(client: TestClient) -> None:
    """Paylaşım hiçbir koşulda engellenmez; yalnızca analiz iliştirilir."""
    r = client.post(
        "/api/posts",
        json={
            "body": "Vali konuşma yaptı, şehir tahliye ediliyor.",
            "media_kind": "video",
            "media_fingerprint": "ai-klon-yetkili-ses",
        },
    )
    assert r.status_code == 201
    post = r.json()
    assert post["analysis"]["verdict"] == "SENTETİK_MEDYA"
    assert post["analysis"]["intervention"]["content_removed"] is False


def test_moderasyon_kuyrugu_yayilima_gore_sirali(client: TestClient) -> None:
    queue = client.get("/api/moderation/queue").json()
    speeds = [i["spread_per_minute"] for i in queue]
    assert speeds == sorted(speeds, reverse=True)


def test_korunan_yardim_cagrisi_kuyruga_girmez(client: TestClient) -> None:
    queue = client.get("/api/moderation/queue").json()
    posts = {p["id"]: p for p in client.get("/api/posts").json()}
    for item in queue:
        assert posts[item["post_id"]]["analysis"]["intervention"]["protected_by_rule_zero"] is False


def test_itiraz_akisi(client: TestClient) -> None:
    post_id = client.get("/api/moderation/queue").json()[0]["post_id"]
    created = client.post(
        "/api/moderation/appeals",
        json={"post_id": post_id, "reason": "Etiket yanlış", "note": "Kaynak var"},
    )
    assert created.status_code == 201
    appeal = created.json()
    assert appeal["status"] == "bekliyor"

    resolved = client.post(f"/api/moderation/appeals/{appeal['id']}/resolve?accepted=true")
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "kabul"


def test_denetim_kaydi_kural_sifiri_iceriyor(client: TestClient) -> None:
    audit = client.get("/api/moderation/audit?limit=100").json()
    assert any(e["action"] == "koruma_kuralı_uygulandı" for e in audit)


def test_radar_sayaclari(client: TestClient) -> None:
    radar = client.get("/api/radar").json()
    assert radar["removed_content"] == 0
    assert radar["protected_help_calls"] >= 1
    assert radar["analyzed_count"] >= 10


def test_metrikler(client: TestClient) -> None:
    m = client.get("/api/metrics").json()
    assert m["total_analyses"] > 0
    assert m["removed_content"] == 0
    assert m["latency_p50_ms"] >= 0


def test_demo_sifirlama(client: TestClient) -> None:
    r = client.post("/api/demo/reset")
    assert r.status_code == 200
    assert r.json()["gönderi"] >= 10
