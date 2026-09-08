"""M3 çıkarım katmanı — eğitilmiş çok görevli model.

Sözlük yolunun (`lexicon.py`) yerini alır ama onu kaldırmaz: model
yüklenemezse `available()` False döner ve `engine.analyse` kural yoluna düşer.

Model üç başlık üretir; sözlük ise modelin üretmediği iki şeyi verir:
yapılandırılmış iddia alanları (konum, büyüklük, zaman, kaynak) ve sekiz
etiketli manipülatif söylem sınıflandırması. Bu nedenle iki yol birbirini
tamamlar — model karar verir, sözlük yapıyı çıkarır.

Kanıt üretimi **modelin kendisinden** gelir: kelime düzeyi örtme (occlusion)
ile hangi kelimelerin skoru taşıdığı ölçülür. Sözlükten devralınan desen
eşleşmeleri kanıt olarak kullanılmaz; aksi hâlde açıklama modelin kararını
değil sözlüğün kararını anlatırdı.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from krizkalkan_core.models import ModelSpec, registry
from krizkalkan_core.taxonomy import HELP_CALL_THRESHOLD, ClaimType

logger = logging.getLogger(__name__)

MODEL_ADI = "m3_text"
GEREKLI_DOSYALAR = ("model.onnx", "tokenizer.json")

#: Eğitim betiğiyle aynı sıra olmak zorundadır (scripts/train/m3_text.py).
CLAIM_SINIFLARI: tuple[str, ...] = tuple(c.value for c in ClaimType)
YANLIS_SINIFLARI: tuple[str, ...] = ("dogru", "yanlis", "diger")

MAKS_UZUNLUK = 128

#: Kanıt için örtülecek azami kelime sayısı. Her kelime bir ileri geçiş demek;
#: tek yığında koştuğu için maliyeti sabittir ama girdi uzunluğuyla büyür.
AZAMI_ORTME = 24

#: Örtme sonrası skor düşüşü bu değerin altındaysa kelime kanıt sayılmaz.
ORTME_ESIGI = 0.02

_KELIME = re.compile(r"\w+", re.UNICODE)


@dataclass(slots=True)
class MetinCiktisi:
    """Modelin ham çıktısı."""

    claim_type: ClaimType
    claim_olasilik: float
    yanlis_etiket: str
    yanlis_olasilik: float
    yardim_olasilik: float
    #: (kelime, karakter_baslangic, karakter_bitis, skor_dususu)
    yardim_kanitlari: list[tuple[str, int, int, float]]


class M3Model:
    """int8 ONNX çok görevli metin modeli."""

    def __init__(self, dizin: Path) -> None:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        from krizkalkan_core.models.cards import ModelCard
        from krizkalkan_core.models.runtime import onnx_session_options

        self._np = np
        self.tokenizer = Tokenizer.from_file(str(dizin / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=MAKS_UZUNLUK)
        self.tokenizer.enable_padding(length=MAKS_UZUNLUK)
        self.oturum = ort.InferenceSession(
            str(dizin / "model.onnx"),
            sess_options=onnx_session_options(),
            providers=["CPUExecutionProvider"],
        )

        # Kural 0 eşiği koda gömülmez: ölçümle birlikte model kartında taşınır.
        # Ağırlık değişince eşik de değişir; ikisinin ayrı düşmesi, sistemin
        # ölçülmemiş bir eşikle çalışması demektir.
        self.yardim_esigi = self._karttan_esik(ModelCard.load(dizin))

    @staticmethod
    def _karttan_esik(kart) -> float:
        if kart is not None:
            for olcum in kart.measurements:
                if olcum.metric == "yardim_esik":
                    return float(olcum.value)
        raise ValueError(
            "Model kartında 'yardim_esik' ölçümü yok. Kural 0 eşiği ölçümle "
            "belirlenir; kartsız ağırlık kullanılamaz "
            "(scripts/eval/m3_text.py --onnx çalıştırın)."
        )

    # ────────────────────────── çıkarım ──────────────────────────

    def _ileri(self, metinler: list[str]):
        np = self._np
        kodlanmis = self.tokenizer.encode_batch(metinler)
        ids = np.array([k.ids for k in kodlanmis], dtype="int64")
        maske = np.array([k.attention_mask for k in kodlanmis], dtype="int64")
        claim, yanlis, yardim = self.oturum.run(None, {"input_ids": ids, "attention_mask": maske})
        return self._softmax(claim), self._softmax(yanlis), self._softmax(yardim)

    def _softmax(self, x):
        np = self._np
        kaydirilmis = x - x.max(axis=-1, keepdims=True)
        ustel = np.exp(kaydirilmis)
        return ustel / ustel.sum(axis=-1, keepdims=True)

    def _ortme_kanitlari(self, metin: str, taban_skor: float) -> list[tuple[str, int, int, float]]:
        """Kelime örtmeyle hangi kelimelerin yardım skorunu taşıdığını ölçer.

        Her aday kelime metinden çıkarılıp model yeniden çalıştırılır; skorun
        ne kadar düştüğü o kelimenin katkısıdır. Tüm varyantlar tek yığında
        koşar, dolayısıyla maliyet tek ileri geçiş mertebesindedir.
        """
        kelimeler = [
            (m.group(), m.start(), m.end()) for m in _KELIME.finditer(metin) if len(m.group()) > 2
        ][:AZAMI_ORTME]
        if not kelimeler:
            return []

        varyantlar = [metin[:bas] + " " * (son - bas) + metin[son:] for _, bas, son in kelimeler]
        _, _, yardim = self._ileri(varyantlar)

        kanitlar = [
            (kelime, bas, son, round(taban_skor - float(olasilik[1]), 4))
            for (kelime, bas, son), olasilik in zip(kelimeler, yardim, strict=True)
        ]
        kanitlar.sort(key=lambda k: -k[3])
        return [k for k in kanitlar if k[3] >= ORTME_ESIGI][:3]

    def analiz(self, metin: str, *, kanit: bool = True) -> MetinCiktisi:
        """Tek bir metni analiz eder."""
        claim, yanlis, yardim = self._ileri([metin])
        yardim_olasilik = float(yardim[0][1])

        return MetinCiktisi(
            claim_type=ClaimType(CLAIM_SINIFLARI[int(claim[0].argmax())]),
            claim_olasilik=round(float(claim[0].max()), 4),
            yanlis_etiket=YANLIS_SINIFLARI[int(yanlis[0].argmax())],
            yanlis_olasilik=round(float(yanlis[0].max()), 4),
            yardim_olasilik=round(yardim_olasilik, 6),
            yardim_kanitlari=(
                self._ortme_kanitlari(metin, yardim_olasilik)
                if kanit and yardim_olasilik >= self.yardim_esigi
                else []
            ),
        )

    # ────────────────────────── eşik eşlemesi ──────────────────────────

    def yardim_skoru(self, olasilik: float) -> float:
        """Ham olasılığı politika katmanının beklediği ölçeğe taşır.

        `policy.decide` sabit bir eşikle (HELP_CALL_THRESHOLD) karşılaştırır.
        Modelin çalışma noktası ise ölçümle belirlenir ve çok küçük bir sayıdır.
        Parçalı doğrusal eşleme, modelin eşiğini politikanın eşiğine oturtur:
        olasılık tam eşikteyken skor tam HELP_CALL_THRESHOLD olur.

        Böylece politika katmanı model değiştiğinde yeniden ayarlanmaz —
        rapor 4.3'teki "model ile politika birbirinden ayrıktır" ilkesi korunur.
        """
        esik = self.yardim_esigi
        if olasilik <= 0.0:
            return 0.0
        if olasilik < esik:
            return round(HELP_CALL_THRESHOLD * (olasilik / esik), 4)
        if olasilik >= 1.0:
            return 1.0
        oran = (olasilik - esik) / (1.0 - esik)
        return round(HELP_CALL_THRESHOLD + (1.0 - HELP_CALL_THRESHOLD) * oran, 4)


def _yukle(dizin: Path) -> M3Model:
    return M3Model(dizin)


registry.register(
    ModelSpec(
        name=MODEL_ADI,
        module="M3",
        title="Türkçe kriz metin motoru (XLM-R, çok görevli)",
        files=GEREKLI_DOSYALAR,
        loader=_yukle,
        kabul_metrigi="claim_makro_f1",
        kabul_esigi=0.60,
    )
)


def get() -> M3Model | None:
    return registry.get(MODEL_ADI)


def available() -> bool:
    return get() is not None


def reason() -> str:
    return registry.reason(MODEL_ADI)
