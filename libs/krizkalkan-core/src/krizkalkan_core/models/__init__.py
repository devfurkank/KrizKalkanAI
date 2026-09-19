"""Model katmanı — ağırlık yükleme, çalışma zamanı seçimi ve model kartları.

Bu paket, analiz modülleri ile eğitilmiş ağırlıklar arasındaki tek arayüzdür.
Modüller ağırlığı doğrudan açmaz; `registry.get(...)` ile ister ve `None`
dönerse kendi kural tabanlı yoluna düşer.
"""

from krizkalkan_core.models.cards import Measurement, ModelCard
from krizkalkan_core.models.registry import ModelSpec, ModelStatus, registry
from krizkalkan_core.models.runtime import describe, model_root, settings

__all__ = [
    "Measurement",
    "ModelCard",
    "ModelSpec",
    "ModelStatus",
    "describe",
    "model_root",
    "registry",
    "settings",
]
