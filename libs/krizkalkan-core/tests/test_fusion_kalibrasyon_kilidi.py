"""Kalibrasyonun bir sinyali sessizce devre dışı bırakmadığını kilitler.

Kalibrasyon bir veri ürünüdür: `scripts/eval/m6_fusion.py` üretir, üretim
onu okur. Ölçümden öğrenilmiş bir eşleme, sinyalin karar eşiğine hiç
ulaşamadığı bir tavan üretebilir. O zaman sinyal ateşleyemez hâle gelir ve
**hiçbir hata vermeden** devreden çıkar.

Yaşandı: M6 kümesinden öğrenilen `synthetic.video` eşlemesi ham 1,0000'i
0,3294'e gönderiyordu. Karar eşiği 0,62 olduğu için SENTETİK_MEDYA sınıfı bir
daha kurulamazdı. İsotonic yanlış öğrenmemişti — o kümede model gerçekten
ayrıştırmıyordu — ama alanla sınırlı bir sonucun küresel eşleme olarak
yazılması modülü kapatırdı.

`m6_fusion.py` artık böyle bir eşlemeyi yazmayı reddediyor. Bu dosya, üretimde
duran eşlemenin gerçekten ateşleyebildiğini doğrular: koruma atlansa ya da
dosya elle düzenlense bile test düşer.
"""

from __future__ import annotations

from krizkalkan_core.fusion import calibration
from krizkalkan_core.fusion.engine import (
    SAHNE_CELISKI_ESIGI,
    SENTETIK_KANIT_ESIGI,
    apply_calibration,
    fuse,
)
from krizkalkan_core.schemas import Signal
from krizkalkan_core.taxonomy import Verdict

#: Sinyal → o sinyalin karara girebilmesi için gereken kalibre skor.
KARAR_ESIKLERI = {
    "synthetic.video": SENTETIK_KANIT_ESIGI,
    "synthetic.audio": SENTETIK_KANIT_ESIGI,
    "synthetic.c2pa": SENTETIK_KANIT_ESIGI,
    "synthetic.metadata": SENTETIK_KANIT_ESIGI,
    "multimodal.scene_claim": SAHNE_CELISKI_ESIGI,
}


def test_her_sinyal_karar_esigine_ulasabiliyor() -> None:
    """Ham 1,0 verildiğinde her sinyal kendi eşiğini geçebilmeli."""
    calibration.reset_cache()
    for anahtar, esik in KARAR_ESIKLERI.items():
        tavan = calibration.calibrate(anahtar, 1.0)
        assert tavan >= esik, (
            f"{anahtar}: kalibrasyon tavanı {tavan:.4f} < karar eşiği {esik:.2f}. "
            f"Bu sinyal üretimde ateşleyemez ({calibration.kalibrasyon_kaynagi(anahtar)} "
            "eşleme). Kalibrasyonu yeniden ölçün ya da noktaları düzeltin."
        )


def test_kalibrasyon_monoton_artan() -> None:
    """Eşleme monoton olmalı: `calibrate()` bunu varsayar."""
    calibration.reset_cache()
    for anahtar in KARAR_ESIKLERI:
        noktalar = calibration.noktalar(anahtar)
        degerler = [y for _, y in noktalar]
        assert degerler == sorted(degerler), f"{anahtar}: eşleme monoton değil — {noktalar}"


def test_doygun_sentetik_sinyal_sentetik_medya_kurar() -> None:
    """Uçtan uca kilit: ham 1,0 skorlu bir M4 sinyali sınıfı kurmalı."""
    calibration.reset_cache()
    sinyal = Signal(module="M4", key="synthetic.video", label="test", score=0.0, raw_score=1.0)
    (sinyal,) = apply_calibration([sinyal])
    verdict, _, katkilar = fuse([sinyal], None, None, None)
    assert verdict is Verdict.SENTETIK_MEDYA
    assert any(s.key == "synthetic.video" for s in katkilar)
