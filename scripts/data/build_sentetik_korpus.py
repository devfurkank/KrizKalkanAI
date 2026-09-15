#!/usr/bin/env python
"""Üretilmiş afet görselleri korpusunu kurar — M4 doğru-pozitif ve M6 SENTETİK_MEDYA.

**Neden bu korpus var.** M4'ün iki yarısı vardır ve bugüne kadar yalnızca biri
ölçüldü:

    ölçüldü   Gerçek afet fotoğrafına "sentetik" der mi?   9/786 (afet_ozgulluk)
    ölçülmedi ÜRETİLMİŞ bir afet fotoğrafını yakalar mı?   — veri yoktu —

İkincisi bizim asıl tehdit modelimizdir: biri sahte bir deprem fotoğrafı üretip
paylaşır. Çapraz veri kümesi (OpenFake) bu soruyu CEVAPLAMAZ: içeriği anime,
tebrik kartı, tişört mockup'ı ve portredir; 16 rastgele örnek gözle incelendi,
kriz fotoğrafçılığı yok. Alan eşleşmeli kamuya açık set de yok (literatürdeki
tek aday Forged Calamity yayınlanmamış ve CC BY-NC-SA).

**Biçim eşitlemesi kritiktir.** Üretici modeller pırıl pırıl PNG verir; gerçek
korpus ise %95 JPEG, bayt/piksel medyanı 0,292, genişlik medyanı 960'tır. Bu
fark düzeltilmezse ölçüm değil ARTEFAKT ölçülür: model "PNG = üretilmiş"
kısayolunu kullanır ve doğru-pozitif oranı sahte biçimde yükselir. Bu yüzden her
görsel gerçek korpusun profiline indirgenir ve indirgeme değerleri kayda yazılır.

Kalite, görsel başına tohumdan türetilir (sabit değil): gerçek korpusun
bayt/piksel dağılımı da tek noktada değil, 0,159–0,444 bandındadır.

Girdi : ham üretilmiş görseller + üretim kaydı (JSON)
Çıktı : data/external/sentetik/goruntuler/*.jpg + kayitlar.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

HEDEF = REPO_ROOT / "data" / "external" / "sentetik"
KOMUTLAR = Path(__file__).resolve().parent / "kumeler" / "sentetik_afet_komutlari.json"

#: Biçim profili SABİT DEĞİL, gerçek korpustan ÖRNEKLENİR.
#:
#: Sabit kalite bandı denendi ve karıştırıcı üretti: üretilmiş görseller aynı
#: JPEG kalitesinde daha çok sıkışıyor (daha az yüksek-frekans detay taşırlar),
#: bayt/piksel medyanı 0,177'de kalıyordu — gerçek korpus 0,297. Ölçüldü:
#: SADECE bayt/piksel ile ayrım AUC 0,8500. Yani M4'ün doğru-pozitif oranının
#: büyük kısmı modelin yeteneğini değil, dosya boyutu farkını ölçerdi.
#:
#: Çözüm: her görsel için hedef (genişlik, bayt/piksel) çifti gerçek korpusun
#: kendi ampirik dağılımından çekilir ve JPEG kalitesi o hedefi tutturacak
#: şekilde aranır. Böylece biçim, sınıf hakkında bilgi taşımaz.
KALITE_ARALIGI = (30, 96)


def _profil_olc() -> None:
    """Gerçek korpusun biçim profilini basar — sabitlerin doğrulaması için."""
    import statistics

    from PIL import Image

    g = REPO_ROOT / "data" / "external" / "provenance" / "goruntuler"
    if not g.exists():
        print("🔴 gerçek korpus yok; profil ölçülemez")
        return
    bpp, en = [], []
    for p in sorted(g.iterdir()):
        try:
            im = Image.open(p)
            if im.format != "JPEG":
                continue
            bpp.append(p.stat().st_size / (im.size[0] * im.size[1]))
            en.append(im.size[0])
        except Exception:
            continue
    d = statistics.quantiles(bpp, n=10)
    print(f"gerçek korpus  n={len(bpp)}")
    print(f"  bayt/piksel  p10 {d[0]:.3f}  medyan {statistics.median(bpp):.3f}  p90 {d[8]:.3f}")
    print(f"  genişlik     medyan {statistics.median(en):.0f}")


#: Dosya adları ASCII ve boşluksuz tutulur: küme JSONL'de yol olarak taşınır ve
#: boşluk/parantez taşıyan adlar kabuk ile betik arasında sessizce bozuluyor.
_HARF = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iIsSgGuUoOcC")


def _slug(metin: str) -> str:
    sade = metin.translate(_HARF).lower()
    return "".join(c if c.isalnum() else "-" for c in sade).strip("-").replace("--", "-")


def _gercek_profil() -> list[tuple[int, float]]:
    """Gerçek korpusun (genişlik, bayt/piksel) çiftleri — hedef havuzu."""
    from PIL import Image

    g = REPO_ROOT / "data" / "external" / "provenance" / "goruntuler"
    cift = []
    for p in sorted(g.iterdir()):
        try:
            im = Image.open(p)
            if im.format != "JPEG":
                continue
            cift.append((im.size[0], p.stat().st_size / (im.size[0] * im.size[1])))
        except Exception:
            continue
    return cift


def _hedef(tohum: str, havuz: list[tuple[int, float]]) -> tuple[int, float]:
    """Görsel kimliğinden türetilmiş, yeniden üretilebilir hedef biçim."""
    h = int(hashlib.blake2b(tohum.encode("utf-8"), digest_size=8).hexdigest(), 16)
    return havuz[h % len(havuz)]


def _indirge(kaynak: Path, hedef: Path, tohum: str, havuz: list[tuple[int, float]]) -> dict:
    """Üretilmiş görseli gerçek korpustan çekilmiş bir biçim hedefine oturtur.

    Kalite, hedef bayt/piksele ikili aramayla yaklaştırılır. Sabit kalite
    kullanılmaz: sabit kalite, içerik farkı yüzünden sistematik bir dosya
    boyutu farkı bırakıyor ve o fark tek başına sınıfı ele veriyordu.
    """
    import io

    from PIL import Image

    im = Image.open(kaynak).convert("RGB")
    ham_boyut = im.size
    hedef_en, hedef_bpp = _hedef(tohum, havuz)
    if im.width != hedef_en:
        oran = hedef_en / im.width
        im = im.resize((hedef_en, max(1, round(im.height * oran))), Image.LANCZOS)

    piksel = im.width * im.height
    alt, ust = KALITE_ARALIGI
    en_iyi, en_iyi_fark = ust, float("inf")
    while alt <= ust:
        orta = (alt + ust) // 2
        tampon = io.BytesIO()
        im.save(tampon, "JPEG", quality=orta, optimize=True)
        bpp = tampon.tell() / piksel
        fark = abs(bpp - hedef_bpp)
        if fark < en_iyi_fark:
            en_iyi, en_iyi_fark = orta, fark
        if bpp < hedef_bpp:
            alt = orta + 1
        else:
            ust = orta - 1

    im.save(hedef, "JPEG", quality=en_iyi, optimize=True)
    bayt = hedef.stat().st_size
    return {
        "boyut": f"{im.width}x{im.height}",
        "uretim_boyutu": f"{ham_boyut[0]}x{ham_boyut[1]}",
        "jpeg_kalite": en_iyi,
        "hedef_bayt_piksel": round(hedef_bpp, 4),
        "bayt": bayt,
        "bayt_piksel": round(bayt / piksel, 4),
    }


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--ham", type=Path, help="ham üretilmiş görsellerin dizini")
    a.add_argument("--kayit", type=Path, help="üretim kaydı JSON (dosya → tur/komut/uretici)")
    a.add_argument("--profil", action="store_true", help="yalnızca gerçek korpus profilini bas")
    args = a.parse_args()

    if args.profil:
        _profil_olc()
        return 0
    if not args.ham or not args.kayit:
        print("🔴 --ham ve --kayit gerekli (ya da --profil)")
        return 1
    if not args.kayit.exists():
        print(f"🔴 üretim kaydı yok: {args.kayit}")
        return 1

    uretim = json.loads(args.kayit.read_text(encoding="utf-8"))
    goruntuler = HEDEF / "goruntuler"
    goruntuler.mkdir(parents=True, exist_ok=True)

    havuz = _gercek_profil()
    if not havuz:
        print("🔴 gerçek korpus yok; biçim hedefi çekilemez")
        return 1

    kayitlar: list[dict] = []
    atlanan = 0
    for kayit in uretim:
        kaynak = args.ham / kayit["dosya"]
        if not kaynak.exists():
            atlanan += 1
            continue
        # SYNTH_ öneki etik protokol 2(d) gereğidir: dosya adı tek başına
        # içeriğin sentetik olduğunu söylemelidir. Filigran ve C2PA işareti
        # (2a, 2c) bilinçli olarak UYGULANMAZ; gerekçe docs/etik-protokol.md §6.3.
        ad = f"SYNTH_{_slug(kayit['tur'])}_{_slug(kayit['uretici'])}_{len(kayitlar):04d}.jpg"
        olcum = _indirge(kaynak, goruntuler / ad, ad, havuz)
        kayitlar.append({"dosya": ad, **{k: v for k, v in kayit.items() if k != "dosya"}, **olcum})

    if atlanan:
        print(f"⚠ {atlanan} ham görsel bulunamadı, atlandı")
    if not kayitlar:
        print("🔴 hiç görsel işlenmedi")
        return 1

    (HEDEF / "kayitlar.jsonl").write_text(
        "".join(json.dumps(k, ensure_ascii=False) + "\n" for k in kayitlar), encoding="utf-8"
    )

    import statistics

    bpp = [k["bayt_piksel"] for k in kayitlar]
    print(f"✓ {len(kayitlar)} görsel → {goruntuler.relative_to(REPO_ROOT)}")
    print(f"  bayt/piksel medyan {statistics.median(bpp):.3f}  (gerçek korpus: 0.292)")
    turler: dict[str, int] = {}
    for k in kayitlar:
        turler[k["tur"]] = turler.get(k["tur"], 0) + 1
    for t, n in sorted(turler.items(), key=lambda p: -p[1]):
        print(f"  {n:4d}  {t}")
    ureticiler: dict[str, int] = {}
    for k in kayitlar:
        ureticiler[k["uretici"]] = ureticiler.get(k["uretici"], 0) + 1
    print("  üretici: " + " · ".join(f"{u} ({n})" for u, n in sorted(ureticiler.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
