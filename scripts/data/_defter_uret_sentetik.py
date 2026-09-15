#!/usr/bin/env python
"""`notebooks/m4_sentetik_uretim.ipynb` dosyasını üretir.

Defter elle düzenlenmez: hücreler burada yazılır ve bu betikle üretilir.
`scripts/train/_defter_uret.py` ile aynı gerekçe — defter, depo sözleşmelerine
(komut bankası, biçim profili, kayıt şeması) bağlıdır ve iki yerde ayrı
tutulursa ikisi birbirinden kayar.

Komut bankası ve biçim profili deftere GÖMÜLEREK yazılır: Colab'da depoyu
klonlamaya gerek kalmasın diye. Kaynakları:

    scripts/data/kumeler/sentetik_afet_komutlari.json
    scripts/data/kumeler/afet_bicim_profili.json

Kullanım: python scripts/data/_defter_uret_sentetik.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KUMELER = REPO_ROOT / "scripts" / "data" / "kumeler"
CIKTI = REPO_ROOT / "notebooks" / "m4_sentetik_uretim.ipynb"


def md(metin: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": metin.strip().splitlines(True)}


def kod(metin: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": metin.strip().splitlines(True),
    }


def _gomulu(ad: str) -> str:
    """Küme dosyasını deftere gömülecek biçimde okur."""
    ham = json.loads((KUMELER / ad).read_text(encoding="utf-8"))
    return json.dumps(ham, ensure_ascii=False, indent=1)


def hucreler() -> list[dict]:
    komutlar = _gomulu("sentetik_afet_komutlari.json")
    profil = _gomulu("afet_bicim_profili.json")

    return [
        md("""
# M4 — Üretilmiş afet görselleri · üretim defteri

**KrizKalkan AI · Colab A100**

Bu defter, M4'ün **kriz alanındaki kör noktasını** kapatmak için gereken
pozitif sınıf verisini üretir.

---

## Neden bu defter var

M4 ölçüldü ve alan içinde çalışmadığı bulundu:

| Soru | Küme | Sonuç |
|---|---|---|
| Gerçek afet fotoğrafına "sentetik" der mi? | Wikimedia afet korpusu (n=786) | 9/786 — çok iyi |
| **Üretilmiş afet fotoğrafını yakalar mı?** | Üretilmiş korpus (n=35) | **0/35 — hiç** |

Model bozuk değil: OpenFake'te AUC 0,8564, sahtelerde medyan skor 0,5152.
Kör nokta **alana özgü**.

Sebep eğitim kümesinin kuruluşunda: afet korpusu **negatif** sınıfa kondu,
pozitif sınıfta hiç afet içeriği yoktu. Model büyük olasılıkla
"afet sahnesi → gerçek" kısayolunu öğrendi. Yanlış alarmların 782/786'dan
9/786'ya düşmesiyle bu kör nokta aynı madalyonun iki yüzü.

Düzeltme: **pozitif sınıfa üretilmiş afet görseli koymak.** Bu defter onu üretir.

---

## Tasarımın kritik noktası: üretici bazlı ayrım

Üretilmiş görselle eğitip üretilmiş görselle ölçmek **alan içi başarım**
ölçmek olurdu ve bu depo onu kabul etmiyor (bkz. `docs/metrikler/m4.md`).
Bu yüzden üreticiler role ayrılır ve roller KARIŞMAZ:

| Üretici | Mimari | Lisans | Rol |
|---|---|---|---|
| FLUX.1-schnell | rectified flow (DiT) | **Apache 2.0** | eğitim |
| SDXL base 1.0 | UNet latent diffusion | OpenRAIL++-M | eğitim |
| SD 2.1 base | UNet latent diffusion | OpenRAIL++-M | **tutulan** (ölçüm) |
| z_image (Tongyi-MAI) | — (API) | — | **tutulan** (elde 35 görsel var) |

Eğitim sonrası ölçüm yalnızca *tutulan* üreticilerde yapılır: o zaman ölçülen
şey **görülmemiş üreticiye aktarım** olur, ezber değil.

> **Lisans notu.** Eğitimde kullanılan üreticinin lisansı ağırlığın köken
> zincirine girer. `genis` modeli tam da bu yüzden devreye alınmamıştı
> (OpenFakeTiny · CC BY-NC). FLUX.1-schnell **Apache 2.0**'dır ve zinciri
> temiz bırakır. SDXL'in OpenRAIL++-M lisansı kullanım kısıtları taşır
> (Ek A dezenformasyon üretimini yasaklar — biz dedektör eğitiyoruz, tersi).
> Zinciri tartışmasız tutmak isterseniz `SADECE_TEMIZ_LISANS = True` yapın:
> yalnızca Apache 2.0 üreticiler çalışır.

---

## Etik

Komutların hiçbiri gerçek kişi, gerçek olay adı veya kurum içermez. Görseller
yalnızca dedektör eğitimi ve ölçümünde kullanılır, gerçek olay diye
etiketlenmez, dosya adları `SYNTH_` ile başlar ve depoya girmez.
Kayıt: `docs/etik-protokol.md` §6.3.

---

## Çalıştırma

Hücreleri sırayla çalıştırın. Her üretici ayrı hücrededir: biri çökerse
diğerleri etkilenmez, hafızadan düşürülüp devam edilir. Sonunda tek bir zip
iner.
"""),
        md("## 1 · Ayarlar"),
        kod("""
# ── Üretim ayarları ────────────────────────────────────────────────────────
TOHUM = 20260915          # tekrarlanabilirlik: aynı tohum aynı görselleri verir
SADECE_TEMIZ_LISANS = False   # True → yalnızca Apache 2.0 üreticiler

# Üretici başına görsel sayısı. Eğitim için toplam ~1200 pozitif hedefliyoruz;
# tutulan küme ölçüm için daha küçük olabilir ama n<150 güven aralığını
# kullanışsız hâle getirir.
ADET = {
    "flux-schnell": 600,   # eğitim
    "sdxl-base":    600,   # eğitim
    "sd21-base":    200,   # TUTULAN — ölçüm
}

# Tür dağılımı gerçek korpusu taklit eder (Kahramanmaraş ağırlıklı).
TUR_AGIRLIK = {"deprem": 0.55, "sel": 0.22, "yangın": 0.23}

CIKTI_DIZINI = "/content/sentetik_afet"
# ───────────────────────────────────────────────────────────────────────────

import os, json, random, math
os.makedirs(CIKTI_DIZINI, exist_ok=True)
os.makedirs(f"{CIKTI_DIZINI}/goruntuler", exist_ok=True)
print("çıktı:", CIKTI_DIZINI)
print("toplam hedef:", sum(ADET.values()), "görsel")
"""),
        md("## 2 · Kurulum"),
        kod("""
!pip -q install "diffusers==0.36.0" "transformers==4.57.1" "accelerate==1.10.1" \\
                "sentencepiece==0.2.1" "protobuf==6.33.1" 2>&1 | tail -2

import torch
print("torch", torch.__version__)
print("GPU  ", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "YOK")
print("VRAM ", f"{torch.cuda.get_device_properties(0).total_mem / 1e9:.0f} GB"
       if torch.cuda.is_available() else "—")
assert torch.cuda.is_available(), "GPU çalışma zamanı seçin (Runtime → Change runtime type → A100)"
"""),
        md("""
## 3 · Komut bankası ve biçim profili

İkisi de depodan **gömülerek** gelir; Colab'da depoyu klonlamaya gerek yok.

**Biçim profili neden gerekli.** Üretici modeller pırıl pırıl PNG verir; gerçek
korpus ise %95 JPEG, bayt/piksel medyanı 0,292, genişlik medyanı 960'tır. Bu
fark düzeltilmezse model "temiz dosya = üretilmiş" kısayolunu öğrenir. Ölçüldü:
düzeltme öncesi **sadece bayt/piksel ile ayrım AUC 0,8500**, sonrası **0,5005**.

Bu yüzden her görsel, gerçek korpustan çekilen bir (genişlik, bayt/piksel)
hedefine oturtulur ve **JPEG olarak tek kez** kodlanır. PNG indirip yerelde
kodlamak her dosyaya ikinci bir kodlama bindirirdi; çift sıkıştırma izi başlı
başına bir karıştırıcıdır.
"""),
        kod(f"""
KOMUTLAR = {komutlar}

BICIM_PROFILI = {profil}

TURLER = [t for t in KOMUTLAR if not t.startswith("_")]
print("komut bankası:", {{t: len(KOMUTLAR[t]) for t in TURLER}})
print("biçim profili:", BICIM_PROFILI["_olcum"])
"""),
        md("""
## 4 · Komut birleştirme ve biçim oturtma

37 temel sahne, fotoğrafçılık değiştiricileriyle çarpılarak binlerce ayrı
komut üretir. Değiştiriciler **bilinçli olarak fotografiktir**: `cinematic`,
`8k`, `artstation` gibi ifadeler modeli konsept sanatına iter ve ölçmek
istediğimiz alanı kaçırır.
"""),
        kod('''
import hashlib
import io
import os
import random

from PIL import Image

# Fotoğrafçılık değiştiricileri — hepsi kadraj/ışık/doku, hiçbiri stil değil.
CERCEVE = [
    "wide shot", "medium shot", "tight shot", "eye-level",
    "slightly low angle", "shot from across the street",
    "shot from a doorway", "elevated view from an upper window",
]
KOSUL = [
    "overcast", "bright midday sun", "late afternoon light", "grey drizzle",
    "dust haze in the air", "early morning light", "blue hour", "harsh backlight",
]
DOKU = [
    "slight motion blur", "visible sensor noise", "shallow depth of field",
    "flat muted colours", "compressed shadows", "slightly underexposed", "",
]

# SD/SDXL için olumsuz komut. İki iş yapar: (1) modeli fotoğraf tarafında
# tutar, (2) pilot koşuda görülen "kadraja telefon tutan el" kusurunu bastırır.
OLUMSUZ = (
    "illustration, painting, drawing, anime, cartoon, 3d render, cgi, "
    "concept art, digital art, watermark, text, caption, logo, signature, "
    "oversaturated, hdr, hand in frame, holding a phone, selfie, "
    "smartphone screen, collage, border, frame"
)


def komut_uret(tur: str, sira: int, rastgele: random.Random) -> str:
    """Temel sahneyi değiştiricilerle birleştirir."""
    taban = KOMUTLAR[tur][sira % len(KOMUTLAR[tur])]
    parcalar = [taban, rastgele.choice(CERCEVE), rastgele.choice(KOSUL)]
    if (doku := rastgele.choice(DOKU)):
        parcalar.append(doku)
    return ", ".join(parcalar)


def tur_plani(toplam: int, rastgele: random.Random) -> list:
    """Tür dağılımını ağırlıklara göre kurar ve karıştırır."""
    plan = []
    for tur, agirlik in TUR_AGIRLIK.items():
        plan += [tur] * round(toplam * agirlik)
    while len(plan) < toplam:
        plan.append(TURLER[0])
    plan = plan[:toplam]
    rastgele.shuffle(plan)
    return plan


_CIFTLER = BICIM_PROFILI["ciftler"]


def _hedef_bicim(ad: str):
    """Dosya adından türetilmiş, yeniden üretilebilir (genişlik, bayt/piksel)."""
    h = int(hashlib.blake2b(ad.encode("utf-8"), digest_size=8).hexdigest(), 16)
    return _CIFTLER[h % len(_CIFTLER)]


def bicime_oturt(im: Image.Image, yol: str, ad: str) -> dict:
    """Görseli gerçek korpusun biçim hedefine oturtup TEK KEZ JPEG kodlar."""
    im = im.convert("RGB")
    ham = im.size
    hedef_en, hedef_bpp = _hedef_bicim(ad)
    if im.width != hedef_en:
        oran = hedef_en / im.width
        im = im.resize((hedef_en, max(1, round(im.height * oran))), Image.LANCZOS)

    piksel = im.width * im.height
    alt, ust, en_iyi, en_iyi_fark = 30, 96, 96, float("inf")
    while alt <= ust:
        orta = (alt + ust) // 2
        tampon = io.BytesIO()
        im.save(tampon, "JPEG", quality=orta, optimize=True)
        bpp = tampon.tell() / piksel
        if (fark := abs(bpp - hedef_bpp)) < en_iyi_fark:
            en_iyi, en_iyi_fark = orta, fark
        if bpp < hedef_bpp:
            alt = orta + 1
        else:
            ust = orta - 1

    im.save(yol, "JPEG", quality=en_iyi, optimize=True)
    bayt = os.path.getsize(yol)
    return {
        "boyut": f"{im.width}x{im.height}",
        "uretim_boyutu": f"{ham[0]}x{ham[1]}",
        "jpeg_kalite": en_iyi,
        "hedef_bayt_piksel": hedef_bpp,
        "bayt": bayt,
        "bayt_piksel": round(bayt / piksel, 4),
    }


print("komut örneği:")
_r = random.Random(TOHUM)
for _t in TURLER:
    print(f"  [{_t}] {komut_uret(_t, 0, _r)[:150]}…")
'''),
        md("""
## 5 · Üretim motoru

Her üretici kendi hücresinde çalışır. Bir hücre çökerse (OOM, indirme hatası)
diğerleri etkilenmez; kayıt dosyası her üreticiden sonra güncellenir, yani
yarıda kesilse bile o ana kadar üretilenler korunur.
"""),
        kod('''
import gc
import json
import os
import random
import time
import traceback

KAYIT_YOLU = f"{CIKTI_DIZINI}/uretim_kayit.json"


def kayitlari_oku() -> list:
    if os.path.exists(KAYIT_YOLU):
        with open(KAYIT_YOLU, encoding="utf-8") as f:
            return json.load(f)
    return []


def kayitlari_yaz(kayitlar: list) -> None:
    with open(KAYIT_YOLU, "w", encoding="utf-8") as f:
        json.dump(kayitlar, f, ensure_ascii=False, indent=1)


def uret(kod_adi: str, boru, uretici_adi: str, lisans: str, rol: str,
         adet: int, cagir, mimari: str) -> None:
    """Bir üreticiyle `adet` görsel üretir ve kayda işler.

    `cagir(komut, tohum)` tek bir PIL görüntüsü döndürmelidir.
    """
    kayitlar = kayitlari_oku()
    varolan = {k["dosya"] for k in kayitlar}
    rastgele = random.Random(f"{TOHUM}-{kod_adi}")
    plan = tur_plani(adet, rastgele)

    basladi = time.time()
    uretilen = 0
    for i, tur in enumerate(plan):
        ad = f"SYNTH_{tur.replace('ı','i')}_{kod_adi}_{i:04d}.jpg"
        if ad in varolan:
            continue
        komut = komut_uret(tur, i, rastgele)
        tohum = TOHUM + i
        try:
            im = cagir(komut, tohum)
        except Exception:
            print(f"  🔴 {ad} üretilemedi:")
            traceback.print_exc(limit=1)
            continue

        yol = f"{CIKTI_DIZINI}/goruntuler/{ad}"
        olcum = bicime_oturt(im, yol, ad)
        kayitlar.append({
            "dosya": ad, "tur": tur, "uretici": uretici_adi, "kod": kod_adi,
            "mimari": mimari, "lisans": lisans, "rol": rol,
            "komut": komut, "tohum": tohum, "cerceve_kusuru": False, **olcum,
        })
        uretilen += 1

        if uretilen % 25 == 0:
            kayitlari_yaz(kayitlar)
            gecen = time.time() - basladi
            hiz = gecen / uretilen
            kalan = (len(plan) - i - 1) * hiz
            print(f"  {uretilen}/{adet}  ·  {hiz:.1f} sn/görsel  ·  "
                  f"kalan ~{kalan/60:.0f} dk")

    kayitlari_yaz(kayitlar)
    print(f"✓ {uretici_adi}: {uretilen} görsel · "
          f"{(time.time()-basladi)/60:.1f} dk · rol={rol}")


def bosalt(*nesneler):
    """Boru hattını hafızadan düşürür — sıradaki model sığsın diye."""
    for n in nesneler:
        del n
    gc.collect()
    torch.cuda.empty_cache()
    print(f"VRAM boşta: {torch.cuda.mem_get_info()[0]/1e9:.1f} GB")
'''),
        md("""
## 6 · FLUX.1-schnell  ·  **eğitim**  ·  Apache 2.0

Rectified flow transformer — SDXL/SD2.1'den bütünüyle farklı bir mimari,
dolayısıyla farklı bir artefakt imzası. 4 adımda üretir, olumsuz komut
kullanmaz (`guidance_scale=0`).

Lisansı **Apache 2.0**: eğitimde kullanılması ağırlığın köken zincirini
temiz bırakır.
"""),
        kod("""
from diffusers import FluxPipeline

boru = FluxPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16)
boru.enable_model_cpu_offload()   # 40 GB'a rahat sığsın diye
boru.set_progress_bar_config(disable=True)

def _flux(komut, tohum):
    return boru(
        prompt=komut,
        num_inference_steps=4,
        guidance_scale=0.0,
        height=768, width=1024,
        max_sequence_length=256,
        generator=torch.Generator("cpu").manual_seed(tohum),
    ).images[0]

uret("flux-schnell", boru, "black-forest-labs/FLUX.1-schnell", "Apache-2.0",
     "egitim", ADET["flux-schnell"], _flux, "rectified flow (DiT)")
bosalt(boru)
"""),
        md("""
## 7 · SDXL base 1.0  ·  **eğitim**  ·  OpenRAIL++-M

`SADECE_TEMIZ_LISANS = True` ise bu hücre kendini atlar.
"""),
        kod("""
if SADECE_TEMIZ_LISANS:
    print("⏭  atlandı: SADECE_TEMIZ_LISANS açık, SDXL OpenRAIL++-M lisanslı")
else:
    from diffusers import StableDiffusionXLPipeline

    boru = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.float16, variant="fp16", use_safetensors=True).to("cuda")
    boru.set_progress_bar_config(disable=True)

    def _sdxl(komut, tohum):
        return boru(
            prompt=komut, negative_prompt=OLUMSUZ,
            num_inference_steps=30, guidance_scale=6.0,
            height=768, width=1024,
            generator=torch.Generator("cuda").manual_seed(tohum),
        ).images[0]

    uret("sdxl-base", boru, "stabilityai/stable-diffusion-xl-base-1.0",
         "CreativeML OpenRAIL++-M", "egitim", ADET["sdxl-base"], _sdxl,
         "UNet latent diffusion")
    bosalt(boru)
"""),
        md("""
## 8 · SD 2.1 base  ·  **TUTULAN** (ölçüm)  ·  OpenRAIL++-M

⚠️ **Bu üreticinin görselleri eğitime GİRMEZ.** Ölçümde "görülmemiş üretici"
rolünü oynarlar. Kayıtta `rol="tutulan"` ile işaretlidirler ve eğitim betiği
o kayıtları dışarıda bırakır.
"""),
        kod("""
from diffusers import StableDiffusionPipeline

boru = StableDiffusionPipeline.from_pretrained(
    "stabilityai/stable-diffusion-2-1-base",
    torch_dtype=torch.float16, use_safetensors=True).to("cuda")
boru.set_progress_bar_config(disable=True)
boru.safety_checker = None   # afet sahneleri boş kare olarak dönüyordu

def _sd21(komut, tohum):
    return boru(
        prompt=komut, negative_prompt=OLUMSUZ,
        num_inference_steps=25, guidance_scale=7.0,
        height=512, width=768,
        generator=torch.Generator("cuda").manual_seed(tohum),
    ).images[0]

uret("sd21-base", boru, "stabilityai/stable-diffusion-2-1-base",
     "CreativeML OpenRAIL++-M", "tutulan", ADET["sd21-base"], _sd21,
     "UNet latent diffusion")
bosalt(boru)
"""),
        md("## 9 · Özet ve denetim"),
        kod("""
import collections, statistics

kayitlar = kayitlari_oku()
print(f"toplam {len(kayitlar)} görsel\\n")

for alan in ("uretici", "tur", "rol", "lisans"):
    print(alan.upper())
    for k, v in collections.Counter(x[alan] for x in kayitlar).most_common():
        print(f"  {v:5d}  {k}")
    print()

bpp = [k["bayt_piksel"] for k in kayitlar]
kal = [k["jpeg_kalite"] for k in kayitlar]
print(f"bayt/piksel  medyan {statistics.median(bpp):.3f}   "
      f"(gerçek korpus {BICIM_PROFILI['_olcum']['bayt_piksel_medyan']})")
print(f"JPEG kalite  medyan {statistics.median(kal):.0f}  "
      f"min {min(kal)}  max {max(kal)}")

# Rol ayrımının bozulmadığını doğrula: aynı üretici iki rolde olamaz.
roller = collections.defaultdict(set)
for k in kayitlar:
    roller[k["uretici"]].add(k["rol"])
bozuk = {u: r for u, r in roller.items() if len(r) > 1}
assert not bozuk, f"🔴 rol ayrımı bozuk: {bozuk}"
print("\\n✓ üretici bazlı rol ayrımı sağlam")
"""),
        md("""
## 10 · Gözle kontrol

Fotogerçekçilik ve kadraj kusuru için örnek bir tabaka. **Bakılacak şey:**
kadraja giren el/telefon, metin/filigran, çizim üslubu. Kusurlu kareler
yerelde `cerceve_kusuru` ile işaretlenip ölçümde ayrı raporlanır.
"""),
        kod("""
from PIL import Image
import random as _rnd

kayitlar = kayitlari_oku()
_rnd.seed(0)
ornek = _rnd.sample(kayitlar, min(24, len(kayitlar)))
K, S = 260, 6
satir = (len(ornek) + S - 1) // S
tabaka = Image.new("RGB", (K*S, satir*K), (18, 18, 18))
for j, kayit in enumerate(ornek):
    im = Image.open(f"{CIKTI_DIZINI}/goruntuler/{kayit['dosya']}").convert("RGB")
    im.thumbnail((K, K))
    tabaka.paste(im, ((j % S)*K + (K-im.width)//2, (j // S)*K + (K-im.height)//2))
tabaka
"""),
        md("""
## 11 · Paketle ve indir

Zip'i bilgisayarınıza indirin. Ömer'e/depoya şu komutla girer:

```bash
unzip sentetik_afet.zip -d /tmp/sentetik_ham
python scripts/data/build_sentetik_korpus.py \\
    --ham /tmp/sentetik_ham/goruntuler \\
    --kayit /tmp/sentetik_ham/uretim_kayit.json \\
    --bicim-uygulanmis
```

`--bicim-uygulanmis` önemlidir: biçim bu defterde zaten uygulandı, yerelde
ikinci kez kodlamak her dosyaya çift sıkıştırma izi bindirirdi.
"""),
        kod("""
import shutil
from google.colab import files

arsiv = shutil.make_archive("/content/sentetik_afet", "zip", CIKTI_DIZINI)
print(f"paket: {arsiv} · {os.path.getsize(arsiv)/1e6:.0f} MB")
files.download(arsiv)
"""),
    ]


def main() -> int:
    hucre = hucreler()
    defter = {
        "cells": hucre,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"provenance": [], "gpuType": "A100"},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 0,
    }
    CIKTI.parent.mkdir(parents=True, exist_ok=True)
    CIKTI.write_text(json.dumps(defter, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✓ {CIKTI.relative_to(REPO_ROOT)} · {len(hucre)} hücre")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
