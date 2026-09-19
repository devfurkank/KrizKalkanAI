#!/usr/bin/env python
"""Afet video kümesinin manifestini üretir.

Küme `data/external/video_afet/{real,fake}` altındadır (commit edilmez).
Manifest her video için sınıf, afet türü, çözünürlük, süre, içerik karması ve
**bölme** bilgisini tutar: `scripts/data/kumeler/video_afet.json`.

**Bölme neden "bilinmiyor"?** Bu videolar M4 video modelinin eğitim ve
doğrulama verisidir. Eğitimde bir eğitim/doğrulama ayrımı kullanıldı, ancak
ayrımın dosya listesi depoda kayıtlı değil. Buradan yeni bir
"eğitim/test" ayrımı üretmek, modelin gördüğü videoları test kümesine koymak
olurdu: o kümede ölçülen başarım genelleme hakkında hiçbir şey söylemez.

Eğitimdeki doğrulama bölmesinin dosya listesi elde edilirse:

    python scripts/data/build_video_afet.py --dogrulama-listesi valid.txt

Listedeki videolar `dogrulama`, diğerleri `egitim` olarak işaretlenir ve
`scripts/eval/m4_video.py` doğrulama bölmesini ayrıca raporlar. Doğrulama
bölmesi eğitimde kullanılmamıştır; ancak eşik ve en iyi kontrol noktası orada
seçildiği için bu bölmedeki sayı da hafif iyimserdir. Görülmemiş bir test
kümesinin yerini tutmaz.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KUME = REPO_ROOT / "data" / "external" / "video_afet"
MANIFEST = REPO_ROOT / "scripts" / "data" / "kumeler" / "video_afet.json"

#: Dosya adındaki afet türü → KrizKalkan olay türü.
_TURLER = {
    "avalanche": "çığ",
    "earthquake": "deprem",
    "hurricane": "kasırga",
    "landslide": "heyelan",
    "volcanic": "yanardağ",
    "water": "sel",
    "wildfire": "orman yangını",
}


def _tur(ad: str) -> str:
    alt = ad.casefold().removeprefix("fake_")
    return next((t for k, t in _TURLER.items() if alt.startswith(k)), "belirsiz")


def _karma(yol: Path) -> str:
    h = hashlib.sha256()
    with yol.open("rb") as dosya:
        for parca in iter(lambda: dosya.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--kume", type=Path, default=KUME)
    ap.add_argument(
        "--dogrulama-listesi",
        type=Path,
        help="Eğitimdeki doğrulama bölmesinin dosya adları (satır başına bir ad)",
    )
    args = ap.parse_args()

    import cv2

    dogrulama: set[str] | None = None
    if args.dogrulama_listesi:
        dogrulama = {
            Path(satir.strip()).name
            for satir in args.dogrulama_listesi.read_text(encoding="utf-8").splitlines()
            if satir.strip()
        }

    kayitlar = []
    for sinif in ("real", "fake"):
        for yol in sorted((args.kume / sinif).iterdir()):
            if yol.name.startswith(".") or not yol.is_file():
                continue
            kaynak = cv2.VideoCapture(str(yol))
            kare = int(kaynak.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = float(kaynak.get(cv2.CAP_PROP_FPS))
            genislik = int(kaynak.get(cv2.CAP_PROP_FRAME_WIDTH))
            yukseklik = int(kaynak.get(cv2.CAP_PROP_FRAME_HEIGHT))
            kaynak.release()
            if dogrulama is None:
                bolum = "bilinmiyor"
            else:
                bolum = "dogrulama" if yol.name in dogrulama else "egitim"
            kayitlar.append(
                {
                    "dosya": f"{sinif}/{yol.name}",
                    "etiket": "gercek" if sinif == "real" else "uretilmis",
                    "tur": _tur(yol.name),
                    "genislik": genislik,
                    "yukseklik": yukseklik,
                    "yon": "dikey"
                    if yukseklik > genislik
                    else "kare"
                    if yukseklik == genislik
                    else "yatay",
                    "kare": kare,
                    "sure_sn": round(kare / fps, 2) if fps > 0 else 0.0,
                    "sha256": _karma(yol),
                    "bolum": bolum,
                }
            )

    # Aynı içerik iki ad altında: ayrım yapılırsa ikisi aynı bölmede olmalı.
    gruplar: dict[str, list[str]] = defaultdict(list)
    for k in kayitlar:
        gruplar[k["sha256"]].append(k["dosya"])
    kopyalar = [sorted(v) for v in gruplar.values() if len(v) > 1]

    if dogrulama is not None:
        eksik = dogrulama - {Path(k["dosya"]).name for k in kayitlar}
        if eksik:
            print(f"⚠ Doğrulama listesindeki {len(eksik)} ad kümede yok: {sorted(eksik)[:5]}")
        for grup in kopyalar:
            bolumler = {k["bolum"] for k in kayitlar if k["dosya"] in grup}
            if len(bolumler) > 1:
                print(f"⚠ Aynı içerik iki bölmede: {grup} — doğrulama sızıntısı")

    ozet = {
        "kaynak": "M4 video modelinin eğitim/doğrulama verisi",
        "bolme_notu": (
            "bilinmiyor = eğitim/doğrulama ayrımının dosya listesi depoda kayıtlı değil; model bu "
            "videoların hepsini ya da çoğunu eğitimde gördü. Bu kümedeki başarım "
            "genelleme ölçüsü değildir."
        ),
        "sayilar": {
            "etiket": dict(Counter(k["etiket"] for k in kayitlar)),
            "bolum": dict(Counter(k["bolum"] for k in kayitlar)),
            "tur_etiket": dict(Counter(f"{k['tur']}/{k['etiket']}" for k in kayitlar)),
            "yon_etiket": dict(Counter(f"{k['yon']}/{k['etiket']}" for k in kayitlar)),
        },
        "birebir_kopyalar": kopyalar,
        "videolar": kayitlar,
    }
    MANIFEST.write_text(json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {MANIFEST.relative_to(REPO_ROOT)} · {len(kayitlar)} video")
    print(f"  {ozet['sayilar']['etiket']} · bölme {ozet['sayilar']['bolum']}")
    print(f"  birebir kopya grubu: {len(kopyalar)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
