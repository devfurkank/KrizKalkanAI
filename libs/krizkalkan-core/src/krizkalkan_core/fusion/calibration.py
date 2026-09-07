"""Sinyal kalibrasyonu.

Modül skorları ham hâlde kullanılmaz. Her sinyal, tutulmuş bir kalibrasyon
kümesinde öğrenilmiş parçalı doğrusal bir eşlemeyle gerçek olasılığa çevrilir
(rapor 3.1 · M6 · isotonic regresyon).

Buradaki eşleme noktaları isotonic regresyonun çıktısı biçimindedir: monoton
artan, parçalı doğrusal. Model eğitildiğinde yalnızca bu noktalar değişir;
çağıran kod aynı kalır.
"""

from __future__ import annotations

from bisect import bisect_left

#: Sinyal anahtarı → isotonic eşleme noktaları (ham_skor, kalibre_olasılık).
#: Monoton artan olmak zorundadır.
CALIBRATION_POINTS: dict[str, list[tuple[float, float]]] = {
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


def calibrate(key: str, raw: float) -> float:
    """Ham skoru kalibre olasılığa çevirir (parçalı doğrusal interpolasyon)."""
    points = CALIBRATION_POINTS.get(key, _IDENTITY)
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
