"""Model kayıt defteri — yedek yola düşüş garantileri.

Bu testlerin tek işi şunu güvence altına almaktır: **ağırlık yoksa sistem
çökmez.** Canlı sunumda ağırlık dizini boş bir makinede sistemin kural
tabanlı yoluyla çalışmaya devam etmesi, bu dosyanın koruduğu davranıştır.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from krizkalkan_core.models import runtime
from krizkalkan_core.models.cards import Measurement, ModelCard
from krizkalkan_core.models.registry import ModelRegistry, ModelSpec, ModelStatus


def _spec(loader=lambda _: object(), files=("model.onnx",), requires="onnx") -> ModelSpec:
    return ModelSpec(
        name="test_model",
        module="M3",
        title="Test modeli",
        files=files,
        loader=loader,
        requires_runtime=requires,
    )


@pytest.fixture
def kayit() -> ModelRegistry:
    r = ModelRegistry()
    r.register(_spec())
    return r


def test_modeller_kapaliyken_none_doner(kayit: ModelRegistry, monkeypatch) -> None:
    monkeypatch.setattr(runtime.settings, "models", False)
    assert kayit.get("test_model") is None
    assert kayit.status("test_model") is ModelStatus.KAPALI


def test_agirlik_yoksa_cokmez(kayit: ModelRegistry, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runtime.settings, "models", True)
    monkeypatch.setattr(runtime, "resolve_runtime", lambda: "onnx")
    monkeypatch.setattr(runtime, "model_root", lambda: tmp_path)

    assert kayit.get("test_model") is None
    assert kayit.status("test_model") is ModelStatus.AGIRLIK_YOK
    assert "kural tabanlı yol" in kayit.reason("test_model")


def test_calisma_zamani_yoksa_cokmez(kayit: ModelRegistry, monkeypatch) -> None:
    monkeypatch.setattr(runtime.settings, "models", True)
    monkeypatch.setattr(runtime, "resolve_runtime", lambda: "yok")

    assert kayit.get("test_model") is None
    assert kayit.status("test_model") is ModelStatus.CALISMA_ZAMANI_YOK


def test_yukleyici_patlarsa_istisna_sizmaz(monkeypatch, tmp_path: Path) -> None:
    """Yükleyicideki herhangi bir hata çağırana sızmamalıdır."""

    def bozuk_yukleyici(_: Path) -> object:
        raise RuntimeError("ağırlık dosyası bozuk")

    r = ModelRegistry()
    r.register(_spec(loader=bozuk_yukleyici))
    monkeypatch.setattr(runtime.settings, "models", True)
    monkeypatch.setattr(runtime, "resolve_runtime", lambda: "onnx")
    monkeypatch.setattr(runtime, "model_root", lambda: tmp_path)
    (tmp_path / "test_model").mkdir()
    (tmp_path / "test_model" / "model.onnx").touch()

    assert r.get("test_model") is None
    assert r.status("test_model") is ModelStatus.YUKLEME_HATASI
    assert "ağırlık dosyası bozuk" in r.reason("test_model")


def test_basarili_yukleme_bir_kez_calisir(monkeypatch, tmp_path: Path) -> None:
    cagri_sayisi = {"n": 0}

    def sayan_yukleyici(_: Path) -> str:
        cagri_sayisi["n"] += 1
        return "model"

    r = ModelRegistry()
    r.register(_spec(loader=sayan_yukleyici))
    monkeypatch.setattr(runtime.settings, "models", True)
    monkeypatch.setattr(runtime, "resolve_runtime", lambda: "onnx")
    monkeypatch.setattr(runtime, "model_root", lambda: tmp_path)
    (tmp_path / "test_model").mkdir()
    (tmp_path / "test_model" / "model.onnx").touch()

    assert r.get("test_model") == "model"
    assert r.get("test_model") == "model"
    assert cagri_sayisi["n"] == 1, "model yalnızca bir kez yüklenmeli (tembel önbellek)"
    assert r.status("test_model") is ModelStatus.HAZIR


def test_tanimsiz_model_none_doner(kayit: ModelRegistry) -> None:
    assert kayit.get("olmayan_model") is None


def test_model_karti_olcum_n_degerini_tasir(tmp_path: Path) -> None:
    """Her ölçüm, kümesi ve n değeriyle birlikte saklanmalıdır."""
    kart = ModelCard(
        name="m3_text",
        module="M3",
        title="Türkçe Kriz Metin Motoru",
        version="0.1.0",
        base_model="dbmdz/bert-base-turkish-cased",
        purpose="Manipülatif söylem sınıflandırması",
        measurements=[
            Measurement(metric="macro-F1", value=0.68, dataset="altın test kümesi", n=500)
        ],
        known_limits=["Bölgesel ağızlarda yanlış pozitif oranı ölçülmedi"],
    )
    kart.save(tmp_path)
    okunan = ModelCard.load(tmp_path)

    assert okunan is not None
    assert okunan.measurements[0].n == 500
    assert okunan.measurements[0].dataset == "altın test kümesi"

    md = okunan.to_markdown()
    assert "| n |" in md, "markdown tablosunda n sütunu bulunmalı"
    assert "Bilinen sınırlar" in md


def test_kart_yoksa_none_doner(tmp_path: Path) -> None:
    assert ModelCard.load(tmp_path) is None


# ─────────────────── Kabul kapısı ───────────────────
#
# Yarım eğitilmiş bir ağırlık, hiç ağırlık olmamasından kötüdür: sistem sessizce
# yanlış cevap vermeye başlar ve bu sunum sırasında fark edilmez. Kapı, ölçülmemiş
# veya eşiğin altında ölçülmüş modelin yüklenmesini yapısal olarak engeller.


def _kapili_spec(esik: float = 0.70) -> ModelSpec:
    return ModelSpec(
        name="kapili_model",
        module="M5",
        title="Kapı testi",
        files=("model.onnx",),
        loader=lambda _: "model",
        kabul_metrigi="dogruluk",
        kabul_esigi=esik,
    )


def _hazirla(monkeypatch, tmp_path: Path) -> ModelRegistry:
    r = ModelRegistry()
    r.register(_kapili_spec())
    monkeypatch.setattr(runtime.settings, "models", True)
    monkeypatch.setattr(runtime, "resolve_runtime", lambda: "onnx")
    monkeypatch.setattr(runtime, "model_root", lambda: tmp_path)
    dizin = tmp_path / "kapili_model"
    dizin.mkdir()
    (dizin / "model.onnx").touch()
    return r


def _kart(deger: float) -> ModelCard:
    return ModelCard(
        name="kapili_model",
        module="M5",
        title="Kapı testi",
        version="0.1.0",
        base_model="test",
        purpose="test",
        measurements=[Measurement("dogruluk", deger, "test kümesi", 100)],
    )


def test_kartsiz_model_yuklenmez(monkeypatch, tmp_path: Path) -> None:
    r = _hazirla(monkeypatch, tmp_path)
    assert r.get("kapili_model") is None
    assert r.status("kapili_model") is ModelStatus.DOGRULANMAMIS
    assert "model kartı yok" in r.reason("kapili_model")


def test_esigin_altindaki_model_yuklenmez(monkeypatch, tmp_path: Path) -> None:
    r = _hazirla(monkeypatch, tmp_path)
    _kart(0.42).save(tmp_path / "kapili_model")

    assert r.get("kapili_model") is None
    assert r.status("kapili_model") is ModelStatus.DOGRULANMAMIS
    assert "0.42" in r.reason("kapili_model")


def test_esigi_gecen_model_yuklenir(monkeypatch, tmp_path: Path) -> None:
    r = _hazirla(monkeypatch, tmp_path)
    _kart(0.88).save(tmp_path / "kapili_model")

    assert r.get("kapili_model") == "model"
    assert r.status("kapili_model") is ModelStatus.HAZIR


def test_kartta_istenen_metrik_yoksa_yuklenmez(monkeypatch, tmp_path: Path) -> None:
    r = _hazirla(monkeypatch, tmp_path)
    kart = _kart(0.95)
    kart.measurements = [Measurement("baska_metrik", 0.99, "test", 100)]
    kart.save(tmp_path / "kapili_model")

    assert r.get("kapili_model") is None
    assert "ölçümü yok" in r.reason("kapili_model")


# ─────────────────── Kural 0 karar kaynağı ───────────────────
#
# Modelin yardım çağrısı başlığı Kural 0'a BAĞLI DEĞİLDİR ve bu bilinçli bir
# karardır (docs/metrikler/m3.md · ölçüm). Model yüklendiğinde bu davranışın
# sessizce değişmemesi gerekir; aşağıdaki testler o kararı kilitler.


class _SahteM3:
    """Her metni yüksek olasılıkla yardım çağrısı sayan model."""

    yardim_esigi = 0.0003

    def analiz(self, metin: str, *, kanit: bool = True):
        from krizkalkan_core.taxonomy import ClaimType
        from krizkalkan_core.text.model import MetinCiktisi

        return MetinCiktisi(
            claim_type=ClaimType.YARDIM_CAGRISI,
            claim_olasilik=0.99,
            yanlis_etiket="diger",
            yanlis_olasilik=0.5,
            yardim_olasilik=0.99,
            yardim_kanitlari=[],
        )

    def yardim_skoru(self, olasilik: float) -> float:
        return 0.99


def test_model_kural_sifiri_tetikleyemez(monkeypatch) -> None:
    """Model "yardım çağrısı" dese bile Kural 0 kararı sözlükte kalır.

    Ölçüm, modelin Türkçe'de seferberlik söylemini yardım çağrısından
    ayıramadığını gösterdi: "hepimiz sokağa dökülelim" metni sınanan tüm
    çalışma noktalarında korumaya alınıyordu. Kural 0 tetiklendiğinde sistem
    hiçbir müdahale uygulamadığı için bu, provokatif içeriğin etiketsiz
    geçmesi demekti.
    """
    from krizkalkan_core.text import engine as text_engine
    from krizkalkan_core.text import model as m3

    monkeypatch.setattr(m3, "get", lambda: _SahteM3())

    analiz, sinyaller = text_engine.analyse(
        "Sorumlular hesap versin, hepimiz sokağa dökülelim! Gerçekleri saklıyorlar."
    )
    assert analiz.help_call_score < 0.35, "Kural 0 model skoruyla tetiklenmemeli"

    model_sinyali = next((s for s in sinyaller if s.key == "text.help_call_model"), None)
    assert model_sinyali is not None, "model çıktısı bilgi olarak raporlanmalı"
    assert model_sinyali.score > 0.35, "sinyal raporlanıyor ama karara girmiyor"


def test_gercek_yardim_cagrisi_sozlukle_korunur(monkeypatch) -> None:
    """Türkçe yardım çağrısı, model olsun olmasın korunmalıdır."""
    from krizkalkan_core.text import engine as text_engine
    from krizkalkan_core.text import model as m3

    monkeypatch.setattr(m3, "get", lambda: _SahteM3())
    analiz, _ = text_engine.analyse(
        "Enkaz altındayız lütfen yardım edin Antakya Sümerler Mahallesi 3. sokak"
    )
    assert analiz.help_call_score > 0.35


def test_model_iddia_tipini_belirler(monkeypatch) -> None:
    """Sınıflandırma modelin, yapısal alanlar sözlüğün işidir."""
    from krizkalkan_core.taxonomy import ClaimType
    from krizkalkan_core.text import engine as text_engine
    from krizkalkan_core.text import model as m3

    monkeypatch.setattr(m3, "get", lambda: _SahteM3())
    analiz, _ = text_engine.analyse("Hatay'da 7.8 büyüklüğünde deprem sonrası köprü çöktü.")

    assert analiz.claims, "iddia çıkarılmalı"
    assert analiz.claims[0].claim_type is ClaimType.YARDIM_CAGRISI, "tür modelden gelmeli"
    assert analiz.claims[0].location is not None, "konum sözlükten korunmalı"
    assert analiz.claims[0].magnitude is not None, "büyüklük sözlükten korunmalı"
