"""Model kayıt defteri — tembel yükleme ve yedek yola düşüş.

Tasarımın tek kritik davranışı şudur: **ağırlık yoksa sistem çökmez.**
`get()` her koşulda ya bir model ya da `None` döndürür; hiçbir zaman istisna
fırlatmaz. `None` dönmesi bir hata değildir — çağıran modül sözlük/kural
yoluna düşer ve ürettiği sinyale "indirgenmiş mod" notunu ekler.

Bu, 20 Eylül canlı sunumunun sigortasıdır: ağırlık dizini boş bir makinede
sistem, bugünkü kural tabanlı davranışıyla eksiksiz çalışmaya devam eder.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from krizkalkan_core.models import runtime

logger = logging.getLogger(__name__)


class ModelStatus(StrEnum):
    """Bir modelin o anki kullanılabilirlik durumu."""

    HAZIR = "hazır"
    KAPALI = "kapalı"
    AGIRLIK_YOK = "ağırlık_yok"
    CALISMA_ZAMANI_YOK = "çalışma_zamanı_yok"
    YUKLEME_HATASI = "yükleme_hatası"
    DOGRULANMAMIS = "doğrulanmamış"


#: Durum → kullanıcıya/denetim kaydına yazılan açıklama.
STATUS_REASON: dict[ModelStatus, str] = {
    ModelStatus.HAZIR: "Model yüklü",
    ModelStatus.KAPALI: "Model katmanı kapalı (KK_MODELS=off) — kural tabanlı yol kullanılıyor",
    ModelStatus.AGIRLIK_YOK: "Ağırlık dosyası bulunamadı — kural tabanlı yol kullanılıyor",
    ModelStatus.CALISMA_ZAMANI_YOK: (
        "Çıkarım çalışma zamanı kurulu değil (onnxruntime/torch) — kural tabanlı yol kullanılıyor"
    ),
    ModelStatus.YUKLEME_HATASI: "Model yüklenemedi — kural tabanlı yol kullanılıyor",
    ModelStatus.DOGRULANMAMIS: (
        "Model kartı ölçüm eşiğini karşılamıyor — kural tabanlı yol kullanılıyor"
    ),
}


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Bir modülün ihtiyaç duyduğu model tanımı.

    `loader`, ağırlık dizinini alıp kullanıma hazır bir nesne döndürür. Kayıt
    defteri bu nesnenin ne olduğunu bilmez; yükleme mantığı ilgili modülün
    kendi sorumluluğundadır.
    """

    name: str
    module: str
    title: str
    #: Ağırlık dizinine göreli, varlığı zorunlu dosyalar.
    files: tuple[str, ...]
    loader: Callable[[Path], Any]
    #: "onnx" | "torch" | None (çalışma zamanı gerektirmeyen modeller için)
    requires_runtime: str | None = "onnx"

    #: Kabul kapısı: model kartında bu metrik en az `kabul_esigi` değerinde
    #: ölçülmüş olmalıdır, aksi hâlde ağırlık yüklenmez.
    #:
    #: Neden yapısal bir kapı: yarım eğitilmiş bir ağırlık, hiç ağırlık
    #: olmamasından KÖTÜDÜR — sistem sessizce yanlış cevap vermeye başlar ve
    #: bu sunum sırasında fark edilmez. Eşik "hedef başarım" değil, "model
    #: gerçekten çalışıyor mu" seviyesidir.
    kabul_metrigi: str | None = None
    kabul_esigi: float = 0.0


@dataclass(slots=True)
class _Entry:
    spec: ModelSpec
    status: ModelStatus = ModelStatus.KAPALI
    detail: str | None = None
    instance: Any = None
    attempted: bool = False


@dataclass
class ModelRegistry:
    """Süreç ömürlü model kayıt defteri."""

    _entries: dict[str, _Entry] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # ────────────────────────── kayıt ──────────────────────────

    def register(self, spec: ModelSpec) -> None:
        """Bir model tanımını kaydeder. Aynı ad yeniden kaydedilirse üzerine yazar."""
        with self._lock:
            self._entries[spec.name] = _Entry(spec=spec)

    def registered(self) -> list[str]:
        return sorted(self._entries)

    # ────────────────────────── erişim ──────────────────────────

    def get(self, name: str) -> Any | None:
        """Modeli döndürür; kullanılamıyorsa `None`.

        Bu fonksiyon **hiçbir koşulda istisna fırlatmaz.** Yükleme sırasında
        oluşan her hata yakalanır, durum olarak kaydedilir ve `None` dönülür.
        """
        entry = self._entries.get(name)
        if entry is None:
            logger.warning("Tanımsız model istendi: %s", name)
            return None

        with self._lock:
            if entry.attempted:
                return entry.instance
            entry.attempted = True
            self._load(entry)
            return entry.instance

    def is_available(self, name: str) -> bool:
        return self.get(name) is not None

    def reason(self, name: str) -> str:
        """Modelin neden kullanılamadığının açıklaması (sinyal notu için)."""
        entry = self._entries.get(name)
        if entry is None:
            return "Tanımsız model"
        if not entry.attempted:
            self.get(name)
        base = STATUS_REASON[entry.status]
        return f"{base} · {entry.detail}" if entry.detail else base

    # ────────────────────────── yükleme ──────────────────────────

    def _load(self, entry: _Entry) -> None:
        """Tek bir modeli yükler; her başarısızlık durumu ayrı raporlanır."""
        spec = entry.spec

        if not runtime.settings.models:
            entry.status = ModelStatus.KAPALI
            return

        required = spec.requires_runtime
        if required is not None:
            available = runtime.resolve_runtime()
            if available == "yok" or (required != "auto" and available != required):
                entry.status = ModelStatus.CALISMA_ZAMANI_YOK
                entry.detail = f"gereken: {required}, bulunan: {available}"
                return

        directory = runtime.model_root() / spec.name
        missing = [f for f in spec.files if not (directory / f).exists()]
        if missing:
            entry.status = ModelStatus.AGIRLIK_YOK
            entry.detail = f"{directory} · eksik: {', '.join(missing)}"
            logger.info("Model ağırlığı yok, kural yoluna düşülüyor: %s (%s)", spec.name, missing)
            return

        if spec.kabul_metrigi is not None:
            kabul, gerekce = _kabul_kapisi(spec, directory)
            if not kabul:
                entry.status = ModelStatus.DOGRULANMAMIS
                entry.detail = gerekce
                logger.warning("Model kabul kapısını geçemedi: %s (%s)", spec.name, gerekce)
                return

        try:
            entry.instance = spec.loader(directory)
        # Yükleme hatası sistemi durdurmamalı: hangi hata olursa olsun
        # kural tabanlı yola düşülür.
        except Exception as exc:
            entry.status = ModelStatus.YUKLEME_HATASI
            entry.detail = f"{type(exc).__name__}: {exc}"
            entry.instance = None
            logger.exception("Model yüklenemedi: %s", spec.name)
            return

        if entry.instance is None:
            entry.status = ModelStatus.YUKLEME_HATASI
            entry.detail = "yükleyici None döndürdü"
            return

        entry.status = ModelStatus.HAZIR
        logger.info("Model yüklendi: %s (%s)", spec.name, directory)

    # ────────────────────────── tanılama ──────────────────────────

    def status(self, name: str) -> ModelStatus:
        entry = self._entries.get(name)
        if entry is None:
            return ModelStatus.AGIRLIK_YOK
        if not entry.attempted:
            self.get(name)
        return entry.status

    def report(self) -> dict[str, dict[str, str]]:
        """Tüm modellerin durumu — sağlık ucu ve değerlendirme betikleri için."""
        return {
            name: {
                "modul": entry.spec.module,
                "baslik": entry.spec.title,
                "durum": self.status(name).value,
                "aciklama": self.reason(name),
            }
            for name, entry in sorted(self._entries.items())
        }

    def reset(self) -> None:
        """Yükleme denemelerini sıfırlar (testler ve ortam değişikliği için)."""
        with self._lock:
            for entry in self._entries.values():
                entry.attempted = False
                entry.instance = None
                entry.status = ModelStatus.KAPALI
                entry.detail = None


#: Uygulama genelinde paylaşılan tek kayıt defteri.
registry = ModelRegistry()


def _kabul_kapisi(spec: ModelSpec, directory: Path) -> tuple[bool, str]:
    """Model kartındaki ölçümü eşikle karşılaştırır.

    Kart yoksa veya istenen metrik ölçülmemişse model yüklenmez: ölçülmemiş
    bir ağırlığın üretimde olması, sistemin ne yaptığını bilmemesi demektir.
    """
    from krizkalkan_core.models.cards import ModelCard

    kart = ModelCard.load(directory)
    if kart is None:
        return False, f"model kartı yok ({directory / 'kart.json'})"

    for olcum in kart.measurements:
        if olcum.metric == spec.kabul_metrigi:
            if olcum.value >= spec.kabul_esigi:
                return True, f"{olcum.metric}={olcum.value:.4g} ≥ {spec.kabul_esigi}"
            return False, (
                f"{olcum.metric}={olcum.value:.4g} < gerekli {spec.kabul_esigi} "
                f"(küme: {olcum.dataset}, n={olcum.n})"
            )
    return False, f"kartta '{spec.kabul_metrigi}' ölçümü yok"
