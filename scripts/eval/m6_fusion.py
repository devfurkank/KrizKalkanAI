#!/usr/bin/env python
"""M6 değerlendirmesi — kalibrasyon ve füzyon.

İki iş yapar:

    1. Her sinyal için isotonic regresyon uydurur ve ECE'yi kalibrasyon
       ÖNCESİ/SONRASI ölçer. Kalibrasyonun işe yarayıp yaramadığı ancak bu
       karşılaştırmayla görülür.
    2. Uçtan uca sınıflandırmayı ölçer (makro-F1, karışıklık matrisi).

Kalibrasyon noktaları elle yazılmıştı; bu betik onları ölçümle değiştirir.
Çıktı, `fusion/calibration.py` içine yapıştırılabilecek biçimdedir.

Veri sızıntısı önlemi: isotonic uydurma ve ECE ölçümü AYRI bölmelerde yapılır.
Aynı veride hem uydurup hem ölçmek, kalibrasyonu olduğundan iyi gösterir.

Çıktı: docs/metrikler/m6.md + models/m6_fusion/kalibrasyon.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.fusion.calibration import expected_calibration_error  # noqa: E402
from krizkalkan_core.pipeline import AnalysisPipeline  # noqa: E402
from krizkalkan_core.taxonomy import Verdict  # noqa: E402

KUME = REPO_ROOT / "data" / "processed" / "m6_uctan_uca.jsonl"
RAPOR = REPO_ROOT / "docs" / "metrikler" / "m6.md"
CIKTI = REPO_ROOT / "models" / "m6_fusion"

#: Sinyal → o sinyalin "doğru" saydığı sınıf. İsotonic regresyon, ham skoru
#: bu olayın gerçekleşme olasılığına eşler.
#:
#: `provenance.match` bu listede YOKTUR ve bu bilinçlidir: köken benzerliği
#: "yanlış bağlam" olasılığını ölçmez, "aynı içerik" olasılığını ölçer. Yanlış
#: bağlam kararı benzerlikten değil konum çelişkisinden gelir (bir kural, bir
#: skor değil). Uçtan uca kümede yanlış bağlam ve temiz medya vakaları AYNI
#: görüntüleri kullandığı için benzerlik ikisinde de aynıdır; o sinyali bu küme
#: üzerinden kalibre etmek düz 0,5 üretir — doğru cevap, ama yanlış soru.
#: Köken sinyali kendi kümesiyle (indeks içi / indeks dışı) kalibre edilir.
SINYAL_HEDEFI: dict[str, Verdict] = {
    "text.manipulative": Verdict.PROVOKATIF_CERCEVELEME,
    "knowledge.verdict": Verdict.DOGRULANMAMIS_IDDIA,
}

#: Sınıf etiketiyle değil, vakanın META VERİSİYLE tanımlanan hedefler.
#:
#: `multimodal.scene_claim` "sahne iddiayla çelişiyor" der. Bunu YANLIŞ_BAĞLAM
#: sınıfına göre kalibre etmek yanlış olurdu: o sınıf konum çelişkisi vakalarını
#: da içerir ve orada sahne İDDİAYLA UYUMLUDUR. Hedef, vakanın kendi
#: alanlarından okunur.
META_HEDEFI: dict[str, str] = {
    "multimodal.scene_claim": "sahne_uyusmazligi",
}


def _sahne_uyusmazligi(vaka: dict) -> int | None:
    """Vaka bir sahne uyuşmazlığı mı? İlgisizse None."""
    gercek, iddia = vaka.get("gercek_tur"), vaka.get("iddia_edilen_tur")
    if gercek is None or iddia is None:
        return None
    return int(gercek != iddia)


META_COZUCU = {"sahne_uyusmazligi": _sahne_uyusmazligi}

#: Kalibrasyon eğrisinde tutulacak azami kırılım noktası sayısı.
AZAMI_NOKTA = 12


def _medya_yolu(medya: str | None) -> str | None:
    """Kümedeki göreli medya yolunu bu makinedeki mutlak yola çevirir.

    Eski kümeler mutlak yol taşıyor olabilir; onlar olduğu gibi geçirilir ve
    dosya yoksa boru hattı zaten medyasız davranır. Yeni kümeler depo köküne
    göreli yazılıyor ve makineden makineye taşınabiliyor.
    """
    if not medya:
        return None
    yol = Path(medya)
    return str(yol if yol.is_absolute() else REPO_ROOT / yol)


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=True,
        ).stdout.strip()
    except Exception:
        return "—"


def vakalari_calistir(vakalar: list[dict]) -> list[dict]:
    """Her vakayı boru hattından geçirip sinyalleri toplar."""
    hat = AnalysisPipeline()
    sonuclar = []
    for sira, vaka in enumerate(vakalar, 1):
        hat.clear_cache()
        analiz = hat.analyse(
            body=vaka["metin"],
            media_kind=vaka["medya_turu"],
            media_fingerprint=_medya_yolu(vaka.get("medya")),
        )
        sonuclar.append(
            {
                "id": vaka["id"],
                "gercek": vaka["sinif"],
                "tahmin": analiz.verdict.value,
                "sinyaller": {s.key: s.raw_score for s in analiz.signals if not s.abstained},
                "meta": {ad: cozucu(vaka) for ad, cozucu in META_COZUCU.items()},
            }
        )
        if sira % 50 == 0:
            print(f"    {sira}/{len(vakalar)}")
    return sonuclar


def isotonic_noktalar(ham: list[float], hedef: list[int]) -> list[tuple[float, float]]:
    """İsotonic regresyonu parçalı doğrusal noktalara indirger.

    Düzgün aralıklı ızgara yerine modelin KENDİ kırılım noktaları kullanılır.
    Izgara keskin geçişleri kaçırıyordu: köken benzerliği neredeyse ikili
    davranır (eşleşen içerik mesafe 0–2, eşleşmeyen ~16) ve altı noktalık ızgara
    bu basamağı 0,94–1,00 arasına sıkıştırıp geçerli eşleşmeleri (benzerlik 0,9)
    sıfıra düşürüyordu.
    """
    from sklearn.isotonic import IsotonicRegression

    model = IsotonicRegression(out_of_bounds="clip", increasing=True, y_min=0.0, y_max=1.0)
    model.fit(np.asarray(ham), np.asarray(hedef, dtype=float))

    xs = np.asarray(model.X_thresholds_, dtype=float)
    ys = np.asarray(model.y_thresholds_, dtype=float)
    if len(xs) > AZAMI_NOKTA:
        secim = np.unique(np.linspace(0, len(xs) - 1, AZAMI_NOKTA).astype(int))
        xs, ys = xs[secim], ys[secim]
    noktalar = [(round(float(x), 4), round(float(y), 4)) for x, y in zip(xs, ys, strict=True)]

    # Uçları tamamla: calibrate() 0 ve 1 arasında tanımlı olmalı.
    if noktalar[0][0] > 0.0:
        noktalar.insert(0, (0.0, noktalar[0][1]))
    if noktalar[-1][0] < 1.0:
        noktalar.append((1.0, noktalar[-1][1]))

    # Monotonluğu garanti et — calibrate() bunu varsayar.
    duzeltilmis = [noktalar[0]]
    for x, y in noktalar[1:]:
        if x > duzeltilmis[-1][0]:
            duzeltilmis.append((x, max(y, duzeltilmis[-1][1])))
    return duzeltilmis


def kalibre_et(sonuclar: list[dict], tohum: int) -> dict[str, dict]:
    """Sinyal başına isotonic uydurur ve ECE'yi ayrı bölmede ölçer."""
    from sklearn.isotonic import IsotonicRegression

    rastgele = np.random.default_rng(tohum)
    cikti: dict[str, dict] = {}

    hedefler: list[tuple[str, object]] = [(a, ("sinif", h)) for a, h in SINYAL_HEDEFI.items()] + [
        (a, ("meta", m)) for a, m in META_HEDEFI.items()
    ]

    for anahtar, (tur, hedef) in hedefler:
        if tur == "sinif":
            ciftler = [
                (s["sinyaller"][anahtar], int(s["gercek"] == hedef.value))
                for s in sonuclar
                if anahtar in s["sinyaller"]
            ]
        else:
            ciftler = [
                (s["sinyaller"][anahtar], s["meta"][hedef])
                for s in sonuclar
                if anahtar in s["sinyaller"] and s["meta"].get(hedef) is not None
            ]
        if len(ciftler) < 30 or len({e for _, e in ciftler}) < 2:
            print(f"  {anahtar:22s} atlandı (n={len(ciftler)}, tek sınıf olabilir)")
            continue

        ham = np.array([c[0] for c in ciftler])
        etiket = np.array([c[1] for c in ciftler])

        # Uydurma ve ölçüm ayrı bölmelerde: aynı veride hem uydurup hem ölçmek
        # kalibrasyonu olduğundan iyi gösterir.
        sira = rastgele.permutation(len(ham))
        kesme = len(ham) // 2
        uydur, olc = sira[:kesme], sira[kesme:]

        model = IsotonicRegression(out_of_bounds="clip", increasing=True, y_min=0.0, y_max=1.0)
        model.fit(ham[uydur], etiket[uydur].astype(float))

        once = expected_calibration_error(
            [(float(p), bool(e)) for p, e in zip(ham[olc], etiket[olc], strict=True)]
        )
        sonra = expected_calibration_error(
            [(float(p), bool(e)) for p, e in zip(model.predict(ham[olc]), etiket[olc], strict=True)]
        )

        cikti[anahtar] = {
            "n": len(ciftler),
            "pozitif": int(etiket.sum()),
            "ece_once": once,
            "ece_sonra": sonra,
            "noktalar": isotonic_noktalar(ham.tolist(), etiket.tolist()),
        }
        print(
            f"  {anahtar:22s} n={len(ciftler):3d} poz={int(etiket.sum()):3d}  "
            f"ECE {once:.4f} → {sonra:.4f}"
        )
    return cikti


def _letterbox_kalibrasyon(goruntu):
    """Kalibrasyon için orta zorlukta geometrik dönüşüm."""
    from PIL import Image as PILImage

    en, boy = goruntu.size
    bant = int(boy * 0.10)
    yeni = PILImage.new("RGB", (en, boy + 2 * bant), (0, 0, 0))
    yeni.paste(goruntu, (0, bant))
    return yeni


def koken_kalibrasyonu(tohum: int) -> dict | None:
    """Köken benzerliğini kendi iddiasına göre kalibre eder.

    Soru: "bu benzerlik skoru, sorgunun indeksteki kayıtla AYNI içerik olma
    olasılığı hakkında ne söylüyor?" Pozitifler dönüşümden geçirilmiş indeks
    içi görüntüler, negatifler indekse hiç girmemiş görüntülerdir.
    """
    from krizkalkan_core.provenance import imaging
    from krizkalkan_core.provenance.index import ProvenanceIndex
    from PIL import Image
    from sklearn.isotonic import IsotonicRegression

    indeks_dizini = REPO_ROOT / "models" / "m1_provenance"
    goruntuler = REPO_ROOT / "data" / "external" / "provenance" / "goruntuler"
    if not (indeks_dizini / "index.jsonl").exists():
        print("  köken kalibrasyonu atlandı: M1 indeksi yok")
        return None

    indeks = ProvenanceIndex(indeks_dizini)

    # İndeks korpusla uyumsuzsa kalibrasyon ÜRETİLMEZ.
    #
    # Yaşandı: uyumsuz bir korpusta koşturulduğunda isotonic, "benzerlik 1,0 →
    # doğru olma olasılığı 0,54" öğrendi ve bu değer üretime yazıldı. Füzyonun
    # yanlış bağlam eşiği 0,60 olduğu için demo senaryoları sessizce TEMİZ
    # dönmeye başladı. Kalibrasyon doğru öğrenilmişti; veri bozuktu.
    #
    # Bozuk veriden öğrenilmiş bir kalibrasyon, kalibrasyonsuz sistemden
    # kötüdür: elle yazılmış yedek noktalar hiç değilse makul davranıyor.
    if getattr(indeks, "uyumsuz_dosya", 0) > 0:
        print(
            f"  🔴 köken kalibrasyonu ATLANDI: indeks korpusla uyumsuz "
            f"({indeks.uyumsuz_dosya} kayıt başka görüntüye işaret ediyor). "
            "İndeks ile görüntüler aynı koşudan gelmeli."
        )
        return None

    rastgele = np.random.default_rng(tohum)

    # İndeks, korpusta artık bulunmayan dosyalara atıf yapabilir: indeks ile
    # görüntüler ayrı taşınıyor ve `fetch_provenance.py` farklı makinelerde
    # farklı sayıda görüntü toplayabiliyor (Commons kategorileri değişiyor).
    # Eksik dosyada çökmek yerine atlanır, ama sessizce değil: kaç kayıt
    # düştüğü basılır, çünkü ölçümün n değeri bundan etkilenir.
    tumu = sorted({k.dosya for k in indeks.kayitlar})
    dosyalar = [d for d in tumu if (goruntuler / d).exists()]
    if (eksik := len(tumu) - len(dosyalar)) > 0:
        print(
            f"  ⚠ indeksteki {eksik}/{len(tumu)} görüntü korpusta yok, atlandı "
            "(indeks ile görüntüler ayrı taşınıyor)"
        )
    if not dosyalar:
        print("  köken kalibrasyonu atlandı: indeksteki hiçbir görüntü korpusta yok")
        return None

    ornekler = list(rastgele.choice(dosyalar, size=min(120, len(dosyalar)), replace=False))

    ham: list[float] = []
    etiket: list[int] = []

    # Pozitif: indeks içi görüntülerin dönüşüme uğramış hâlleri.
    for dosya in ornekler:
        goruntu = Image.open(goruntuler / dosya).convert("RGB")
        # Dönüşümler kolaydan zora: kolaylar mesafe 0–2, zorlar 6–14 üretir.
        # Orta bant doldurulmazsa isotonic o aralıkta veri görmez ve geçerli
        # eşleşmeleri sıfıra düşürür.
        for donusum in (
            lambda g: g,
            lambda g: g.resize((854, 480)),
            lambda g: g.crop(
                (int(g.width * 0.1), int(g.height * 0.1), int(g.width * 0.9), int(g.height * 0.9))
            ),
            lambda g: g.rotate(4, expand=False, fillcolor=(0, 0, 0)),
            lambda g: g.rotate(8, expand=False, fillcolor=(0, 0, 0)),
            _letterbox_kalibrasyon,
        ):
            d, f = imaging.karmalar(donusum(goruntu))
            adaylar = indeks.ara(d, f, k=1)
            if adaylar:
                ham.append(adaylar[0].benzerlik)
                etiket.append(int(adaylar[0].kayit.dosya == dosya))

    # Negatif: indekse hiç girmemiş görüntüler.
    tutulan = indeks_dizini / "tutulan.jsonl"
    if tutulan.exists():
        indekstekiler = set(dosyalar)
        for satir in tutulan.read_text(encoding="utf-8").splitlines()[:120]:
            if not satir:
                continue
            ad = json.loads(satir)["dosya"]
            if ad in indekstekiler or not (goruntuler / ad).exists():
                continue
            d, f = imaging.karmalar(goruntuler / ad)
            adaylar = indeks.ara(d, f, k=1)
            if adaylar:
                ham.append(adaylar[0].benzerlik)
                etiket.append(0)

    if len(ham) < 30 or len(set(etiket)) < 2:
        print(f"  köken kalibrasyonu atlandı (n={len(ham)})")
        return None

    ham_d, etiket_d = np.array(ham), np.array(etiket)
    sira = rastgele.permutation(len(ham_d))
    kesme = len(ham_d) // 2
    uydur, olc = sira[:kesme], sira[kesme:]

    model = IsotonicRegression(out_of_bounds="clip", increasing=True, y_min=0.0, y_max=1.0)
    model.fit(ham_d[uydur], etiket_d[uydur].astype(float))

    once = expected_calibration_error(
        [(float(p), bool(e)) for p, e in zip(ham_d[olc], etiket_d[olc], strict=True)]
    )
    sonra = expected_calibration_error(
        [(float(p), bool(e)) for p, e in zip(model.predict(ham_d[olc]), etiket_d[olc], strict=True)]
    )
    print(
        f"  {'provenance.match':22s} n={len(ham_d):3d} poz={int(etiket_d.sum()):3d}  "
        f"ECE {once:.4f} → {sonra:.4f}  (indeks içi/dışı kümesi)"
    )
    return {
        "n": len(ham_d),
        "pozitif": int(etiket_d.sum()),
        "ece_once": once,
        "ece_sonra": sonra,
        "noktalar": isotonic_noktalar(ham_d.tolist(), etiket_d.tolist()),
        "kume": "M1 indeks içi/dışı",
    }


def siniflandirma_olcumu(sonuclar: list[dict]) -> dict:
    """Uçtan uca sınıf başarımı ve karışıklık matrisi."""
    siniflar = sorted({s["gercek"] for s in sonuclar} | {s["tahmin"] for s in sonuclar})
    matris: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s in sonuclar:
        matris[s["gercek"]][s["tahmin"]] += 1

    f1ler = {}
    for sinif in sorted({s["gercek"] for s in sonuclar}):
        tp = matris[sinif][sinif]
        fp = sum(matris[g][sinif] for g in matris if g != sinif)
        fn = sum(matris[sinif][t] for t in matris[sinif] if t != sinif)
        kesinlik = tp / (tp + fp) if tp + fp else 0.0
        duyarlilik = tp / (tp + fn) if tp + fn else 0.0
        f1ler[sinif] = (
            0.0
            if kesinlik + duyarlilik == 0
            else 2 * kesinlik * duyarlilik / (kesinlik + duyarlilik)
        )

    return {
        "makro_f1": round(float(np.mean(list(f1ler.values()))), 4),
        "dogruluk": round(
            sum(1 for s in sonuclar if s["gercek"] == s["tahmin"]) / len(sonuclar), 4
        ),
        "sinif_f1": {k: round(v, 4) for k, v in f1ler.items()},
        "matris": {g: dict(t) for g, t in matris.items()},
        "siniflar": siniflar,
    }


def rapor_yaz(kalibrasyon: dict, siniflandirma: dict, n: int) -> Path:
    simdi = datetime.now(UTC).strftime("%d.%m.%Y %H:%M UTC")
    s = [
        "# M6 — Kalibre Kanıt Füzyonu · Değerlendirme",
        "",
        f"*`scripts/eval/m6_fusion.py` tarafından üretildi · {simdi} · commit `{_git_commit()}`*",
        "",
        "| | |",
        "|---|---|",
        f"| Değerlendirme kümesi | {n} vaka |",
        f"| Sınıf sayısı | {len(siniflandirma['sinif_f1'])} (7'nin {len(siniflandirma['sinif_f1'])}'i) |",
        "",
        "## Kalibrasyon",
        "",
        "Kalibrasyon noktaları önceden elle yazılmıştı. Bu tablo onları ölçümle",
        "değiştirir. ECE, uydurmada KULLANILMAYAN ayrı bölmede hesaplanır: aynı",
        "veride hem uydurup hem ölçmek kalibrasyonu olduğundan iyi gösterir.",
        "",
        "| Sinyal | n | Pozitif | ECE (önce) | ECE (sonra) |",
        "|---|---|---|---|---|",
    ]
    s += [
        f"| `{k}` | {d['n']} | {d['pozitif']} | {d['ece_once']:.4f} | **{d['ece_sonra']:.4f}** |"
        for k, d in kalibrasyon.items()
    ]
    s += [
        "",
        "> Rapor 3.2 hedefi: ECE ≤ 0,05",
        "",
        "## Uçtan uca sınıflandırma",
        "",
        "| | |",
        "|---|---|",
        f"| Makro-F1 | **{siniflandirma['makro_f1']:.4f}** |",
        f"| Doğruluk | {siniflandirma['dogruluk']:.4f} |",
        "",
        "| Sınıf | F1 |",
        "|---|---|",
    ]
    s += [f"| {k} | {v:.4f} |" for k, v in sorted(siniflandirma["sinif_f1"].items())]

    s += [
        "",
        "### Karışıklık matrisi",
        "",
        "| gerçek \\\\ tahmin | " + " | ".join(siniflandirma["siniflar"]) + " |",
        "|" + "---|" * (len(siniflandirma["siniflar"]) + 1),
    ]
    for gercek in sorted(siniflandirma["matris"]):
        satir = siniflandirma["matris"][gercek]
        s.append(
            f"| **{gercek}** | "
            + " | ".join(str(satir.get(t, 0)) for t in siniflandirma["siniflar"])
            + " |"
        )

    s += [
        "",
        "## Kapsam sınırı",
        "",
        "SENTETİK_MEDYA ve MANİPÜLE_MEDYA sınıfları kümede YOKTUR: bu sınıflar",
        "M4 ve M2 modüllerini gerektirir ve o modüller henüz kurulmadı. Makro-F1",
        "bu nedenle 7 sınıfın değil, veri bulunan sınıfların ortalamasıdır ve",
        "rapor 3.2'deki 6 sınıflı hedefle doğrudan karşılaştırılamaz.",
        "",
        "Görüntü tabanlı vakalarda metin şablondan üretilmiştir; o vakaların",
        "hedefi köken sinyalini yalıtmaktır, metin motorunu ölçmek değil.",
        "",
        "PROVOKATİF_ÇERÇEVELEME ve elle yazılmış TEMİZ metinler takım tarafından",
        "yazılmıştır (gerçek veri kaynağı yok); n değerleri tabloda görünür.",
        "",
    ]
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text("\n".join(s), encoding="utf-8")
    return RAPOR


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--tohum", type=int, default=42)
    args = a.parse_args()

    if not KUME.exists():
        print(f"🔴 {KUME} yok. Önce: python scripts/data/build_m6_set.py")
        return 1

    vakalar = [json.loads(s) for s in KUME.read_text(encoding="utf-8").splitlines() if s]
    print(f"→ {len(vakalar)} vaka boru hattından geçiriliyor")
    sonuclar = vakalari_calistir(vakalar)

    print("\n→ kalibrasyon")
    kalibrasyon = kalibre_et(sonuclar, args.tohum)
    if (koken := koken_kalibrasyonu(args.tohum)) is not None:
        kalibrasyon["provenance.match"] = koken

    print("\n→ sınıflandırma")
    siniflandirma = siniflandirma_olcumu(sonuclar)
    print(f"  makro-F1 {siniflandirma['makro_f1']:.4f} · doğruluk {siniflandirma['dogruluk']:.4f}")
    for k, v in sorted(siniflandirma["sinif_f1"].items()):
        print(f"    {k:26s} {v:.4f}")

    CIKTI.mkdir(parents=True, exist_ok=True)
    (CIKTI / "kalibrasyon.json").write_text(
        json.dumps(
            {
                k: {"noktalar": d["noktalar"], "n": d["n"], "ece": d["ece_sonra"]}
                for k, d in kalibrasyon.items()
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n✓ {rapor_yaz(kalibrasyon, siniflandirma, len(vakalar)).relative_to(REPO_ROOT)}")
    print(f"✓ {(CIKTI / 'kalibrasyon.json').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
