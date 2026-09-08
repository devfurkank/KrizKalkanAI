"""Model çalışma zamanı — yapılandırma, çalışma zamanı seçimi ve cihaz tespiti.

Bu modül ağır bağımlılıkların (torch, onnxruntime) *varlığını* sorgular ama
onları içe aktarmaz. Böylece çekirdek kütüphane, ML paketleri kurulu olmayan
bir ortamda da içe aktarılabilir kalır (rapor 4.1 · demo taşınabilirliği).
"""

from __future__ import annotations

import importlib.util
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelSettings(BaseSettings):
    """Model katmanının ortam değişkenleri (`KK_` önekiyle okunur)."""

    model_config = SettingsConfigDict(env_prefix="KK_", env_file=".env", extra="ignore")

    #: Kapalıysa hiçbir ağırlık yüklenmez; tüm modüller sözlük/kural yoluna düşer.
    #: Sunum güvenliği için tek anahtarlık geri dönüş yolu budur.
    models: bool = False

    #: İndirilmiş ağırlıkların kök dizini.
    model_dir: Path = Path("models")

    #: "onnx" | "torch" | "auto"
    model_runtime: str = "auto"

    #: "cpu" | "mps" | "cuda" | "auto"
    model_device: str = "auto"

    #: ONNX Runtime iş parçacığı sayısı (0 = kütüphane varsayılanı).
    model_threads: int = 0


settings = ModelSettings()


def _installed(module: str) -> bool:
    """Paket içe aktarılmadan kurulu olup olmadığını söyler."""
    return importlib.util.find_spec(module) is not None


@lru_cache(maxsize=1)
def has_onnxruntime() -> bool:
    return _installed("onnxruntime")


@lru_cache(maxsize=1)
def has_torch() -> bool:
    return _installed("torch")


@lru_cache(maxsize=1)
def resolve_runtime() -> str:
    """Kullanılacak çıkarım çalışma zamanını seçer.

    ONNX tercih edilir: demo makinesinde CUDA yoktur ve nicelenmiş ONNX
    modelleri CPU'da torch'tan belirgin biçimde hızlıdır (rapor 4.1).
    """
    choice = settings.model_runtime.lower()
    if choice == "onnx":
        return "onnx" if has_onnxruntime() else "yok"
    if choice == "torch":
        return "torch" if has_torch() else "yok"
    if has_onnxruntime():
        return "onnx"
    if has_torch():
        return "torch"
    return "yok"


@lru_cache(maxsize=1)
def resolve_device() -> str:
    """Çıkarımın koşacağı cihazı belirler.

    `auto` durumunda CUDA → MPS → CPU sırası denenir. Tespit için torch
    gerekir; torch yoksa CPU varsayılır (ONNX Runtime zaten CPU'dadır).
    """
    choice = settings.model_device.lower()
    if choice != "auto":
        return choice
    if not has_torch():
        return "cpu"
    try:  # pragma: no cover — donanıma bağlı dal
        import torch

        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
    except Exception:  # noqa: BLE001 — tespit hatası çıkarımı engellememeli
        return "cpu"
    return "cpu"


def onnx_session_options() -> object | None:
    """ONNX Runtime oturum seçenekleri; onnxruntime yoksa None."""
    if not has_onnxruntime():
        return None
    import onnxruntime as ort

    options = ort.SessionOptions()
    if settings.model_threads > 0:
        options.intra_op_num_threads = settings.model_threads
        options.inter_op_num_threads = 1
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return options


def model_root() -> Path:
    """Ağırlık dizininin mutlak yolu.

    Göreli yol verildiğinde depo kökü aranır; böylece komut hangi dizinden
    çalıştırılırsa çalıştırılsın aynı dizin bulunur.
    """
    configured = settings.model_dir
    if configured.is_absolute():
        return configured

    if env_root := os.environ.get("KK_REPO_ROOT"):
        return Path(env_root) / configured

    # libs/krizkalkan-core/src/krizkalkan_core/models/runtime.py → depo kökü
    repo_root = Path(__file__).resolve().parents[5]
    candidate = repo_root / configured
    return candidate if candidate.exists() else configured.resolve()


def describe() -> dict[str, str | bool]:
    """Tanılama çıktısı — `/api/health` ve `scripts/eval` bunu raporlar."""
    return {
        "modeller_acik": settings.models,
        "calisma_zamani": resolve_runtime(),
        "cihaz": resolve_device(),
        "agirlik_dizini": str(model_root()),
        "onnxruntime": has_onnxruntime(),
        "torch": has_torch(),
    }
