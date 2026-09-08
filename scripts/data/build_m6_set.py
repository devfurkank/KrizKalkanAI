#!/usr/bin/env python
"""M6 uçtan uca değerlendirme kümesini kurar.

Kalibrasyon ve füzyon ölçümü, sınıfı bilinen içerik gerektirir. Küme, elde
gerçek veri BULUNAN sınıflardan kurulur; bulunmayanlar kasten boş bırakılır ve
raporda öyle beyan edilir:

    YANLIŞ_BAĞLAM        ✓ M1 korpusu görüntüsü + başka şehir iddiası
    TEMİZ (medya)        ✓ aynı görüntü + doğru şehir iddiası
    DOĞRULANMAMIŞ_İDDİA  ✓ DMM'de yalanlanmış gerçek iddia metinleri
    TEMİZ (metin)        ✓ DMM tekzip metinleri + elle yazılmış resmî duyurular
    PROVOKATİF_ÇERÇEVELEME ✓ elle yazılmış metinler
    SENTETİK_MEDYA       ✗ M4 yok — üretilmiş medya kümesi gerekir
    MANİPÜLE_MEDYA       ✗ M2 yok — ses/görüntü oynanmış içerik gerekir

Görüntü tabanlı çiftlerde metin şablondan üretilir ve bu raporda belirtilir:
o vakaların hedefi köken sinyalini ölçmektir, metin motorunu değil.

Çıktı: data/processed/m6_uctan_uca.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.knowledge import corpus as bilgi  # noqa: E402
from krizkalkan_core.taxonomy import Verdict  # noqa: E402

GORUNTU_DIZINI = REPO_ROOT / "data" / "external" / "provenance" / "goruntuler"
PROVENANCE_KAYIT = REPO_ROOT / "data" / "external" / "provenance" / "kayitlar.jsonl"
METINLER = REPO_ROOT / "scripts" / "eval" / "kumeler" / "m6_metinler.json"
CIKTI = REPO_ROOT / "data" / "processed" / "m6_uctan_uca.jsonl"

#: Görüntü vakalarında kullanılan metin şablonları. İddia edilen şehir
#: dışında hiçbir manipülatif işaret taşımazlar; amaç köken sinyalini
#: yalıtmaktır.
SABLONLAR = (
    "{sehir}'da çekilen görüntüler. Durum çok ağır.",
    "{sehir}'de yaşananlar. Ekipler bölgede çalışıyor.",
    "{sehir} bölgesinden son görüntüler.",
    "{sehir}'daki durum böyle. Paylaşmak istedim.",
)

#: Çelişki üretmek için kullanılan, korpusta BULUNMAYAN şehirler.
UZAK_SEHIRLER = ("İzmir", "Trabzon", "Edirne", "Rize", "Aydın", "Samsun", "Bursa")


def _sehir(konum: str) -> str:
    """Birleşik konumdan tek bir şehir adı çıkarır."""
    return konum.split("/")[0].strip()


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--medya-basina", type=int, default=60, help="görüntü sınıfı başına vaka")
    a.add_argument("--metin-basina", type=int, default=60, help="metin sınıfı başına vaka")
    a.add_argument("--tohum", type=int, default=42)
    args = a.parse_args()

    rastgele = random.Random(args.tohum)
    vakalar: list[dict] = []

    # ── Görüntü tabanlı sınıflar ──
    if PROVENANCE_KAYIT.exists():
        kayitlar = [
            k
            for s in PROVENANCE_KAYIT.read_text(encoding="utf-8").splitlines()
            if s
            and (k := json.loads(s))
            and (GORUNTU_DIZINI / k["dosya"]).exists()
            and _sehir(k["konum"]) not in ("Türkiye", "Deprem bölgesi")
        ]
        rastgele.shuffle(kayitlar)
        n = min(args.medya_basina, len(kayitlar) // 2)

        for kayit in kayitlar[:n]:
            sehir = _sehir(kayit["konum"])
            uzak = rastgele.choice([s for s in UZAK_SEHIRLER if s != sehir])
            vakalar.append(
                {
                    "id": f"m6-yb-{len(vakalar):04d}",
                    "sinif": Verdict.YANLIS_BAGLAM.value,
                    "metin": rastgele.choice(SABLONLAR).format(sehir=uzak),
                    "medya": str(GORUNTU_DIZINI / kayit["dosya"]),
                    "medya_turu": "image",
                    "kaynak": "M1 korpusu · şablon metin",
                    "gercek_konum": kayit["konum"],
                    "iddia_edilen_konum": uzak,
                }
            )

        for kayit in kayitlar[n : 2 * n]:
            sehir = _sehir(kayit["konum"])
            vakalar.append(
                {
                    "id": f"m6-tm-{len(vakalar):04d}",
                    "sinif": Verdict.TEMIZ.value,
                    "metin": rastgele.choice(SABLONLAR).format(sehir=sehir),
                    "medya": str(GORUNTU_DIZINI / kayit["dosya"]),
                    "medya_turu": "image",
                    "kaynak": "M1 korpusu · şablon metin · doğru bağlam",
                    "gercek_konum": kayit["konum"],
                    "iddia_edilen_konum": sehir,
                }
            )
    else:
        print("⚠️ M1 korpusu yok; görüntü tabanlı sınıflar atlandı")

    # ── Metin tabanlı sınıflar ──
    dmm = [k for k in bilgi.records() if k.record_id.startswith("DMM-B")]
    rastgele.shuffle(dmm)

    for kayit in dmm[: args.metin_basina]:
        vakalar.append(
            {
                "id": f"m6-di-{len(vakalar):04d}",
                "sinif": Verdict.DOGRULANMAMIS_IDDIA.value,
                "metin": kayit.claim[:400],
                "medya": None,
                "medya_turu": "yok",
                "kaynak": f"DMM · {kayit.record_id}",
            }
        )

    for kayit in dmm[args.metin_basina : 2 * args.metin_basina]:
        # Tekzip metni iddiayı öne sürmez, düzeltir: kurumsal ve temiz dildir.
        vakalar.append(
            {
                "id": f"m6-tt-{len(vakalar):04d}",
                "sinif": Verdict.TEMIZ.value,
                "metin": kayit.fact_check[:400],
                "medya": None,
                "medya_turu": "yok",
                "kaynak": f"DMM tekzip · {kayit.record_id}",
            }
        )

    metinler = json.loads(METINLER.read_text(encoding="utf-8"))
    for metin in metinler["provokatif"]:
        vakalar.append(
            {
                "id": f"m6-pr-{len(vakalar):04d}",
                "sinif": Verdict.PROVOKATIF_CERCEVELEME.value,
                "metin": metin,
                "medya": None,
                "medya_turu": "yok",
                "kaynak": "elle yazılmış",
            }
        )
    for metin in metinler["temiz"]:
        vakalar.append(
            {
                "id": f"m6-tr-{len(vakalar):04d}",
                "sinif": Verdict.TEMIZ.value,
                "metin": metin,
                "medya": None,
                "medya_turu": "yok",
                "kaynak": "elle yazılmış · resmî duyuru dili",
            }
        )

    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    with CIKTI.open("w", encoding="utf-8") as f:
        for v in vakalar:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")

    print(f"✓ {len(vakalar)} vaka → {CIKTI.relative_to(REPO_ROOT)}\n")
    dagilim: dict[str, int] = {}
    for v in vakalar:
        dagilim[v["sinif"]] = dagilim.get(v["sinif"], 0) + 1
    for sinif, sayi in sorted(dagilim.items(), key=lambda p: -p[1]):
        print(f"  {sayi:4d}  {sinif}")
    eksik = {Verdict.SENTETIK_MEDYA.value, Verdict.MANIPULE_MEDYA.value} - set(dagilim)
    if eksik:
        print(f"\n  ⚠️ veri bulunmayan sınıflar: {', '.join(sorted(eksik))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
