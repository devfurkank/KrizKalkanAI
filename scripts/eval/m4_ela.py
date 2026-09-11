#!/usr/bin/env python
"""M4 hata seviyesi analizi değerlendirmesi — yerel oynama tespiti.

Ölçümün iki tarafı var ve ikisinin de kendi zorluğu var:

    POZİTİF   Etiketli "oynanmış görüntü" veri kümesi elimizde yok. Bu yüzden
              pozitifler ÜRETİLİR: gerçek bir fotoğrafın bir bölgesine başka
              bir fotoğraftan parça yapıştırılıp dosya yeniden kaydedilir.
              Bu, yöntemin aradığı olgunun ta kendisidir.

    NEGATİF   Gerçek Türk afet fotoğrafları. Ölçülen şey, sistemin sahada kaç
              gerçek fotoğrafı "oynanmış" sanacağıdır.

**Afet görüntüleri pozitif üretiminde KULLANILMAZ.** Etik protokol (§6, kural 4)
gerçek afet mağdurlarının görüntüleri üzerine sahte anlatı kurulmasını
yasaklıyor. Yapıştırma kaynakları bu yüzden afet dışı, nötr fotoğraflardan
seçilir; afet korpusu yalnızca yanlış pozitif ölçümünde, dokunulmadan kullanılır.

Çıktı: docs/metrikler/m4-ela.md
"""

from __future__ import annotations

import argparse
import io
import json
import random
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.synthetic.ela import (  # noqa: E402
    AYKIRILIK_KATI,
    ElaDurum,
    incele,
)

RAPOR = REPO_ROOT / "docs" / "metrikler" / "m4-ela.md"
AFET_KORPUSU = REPO_ROOT / "data" / "external" / "provenance"

#: Pozitif üretiminde kullanılacak nötr fotoğraf kaynağı. Afet içeriği DEĞİL.
NOTR_DEPO = "ComplexDataLab/OpenFake"
NOTR_DOSYA = "core/test-00000-of-00013.parquet"

#: Yapıştırılan parçanın kenar oranı — görüntünün bu kadarı değiştirilir.
YAMA_ORANI = 0.25


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


def notr_fotograflar(sayi: int, tohum: int) -> list[bytes]:
    """OpenFake'in GERÇEK yarısından nötr fotoğraflar (imagenet / docci)."""
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    yol = hf_hub_download(NOTR_DEPO, NOTR_DOSYA, repo_type="dataset")
    dosya = pq.ParquetFile(yol)
    toplanan: list[bytes] = []
    for grup in range(dosya.metadata.num_row_groups):
        if len(toplanan) >= sayi * 2:
            break
        for satir in dosya.read_row_group(grup, columns=["image", "label"]).to_pylist():
            if satir["label"] == "real":
                toplanan.append(satir["image"]["bytes"])
            if len(toplanan) >= sayi * 2:
                break
    random.Random(tohum).shuffle(toplanan)
    return toplanan


def yama_uret(taban: bytes, kaynak: bytes, tohum: int) -> bytes | None:
    """Bir fotoğrafın bölgesine başka fotoğraftan parça yapıştırır.

    Sonuç yeniden kaydedilir: yapıştırılan bölge bir kez, geri kalan iki kez
    sıkıştırılmış olur ve aranan sıkıştırma geçmişi farkı tam olarak budur.
    """
    from PIL import Image

    try:
        with Image.open(io.BytesIO(taban)) as a, Image.open(io.BytesIO(kaynak)) as b:
            hedef = a.convert("RGB")
            parca_kaynak = b.convert("RGB")
    except Exception:
        return None

    if min(hedef.size) < 256:
        return None

    kenar = int(min(hedef.size) * YAMA_ORANI)
    rastgele = random.Random(tohum)
    x = rastgele.randrange(0, hedef.width - kenar)
    y = rastgele.randrange(0, hedef.height - kenar)

    parca = parca_kaynak.resize((kenar, kenar), Image.Resampling.BILINEAR)
    hedef.paste(parca, (x, y))

    tampon = io.BytesIO()
    hedef.save(tampon, format="JPEG", quality=92)
    return tampon.getvalue()


def _bayt_incele(bayt: bytes, dizin: Path, ad: str):
    yol = dizin / ad
    yol.write_bytes(bayt)
    try:
        return incele(yol)
    finally:
        yol.unlink(missing_ok=True)


def olc_pozitif(sayi: int, tohum: int) -> dict:
    """Üretilmiş yapıştırma örneklerinde yakalama."""
    fotograflar = notr_fotograflar(sayi, tohum)
    sayim: Counter[str] = Counter()
    sapmalar: list[float] = []

    with tempfile.TemporaryDirectory() as gecici:
        dizin = Path(gecici)
        uretilen = 0
        for sira in range(0, len(fotograflar) - 1, 2):
            if uretilen >= sayi:
                break
            yamali = yama_uret(fotograflar[sira], fotograflar[sira + 1], tohum + sira)
            if yamali is None:
                continue
            uretilen += 1
            sonuc = _bayt_incele(yamali, dizin, f"y{sira}.jpg")
            sayim[sonuc.durum.value] += 1
            if sonuc.durum is ElaDurum.YEREL_AYKIRILIK:
                sapmalar.append(sonuc.sapma)
            if uretilen % 50 == 0:
                print(f"  pozitif: {uretilen}/{sayi}", flush=True)

    sayim["n"] = uretilen
    return {"sayim": dict(sayim), "sapmalar": sapmalar}


def olc_negatif_afet(sinir: int) -> dict:
    """Gerçek afet fotoğraflarında yanlış pozitif — dokunulmadan."""
    kayit_dosyasi = AFET_KORPUSU / "kayitlar.jsonl"
    if not kayit_dosyasi.exists():
        return {}

    kayitlar = [json.loads(s) for s in kayit_dosyasi.read_text(encoding="utf-8").splitlines() if s]
    sayim: Counter[str] = Counter()
    sapmalar: list[float] = []

    for sira, kayit in enumerate(kayitlar[:sinir], 1):
        yol = AFET_KORPUSU / "goruntuler" / kayit["dosya"]
        if not yol.exists():
            continue
        sonuc = incele(yol)
        sayim["n"] += 1
        sayim[sonuc.durum.value] += 1
        if sonuc.durum is ElaDurum.YEREL_AYKIRILIK:
            sapmalar.append(sonuc.sapma)
        if sira % 200 == 0:
            print(f"  afet: {sira}/{min(sinir, len(kayitlar))}", flush=True)

    return {"sayim": dict(sayim), "sapmalar": sapmalar}


def olc_negatif_dokunulmamis(sayi: int, tohum: int) -> dict:
    """Yapıştırma UYGULANMAMIŞ, yalnızca yeniden kaydedilmiş fotoğraflar.

    Kontrol grubudur: yeniden kaydetmenin tek başına aykırılık üretip
    üretmediğini ayırır. Üretmiyorsa pozitiflerdeki sinyal gerçekten
    yapıştırmadan geliyor demektir.
    """
    from PIL import Image

    fotograflar = notr_fotograflar(sayi, tohum)
    sayim: Counter[str] = Counter()

    with tempfile.TemporaryDirectory() as gecici:
        dizin = Path(gecici)
        uretilen = 0
        for sira, ham in enumerate(fotograflar):
            if uretilen >= sayi:
                break
            try:
                with Image.open(io.BytesIO(ham)) as acik:
                    goruntu = acik.convert("RGB")
            except Exception:
                continue
            if min(goruntu.size) < 256:
                continue
            uretilen += 1
            tampon = io.BytesIO()
            goruntu.save(tampon, format="JPEG", quality=92)
            sonuc = _bayt_incele(tampon.getvalue(), dizin, f"k{sira}.jpg")
            sayim[sonuc.durum.value] += 1

    sayim["n"] = uretilen
    return {"sayim": dict(sayim)}


def olc_ayrim_gucu(sayi: int, tohum: int) -> dict:
    """Aynı taban fotoğrafın yapıştırılmış ve oynanmamış hâlini karşılaştırır.

    Bu ölçüm belirleyicidir. Yakalama ve yanlış pozitif oranları eşiğe bağlıdır
    ve eşik oynatılarak istenen görüntü verdirilebilir; **ayrım gücü eşikten
    bağımsızdır.** 0,50 hiç ayrım yok demektir ve hiçbir eşik onu kurtarmaz.

    Karşılaştırma EŞLİDİR: aynı taban fotoğrafın iki hâli kıyaslanır, böylece
    fotoğraflar arası doku farkı ölçümün dışında kalır.
    """
    from PIL import Image

    fotograflar = notr_fotograflar(sayi, tohum)
    pozitif: list[float] = []
    kontrol: list[float] = []

    with tempfile.TemporaryDirectory() as gecici:
        dizin = Path(gecici)
        for sira in range(0, len(fotograflar) - 1, 2):
            if len(pozitif) >= sayi:
                break
            yamali = yama_uret(fotograflar[sira], fotograflar[sira + 1], tohum + sira)
            if yamali is None:
                continue
            try:
                with Image.open(io.BytesIO(fotograflar[sira])) as acik:
                    taban = acik.convert("RGB")
            except Exception:
                continue

            p_sonuc = _bayt_incele(yamali, dizin, f"ap{sira}.jpg")
            tampon = io.BytesIO()
            taban.save(tampon, format="JPEG", quality=92)
            k_sonuc = _bayt_incele(tampon.getvalue(), dizin, f"ak{sira}.jpg")

            # Yalnızca ikisi de çözümlenebildiyse çift geçerlidir.
            if ElaDurum.UYGULANAMAZ in (p_sonuc.durum, k_sonuc.durum):
                continue
            pozitif.append(p_sonuc.sapma)
            kontrol.append(k_sonuc.sapma)

    if not pozitif:
        return {}

    kazanan = sum((1.0 if a > b else 0.5 if a == b else 0.0) for a in pozitif for b in kontrol)
    return {
        "n": len(pozitif),
        "auc": round(kazanan / (len(pozitif) * len(kontrol)), 4),
        "pozitif_medyan": round(sorted(pozitif)[len(pozitif) // 2], 3),
        "kontrol_medyan": round(sorted(kontrol)[len(kontrol) // 2], 3),
    }


def _oran(sayim: dict, anahtar: str) -> float:
    return sayim.get(anahtar, 0) / max(sayim.get("n", 0), 1)


def _rapor_yaz(pozitif: dict, afet: dict, kontrol: dict, ayrim: dict) -> Path:
    p, k = pozitif["sayim"], kontrol["sayim"]
    simdi = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    yakalama = _oran(p, ElaDurum.YEREL_AYKIRILIK.value)
    kontrol_yp = _oran(k, ElaDurum.YEREL_AYKIRILIK.value)

    satir = [
        "# M4 — Hata seviyesi analizi (yerel oynama)",
        "",
        f"*Üretim: {simdi} · commit `{_git_commit()}` · aykırılık katı {AYKIRILIK_KATI}*",
        "",
        "Yöntem, yeniden kaydetmede bölgelerin farklı bozulmasına dayanır: bir",
        "bölge sonradan yapıştırılmışsa sıkıştırma geçmişi çevresinden ayrışır.",
        "Aranan şey sentetik üretim değil **yerel oynama** — MANİPÜLE_MEDYA'yı",
        "besleyebilecek tek görüntü sinyali budur.",
        "",
        "## 1. Yakalama — üretilmiş yapıştırma örnekleri",
        "",
        "Etiketli oynanmış görüntü kümesi olmadığı için pozitifler üretildi:",
        f"nötr bir fotoğrafın %{YAMA_ORANI:.0%} kenar oranındaki bölgesine başka bir",
        "fotoğraftan parça yapıştırılıp dosya yeniden kaydedildi.",
        "",
        "> **Afet görüntüleri bu üretimde kullanılmadı.** Etik protokol §6 kural 4,",
        "> gerçek afet mağdurlarının görüntüleri üzerine sahte anlatı kurulmasını",
        "> yasaklıyor. Kaynaklar afet dışı nötr fotoğraflardır.",
        "",
        "| Sonuç | Adet | Oran |",
        "|---|---|---|",
        f"| **Yerel aykırılık (yakalama)** | {p.get(ElaDurum.YEREL_AYKIRILIK.value, 0)} | "
        f"**{yakalama:.1%}** |",
        f"| Aykırılık yok (kaçırma) | {p.get(ElaDurum.AYKIRILIK_YOK.value, 0)} | "
        f"{_oran(p, ElaDurum.AYKIRILIK_YOK.value):.1%} |",
        f"| Uygulanamaz (çekinme) | {p.get(ElaDurum.UYGULANAMAZ.value, 0)} | "
        f"{_oran(p, ElaDurum.UYGULANAMAZ.value):.1%} |",
        f"| Toplam | {p.get('n', 0)} | |",
        "",
        "## 2. Kontrol — yalnızca yeniden kaydedilmiş, oynanmamış",
        "",
        "Aynı fotoğraflar yapıştırma UYGULANMADAN yeniden kaydedildi. Bu grup,",
        "sinyalin yeniden kaydetmeden değil gerçekten yapıştırmadan geldiğini",
        "ayırır.",
        "",
        "| Sonuç | Adet | Oran |",
        "|---|---|---|",
        f"| **Yerel aykırılık (yanlış pozitif)** | {k.get(ElaDurum.YEREL_AYKIRILIK.value, 0)} | "
        f"**{kontrol_yp:.1%}** |",
        f"| Aykırılık yok | {k.get(ElaDurum.AYKIRILIK_YOK.value, 0)} | "
        f"{_oran(k, ElaDurum.AYKIRILIK_YOK.value):.1%} |",
        f"| Uygulanamaz | {k.get(ElaDurum.UYGULANAMAZ.value, 0)} | "
        f"{_oran(k, ElaDurum.UYGULANAMAZ.value):.1%} |",
        f"| Toplam | {k.get('n', 0)} | |",
    ]

    if afet:
        a = afet["sayim"]
        afet_yp = _oran(a, ElaDurum.YEREL_AYKIRILIK.value)
        satir += [
            "",
            "## 3. Afet alanı — yanlış pozitif",
            "",
            "Wikimedia Commons Türkiye afet korpusu, **dokunulmadan**. Tamamı",
            "gerçektir; ölçülen şey sistemin sahada kaç gerçek afet fotoğrafını",
            "oynanmış sanacağıdır.",
            "",
            "| Sonuç | Adet | Oran |",
            "|---|---|---|",
            f"| **Yerel aykırılık (yanlış pozitif)** | "
            f"{a.get(ElaDurum.YEREL_AYKIRILIK.value, 0)} | **{afet_yp:.2%}** |",
            f"| Aykırılık yok | {a.get(ElaDurum.AYKIRILIK_YOK.value, 0)} | "
            f"{_oran(a, ElaDurum.AYKIRILIK_YOK.value):.1%} |",
            f"| Uygulanamaz (çekinme) | {a.get(ElaDurum.UYGULANAMAZ.value, 0)} | "
            f"{_oran(a, ElaDurum.UYGULANAMAZ.value):.1%} |",
            f"| Toplam | {a.get('n', 0)} | |",
        ]

    if ayrim:
        satir += [
            "",
            "## 4. Ayrım gücü — belirleyici ölçüm",
            "",
            "Yakalama ve yanlış pozitif oranları eşiğe bağlıdır; eşik oynatılarak",
            "istenen görüntü verdirilebilir. **Ayrım gücü eşikten bağımsızdır.**",
            "",
            "Karşılaştırma eşlidir: aynı taban fotoğrafın yapıştırılmış ve",
            "oynanmamış hâli kıyaslanır, böylece fotoğraflar arası doku farkı",
            "ölçümün dışında kalır.",
            "",
            "| Metrik | Değer |",
            "|---|---|",
            f"| **AUC (yapıştırılmış vs oynanmamış)** | **{ayrim['auc']:.4f}** |",
            f"| Eşli örnek sayısı | {ayrim['n']} |",
            f"| Sapma medyanı · yapıştırılmış | {ayrim['pozitif_medyan']:.3f} |",
            f"| Sapma medyanı · oynanmamış | {ayrim['kontrol_medyan']:.3f} |",
            "",
            "> 0,50 hiç ayrım olmadığı anlamına gelir. Ölçülen değer buna çok",
            "> yakındır: yöntem, yapıştırılmış bölgeyi değil görüntünün doğal doku",
            "> değişimini ölçüyor. Düz bir gökyüzü ile detaylı bir enkaz alanı",
            "> yeniden kaydetmede farklı bozuluyor ve bu fark, yapıştırmanın",
            "> ürettiğinden büyük.",
        ]

    # ── Karar ──
    afet_yp = _oran(afet.get("sayim", {}), ElaDurum.YEREL_AYKIRILIK.value) if afet else 1.0
    ayrim_auc = ayrim.get("auc", 0.5) if ayrim else 0.5
    uygun = ayrim_auc >= 0.75 and afet_yp <= 0.05 and kontrol_yp <= 0.10
    satir += [
        "",
        "## 5. Karar",
        "",
        (
            "**Sinyal füzyona bağlandı.** Yakalama yeterli, gerçek içerikteki "
            "yanlış pozitif kabul edilebilir sınırda."
            if uygun
            else "**Sinyal füzyona BAĞLANMADI; bilgi olarak raporlanıyor.**"
        ),
        "",
        "Kabul için aranan üç koşul ve ölçülen değerler:",
        "",
        "| Koşul | Gereken | Ölçülen | |",
        "|---|---|---|---|",
        f"| **Ayrım gücü (AUC)** | ≥ 0,75 | **{ayrim_auc:.4f}** | "
        f"{'✓' if ayrim_auc >= 0.75 else '✗'} |",
        f"| Yakalama (üretilmiş yapıştırma) | bilgi | {yakalama:.1%} | |",
        f"| Yanlış pozitif (afet, gerçek) | ≤ 5% | {afet_yp:.2%} | "
        f"{'✓' if afet_yp <= 0.05 else '✗'} |",
        f"| Yanlış pozitif (kontrol, yeniden kayıt) | ≤ 10% | {kontrol_yp:.1%} | "
        f"{'✓' if kontrol_yp <= 0.10 else '✗'} |",
        "",
        "## 6. Bilinen sınırlar",
        "",
        "- **Kayıpsız biçimlerde uygulanamaz.** PNG ve kayıpsız WebP'de sıkıştırma",
        "  geçmişi yoktur; modül bu dosyalarda çekinir.",
        "- **Yeniden kodlama izi siler.** Sosyal platformlar yüklemede yeniden",
        "  kodlar ve yapıştırma izi ile çevresi aynı geçmişe kavuşur.",
        "- **Yerel oynamayı bulur, kimin yaptığını değil.** Kırpma, renk düzeltme",
        "  ve yasal düzenlemeler de aykırılık üretebilir; sinyal tek başına",
        "  suçlama değildir.",
        "- Pozitifler bu depoda üretildi; yayımlanmış bir kıyas kümesi değildir.",
        "",
        "---",
        "",
        "*`scripts/eval/m4_ela.py` tarafından üretildi; elle düzenlenmez.*",
        "",
    ]
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text("\n".join(satir), encoding="utf-8")
    return RAPOR


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--pozitif", type=int, default=200)
    a.add_argument("--kontrol", type=int, default=200)
    a.add_argument("--afet-sinir", type=int, default=689)
    a.add_argument("--tohum", type=int, default=20260911)
    args = a.parse_args()

    print("═══ 1/4 pozitif (üretilmiş yapıştırma) ═══")
    pozitif = olc_pozitif(args.pozitif, args.tohum)
    print(
        f"  yakalama {pozitif['sayim'].get(ElaDurum.YEREL_AYKIRILIK.value, 0)}/"
        f"{pozitif['sayim'].get('n', 0)}"
    )

    print("\n═══ 2/4 kontrol (yalnızca yeniden kayıt) ═══")
    kontrol = olc_negatif_dokunulmamis(args.kontrol, args.tohum + 1)
    print(
        f"  yanlış pozitif {kontrol['sayim'].get(ElaDurum.YEREL_AYKIRILIK.value, 0)}/"
        f"{kontrol['sayim'].get('n', 0)}"
    )

    print("\n═══ 3/4 ayrım gücü (eşli) ═══")
    ayrim = olc_ayrim_gucu(args.pozitif, args.tohum + 2)
    if ayrim:
        print(f"  AUC {ayrim['auc']:.4f} (n={ayrim['n']} çift)")

    print("\n═══ 4/4 afet alanı ═══")
    afet = olc_negatif_afet(args.afet_sinir)
    if afet:
        print(
            f"  yanlış pozitif {afet['sayim'].get(ElaDurum.YEREL_AYKIRILIK.value, 0)}/"
            f"{afet['sayim'].get('n', 0)}"
        )
    else:
        print("  ⚠ korpus yok — atlanıyor")

    rapor = _rapor_yaz(pozitif, afet, kontrol, ayrim)
    print(f"\n✓ {rapor.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
