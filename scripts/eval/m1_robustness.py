#!/usr/bin/env python
"""M1 dayanıklılık değerlendirmesi — dönüşüm altında köken tespiti.

Dezenformasyon üreticileri pasif değildir: bir görüntüyü yeniden bağlamda
paylaşırken sıkıştırır, kırpar, çerçeveler, aynalar. Bu betik o dönüşümleri
uygular ve her biri için Recall@1'i ayrı ölçer (rapor 3.2 · dayanıklılık).

Ayrıca yanlış eşleşme oranı ölçülür: indekste OLMAYAN görüntülerle sorgu
yapıldığında sistem kaç kez "eşleşti" der? Bu sayı, Recall'dan daha kritiktir —
yanlış bir köken eşleşmesi kullanıcıya "bu görüntü başka bir olaya ait" demek
anlamına gelir ve sistemin en görünür hatasıdır.

Çıktı: docs/metrikler/m1-dayaniklilik.md + model kartı
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.models.cards import Measurement, ModelCard  # noqa: E402
from krizkalkan_core.provenance import imaging  # noqa: E402
from krizkalkan_core.provenance.hashing import MATCH_MAX_DISTANCE  # noqa: E402
from krizkalkan_core.provenance.index import ProvenanceIndex  # noqa: E402

KAYNAK = REPO_ROOT / "data" / "external" / "provenance" / "goruntuler"
INDEKS = REPO_ROOT / "models" / "m1_provenance"
RAPOR = REPO_ROOT / "docs" / "metrikler" / "m1-dayaniklilik.md"


# ─────────────────────────── Dönüşümler ───────────────────────────


def _yeniden_kodla(g: Image.Image, kalite: int = 30) -> Image.Image:
    tampon = BytesIO()
    g.save(tampon, format="JPEG", quality=kalite)
    tampon.seek(0)
    return Image.open(tampon).convert("RGB")


def _kirp(g: Image.Image, oran: float = 0.2) -> Image.Image:
    en, boy = g.size
    dx, dy = int(en * oran / 2), int(boy * oran / 2)
    return g.crop((dx, dy, en - dx, boy - dy))


def _letterbox(g: Image.Image, oran: float = 0.25) -> Image.Image:
    en, boy = g.size
    bant = int(boy * oran / 2)
    yeni = Image.new("RGB", (en, boy + 2 * bant), (0, 0, 0))
    yeni.paste(g, (0, bant))
    return yeni


def _logo(g: Image.Image) -> Image.Image:
    g = g.copy()
    cizim = ImageDraw.Draw(g)
    en, boy = g.size
    cizim.rectangle([en - int(en * 0.28), 8, en - 8, 8 + int(boy * 0.12)], fill=(220, 30, 30))
    cizim.text((en - int(en * 0.26), 14), "SON DAKIKA", fill=(255, 255, 255))
    return g


def _sosyal_cerceve(g: Image.Image) -> Image.Image:
    """Sosyal medya paylaşımı: üstte başlık bandı, altta hesap adı."""
    en, boy = g.size
    bant = int(boy * 0.14)
    yeni = Image.new("RGB", (en, boy + 2 * bant), (255, 255, 255))
    yeni.paste(g, (0, bant))
    cizim = ImageDraw.Draw(yeni)
    cizim.text((12, bant // 3), "ACIL! PAYLASIN!!", fill=(0, 0, 0))
    cizim.text((12, boy + bant + bant // 3), "@kaynak_hesap", fill=(90, 90, 90))
    return yeni


def _gurultu_ve_renk(g: Image.Image) -> Image.Image:
    import numpy as np

    dizi = np.asarray(g).astype("int16")
    rng = np.random.default_rng(0)
    dizi += rng.integers(-18, 18, dizi.shape, dtype="int16")
    dizi = np.clip(dizi, 0, 255).astype("uint8")
    return ImageEnhance.Color(Image.fromarray(dizi)).enhance(1.4)


DONUSUMLER: dict[str, Callable[[Image.Image], Image.Image]] = {
    "temiz (kontrol)": lambda g: g,
    "yeniden kodlama (JPEG q30)": _yeniden_kodla,
    "aşırı sıkıştırma (q10)": lambda g: _yeniden_kodla(g, 10),
    "ölçekleme (480p)": lambda g: g.resize((854, 480)),
    "kırpma %20": _kirp,
    "letterbox bant": _letterbox,
    "logo bindirme": _logo,
    "sosyal medya çerçevesi": _sosyal_cerceve,
    "gürültü + renk kayması": _gurultu_ve_renk,
    "parlaklık %130": lambda g: ImageEnhance.Brightness(g).enhance(1.3),
    "hafif bulanıklık": lambda g: g.filter(ImageFilter.GaussianBlur(1.2)),
    "ayna çevirme": lambda g: g.transpose(Image.FLIP_LEFT_RIGHT),
    "döndürme 5°": lambda g: g.rotate(5, expand=False, fillcolor=(0, 0, 0)),
}


# ─────────────────────────── Ölçüm ───────────────────────────


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


def dayaniklilik(indeks: ProvenanceIndex, ornekler: list[str]) -> dict[str, dict[str, float]]:
    """Her dönüşüm için Recall@1 ve ortalama mesafe."""
    dosya_kayit = {k.dosya: k.kayit_id for k in indeks.kayitlar}
    sonuc: dict[str, dict[str, float]] = {}

    for ad, donusum in DONUSUMLER.items():
        dogru = 0
        mesafeler: list[int] = []
        for dosya in ornekler:
            goruntu = Image.open(KAYNAK / dosya).convert("RGB")
            dhash, phash = imaging.karmalar(donusum(goruntu))
            eslesmeler = indeks.ara(dhash, phash, k=1)
            if not eslesmeler:
                continue
            en_iyi = eslesmeler[0]
            mesafeler.append(en_iyi.mesafe)
            if en_iyi.kayit.kayit_id == dosya_kayit[dosya] and en_iyi.eslesti:
                dogru += 1
        sonuc[ad] = {
            "recall1": round(dogru / len(ornekler), 4),
            "ortalama_mesafe": round(sum(mesafeler) / max(len(mesafeler), 1), 2),
        }
        print(
            f"  {ad:30s} Recall@1 {sonuc[ad]['recall1']:.4f}  ort. mesafe "
            f"{sonuc[ad]['ortalama_mesafe']:5.2f}"
        )
    return sonuc


def yanlis_eslesme(indeks: ProvenanceIndex, disaridakiler: list[Path]) -> dict[str, float]:
    """İndekste OLMAYAN görüntüler kaç kez eşleşti sayılıyor?"""
    yanlis = 0
    mesafeler: list[int] = []
    for yol in disaridakiler:
        dhash, phash = imaging.karmalar(yol)
        eslesmeler = indeks.ara(dhash, phash, k=1)
        if not eslesmeler:
            continue
        mesafeler.append(eslesmeler[0].mesafe)
        if eslesmeler[0].eslesti:
            yanlis += 1
    return {
        "yanlis_eslesme_orani": round(yanlis / max(len(disaridakiler), 1), 4),
        "ortalama_mesafe": round(sum(mesafeler) / max(len(mesafeler), 1), 2),
        "n": len(disaridakiler),
    }


#: Eşik taramasında denenen Hamming mesafeleri (64 bit üzerinden).
ESIK_ADAYLARI = (4, 6, 8, 10, 12, 14, 16)

#: Taramada "ağır dönüşüm" sayılanlar — geometrik saldırılar.
AGIR_DONUSUMLER = ("kırpma %20", "letterbox bant", "sosyal medya çerçevesi", "döndürme 5°")


def esik_taramasi(
    indeks: ProvenanceIndex, ornekler: list[str], disarida: list[Path]
) -> list[dict[str, float]]:
    """Eşleşme eşiği ödünleşimi: hangi mesafe ne kadar duyarlılık, ne kadar hata?

    Eşik seçimi bir sayı değil bir karardır ve iki yönde de maliyetlidir.
    Gevşek eşik dönüşümlere dayanır ama alakasız görüntüleri eşleştirir;
    yanlış köken eşleşmesi kullanıcıya "bu görüntü başka bir olaya ait" demek
    anlamına gelir ve sistemin en görünür hatasıdır.
    """
    dosya_kayit = {k.dosya: k.kayit_id for k in indeks.kayitlar}

    # Mesafeler eşikten bağımsızdır; bir kez hesaplanıp tüm eşiklerde kullanılır.
    dogru_mesafeler: list[int] = []
    for ad in AGIR_DONUSUMLER:
        donusum = DONUSUMLER[ad]
        for dosya in ornekler:
            goruntu = Image.open(KAYNAK / dosya).convert("RGB")
            dhash, phash = imaging.karmalar(donusum(goruntu))
            adaylar = indeks.ara(dhash, phash, k=1)
            if adaylar and adaylar[0].kayit.kayit_id == dosya_kayit[dosya]:
                dogru_mesafeler.append(adaylar[0].mesafe)
            else:
                dogru_mesafeler.append(999)  # doğru kayıt ilk sırada değil

    disari_mesafeler: list[int] = []
    for yol in disarida:
        dhash, phash = imaging.karmalar(yol)
        adaylar = indeks.ara(dhash, phash, k=1)
        disari_mesafeler.append(adaylar[0].mesafe if adaylar else 999)

    return [
        {
            "esik": esik,
            "agir_recall1": round(
                sum(1 for m in dogru_mesafeler if m <= esik) / max(len(dogru_mesafeler), 1), 4
            ),
            "yanlis_eslesme": round(
                sum(1 for m in disari_mesafeler if m <= esik) / max(len(disari_mesafeler), 1), 4
            ),
        }
        for esik in ESIK_ADAYLARI
    ]


def rapor_yaz(
    sonuc: dict[str, dict[str, float]],
    yanlis: dict[str, float],
    indeks_boyu: int,
    n: int,
    tarama: list[dict[str, float]],
) -> Path:
    simdi = datetime.now(UTC).strftime("%d.%m.%Y %H:%M UTC")
    temiz = sonuc.get("temiz (kontrol)", {}).get("recall1", 0.0)
    s = [
        "# M1 — Köken Motoru · Dayanıklılık Değerlendirmesi",
        "",
        f"*`scripts/eval/m1_robustness.py` tarafından üretildi · {simdi} · "
        f"commit `{_git_commit()}`*",
        "",
        "| | |",
        "|---|---|",
        f"| İndeks | {indeks_boyu:,} kayıt |",
        f"| Sorgu örneklemi | {n} görüntü |",
        f"| Eşleşme eşiği | Hamming ≤ {MATCH_MAX_DISTANCE} bit (64 bitte) |",
        "| Karma | dHash + pHash, ikisinin iyisi |",
        "",
        "## Dönüşüm altında Recall@1",
        "",
        "Her satır, aynı görüntünün o dönüşümden geçirilip indekste aranmasıdır.",
        "Doğru kayıt ilk sırada VE eşik içinde bulunduysa başarılı sayılır.",
        "",
        "| Dönüşüm | Recall@1 | Ortalama Hamming mesafesi |",
        "|---|---|---|",
    ]
    s += [f"| {ad} | {d['recall1']:.4f} | {d['ortalama_mesafe']:.2f} |" for ad, d in sonuc.items()]
    s += [
        "",
        f"> Temiz kontrol: **{temiz:.4f}** · rapor 3.2 hedefi ≥ 0,90",
        "",
        "## Yanlış eşleşme oranı",
        "",
        "İndekste bulunmayan görüntülerle sorgulandığında sistem kaç kez",
        '"eşleşti" diyor? Bu sayı Recall\'dan kritiktir: yanlış bir köken',
        'eşleşmesi kullanıcıya "bu görüntü başka bir olaya ait" demek anlamına',
        "gelir ve sistemin en görünür hatasıdır.",
        "",
        "| | |",
        "|---|---|",
        f"| Sorgu | {yanlis['n']} indeks dışı görüntü |",
        f"| Yanlış eşleşme oranı | **{yanlis['yanlis_eslesme_orani']:.4f}** |",
        f"| Ortalama en yakın mesafe | {yanlis['ortalama_mesafe']:.2f} bit |",
        "",
        "> Rapor 3.2 hedefi < %1",
        "",
        "## Eşik ödünleşimi",
        "",
        "Eşleşme eşiği bir sayı değil bir karardır ve iki yönde de maliyetlidir:",
        "gevşek eşik geometrik dönüşümlere dayanır ama alakasız görüntüleri",
        "eşleştirir. Aşağıdaki tarama, ağır (geometrik) dönüşümlerdeki Recall@1 ile",
        "yanlış eşleşme oranını aynı eksende gösterir.",
        "",
        "| Hamming eşiği | Ağır dönüşüm Recall@1 | Yanlış eşleşme oranı |",
        "|---|---|---|",
    ]
    s += [
        f"| {t_['esik']} | {t_['agir_recall1']:.4f} | {t_['yanlis_eslesme']:.4f} |" for t_ in tarama
    ]
    s += [
        "",
        f"Yürürlükteki eşik: **{MATCH_MAX_DISTANCE} bit** "
        "(`provenance/hashing.py · MATCH_MAX_DISTANCE`).",
        "",
        "## Yorum",
        "",
        "Ayna çevirme algısal karmayı yapısal olarak kırar: dHash komşu piksel",
        "farklarına, pHash DCT katsayılarına bakar ve çevirme her ikisinin de",
        "uzamsal düzenini bozar. Bu bir kusur değil, karma tabanlı aramanın",
        "bilinen sınırıdır ve görsel-dil gömmesi tabanlı ikinci bir arama",
        "katmanıyla kapatılır (rapor 3.1 · M1 · gömme indeksi).",
        "",
    ]
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text("\n".join(s), encoding="utf-8")
    return RAPOR


def kart_yaz(sonuc: dict, yanlis: dict, indeks_boyu: int, n: int) -> Path:
    temiz = sonuc.get("temiz (kontrol)", {}).get("recall1", 0.0)
    agir = [
        d["recall1"]
        for ad, d in sonuc.items()
        if ad in ("kırpma %20", "sosyal medya çerçevesi", "letterbox bant", "döndürme 5°")
    ]
    kart = ModelCard(
        name="m1_provenance",
        module="M1",
        title="Köken Referans İndeksi",
        version="0.1.0",
        base_model="dHash + pHash (8×8, 64 bit)",
        purpose=(
            "Bir görüntünün daha önce, başka bir tarih veya olayda yayımlanıp "
            "yayımlanmadığını tespit eder. Yanlış bağlam sınıfının kanıt kaynağıdır."
        ),
        training_data=[
            f"Wikimedia Commons açık lisanslı Türkiye afet görüntüleri — {indeks_boyu:,} kayıt",
            "Her kayıt olay ve il düzeyinde konum etiketi taşır",
        ],
        training_procedure="Eğitim yok; algısal karma hesabı ve tam tarama indeksi.",
        hyperparameters={"karma_boyutu": "8×8 (64 bit)", "esik": MATCH_MAX_DISTANCE},
        split_strategy="Yanlış eşleşme ölçümü indeks dışı görüntülerle yapılır",
        measurements=[
            Measurement("recall1_temiz", temiz, "dönüşümsüz sorgu", n),
            Measurement(
                "recall1_agir_donusum",
                round(sum(agir) / max(len(agir), 1), 4),
                "kırpma/çerçeve/letterbox/döndürme ortalaması",
                n,
            ),
            Measurement(
                "yanlis_eslesme_orani",
                yanlis["yanlis_eslesme_orani"],
                "indeks dışı görüntüler",
                yanlis["n"],
            ),
        ],
        known_limits=[
            "Ayna çevirme algısal karmayı yapısal olarak kırar; bu saldırı ancak "
            "görsel-dil gömmesi tabanlı ikinci arama katmanıyla yakalanabilir "
            "ve o katman henüz kurulmadı.",
            f"İndeks {indeks_boyu:,} kayıtla sınırlıdır ve yalnızca Wikimedia Commons "
            "kaynaklıdır; haber ajansı arşivleri ve DMM'de yalanlanan görseller "
            "henüz eklenmedi.",
            "Video desteği ffmpeg gerektirir; kurulu değilse video yolu devre dışı "
            "kalır ve modül çekinir.",
        ],
        ethical_notes=[
            "Yanlış köken eşleşmesi, kullanıcıya içeriğinin başka bir olaya ait "
            "olduğunu söylemek demektir; eşik bu yüzden duyarlılık değil kesinlik "
            "lehine ayarlanmıştır.",
        ],
        out_of_scope=[
            "Eşleşme bulunmamasını 'içerik sahte' olarak yorumlamak",
            "İndeks kapsamı dışındaki olaylar hakkında köken hükmü vermek",
        ],
        license="Veri: Wikimedia Commons (kayıt başına lisans indekste tutulur)",
        git_commit=_git_commit(),
    )
    kart.save(INDEKS)
    return kart.write_markdown(REPO_ROOT / "docs" / "model-kartlari")


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--ornek", type=int, default=150, help="kaç görüntüyle sınanacak")
    a.add_argument("--tohum", type=int, default=42)
    args = a.parse_args()

    if not (INDEKS / "index.jsonl").exists():
        print(f"🔴 İndeks yok: {INDEKS}. Önce: python scripts/data/build_provenance_index.py")
        return 1

    indeks = ProvenanceIndex(INDEKS)
    print(f"→ indeks: {len(indeks):,} kayıt")

    rastgele = random.Random(args.tohum)
    # Aynı görüntü birden çok görünümle indekslendiği için tekilleştir.
    dosyalar = sorted({k.dosya for k in indeks.kayitlar})
    ornekler = rastgele.sample(dosyalar, min(args.ornek, len(dosyalar)))

    # İndeks dışı sorgular, indeks kurulurken bilinçli olarak AYRILAN kümedir.
    # Dizindeki tüm dosyalardan farkını almak yanıltıcı olurdu: korpus toplama
    # sürerken yeni inen görüntüler de "indeks dışı" sayılır ve ölçüm kayardı.
    tutulan_dosyasi = INDEKS / "tutulan.jsonl"
    disarida: list[Path] = []
    if tutulan_dosyasi.exists():
        indekstekiler = set(dosyalar)
        for satir in tutulan_dosyasi.read_text(encoding="utf-8").splitlines():
            if not satir:
                continue
            ad = json.loads(satir)["dosya"]
            if ad not in indekstekiler and (KAYNAK / ad).exists():
                disarida.append(KAYNAK / ad)
        disarida = disarida[: args.ornek]

    print(f"→ {len(ornekler)} görüntü × {len(DONUSUMLER)} dönüşüm\n")
    sonuc = dayaniklilik(indeks, ornekler)

    print(f"\n→ yanlış eşleşme ({len(disarida)} indeks dışı görüntü)")
    if disarida:
        yanlis = yanlis_eslesme(indeks, disarida)
        print(
            f"  oran {yanlis['yanlis_eslesme_orani']:.4f} · "
            f"ortalama mesafe {yanlis['ortalama_mesafe']:.2f}"
        )
    else:
        print("  ⚠️ indeks dışı görüntü yok — ölçüm atlandı")
        yanlis = {"yanlis_eslesme_orani": -1.0, "ortalama_mesafe": -1.0, "n": 0}

    print("\n→ eşik taraması")
    tarama = esik_taramasi(indeks, ornekler[:60], disarida)
    print(f"  {'eşik':>5s} {'ağır Recall@1':>14s} {'yanlış eşleşme':>15s}")
    for t_ in tarama:
        print(f"  {int(t_['esik']):5d} {t_['agir_recall1']:14.4f} {t_['yanlis_eslesme']:15.4f}")

    print(
        f"\n✓ {rapor_yaz(sonuc, yanlis, len(indeks), len(ornekler), tarama).relative_to(REPO_ROOT)}"
    )
    print(f"✓ {kart_yaz(sonuc, yanlis, len(indeks), len(ornekler)).relative_to(REPO_ROOT)}")
    print(json.dumps({"temiz": sonuc["temiz (kontrol)"]["recall1"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
