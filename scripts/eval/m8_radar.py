#!/usr/bin/env python
"""M8 değerlendirmesi — iddia kümeleme kalitesi.

Kriz Radar'ın işi, aynı iddianın farklı ifadelerini tek satırda toplamaktır.
Ölçüm bu yüzden şunu sorar: **aynı iddiayı anlatan iki metin aynı kümeye
düşüyor mu?**

Değerlendirme çiftleri M5 kümesinden gelir: her madde gerçek bir DMM iddiası ve
o iddianın sosyal medya diline elle yeniden yazılmış hâlidir. Kelime örtüşmesi
kasten düşük tutulduğu için bu, kümelemenin anlamsal olup olmadığını sınayan
zor bir testtir.

Ayrıca gürültü dayanıklılığı ölçülür: gerçek iddialara sosyal medya eklentileri
("ACİL!! PAYLAŞIN") eklenmiş varyantlar aynı kümede kalmalıdır.

Çıktı: docs/metrikler/m8.md
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.knowledge import corpus  # noqa: E402
from krizkalkan_core.models.cards import Measurement, ModelCard  # noqa: E402
from krizkalkan_core.radar.engine import _token_kumeleri, kumele  # noqa: E402
from krizkalkan_core.text.lexicon import normalize  # noqa: E402

KUME = Path(__file__).parent / "kumeler" / "m5_geri_getirme.json"
RAPOR = REPO_ROOT / "docs" / "metrikler" / "m8.md"

#: Sosyal medyada aynı iddianın üzerine eklenen tipik gürültü.
GURULTU_SABLONLARI = (
    "ACİL!! {metin} HERKES PAYLAŞSIN",
    "Duyduğuma göre {metin} doğru mu acaba",
    "{metin} Bu nasıl olur ya!!! 😡",
)


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


def _ari(gercek: list[int], tahmin: list[int]) -> float:
    """Düzeltilmiş Rand İndeksi — rastgele kümelemede 0, kusursuzda 1."""
    from sklearn.metrics import adjusted_rand_score

    return round(float(adjusted_rand_score(gercek, tahmin)), 4)


def _birlikte_oran(gercek: list[int], tahmin: list[int]) -> float:
    """Aynı gruba ait çiftlerin kaçı aynı kümeye düştü?"""
    birlikte = toplam = 0
    for i in range(len(gercek)):
        for j in range(i + 1, len(gercek)):
            if gercek[i] == gercek[j]:
                toplam += 1
                birlikte += int(tahmin[i] == tahmin[j])
    return round(birlikte / max(toplam, 1), 4)


def _ayri_oran(gercek: list[int], tahmin: list[int]) -> float:
    """Farklı gruplara ait çiftlerin kaçı ayrı kümede kaldı? (kirlilik ölçüsü)"""
    ayri = toplam = 0
    for i in range(len(gercek)):
        for j in range(i + 1, len(gercek)):
            if gercek[i] != gercek[j]:
                toplam += 1
                ayri += int(tahmin[i] != tahmin[j])
    return round(ayri / max(toplam, 1), 4)


def yeniden_ifade_kumesi() -> tuple[list[str], list[int]]:
    """M5 kümesinden (gerçek iddia, elle yazılmış yeniden ifade) çiftleri."""
    veri = json.loads(KUME.read_text(encoding="utf-8"))
    kayitlar = corpus.records()
    metinler: list[str] = []
    gruplar: list[int] = []

    for grup, madde in enumerate(veri["sorgular"]):
        hedef = normalize(madde["hedef_desen"])
        kayit = next((k for k in kayitlar if hedef in normalize(k.claim)), None)
        if kayit is None:
            continue
        # Kaydın iddiası uzun olabilir; ilk cümlesi yeterlidir.
        metinler.append(kayit.claim[:160])
        gruplar.append(grup)
        metinler.append(madde["sorgu"])
        gruplar.append(grup)
    return metinler, gruplar


def gurultu_kumesi(adet: int = 30) -> tuple[list[str], list[int]]:
    """Gerçek iddialar + sosyal medya gürültüsü eklenmiş varyantları."""
    kayitlar = [k for k in corpus.records() if 60 < len(k.claim) < 200][:adet]
    metinler: list[str] = []
    gruplar: list[int] = []
    for grup, kayit in enumerate(kayitlar):
        temel = kayit.claim[:140]
        metinler.append(temel)
        gruplar.append(grup)
        for sablon in GURULTU_SABLONLARI:
            metinler.append(sablon.format(metin=temel))
            gruplar.append(grup)
    return metinler, gruplar


def olc(ad: str, metinler: list[str], gercek: list[int]) -> dict:
    """Her iki yöntemi aynı küme üzerinde ölçer."""
    gomme_etiket, yontem = kumele(metinler)
    token_etiket = _token_kumeleri(metinler)

    sonuc = {
        "ad": ad,
        "n": len(metinler),
        "grup": len(set(gercek)),
        "yontem": yontem,
        "gomme": {
            "ari": _ari(gercek, gomme_etiket),
            "birlikte": _birlikte_oran(gercek, gomme_etiket),
            "ayri": _ayri_oran(gercek, gomme_etiket),
            "kume": len(set(gomme_etiket)),
        },
        "token": {
            "ari": _ari(gercek, token_etiket),
            "birlikte": _birlikte_oran(gercek, token_etiket),
            "ayri": _ayri_oran(gercek, token_etiket),
            "kume": len(set(token_etiket)),
        },
    }
    print(f"\n  {ad} · n={len(metinler)} · {len(set(gercek))} gerçek grup")
    for yol in ("token", "gomme"):
        d = sonuc[yol]
        etiket = "anahtar terim" if yol == "token" else "gömme + HDBSCAN"
        print(
            f"    {etiket:18s} ARI {d['ari']:6.4f} · birlikte {d['birlikte']:.4f} · "
            f"ayrı {d['ayri']:.4f} · {d['kume']} küme"
        )
    return sonuc


def rapor_yaz(sonuclar: list[dict]) -> Path:
    simdi = datetime.now(UTC).strftime("%d.%m.%Y %H:%M UTC")
    s = [
        "# M8 — Kriz Radar · Kümeleme Değerlendirmesi",
        "",
        f"*`scripts/eval/m8_radar.py` tarafından üretildi · {simdi} · commit `{_git_commit()}`*",
        "",
        "Radar'ın işi aynı iddianın farklı ifadelerini tek satırda toplamaktır.",
        "Ölçüm bunu sorar: aynı iddiayı anlatan iki metin aynı kümeye düşüyor mu?",
        "",
        "- **birlikte**: aynı gruba ait çiftlerin aynı kümeye düşme oranı (duyarlılık)",
        "- **ayrı**: farklı gruplara ait çiftlerin ayrı kalma oranı (kesinlik)",
        "- **ARI**: düzeltilmiş Rand indeksi — rastgele kümelemede 0, kusursuzda 1",
        "",
    ]
    for sonuc in sonuclar:
        s += [
            f"## {sonuc['ad']}",
            "",
            f"n = {sonuc['n']} metin · {sonuc['grup']} gerçek grup",
            "",
            "| Yöntem | ARI | Birlikte | Ayrı | Bulunan küme |",
            "|---|---|---|---|---|",
            f"| Anahtar terim örtüşmesi | {sonuc['token']['ari']:.4f} | "
            f"{sonuc['token']['birlikte']:.4f} | {sonuc['token']['ayri']:.4f} | "
            f"{sonuc['token']['kume']} |",
            f"| **Gömme + HDBSCAN** | **{sonuc['gomme']['ari']:.4f}** | "
            f"**{sonuc['gomme']['birlikte']:.4f}** | {sonuc['gomme']['ayri']:.4f} | "
            f"{sonuc['gomme']['kume']} |",
            "",
        ]
    s += [
        "## Yöntem notu",
        "",
        "Yeniden ifade kümesi, gerçek DMM iddiaları ile onların sosyal medya",
        "diline **elle** yeniden yazılmış hâllerinden oluşur. Kelime örtüşmesi",
        "kasten düşük tutulduğu için bu, kümelemenin gerçekten anlamsal olup",
        "olmadığını sınayan zor bir testtir.",
        "",
        "Gürültü kümesi, aynı iddianın üzerine sosyal medya eklentileri",
        '("ACİL!! PAYLAŞIN") eklenmiş varyantlarını içerir; kolay testtir ve',
        "kümelemenin gürültüyle dağılmadığını doğrular.",
        "",
        "HDBSCAN'in gürültü olarak işaretlediği iddialar tek üyeli kümelere",
        "dönüştürülür: bir kez görülmüş iddia da bir iddiadır, panelden düşürülmez.",
        "",
    ]
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text("\n".join(s), encoding="utf-8")
    return RAPOR


def kart_yaz(sonuclar: list[dict]) -> Path:
    """Model kartı — M8'in kendi ağırlığı yoktur, M5'in kodlayıcısını kullanır."""
    zor = next(s for s in sonuclar if "zor" in s["ad"])
    kolay = next(s for s in sonuclar if "kolay" in s["ad"])

    kart = ModelCard(
        name="m8_radar",
        module="M8",
        title="Kriz Radar İddia Kümeleme",
        version="0.1.0",
        base_model="intfloat/multilingual-e5-base (M5 kodlayıcısı) + HDBSCAN",
        purpose=(
            "Aynı iddianın farklı ifadelerini tek kümede toplar; panel yayılım "
            "hızını ve ivmesini bu kümeler üzerinden hesaplar."
        ),
        training_data=["Eğitim verisi yok; kümeleme denetimsizdir"],
        training_procedure=(
            "Eğitim yok. Cümle gömmesi M5'in kodlayıcısıyla üretilir (ek ağırlık "
            "indirilmez), HDBSCAN ile kümelenir. Gürültü olarak işaretlenen "
            "iddialar tek üyeli kümelere dönüştürülür: bir kez görülmüş iddia da "
            "bir iddiadır, panelden düşürülmez."
        ),
        hyperparameters={"min_cluster_size": 2, "metric": "euclidean"},
        split_strategy="Değerlendirme, gerçek DMM iddiaları ve elle yazılmış "
        "yeniden ifadeleri üzerinde yapılır",
        measurements=[
            Measurement("ari_zor", zor["gomme"]["ari"], "elle yazılmış yeniden ifadeler", zor["n"]),
            Measurement(
                "birlikte_zor", zor["gomme"]["birlikte"], "elle yazılmış yeniden ifadeler", zor["n"]
            ),
            Measurement("ari_kolay", kolay["gomme"]["ari"], "gürültü varyantları", kolay["n"]),
        ],
        known_limits=[
            f"Zor kümede ARI {zor['gomme']['ari']:.4f}: aynı iddianın elle yeniden "
            "yazılmış hâllerinin yaklaşık yarısı ayrı kümelerde kalıyor. Panel bu "
            "durumda tek bir yalanı iki satır olarak gösterir — birleştirmeyi "
            "kaçırmak, yanlış birleştirmekten daha az zararlıdır ve eşik bu yönde "
            "seçilmiştir.",
            "Kümeleme denetimsizdir ve kriz alanına uyarlanmamıştır; gömme modeli genel amaçlıdır.",
            "Değerlendirme kümesi küçüktür (n=" + str(zor["n"]) + " ve " + str(kolay["n"]) + ").",
        ],
        ethical_notes=[
            "Panelin iki sayacı her koşulda görünür kalır: Kural 0 ile korunan "
            "yardım çağrısı sayısı ve kaldırılan içerik sayısı (her zaman sıfır).",
            "Kümeleme bir sıralama aracıdır, hüküm değil: küme büyüklüğü içeriğin "
            "yanlış olduğunu göstermez, yalnızca yayılımını gösterir.",
        ],
        out_of_scope=[
            "Küme büyüklüğünden doğruluk hükmü çıkarmak",
            "Kural 0 ile korunmuş içerikleri kümelemek — panel onları hiç almaz",
        ],
        license="Model: MIT (e5) · BSD-3 (scikit-learn)",
        git_commit=_git_commit(),
    )
    return kart.write_markdown(REPO_ROOT / "docs" / "model-kartlari")


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    sonuclar = [
        olc("Yeniden ifade kümesi (zor)", *yeniden_ifade_kumesi()),
        olc("Gürültü dayanıklılığı (kolay)", *gurultu_kumesi()),
    ]
    print(f"\n✓ {rapor_yaz(sonuclar).relative_to(REPO_ROOT)}")
    print(f"✓ {kart_yaz(sonuclar).relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
