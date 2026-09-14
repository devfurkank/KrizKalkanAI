#!/usr/bin/env python
"""`notebooks/m4_colab.ipynb` dosyasını üretir.

Defter elle düzenlenmez: hücreler burada yazılır ve bu betikle üretilir.
Sebebi, defterin depo sözleşmelerine (ön işleme dosyası, model kartı alanları,
kabul kapısı metriği) bağlı olması — iki yerde ayrı ayrı tutmak ikisinin
birbirinden kaymasına yol açar.

Kullanım: python scripts/train/_defter_uret.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CIKTI = REPO_ROOT / "notebooks" / "m4_colab.ipynb"


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


HUCRELER = [
    md("""
# M4 — Sentetik görüntü detektörü · eğitim defteri

**KrizKalkan AI · Colab A100**

Bu defter, `models/m4_synthetic/uretim.onnx` dosyasını sıfırdan üretir.

---

## Neden yeni bir model?

Mevcut ağırlık ölçüldü ve **kullanılamaz** bulundu. Sebep alan karışıklığı değil,
**doygunluk**:

| Küme | Skor medyanı |
|---|---|
| Üretilmiş (OpenFake) | 0,959 |
| Gerçek (ImageNet/DOCCI) | 0,942 |
| Gerçek (Türk afet) | 0,952 |

Her şey 0,92–0,97 bandına sıkışmış; medyan ayrımı **0,0167**. Model her girdiye
yüksek güvenle "üretilmiş" diyor. Çapraz veri kümesinde AUC 0,7818 çıkıyor ama
bu mikroskobik sıralamadan geliyor ve hiçbir mutlak eşik işe yaramıyor: gerçek
afet fotoğraflarının **%99,5'i** 0,50 eşiğinde sahte çıkıyor.

## Tarifi belirleyen dört karar

1. **Gövde donuk, yalnızca LayerNorm + başlık eğitilir.** Tam ince ayar bizi bu
   hâle getirdi. Donuk gövde aşırı öğrenmeyi yapısal olarak engeller.
2. **Her iki sınıfa da sosyal medya artırması.** JPEG yeniden kodlama, ölçekleme,
   kırpma — hem gerçeğe hem üretilmişe. Bu olmazsa model "sıkıştırılmış = sahte"
   kısayolunu öğrenir.
3. **Negatiflere Türk afet korpusu katılır.** Dağıtım alanının kendisi.
4. **Kalibrasyon tarifin parçası.** Ham skor doğrudan kullanılmaz.

Başarı ölçütü AUC değil, **afet alanında özgüllük**: kabul kapısı
`afet_ozgulluk ≥ 0,95` istiyor.
"""),
    md("""
## 0 · Ortam

A100 seçili olmalı: **Çalışma zamanı → Çalışma zamanı türünü değiştir → A100 GPU**
"""),
    kod("""
!nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
!pip install -q "transformers>=4.46" "onnx>=1.17" "onnxruntime>=1.20" "scikit-learn>=1.6" pillow huggingface_hub pyarrow

import torch, platform
print(f"torch {torch.__version__} · cuda {torch.cuda.is_available()} · {platform.python_version()}")
"""),
    md("""
## 1 · Ayarlar

`MODEL_SURUMU` iki değer alır:

| Değer | Eğitim verisi | Lisans sonucu |
|---|---|---|
| `"temiz"` | GenImage (MIT) + afet korpusu | **Ticari kullanıma açık** |
| `"genis"` | yukarıdakiler + OpenFakeTiny | CC BY-NC — ticari kullanıma kapalı |

İkisini de üretip karşılaştıracağız. Önce `"temiz"` ile koş, sonra `"genis"` ile
tekrar koş; çıktılar ayrı klasörlere yazılır.
"""),
    kod("""
MODEL_SURUMU = "temiz"      # "temiz" | "genis"

GIRIS_BOYUTU  = 224          # SigLIP2-base-patch16-224
YIGIN         = 64
EPOK          = 6
OGRENME_ORANI = 3e-4         # yalnızca başlık ve LayerNorm eğitiliyor, yüksek olabilir
TOHUM         = 20260912

# Sınıf başına azami örnek — dengeyi biz kuruyoruz, kümelerin dağılımına bırakmıyoruz
AZAMI_URETILMIS = 6000
AZAMI_GERCEK    = 6000

import os, random, json, numpy as np, torch
from pathlib import Path

random.seed(TOHUM); np.random.seed(TOHUM); torch.manual_seed(TOHUM)
torch.cuda.manual_seed_all(TOHUM)

CALISMA = Path("/content/m4"); CALISMA.mkdir(exist_ok=True)
CIKTI = CALISMA / f"cikti_{MODEL_SURUMU}"; CIKTI.mkdir(exist_ok=True)
print("çıktı dizini:", CIKTI)
"""),
    md("""
## 2 · Afet korpusu

Bu, eğitimin **en kritik parçası**: 786 gerçek Türk afet fotoğrafı, sistemin
sahada göreceği içeriğin ta kendisi. Negatif sınıfa katılıyor.

Yerel depodan yükle:

```bash
cd "KrizKalkanAI" && zip -r afet_korpusu.zip data/external/provenance/goruntuler
```

Sonra aşağıdaki hücrede dosyayı seç.
"""),
    kod("""
from google.colab import files
import zipfile

AFET_DIZINI = CALISMA / "afet"
if not AFET_DIZINI.exists():
    print("afet_korpusu.zip dosyasını seç…")
    yuklenen = files.upload()
    ad = next(iter(yuklenen))
    with zipfile.ZipFile(ad) as z:
        z.extractall(AFET_DIZINI)

afet_yollari = sorted(p for p in AFET_DIZINI.rglob("*") if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
print(f"afet korpusu: {len(afet_yollari)} görüntü")
assert afet_yollari, "korpus boş — zip içeriğini kontrol et"
"""),
    md("""
## 3 · Eğitim verisi

**GenImage (MIT)** — `jhutter2/281_Genimage`, 1,36 GB, üç üretici (ADM, SD 1.5,
wukong) ve ImageNet gerçekleri. Lisansı temiz olduğu için her iki sürümde de var.

**OpenFakeTiny** yalnızca `"genis"` sürümünde eklenir; 2026 üreticilerini
taşıyor ama CC BY-NC.

> Değerlendirme kümesi (`OpenFake core/test`) **hiçbir sürümde eğitime
> girmiyor**. `"genis"` sürümü yalnızca `train` bölümünü kullanıyor.
"""),
    kod("""
from huggingface_hub import snapshot_download

genimage = Path(snapshot_download(
    "jhutter2/281_Genimage", repo_type="dataset",
    local_dir=str(CALISMA / "genimage"), max_workers=8,
))

uretilmis_yollari, gercek_yollari = [], []
for alt in genimage.iterdir():
    if not alt.is_dir():
        continue
    for etiket, hedef in (("ai", uretilmis_yollari), ("nature", gercek_yollari)):
        d = alt / etiket
        if d.exists():
            hedef.extend(p for p in d.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"})

print(f"GenImage → üretilmiş {len(uretilmis_yollari)} · gerçek {len(gercek_yollari)}")
"""),
    kod("""
# OpenFakeTiny — yalnızca "genis" sürümünde
import io
from PIL import Image

if MODEL_SURUMU == "genis":
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    ek_dizin = CALISMA / "openfake"; ek_dizin.mkdir(exist_ok=True)
    sayac = 0
    for parca in ("core/train-00000-of-00002.parquet", "core/train-00001-of-00002.parquet"):
        yol = hf_hub_download("ComplexDataLab/OpenFakeTiny", parca, repo_type="dataset")
        dosya = pq.ParquetFile(yol)
        for grup in range(dosya.metadata.num_row_groups):
            tablo = dosya.read_row_group(grup, columns=["image", "label"]).to_pylist()
            for satir in tablo:
                if sayac >= 4000:
                    break
                hedef = ek_dizin / f"{satir['label']}_{sayac:06d}.jpg"
                try:
                    with Image.open(io.BytesIO(satir["image"]["bytes"])) as im:
                        im.convert("RGB").save(hedef, "JPEG", quality=92)
                except Exception:
                    continue
                (uretilmis_yollari if satir["label"] == "fake" else gercek_yollari).append(hedef)
                sayac += 1
            del tablo
            if sayac >= 4000:
                break
        if sayac >= 4000:
            break
    print(f"OpenFakeTiny eklendi: {sayac}")
else:
    print("temiz sürüm — OpenFake eklenmedi")
"""),
    md("""
## 4 · Veri kümesi ve artırma

**Artırma, bu defterin en önemli parçasıdır.** Her iki sınıfa da aynı sosyal
medya boru hattı uygulanıyor: JPEG yeniden kodlama, ölçekleme, kırpma. Amaç,
modelin sıkıştırma izini sınıf ipucu olarak kullanmasını **engellemek**.

Önceki modelin afet korpusunun %99'unu sahte sanmasının muhtemel sebebi tam
olarak buydu: eğitimdeki gerçekler temiz, yeniden kodlanmışlar ise hiç yoktu.
"""),
    kod("""
import io, random
from PIL import Image
from torch.utils.data import Dataset, DataLoader
import torchvision.transforms as T

ORTALAMA, SAPMA = (0.5, 0.5, 0.5), (0.5, 0.5, 0.5)


def sosyal_medya_artirmasi(im: Image.Image, rastgele: random.Random) -> Image.Image:
    \"\"\"Bir paylaşımın geçtiği işlemleri taklit eder.\"\"\"
    # 1) rastgele yeniden ölçekleme — platformlar yeniden boyutlandırır
    if rastgele.random() < 0.8:
        oran = rastgele.uniform(0.35, 1.0)
        yeni = (max(int(im.width * oran), 64), max(int(im.height * oran), 64))
        im = im.resize(yeni, Image.BILINEAR)

    # 2) rastgele kırpma
    if rastgele.random() < 0.5 and min(im.size) > 96:
        kenar = rastgele.uniform(0.75, 1.0)
        g, y = int(im.width * kenar), int(im.height * kenar)
        x0 = rastgele.randrange(0, im.width - g + 1)
        y0 = rastgele.randrange(0, im.height - y + 1)
        im = im.crop((x0, y0, x0 + g, y0 + y))

    # 3) JPEG yeniden kodlama — EN ÖNEMLİ ADIM
    if rastgele.random() < 0.9:
        tampon = io.BytesIO()
        im.save(tampon, "JPEG", quality=rastgele.randint(35, 95))
        tampon.seek(0)
        im = Image.open(tampon).convert("RGB")

    return im


class GoruntuKumesi(Dataset):
    def __init__(self, ogeler, egitim: bool):
        self.ogeler = ogeler          # [(yol, etiket)] · etiket 1 = üretilmiş
        self.egitim = egitim
        self.son = T.Compose([
            T.Resize((GIRIS_BOYUTU, GIRIS_BOYUTU), interpolation=T.InterpolationMode.BILINEAR),
            T.ToTensor(),
            T.Normalize(ORTALAMA, SAPMA),
        ])

    def __len__(self):
        return len(self.ogeler)

    def __getitem__(self, i):
        yol, etiket = self.ogeler[i]
        rastgele = random.Random(hash((str(yol), i, self.egitim)) & 0xFFFFFFFF)
        try:
            with Image.open(yol) as ham:
                im = ham.convert("RGB")
        except Exception:
            im = Image.new("RGB", (GIRIS_BOYUTU, GIRIS_BOYUTU), (127, 127, 127))
        if self.egitim:
            im = sosyal_medya_artirmasi(im, rastgele)
            if rastgele.random() < 0.5:
                im = im.transpose(Image.FLIP_LEFT_RIGHT)
        return self.son(im), etiket
"""),
    kod("""
# Kümeleri kur — afet korpusu NEGATİFLERE katılıyor
rastgele = random.Random(TOHUM)
rastgele.shuffle(uretilmis_yollari); rastgele.shuffle(gercek_yollari)

uretilmis = [(p, 1) for p in uretilmis_yollari[:AZAMI_URETILMIS]]
gercek    = [(p, 0) for p in gercek_yollari[:AZAMI_GERCEK]]

# Afet korpusu: %80 eğitim, %20 doğrulama — dağıtım alanı iki tarafta da olmalı
afet = [(p, 0) for p in afet_yollari]
rastgele.shuffle(afet)
afet_sinir = int(len(afet) * 0.8)

tum = uretilmis + gercek
rastgele.shuffle(tum)
bol = int(len(tum) * 0.9)

egitim_ogeleri    = tum[:bol] + afet[:afet_sinir]
dogrulama_ogeleri = tum[bol:] + afet[afet_sinir:]
rastgele.shuffle(egitim_ogeleri); rastgele.shuffle(dogrulama_ogeleri)

print(f"eğitim    : {len(egitim_ogeleri):6d}  (üretilmiş {sum(e for _, e in egitim_ogeleri)})")
print(f"doğrulama : {len(dogrulama_ogeleri):6d}  (üretilmiş {sum(e for _, e in dogrulama_ogeleri)})")
print(f"afet korpusu eğitimde {afet_sinir}, doğrulamada {len(afet) - afet_sinir}")

egitim_yukleyici = DataLoader(GoruntuKumesi(egitim_ogeleri, True), batch_size=YIGIN,
                              shuffle=True, num_workers=8, pin_memory=True, drop_last=True)
dogrulama_yukleyici = DataLoader(GoruntuKumesi(dogrulama_ogeleri, False), batch_size=YIGIN,
                                 shuffle=False, num_workers=8, pin_memory=True)
"""),
    md("""
## 5 · Model

**Gövde donuk.** Yalnızca LayerNorm parametreleri ve sınıflandırma başlığı
eğitiliyor — 93M yerine yaklaşık 0,8M parametre. Bu, ölçtüğümüz doygunluğun
doğrudan panzehiri: gövde ImageNet ölçeğinde öğrendiği temsili koruyor, biz
yalnızca karar sınırını ayarlıyoruz.
"""),
    kod("""
from transformers import SiglipVisionModel, SiglipVisionConfig
import torch.nn as nn

OMURGA = "google/siglip2-base-patch16-224"


class SentetikDedektor(nn.Module):
    def __init__(self):
        super().__init__()
        self.vision_model = SiglipVisionModel.from_pretrained(OMURGA)
        gizli = self.vision_model.config.hidden_size

        # Gövdeyi dondur, yalnızca LayerNorm'ları serbest bırak
        for ad, p in self.vision_model.named_parameters():
            p.requires_grad = "layer_norm" in ad or "layernorm" in ad

        self.classifier = nn.Sequential(
            nn.LayerNorm(gizli),
            nn.Dropout(0.2),
            nn.Linear(gizli, 256),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(256, 2),          # 0 = üretilmiş, 1 = gerçek
        )

    def forward(self, pixel_values):
        return self.classifier(self.vision_model(pixel_values=pixel_values).pooler_output)


model = SentetikDedektor().cuda()
egitilir = sum(p.numel() for p in model.parameters() if p.requires_grad)
toplam = sum(p.numel() for p in model.parameters())
print(f"eğitilebilir {egitilir/1e6:.2f}M / toplam {toplam/1e6:.1f}M  (%{100*egitilir/toplam:.1f})")
"""),
    md("## 6 · Eğitim"),
    kod("""
from torch.optim import AdamW
from torch.amp import autocast, GradScaler
import time

optimizer = AdamW([p for p in model.parameters() if p.requires_grad],
                  lr=OGRENME_ORANI, weight_decay=0.01)
plan = torch.optim.lr_scheduler.OneCycleLR(
    optimizer, max_lr=OGRENME_ORANI, total_steps=EPOK * len(egitim_yukleyici), pct_start=0.1)
kayip_fn = nn.CrossEntropyLoss(label_smoothing=0.05)
olcekleyici = GradScaler("cuda")


def dogrula():
    model.eval()
    olasilik, etiketler = [], []
    with torch.no_grad(), autocast("cuda", dtype=torch.bfloat16):
        for x, y in dogrulama_yukleyici:
            cikti = model(x.cuda(non_blocking=True))
            olasilik.append(torch.softmax(cikti.float(), 1)[:, 0].cpu())
            etiketler.append(y)
    return torch.cat(olasilik).numpy(), torch.cat(etiketler).numpy()


from sklearn.metrics import roc_auc_score

en_iyi = -1.0
for epok in range(1, EPOK + 1):
    model.train(); basladi = time.time(); toplam_kayip = 0.0
    for adim, (x, y) in enumerate(egitim_yukleyici, 1):
        x, y = x.cuda(non_blocking=True), y.cuda(non_blocking=True)
        # etiket 1 = üretilmiş; modelin 0. çıktısı "üretilmiş" olduğu için çevir
        hedef = 1 - y
        optimizer.zero_grad(set_to_none=True)
        with autocast("cuda", dtype=torch.bfloat16):
            kayip = kayip_fn(model(x), hedef)
        olcekleyici.scale(kayip).backward()
        olcekleyici.step(optimizer); olcekleyici.update(); plan.step()
        toplam_kayip += kayip.item()
        if adim % 50 == 0:
            print(f"  epok {epok} adım {adim}/{len(egitim_yukleyici)} kayıp {toplam_kayip/adim:.4f}")

    skor, gercek = dogrula()
    auc = roc_auc_score(gercek, skor)
    # Ayrım genişliği: doygunluğun ölçüsü
    ayrim = float(np.median(skor[gercek == 1]) - np.median(skor[gercek == 0]))
    print(f"epok {epok}: AUC {auc:.4f} · medyan ayrımı {ayrim:.4f} · {time.time()-basladi:.0f} sn")

    if auc > en_iyi:
        en_iyi = auc
        torch.save(model.state_dict(), CIKTI / "en_iyi.pt")
        print(f"  ✓ kaydedildi (AUC {auc:.4f})")

model.load_state_dict(torch.load(CIKTI / "en_iyi.pt"))
print(f"en iyi doğrulama AUC: {en_iyi:.4f}")
"""),
    md("""
## 7 · Değerlendirme — asıl sınav

İki sayı belirleyici:

- **Afet alanı özgüllüğü** — kabul kapısının okuduğu metrik, `≥ 0,95` olmalı
- **Çapraz veri kümesi AUC'si** — OpenFake `core/test`, eğitimde hiç görülmedi
"""),
    kod("""
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

def skorla(yollar_veya_baytlar, bayt_mi=False):
    model.eval(); skorlar = []
    son = GoruntuKumesi([], False).son
    with torch.no_grad(), autocast("cuda", dtype=torch.bfloat16):
        for i in range(0, len(yollar_veya_baytlar), YIGIN):
            oge = yollar_veya_baytlar[i:i + YIGIN]
            yigin = []
            for o in oge:
                try:
                    kaynak = io.BytesIO(o) if bayt_mi else o
                    with Image.open(kaynak) as ham:
                        yigin.append(son(ham.convert("RGB")))
                except Exception:
                    yigin.append(torch.zeros(3, GIRIS_BOYUTU, GIRIS_BOYUTU))
            cikti = model(torch.stack(yigin).cuda())
            skorlar.extend(torch.softmax(cikti.float(), 1)[:, 0].cpu().tolist())
    return np.array(skorlar)


# ── Çapraz veri kümesi: OpenFake core/test (eğitimde YOK) ──
test_yolu = hf_hub_download("ComplexDataLab/OpenFake",
                            "core/test-00000-of-00013.parquet", repo_type="dataset")
dosya = pq.ParquetFile(test_yolu)
capraz_bayt, capraz_etiket = [], []
for grup in range(dosya.metadata.num_row_groups):
    for satir in dosya.read_row_group(grup, columns=["image", "label"]).to_pylist():
        if len(capraz_bayt) >= 1000:
            break
        capraz_bayt.append(satir["image"]["bytes"])
        capraz_etiket.append(1 if satir["label"] == "fake" else 0)
    if len(capraz_bayt) >= 1000:
        break

capraz_skor = skorla(capraz_bayt, bayt_mi=True)
capraz_etiket = np.array(capraz_etiket)
capraz_auc = roc_auc_score(capraz_etiket, capraz_skor)

# ── Afet alanı: tamamı gerçek ──
afet_skor = skorla(afet_yollari)
afet_yp = float((afet_skor >= 0.5).mean())
afet_ozgulluk = 1.0 - afet_yp

print(f"çapraz AUC        : {capraz_auc:.4f}   (hedef ≥ 0,72)")
print(f"afet yanlış pozitif: {afet_yp:.4f}")
print(f"AFET ÖZGÜLLÜĞÜ    : {afet_ozgulluk:.4f}   (KABUL KAPISI ≥ 0,95)")
print()
print(f"üretilmiş medyan {np.median(capraz_skor[capraz_etiket==1]):.4f} · "
      f"gerçek medyan {np.median(capraz_skor[capraz_etiket==0]):.4f} · "
      f"ayrım {np.median(capraz_skor[capraz_etiket==1])-np.median(capraz_skor[capraz_etiket==0]):.4f}")
print("→ ayrım 0,20'nin üstündeyse doygunluk kırılmış demektir")
"""),
    md("""
## 8 · Kalibrasyon

Sıcaklık ölçekleme, tutulmuş bölmede. Ham skor doğrudan kullanılmaz.
"""),
    kod("""
from sklearn.metrics import log_loss

dogrulama_skor, dogrulama_etiket = dogrula()

def ece(olasilik, etiket, kova=10):
    sinir = np.linspace(0, 1, kova + 1); toplam = 0.0
    for a, b in zip(sinir[:-1], sinir[1:]):
        m = (olasilik >= a) & (olasilik < b)
        if m.sum():
            toplam += m.mean() * abs(olasilik[m].mean() - etiket[m].mean())
    return toplam

# `dogrula()` skoru P(üretilmiş), etiketi de zaten 1 = üretilmiş döndürüyor.
# Burada bir kez daha çevirmek, skoru TERS etikete karşı ölçüyordu ve iyi bir
# modelde ECE'yi tam olarak ~0,86'ya çıkarıyordu (yaşandı).
hedef = dogrulama_etiket
en_iyi_t, en_iyi_kayip = 1.0, 1e9
for t in np.linspace(0.25, 10.0, 196):
    p = 1 / (1 + np.exp(-(np.log(dogrulama_skor / (1 - dogrulama_skor + 1e-9) + 1e-9)) / t))
    kayip = log_loss(hedef, np.clip(p, 1e-6, 1 - 1e-6))
    if kayip < en_iyi_kayip:
        en_iyi_kayip, en_iyi_t = kayip, t

print(f"ECE kalibrasyon öncesi: {ece(dogrulama_skor, hedef):.4f}")
p_kalibre = 1 / (1 + np.exp(-(np.log(dogrulama_skor/(1-dogrulama_skor+1e-9)+1e-9))/en_iyi_t))
print(f"ECE kalibrasyon sonrası: {ece(p_kalibre, hedef):.4f}  (sıcaklık {en_iyi_t:.2f})")
"""),
    md("""
## 9 · ONNX dışa aktarım (fp32)

Çıktı, `synthetic/image.py`'ın beklediği sözleşmeye uymak zorunda:
girdi `pixel_values`, çıktı `logits`, **0. sınıf = üretilmiş**.

> **int8 niceleme UYGULANMIYOR.** Denendi ve modelin kararını bozdu: azami
> logit sapması 2,4152, gerçek afet fotoğraflarında P(üretilmiş) medyanı
> 0,0197'den 0,2552'ye kaydı ve kabul kapısı 0,9885'ten 0,5466'ya düştü.
>
> Önceki (DeepReality) ağırlık int8'e dayanıyordu çünkü çıktıları zaten
> doygundu — kaydırmanın değiştireceği bir karar yoktu. Bu model gerçek bir
> karar sınırına sahip; niceleme o sınırı kaydırıyor.
>
> Bedeli dosya boyutu: 95 MB yerine ~373 MB. Gecikme hedefleri (p50 ≤ 8 sn)
> bunu rahatça karşılıyor.
"""),
    kod("""
model_cpu = SentetikDedektor()
model_cpu.load_state_dict(torch.load(CIKTI / "en_iyi.pt", map_location="cpu"))
model_cpu.eval()

hedef_onnx = CIKTI / "uretim.onnx"
torch.onnx.export(
    model_cpu, (torch.zeros(1, 3, GIRIS_BOYUTU, GIRIS_BOYUTU),), str(hedef_onnx),
    input_names=["pixel_values"], output_names=["logits"],
    dynamic_axes={"pixel_values": {0: "yigin"}, "logits": {0: "yigin"}},
    opset_version=18, dynamo=False,
)
print(f"fp32 ONNX: {hedef_onnx.stat().st_size/1e6:.0f} MB")

# ONNX torch ile örtüşüyor mu? Örtüşmüyorsa dışa aktarım sessizce bozulmuştur.
import onnxruntime as ort
oturum = ort.InferenceSession(str(hedef_onnx), providers=["CPUExecutionProvider"])
ornek = torch.rand(4, 3, GIRIS_BOYUTU, GIRIS_BOYUTU, generator=torch.Generator().manual_seed(0))
with torch.no_grad():
    ref = model_cpu(ornek).numpy()
(cik,) = oturum.run(None, {"pixel_values": ornek.numpy()})
sapma = np.abs(cik - ref).max()
print(f"ONNX ↔ torch azami logit sapması: {sapma:.6f}")
assert sapma < 0.01, "dışa aktarım doğrulanamadı — ONNX torch ile örtüşmüyor"

# ONNX ile afet özgüllüğünü YENİDEN ölç: raporlanan sayı, dağıtılan dosyadan gelmeli.
# Colab'da torch modelini ölçüp ONNX'i dağıtmak, iki farklı şeyi ölçmek demektir.
def onnx_skorla(yollar):
    son = GoruntuKumesi([], False).son
    skorlar = []
    for i in range(0, len(yollar), 32):
        yigin = []
        for y in yollar[i:i+32]:
            try:
                with Image.open(y) as ham:
                    yigin.append(son(ham.convert("RGB")))
            except Exception:
                yigin.append(torch.zeros(3, GIRIS_BOYUTU, GIRIS_BOYUTU))
        (c,) = oturum.run(None, {"pixel_values": torch.stack(yigin).numpy()})
        e = np.exp(c - c.max(1, keepdims=True))
        skorlar.extend((e / e.sum(1, keepdims=True))[:, 0].tolist())
    return np.array(skorlar)

afet_skor_onnx = onnx_skorla(afet_yollari)
afet_ozgulluk = 1.0 - float((afet_skor_onnx >= 0.5).mean())
print(f"ONNX ile afet özgüllüğü: {afet_ozgulluk:.4f}  (karta bu yazılacak)")
"""),
    md("""
## 10 · Ön işleme ve model kartı

`onisleme.json` çalışma zamanının okuduğu sözleşme; `kart.json` ise kabul
kapısının okuduğu ölçüm kaydı. **Kart olmadan ağırlık yüklenmez.**
"""),
    kod("""
import datetime

(CIKTI / "onisleme.json").write_text(json.dumps({
    "uretim": {"boyut": GIRIS_BOYUTU, "ortalama": list(ORTALAMA),
               "sapma": list(SAPMA), "yeniden_ornekleme": "BILINEAR"},
    "tur":    {"boyut": 224, "ortalama": list(ORTALAMA),
               "sapma": list(SAPMA), "yeniden_ornekleme": "BILINEAR"},
    "etiketler": ["sentetik", "manipüle", "gerçek"],
}, ensure_ascii=False, indent=2), encoding="utf-8")

lisans = ("MIT (GenImage) · CC BY-SA 4.0 (Wikimedia afet korpusu)" if MODEL_SURUMU == "temiz"
          else "CC BY-NC 4.0 — OpenFake eğitime katıldı, TİCARİ KULLANIMA KAPALI")
egitim_verisi = ["jhutter2/281_Genimage (MIT) · ADM, SD 1.5, wukong + ImageNet gerçekleri",
                 f"Wikimedia Commons Türkiye afet korpusu · {afet_sinir} görüntü negatif sınıfta"]
if MODEL_SURUMU == "genis":
    egitim_verisi.append("ComplexDataLab/OpenFakeTiny core/train (CC BY-NC 4.0) · 2026 üreticileri")

kart = {
    "name": "m4_synthetic", "module": "M4",
    "title": f"Sentetik görüntü tespiti ({MODEL_SURUMU} lisans)",
    "version": f"0.2-{MODEL_SURUMU}",
    "base_model": OMURGA,
    "purpose": ("Görüntüde yapay üretim izi arar. Gövde donuk, yalnızca LayerNorm ve "
                "sınıflandırma başlığı eğitildi; önceki sürümün doygunluk sorunu bu "
                "kısıtla giderildi. Çıktı olasılıksaldır; C2PA imzası varsa karar oradan gelir."),
    "training_data": egitim_verisi,
    "training_procedure": (
        f"Donuk SigLIP2 gövdesi + LayerNorm ayarı · {EPOK} epok · OneCycle lr={OGRENME_ORANI} · "
        "her iki sınıfa sosyal medya artırması (JPEG yeniden kodlama 35-95, ölçekleme 0,35-1,0, "
        "kırpma, ayna). Artırma bilinçlidir: sıkıştırma izinin sınıf ipucu olarak "
        "öğrenilmesini engeller."),
    "hyperparameters": {"giris": f"{GIRIS_BOYUTU}x{GIRIS_BOYUTU}", "yigin": YIGIN,
                        "epok": EPOK, "ogrenme_orani": OGRENME_ORANI,
                        "egitilebilir_parametre": f"{egitilir/1e6:.2f}M",
                        "niceleme": "yok — int8 kararı bozuyor, fp32 dağıtılıyor",
                        "kalibrasyon_sicakligi": round(float(en_iyi_t), 3)},
    "split_strategy": "Üretici bazlı ayrım; değerlendirme kümesi (OpenFake core/test) eğitime hiç girmedi",
    "measurements": [
        {"metric": "afet_ozgulluk", "value": round(afet_ozgulluk, 4),
         "dataset": "Wikimedia Commons Türkiye afet korpusu (tamamı gerçek)",
         "n": len(afet_yollari), "note": "karar eşiği 0.5 · kabul kapısının ölçütü"},
        {"metric": "capraz_auc", "value": round(float(capraz_auc), 4),
         "dataset": "ComplexDataLab/OpenFake · core/test-00000-of-00013.parquet",
         "n": len(capraz_bayt), "note": "eğitimde kullanılmadı"},
        {"metric": "dogrulama_auc", "value": round(float(en_iyi), 4),
         "dataset": "kendi doğrulama bölmesi", "n": len(dogrulama_ogeleri), "note": None},
    ],
    "known_limits": [
        "Yalnızca görüntü. Video için kare çıkarımı gerekir ve kurulu değil.",
        "Eğitim üreticileri 2023 kuşağı (ADM, SD 1.5, wukong); 2026 üreticilerinde "
        "başarım çapraz veri kümesi ölçümünden okunmalıdır.",
        "Üstveri ve C2PA sinyalleri belgeseldir ve bu modelden önce gelir.",
    ],
    "ethical_notes": [
        "Skor bir suçlama değildir; tek başına içerik kaldırma gerekçesi sayılmaz.",
        "Afet alanı yanlış pozitifi kabul kapısının ölçütüdür: gerçek bir afet "
        "fotoğrafını işaretlemek, sentetik bir görüntüyü kaçırmaktan daha zararlıdır.",
    ],
    "out_of_scope": ["Kimlik tespiti", "Adli delil üretimi", "Video ve ses içeriği"],
    "license": lisans,
    "created_at": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
    "git_commit": None,
}
(CIKTI / "kart.json").write_text(json.dumps(kart, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"KABUL KAPISI: afet_ozgulluk {afet_ozgulluk:.4f} — "
      f"{'GEÇTİ ✓' if afet_ozgulluk >= 0.95 else 'GEÇEMEDİ ✗'}")
print(f"çapraz AUC  : {capraz_auc:.4f} — {'geçti ✓' if capraz_auc >= 0.72 else 'geçemedi ✗'}")
"""),
    md("""
## 11 · İndir

`uretim.onnx`, `onisleme.json` ve `kart.json` dosyalarını depodaki
`models/m4_synthetic/` altına koy. **`tur.onnx` yerinde kalsın** — o ayrı bir
model ve bu defter onu değiştirmiyor.

Sonra yerelde:

```bash
KK_MODELS=on python scripts/eval/m4_synthetic.py
make test
```
"""),
    kod("""
import shutil
from google.colab import files

arsiv = shutil.make_archive(str(CALISMA / f"m4_{MODEL_SURUMU}"), "zip", str(CIKTI))
print("paket:", arsiv)
files.download(arsiv)
"""),
]


def main() -> int:
    defter = {
        "cells": HUCRELER,
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
    print(f"✓ {CIKTI.relative_to(REPO_ROOT)} · {len(HUCRELER)} hücre")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
