#!/usr/bin/env python
"""M1 köken indeksini kurar — indirilen görüntülerden algısal karmalar.

Girdi : data/external/provenance/{goruntuler/, kayitlar.jsonl}
Çıktı : models/m1_provenance/index.jsonl

Karma hesabı ucuzdur ve GPU gerektirmez; indeks yeniden kurulabilir bir
türev üründür, bu yüzden depoya değil ağırlık dizinine yazılır.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.provenance import imaging  # noqa: E402

KAYNAK = REPO_ROOT / "data" / "external" / "provenance"
CIKTI = REPO_ROOT / "models" / "m1_provenance"

#: Her görüntü birden çok görünümle indekslenir.
#:
#: Gerekçe ölçüldü (docs/metrikler/m1-dayaniklilik.md): algısal karma
#: fotometrik değişime (sıkıştırma, gürültü, parlaklık) neredeyse bağışık ama
#: geometrik değişime kırılgan — kırpma %20'de Recall@1 tek görünümle 0,02'ye
#: düşüyor. Kırpılmış varyantı da indekslemek, saldırganın en ucuz dönüşümünü
#: kapatır ve indeksi yalnızca iki katına çıkarır.
GORUNUMLER: tuple[tuple[str, float], ...] = (
    ("tam", 1.0),
    ("merkez_%80", 0.80),
    ("merkez_%60", 0.60),
)


def _gorunum(goruntu, oran: float):
    """Görüntünün merkezden verilen oranda kırpılmış hâli."""
    if oran >= 1.0:
        return goruntu
    en, boy = goruntu.size
    dx, dy = int(en * (1 - oran) / 2), int(boy * (1 - oran) / 2)
    return goruntu.crop((dx, dy, en - dx, boy - dy))


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--sinir", type=int, default=0, help="yalnızca ilk N kayıt (0 = tümü)")
    a.add_argument(
        "--tut",
        type=int,
        default=100,
        help="indekse GİRMEYECEK kayıt sayısı — yanlış eşleşme ölçümü bunlarla yapılır",
    )
    args = a.parse_args()

    kayit_dosyasi = KAYNAK / "kayitlar.jsonl"
    if not kayit_dosyasi.exists():
        print(f"🔴 {kayit_dosyasi} yok. Önce: python scripts/data/fetch_provenance.py")
        return 1

    kayitlar = [json.loads(s) for s in kayit_dosyasi.read_text(encoding="utf-8").splitlines() if s]
    if args.sinir:
        kayitlar = kayitlar[: args.sinir]
    print(f"→ {len(kayitlar):,} kayıt işleniyor")

    # Tutulan küme indekse GİRMEZ: yanlış eşleşme oranı ancak indekste
    # bulunmayan sorgularla ölçülebilir.
    import random

    rastgele = random.Random(42)
    rastgele.shuffle(kayitlar)
    tutulan = kayitlar[: args.tut] if args.tut else []
    indekslenecek = kayitlar[args.tut :] if args.tut else kayitlar
    print(f"  indekslenecek {len(indekslenecek):,} · tutulan {len(tutulan):,}")

    CIKTI.mkdir(parents=True, exist_ok=True)
    (CIKTI / "tutulan.jsonl").write_text(
        "".join(json.dumps(k, ensure_ascii=False) + "\n" for k in tutulan), encoding="utf-8"
    )

    from PIL import Image

    basladi = time.perf_counter()
    yazilan = 0
    atlanan = 0

    with (CIKTI / "index.jsonl").open("w", encoding="utf-8") as f:
        for sira, kayit in enumerate(indekslenecek):
            yol = KAYNAK / "goruntuler" / kayit["dosya"]
            if not yol.exists():
                atlanan += 1
                continue
            try:
                goruntu = Image.open(yol).convert("RGB")
                girdiler = [
                    (ad, *imaging.karmalar(_gorunum(goruntu, oran))) for ad, oran in GORUNUMLER
                ]
            except Exception as hata:  # bozuk/kesik indirme tüm kurulumu durdurmamalı
                print(f"  ⚠️ {kayit['dosya']}: {type(hata).__name__}")
                atlanan += 1
                continue

            for gorunum, dhash, phash in girdiler:
                f.write(
                    json.dumps(
                        {
                            "kayit_id": f"KRP-{sira:05d}",
                            "gorunum": gorunum,
                            "olay": kayit["olay"],
                            "konum": kayit["konum"],
                            "ilk_yayin": kayit.get("ilk_yayin"),
                            "kaynak_url": kayit.get("kaynak_url"),
                            "lisans": kayit.get("lisans"),
                            "dosya": kayit["dosya"],
                            "dhash": f"{dhash:016x}",
                            "phash": f"{phash:016x}",
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            yazilan += 1
            if yazilan % 200 == 0:
                print(f"    {yazilan:,}/{len(indekslenecek):,}")

    sure = time.perf_counter() - basladi
    print(
        f"\n✓ {yazilan:,} görüntü × {len(GORUNUMLER)} görünüm = "
        f"{yazilan * len(GORUNUMLER):,} indeks girdisi · {sure:.1f} sn · atlanan {atlanan}"
    )
    print(f"  {(CIKTI / 'index.jsonl').relative_to(REPO_ROOT)}")

    # Çakışma denetimi: aynı karmaya sahip farklı görüntüler yanlış eşleşme üretir.
    karmalar: dict[str, int] = {}
    for satir in (CIKTI / "index.jsonl").read_text(encoding="utf-8").splitlines():
        if satir:
            karmalar[json.loads(satir)["dhash"]] = karmalar.get(json.loads(satir)["dhash"], 0) + 1
    cakisan = sum(v - 1 for v in karmalar.values() if v > 1)
    print(f"  dHash çakışması: {cakisan} kayıt ({cakisan / max(yazilan, 1):.2%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
