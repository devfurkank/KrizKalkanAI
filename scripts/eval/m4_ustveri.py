#!/usr/bin/env python
"""M4 üretici üstverisi değerlendirmesi — belgesel sinyalin kesinliği.

Bu sinyal sinir ağı detektöründen farklı bir ödünleşim noktasında durur ve
ölçümün amacı tam olarak bunu göstermektir:

    sinir ağı  → yüksek yakalama, alan içinde kabul edilemez yanlış pozitif
    üstveri    → düşük yakalama, **sıfır** yanlış pozitif

Kriz alanında ikincisi kıymetlidir. Gerçek bir afet fotoğrafını sentetik diye
işaretlemek, bir sentetik görüntüyü kaçırmaktan daha zararlıdır; sistemin etik
duruşu bunu söylüyor ve bu sinyal o duruşa uyan tek görüntü sinyalidir.

Ölçülen üç şey:

    1. YAKALAMA ve KESİNLİK   Üretilmiş/gerçek ayrımı, üretici ailesi başına.
    2. AFET ALANI             Gerçek Türk afet fotoğraflarında yanlış pozitif.
    3. ÇEKİNME                Kaç içerikte "bilmiyorum" dendiği. Yüksek olması
                              beklenir ve kusur değildir: üstveri yokluğu
                              suçlama değil, sessizliktir.

Ağırlık gerektirmez; tamamı kural tabanlıdır ve saniyeler içinde koşar.

Çıktı: docs/metrikler/m4-ustveri.md
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.synthetic.metadata import UstveriDurum, incele  # noqa: E402

RAPOR = REPO_ROOT / "docs" / "metrikler" / "m4-ustveri.md"
AFET_KORPUSU = REPO_ROOT / "data" / "external" / "provenance"

CAPRAZ_DEPO = "ComplexDataLab/OpenFake"
CAPRAZ_DOSYA = "core/test-00000-of-00013.parquet"


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


def _gecici_incele(bayt: bytes, ad: str, dizin: Path):
    """Baytları diske yazıp inceler — ham bayt taraması dosya gerektirir."""
    yol = dizin / f"{abs(hash(ad)):016x}{Path(ad).suffix or '.jpg'}"
    yol.write_bytes(bayt)
    try:
        return incele(yol)
    finally:
        yol.unlink(missing_ok=True)


def capraz_olc(sinir: int, dizin: Path) -> dict:
    """OpenFake parçası üzerinde yakalama ve kesinlik.

    Örneklem tabakalanmaz: bu ölçümde amaç ayrımın kendisi değil, üretici
    ailelerinin üstveri bırakma alışkanlığıdır ve doğal dağılım o bilgiyi
    daha iyi taşır.
    """
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    yol = hf_hub_download(CAPRAZ_DEPO, CAPRAZ_DOSYA, repo_type="dataset")
    dosya = pq.ParquetFile(yol)

    sayim: dict[str, int] = defaultdict(int)
    aile: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    ornekler: list[tuple[str, str]] = []
    islenen = 0

    for grup in range(dosya.metadata.num_row_groups):
        if islenen >= sinir:
            break
        tablo = dosya.read_row_group(grup, columns=["image", "label", "model"]).to_pylist()
        for satir in tablo:
            if islenen >= sinir:
                break
            islenen += 1
            etiket = "uretilmis" if satir["label"] == "fake" else "gercek"
            sonuc = _gecici_incele(satir["image"]["bytes"], satir["image"]["path"], dizin)

            sayim[f"{etiket}_n"] += 1
            sayim[f"{etiket}_{sonuc.durum.value}"] += 1

            uretici = satir["model"] or "bilinmiyor"
            aile[uretici][1] += 1
            if sonuc.durum is UstveriDurum.URETICI_IMZASI:
                aile[uretici][0] += 1
                if len(ornekler) < 5 and sonuc.alinti:
                    ornekler.append((uretici, f"{sonuc.isaret} → {sonuc.alinti[:110]}"))
        del tablo
        print(f"  çapraz: {islenen}/{sinir}", flush=True)

    return {"sayim": dict(sayim), "aile": dict(aile), "ornekler": ornekler}


def afet_olc(sinir: int) -> dict:
    """Wikimedia afet korpusu — tamamı gerçek. Yanlış pozitif için."""
    kayit_dosyasi = AFET_KORPUSU / "kayitlar.jsonl"
    if not kayit_dosyasi.exists():
        return {}

    kayitlar = [json.loads(s) for s in kayit_dosyasi.read_text(encoding="utf-8").splitlines() if s]
    sayim: dict[str, int] = defaultdict(int)
    kameralar: list[str] = []

    for kayit in kayitlar[: sinir or len(kayitlar)]:
        yol = AFET_KORPUSU / "goruntuler" / kayit["dosya"]
        if not yol.exists():
            continue
        sonuc = incele(yol)
        sayim["n"] += 1
        sayim[sonuc.durum.value] += 1
        if sonuc.kamera and len(kameralar) < 5:
            kameralar.append(sonuc.kamera)

    return {"sayim": dict(sayim), "kameralar": kameralar}


def _rapor_yaz(capraz: dict, afet: dict) -> Path:
    s = capraz["sayim"]
    n_uret = s.get("uretilmis_n", 0)
    n_ger = s.get("gercek_n", 0)
    imza_uret = s.get(f"uretilmis_{UstveriDurum.URETICI_IMZASI.value}", 0)
    imza_ger = s.get(f"gercek_{UstveriDurum.URETICI_IMZASI.value}", 0)
    kamera_ger = s.get(f"gercek_{UstveriDurum.KAMERA_TELEMETRISI.value}", 0)
    kamera_uret = s.get(f"uretilmis_{UstveriDurum.KAMERA_TELEMETRISI.value}", 0)

    kesinlik = imza_uret / max(imza_uret + imza_ger, 1)
    simdi = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    satir = [
        "# M4 — Üretici üstverisi",
        "",
        f"*Üretim: {simdi} · commit `{_git_commit()}`*",
        "",
        "Üretici araçlar dosyaya kendi parametrelerini yazar: Stable Diffusion ve",
        "ComfyUI PNG `tEXt` bloklarına `parameters`, `prompt`, `workflow` alanlarını",
        "gömer. Bu bir tahmin değil **beyandır** — bulunduğunda kullanıcıya gömülü",
        "istemin kendisi gösterilebilir.",
        "",
        "## 1. Yakalama ve kesinlik",
        "",
        f"Küme: `{CAPRAZ_DEPO}` · `{CAPRAZ_DOSYA}`",
        "",
        "| Metrik | Değer |",
        "|---|---|",
        f"| Üretilmiş · üretici imzası bulunan | {imza_uret} / {n_uret} "
        f"(**{imza_uret / max(n_uret, 1):.1%}** yakalama) |",
        f"| Gerçek · üretici imzası bulunan | {imza_ger} / {n_ger} "
        f"(**{imza_ger / max(n_ger, 1):.1%}** yanlış pozitif) |",
        f"| **Kesinlik** | **{kesinlik:.4f}** |",
        f"| Gerçek · kamera telemetrisi bulunan | {kamera_ger} / {n_ger} "
        f"({kamera_ger / max(n_ger, 1):.1%}) |",
        f"| Üretilmiş · kamera telemetrisi bulunan | {kamera_uret} / {n_uret} "
        f"({kamera_uret / max(n_uret, 1):.1%}) |",
        f"| Çekinme (üstveri yok) | "
        f"{(n_uret + n_ger - imza_uret - imza_ger - kamera_uret - kamera_ger) / max(n_uret + n_ger, 1):.1%} |",
        "",
        "> Yakalama düşüktür ve bu kusur değildir. Sinyalin değeri kesinliğinde:",
        "> imza bulunduğunda yanılma payı yok denecek kadar azdır. Sinir ağı",
        "> detektörü (`docs/metrikler/m4.md`) ters ödünleşimde durur ve alan",
        "> içinde kullanılamaz durumdadır.",
        "",
        "### 1.1. Üretici ailesi başına",
        "",
        "Üstveri bırakma alışkanlığı araca göre değişiyor. Tablo, sinyalin hangi",
        "üreticilerde çalıştığını ve hangilerinde sessiz kaldığını gösterir.",
        "",
        "| Üretici | İmza bulunan | n | Oran |",
        "|---|---|---|---|",
    ]
    for ad, (bulunan, toplam) in sorted(
        capraz["aile"].items(), key=lambda kv: (-kv[1][0] / max(kv[1][1], 1), -kv[1][1])
    ):
        satir.append(f"| `{ad}` | {bulunan} | {toplam} | {bulunan / max(toplam, 1):.1%} |")

    if capraz["ornekler"]:
        satir += [
            "",
            "### 1.2. Bulunan kanıt örnekleri",
            "",
            "Kanıt panelinde kullanıcıya gösterilecek olan metin budur:",
            "",
        ]
        satir += [f"- `{ad}` — {alinti}" for ad, alinti in capraz["ornekler"]]

    if afet:
        a = afet["sayim"]
        n = a.get("n", 0)
        satir += [
            "",
            "## 2. Afet alanı — yanlış pozitif",
            "",
            "Wikimedia Commons Türkiye afet korpusu. **Tamamı gerçektir.**",
            "",
            "| Durum | Adet | Oran |",
            "|---|---|---|",
            f"| Üretici imzası (yanlış pozitif) | "
            f"{a.get(UstveriDurum.URETICI_IMZASI.value, 0)} | "
            f"**{a.get(UstveriDurum.URETICI_IMZASI.value, 0) / max(n, 1):.2%}** |",
            f"| Kamera telemetrisi | {a.get(UstveriDurum.KAMERA_TELEMETRISI.value, 0)} | "
            f"{a.get(UstveriDurum.KAMERA_TELEMETRISI.value, 0) / max(n, 1):.1%} |",
            f"| Üstveri yok (çekinme) | {a.get(UstveriDurum.USTVERI_YOK.value, 0)} | "
            f"{a.get(UstveriDurum.USTVERI_YOK.value, 0) / max(n, 1):.1%} |",
            f"| Toplam | {n} | |",
            "",
            "> Çekinme oranının yüksekliği beklenen sonuçtur: Wikimedia küçük boy",
            "> görüntüleri yeniden kodlarken üstveriyi siler, sosyal platformlar da",
            "> aynısını yapar. Sinyal bu içerikte **susuyor**, yanlış konuşmuyor.",
        ]

    satir += [
        "",
        "## 3. Bilinen sınırlar",
        "",
        "- **Üstveri silinebilir ve siliniyor.** Sosyal platformların çoğu yüklemede",
        "  siler; sahadaki yakalama bu tablodakinden düşük olacaktır.",
        "- **Üstveri elle yazılabilir.** Ama tehdit modeli asimetriktir: kimse kendi",
        '  gerçek fotoğrafına "bunu Stable Diffusion üretti" yazmaz. Silme sessizliğe',
        "  yol açar, yanlış suçlamaya değil.",
        "- **Üretici kapsamı eksiktir.** Midjourney, GPT-Image ve Sora örneklerinde",
        "  imza bulunamadı; bu araçlar üstveri bırakmıyor ya da platform siliyor.",
        "- Sinyal yalnızca gerçek dosyalarda çalışır; demo parmak izlerinde değil.",
        "",
        "---",
        "",
        "*`scripts/eval/m4_ustveri.py` tarafından üretildi; elle düzenlenmez.*",
        "",
    ]
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text("\n".join(satir), encoding="utf-8")
    return RAPOR


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--sinir", type=int, default=2000, help="çapraz kümeden örnek sayısı")
    a.add_argument("--afet-sinir", type=int, default=0, help="0 = korpusun tamamı")
    args = a.parse_args()

    import tempfile

    print("═══ 1/2 çapraz veri kümesi ═══")
    with tempfile.TemporaryDirectory() as gecici:
        capraz = capraz_olc(args.sinir, Path(gecici))

    s = capraz["sayim"]
    imza_uret = s.get(f"uretilmis_{UstveriDurum.URETICI_IMZASI.value}", 0)
    imza_ger = s.get(f"gercek_{UstveriDurum.URETICI_IMZASI.value}", 0)
    print(
        f"  yakalama {imza_uret}/{s.get('uretilmis_n', 0)} · "
        f"yanlış pozitif {imza_ger}/{s.get('gercek_n', 0)}"
    )

    print("\n═══ 2/2 afet alanı ═══")
    afet = afet_olc(args.afet_sinir)
    if afet:
        yp = afet["sayim"].get(UstveriDurum.URETICI_IMZASI.value, 0)
        print(f"  yanlış pozitif {yp}/{afet['sayim'].get('n', 0)}")
    else:
        print("  ⚠ korpus yok — atlanıyor")

    rapor = _rapor_yaz(capraz, afet)
    print(f"\n✓ {rapor.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
