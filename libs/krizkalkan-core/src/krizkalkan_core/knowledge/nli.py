"""M5 · Aşama 2 — doğal dil çıkarımı ile karar katmanı.

Geri getirme aday üretir, karar buradadır. Ayrımın gerekçesi ölçülmüştür
(`docs/metrikler/m5.md`): benzerlik skoru tek başına "aynı iddia" ile
"benzer konu"yu ayıramaz — en yüksek skorlu alakasız sorgu resmî bir AFAD
duyurusuydu.

Görev kurulumu:

    öncül    = havuzdaki kaydın tekzip ettiği iddia
    varsayım = kullanıcının metninden çıkarılan iddia

    entailment    → aynı iddia          → kaydın derecesi karara dönüşür
    neutral       → farklı iddia        → İLGİSİZ
    contradiction → iddianın tersi      → kullanıcı tekzibi paylaşıyor olabilir

Son satır sistemin bilinen hata modunu kapatır: tekzip metnini paylaşan
kullanıcı dezenformasyon yayıyor sayılmamalıdır.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from krizkalkan_core.models import ModelSpec, registry

logger = logging.getLogger(__name__)

MODEL_ADI = "m5_nli"
GEREKLI_DOSYALAR = ("model.onnx", "tokenizer.json")

#: Eğitim betiğiyle aynı sıra olmak zorundadır (scripts/train/m5_nli.py).
SINIFLAR = ("entailment", "neutral", "contradiction")

#: "Aynı iddia" kararı için gereken asgari olasılık. Kasten yüksek tutulmuştur:
#: yanlış bir eşleşme, kullanıcıya "resmî kaynak seni yalanlıyor" demek anlamına
#: gelir ve sistemin en pahalı hatasıdır.
ENTAILMENT_ESIGI = 0.75

MAKS_UZUNLUK = 256


@dataclass(slots=True)
class Cikarim:
    """Tek bir (öncül, varsayım) çifti için çıkarım sonucu."""

    etiket: str
    olasilik: float

    @property
    def ayni_iddia(self) -> bool:
        return self.etiket == "entailment" and self.olasilik >= ENTAILMENT_ESIGI

    @property
    def tersini_soyluyor(self) -> bool:
        """Metin iddiayı öne sürmüyor, tersini söylüyor (tekzip paylaşımı)."""
        return self.etiket == "contradiction" and self.olasilik >= ENTAILMENT_ESIGI


class NliModel:
    """ONNX tabanlı çıkarım modeli."""

    def __init__(self, dizin: Path) -> None:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        from krizkalkan_core.models.runtime import onnx_session_options

        self._np = np
        self.tokenizer = Tokenizer.from_file(str(dizin / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=MAKS_UZUNLUK)
        self.tokenizer.enable_padding()
        self.oturum = ort.InferenceSession(
            str(dizin / "model.onnx"),
            sess_options=onnx_session_options(),
            providers=["CPUExecutionProvider"],
        )

    def siniflandir(self, ciftler: list[tuple[str, str]]) -> list[Cikarim]:
        """(öncül, varsayım) çiftlerini toplu sınıflandırır."""
        if not ciftler:
            return []
        np = self._np

        kodlanmis = self.tokenizer.encode_batch([(oncul, varsayim) for oncul, varsayim in ciftler])
        ids = np.array([k.ids for k in kodlanmis], dtype="int64")
        maske = np.array([k.attention_mask for k in kodlanmis], dtype="int64")
        (logitler,) = self.oturum.run(None, {"input_ids": ids, "attention_mask": maske})

        # Sayısal kararlılık için kaydırmalı softmax.
        kaydirilmis = logitler - logitler.max(axis=-1, keepdims=True)
        ustel = np.exp(kaydirilmis)
        olasiliklar = ustel / ustel.sum(axis=-1, keepdims=True)

        return [
            Cikarim(etiket=SINIFLAR[int(satir.argmax())], olasilik=round(float(satir.max()), 4))
            for satir in olasiliklar
        ]


def _yukle(dizin: Path) -> NliModel:
    return NliModel(dizin)


registry.register(
    ModelSpec(
        name=MODEL_ADI,
        module="M5",
        title="Türkçe çıkarım modeli (NLI-TR)",
        files=GEREKLI_DOSYALAR,
        loader=_yukle,
        kabul_metrigi="dogruluk",
        kabul_esigi=0.7,
    )
)


def get() -> NliModel | None:
    return registry.get(MODEL_ADI)


def available() -> bool:
    return get() is not None


def reason() -> str:
    return registry.reason(MODEL_ADI)
