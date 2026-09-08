"""Sinyal kalibrasyonu.

Modül skorları ham hâlde kullanılmaz. Her sinyal, tutulmuş bir kalibrasyon
kümesinde öğrenilmiş parçalı doğrusal bir eşlemeyle gerçek olasılığa çevrilir
(rapor 3.1 · M6 · isotonic regresyon).

Buradaki eşleme noktaları isotonic regresyonun çıktısı biçimindedir: monoton
artan, parçalı doğrusal. Model eğitildiğinde yalnızca bu noktalar değişir;
çağıran kod aynı kalır.
"""

from __future__ import annotations

import json
import logging
from bisect import bisect_left
from functools import lru_cache

logger = logging.getLogger(__name__)

#: Elle yazılmış YEDEK eşleme noktaları.
#:
#: Ölçülmüş kalibrasyon `models/m6_fusion/kalibrasyon.json` dosyasından
#: yüklenir ve bunların yerine geçer. Dosya yoksa (ağırlıksız kurulum) sistem
#: bu noktalarla çalışmaya devam eder; değerler literatürdeki tipik davranışa
#: göre elle seçilmiştir ve ÖLÇÜLMEMİŞTİR.
VARSAYILAN_NOKTALAR: dict[str, list[tuple[float, float]]] = {
    # Köken eşleşmesi keskin bir olgudur: ya eşleşir ya eşleşmez.
    "provenance.match": [(0.0, 0.0), (0.80, 0.10), (0.86, 0.62), (0.92, 0.93), (1.0, 0.98)],
    # Sentetik medya dedektörleri aşırı güvenlidir; yüksek skorlar bastırılır.
    "synthetic.video": [(0.0, 0.02), (0.30, 0.12), (0.60, 0.38), (0.80, 0.68), (1.0, 0.88)],
    "synthetic.audio": [(0.0, 0.02), (0.30, 0.14), (0.60, 0.42), (0.80, 0.72), (1.0, 0.90)],
    "synthetic.c2pa": [(0.0, 0.0), (0.5, 0.5), (1.0, 0.99)],
    "multimodal.av_sync": [(0.0, 0.03), (0.30, 0.15), (0.60, 0.45), (0.85, 0.78), (1.0, 0.92)],
    "multimodal.speaker_face": [(0.0, 0.03), (0.30, 0.13), (0.60, 0.40), (0.85, 0.70), (1.0, 0.86)],
    "multimodal.scene_claim": [(0.0, 0.04), (0.40, 0.24), (0.70, 0.56), (1.0, 0.80)],
    # Sözlük tabanlı metin skorları iyi ayrışır, hafif düzeltme yeterlidir.
    "text.manipulative": [(0.0, 0.02), (0.35, 0.28), (0.65, 0.62), (0.85, 0.82), (1.0, 0.93)],
    "text.help_call": [(0.0, 0.0), (0.35, 0.35), (0.70, 0.78), (1.0, 0.96)],
    "text.claim": [(0.0, 0.0), (0.6, 0.6), (1.0, 1.0)],
    "knowledge.verdict": [(0.0, 0.02), (0.45, 0.45), (0.92, 0.94), (1.0, 0.97)],
}

#: Tanımlı eşlemesi olmayan sinyaller için birim eşleme.
_IDENTITY = [(0.0, 0.0), (1.0, 1.0)]

#: Ölçülmüş kalibrasyonun ağırlık dizinindeki konumu.
KALIBRASYON_DIZINI = "m6_fusion"
KALIBRASYON_DOSYASI = "kalibrasyon.json"


@lru_cache(maxsize=1)
def _olculmus_noktalar() -> dict[str, list[tuple[float, float]]]:
    """Ölçülmüş kalibrasyonu yükler; yoksa boş sözlük.

    Kalibrasyon bir veri ürünüdür, kod sabiti değil: `scripts/eval/m6_fusion.py`
    üretir, buradan okunur. İkisinin ayrı düşmesi, sistemin ölçülmemiş bir
    eşlemeyle çalışması demektir.
    """
    from krizkalkan_core.models.runtime import model_root

    yol = model_root() / KALIBRASYON_DIZINI / KALIBRASYON_DOSYASI
    if not yol.exists():
        logger.info("Ölçülmüş kalibrasyon yok (%s); elle yazılmış noktalar kullanılıyor", yol)
        return {}

    try:
        ham = json.loads(yol.read_text(encoding="utf-8"))
        return {
            anahtar: [(float(x), float(y)) for x, y in bilgi["noktalar"]]
            for anahtar, bilgi in ham.items()
            if bilgi.get("noktalar")
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as hata:
        logger.warning("Kalibrasyon dosyası okunamadı (%s): %s", yol, hata)
        return {}


def noktalar(key: str) -> list[tuple[float, float]]:
    """Bir sinyalin eşleme noktaları: ölçülmüş varsa o, yoksa elle yazılmış."""
    return _olculmus_noktalar().get(key) or VARSAYILAN_NOKTALAR.get(key, _IDENTITY)


def kalibrasyon_kaynagi(key: str) -> str:
    """Sinyalin hangi kaynaktan kalibre edildiği — rapor ve tanılama için."""
    if key in _olculmus_noktalar():
        return "ölçülmüş"
    return "elle yazılmış" if key in VARSAYILAN_NOKTALAR else "kalibre edilmemiş"


def reset_cache() -> None:
    """Kalibrasyon önbelleğini temizler (testler ve yeniden ölçüm için)."""
    _olculmus_noktalar.cache_clear()


def calibrate(key: str, raw: float) -> float:
    """Ham skoru kalibre olasılığa çevirir (parçalı doğrusal interpolasyon)."""
    points = noktalar(key)
    xs = [p[0] for p in points]

    if raw <= xs[0]:
        return round(points[0][1], 4)
    if raw >= xs[-1]:
        return round(points[-1][1], 4)

    i = bisect_left(xs, raw)
    x0, y0 = points[i - 1]
    x1, y1 = points[i]
    if x1 == x0:
        return round(y1, 4)
    ratio = (raw - x0) / (x1 - x0)
    return round(y0 + ratio * (y1 - y0), 4)


def expected_calibration_error(predictions: list[tuple[float, bool]], bins: int = 10) -> float:
    """Beklenen Kalibrasyon Hatası (ECE).

    `predictions`: (tahmin_olasılığı, gerçek_etiket) çiftleri.
    Rapor 3.2'de M6 için hedef ≤ 0,05 olarak tanımlanmıştır.
    """
    if not predictions:
        return 0.0

    total = len(predictions)
    error = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        bucket = [(p, y) for p, y in predictions if (lo < p <= hi) or (b == 0 and p == 0.0)]
        if not bucket:
            continue
        avg_conf = sum(p for p, _ in bucket) / len(bucket)
        accuracy = sum(1 for _, y in bucket if y) / len(bucket)
        error += (len(bucket) / total) * abs(avg_conf - accuracy)
    return round(error, 4)
