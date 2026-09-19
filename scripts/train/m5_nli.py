#!/usr/bin/env python
"""M5 · Aşama 2 — Türkçe doğal dil çıkarımı (NLI) ince ayarı.

Geri getirme aday üretir, karar bu modelindir (rapor 3.1 · M5).

Neden gerekli: `docs/metrikler/m5.md` ölçümü, benzerlik skorunun tek başına
karar verdiremediğini gösteriyor — en yüksek skorlu alakasız sorgu resmî bir
AFAD duyurusuydu (0,890). Konu benzerliği ile *aynı iddiayı öne sürme* farklı
şeylerdir; ikincisi bir çıkarım görevidir.

Görev kurulumu:

    öncül  (premise)    = havuzdaki kaydın tekzip ettiği iddia
    varsayım (hypothesis) = kullanıcının metninden çıkarılan iddia

    entailment  → aynı iddia · DMM bu iddiayı yalanlamış → ÇELİŞİYOR
    neutral     → farklı iddia                          → İLGİSİZ
    contradiction → iddianın tersi (ör. tekzip metni)    → DESTEKLİYOR

Son satır önemlidir: kullanıcı tekzibin kendisini paylaşıyorsa sistem onu
dezenformasyon saymamalıdır (bkz. fusion/engine.py · yalanlama çerçevesi).

Kullanım:
    python scripts/train/m5_nli.py --smoke
    python scripts/train/m5_nli.py --epok 2 --ornek 150000
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

#: SNLI-TR etiket düzeni. -1 altın etiketi olmayan satırları işaretler ve elenir.
SINIFLAR = ("entailment", "neutral", "contradiction")
GECERSIZ = -1

VARSAYILAN_CIKTI = (
    Path("/kaggle/working") if Path("/kaggle/working").exists() else REPO_ROOT / "cikti"
)


@dataclass
class Ayarlar:
    omurga: str = "FacebookAI/xlm-roberta-base"
    epok: int = 2
    yigin: int = 32
    ogrenme_orani: float = 2e-5
    maks_uzunluk: int = 128
    isinma_orani: float = 0.06
    agirlik_sonumu: float = 0.01
    #: SNLI-TR'nin tamamı 550 bin satır; Kaggle kotası buna yetmez ve gerekmez.
    ornek: int = 150_000
    sabir: int = 1
    tohum: int = 42
    smoke: bool = False
    cikti: Path = field(default_factory=lambda: VARSAYILAN_CIKTI / "m5_nli")


class NliVeriKumesi(Dataset):
    def __init__(self, df: pd.DataFrame, tokenizer, maks_uzunluk: int) -> None:
        self.onculler = df["premise"].astype(str).tolist()
        self.varsayimlar = df["hypothesis"].astype(str).tolist()
        self.etiketler = df["label"].astype(int).tolist()
        self.tokenizer = tokenizer
        self.maks_uzunluk = maks_uzunluk

    def __len__(self) -> int:
        return len(self.etiketler)

    def __getitem__(self, i: int) -> dict[str, torch.Tensor]:
        kodlanmis = self.tokenizer(
            self.onculler[i],
            self.varsayimlar[i],
            truncation=True,
            max_length=self.maks_uzunluk,
            padding="max_length",
            return_tensors="pt",
        )
        return {
            "input_ids": kodlanmis["input_ids"].squeeze(0),
            "attention_mask": kodlanmis["attention_mask"].squeeze(0),
            "labels": torch.tensor(self.etiketler[i]),
        }


def _git_commit() -> str | None:
    """Ağırlığın hangi kodla üretildiğini kart üzerinden izlenebilir kılar."""
    import subprocess

    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=True,
        ).stdout.strip()
    except Exception:
        return None


def veri_yukle(ayarlar: Ayarlar) -> tuple[pd.DataFrame, pd.DataFrame]:
    """SNLI-TR eğitim ve doğrulama kümelerini hazırlar.

    Kaggle'da ham dosyalar yoksa doğrudan HF'in otomatik parquet dalından
    okunur; betik hem yerelde hem Kaggle'da aynı biçimde çalışır.
    """
    ham = REPO_ROOT / "data" / "raw"
    if (ham / "d8_nli_tr.parquet").exists():
        egitim = pd.read_parquet(ham / "d8_nli_tr.parquet")
        dogrulama = pd.read_parquet(ham / "d8b_nli_tr.parquet")
    else:
        from huggingface_hub import hf_hub_download

        def indir(dosya: str) -> pd.DataFrame:
            return pd.read_parquet(
                hf_hub_download(
                    "boun-tabi/nli_tr", dosya, repo_type="dataset", revision="refs/convert/parquet"
                )
            )

        egitim = indir("snli_tr/train/0000.parquet")
        dogrulama = indir("snli_tr/validation/0000.parquet")

    # Altın etiketi olmayan satırlar (etiketleyiciler uzlaşamamış) elenir.
    egitim = egitim[egitim["label"] != GECERSIZ]
    dogrulama = dogrulama[dogrulama["label"] != GECERSIZ]

    if ayarlar.smoke:
        return egitim.head(256), dogrulama.head(128)
    if ayarlar.ornek and len(egitim) > ayarlar.ornek:
        # Sınıf dengesi korunarak altörnekleme.
        #
        # groupby(...).apply(...) BİLİNÇLİ olarak kullanılmıyor: pandas 3'te
        # apply, gruplama sütununu sonuçtan düşürüyor. Bu sessizce `label`
        # kolonunu yok ediyor ve hata ancak eğitim başlarken, veri indirildikten
        # ve model yüklendikten sonra ortaya çıkıyordu.
        pay = ayarlar.ornek // len(SINIFLAR)
        parcalar = [
            grup.sample(min(len(grup), pay), random_state=ayarlar.tohum)
            for _, grup in egitim.groupby("label")
        ]
        egitim = (
            pd.concat(parcalar).sample(frac=1.0, random_state=ayarlar.tohum).reset_index(drop=True)
        )

    eksik = {"premise", "hypothesis", "label"} - set(egitim.columns)
    if eksik:
        raise ValueError(f"eğitim kümesinde beklenen sütunlar yok: {sorted(eksik)}")
    return egitim, dogrulama


@torch.no_grad()
def degerlendir(model, yukleyici, cihaz: str) -> dict[str, float]:
    model.eval()
    gercekler, tahminler = [], []
    for yigin in yukleyici:
        girdi = {k: yigin[k].to(cihaz) for k in ("input_ids", "attention_mask")}
        tahminler.append(model(**girdi).logits.argmax(-1).cpu().numpy())
        gercekler.append(yigin["labels"].numpy())
    gercek, tahmin = np.concatenate(gercekler), np.concatenate(tahminler)

    sonuc = {"dogruluk": round(float((gercek == tahmin).mean()), 4)}
    for i, ad in enumerate(SINIFLAR):
        pozitif = gercek == i
        if pozitif.any():
            tp = int(((tahmin == i) & pozitif).sum())
            fp = int(((tahmin == i) & ~pozitif).sum())
            kesinlik = tp / (tp + fp) if tp + fp else 0.0
            duyarlilik = tp / int(pozitif.sum())
            f1 = (
                0.0
                if kesinlik + duyarlilik == 0
                else 2 * kesinlik * duyarlilik / (kesinlik + duyarlilik)
            )
            sonuc[f"f1_{ad}"] = round(f1, 4)
    sonuc["makro_f1"] = round(
        float(np.mean([v for k, v in sonuc.items() if k.startswith("f1_")])), 4
    )
    return sonuc


def egit(ayarlar: Ayarlar) -> dict:
    torch.manual_seed(ayarlar.tohum)
    np.random.seed(ayarlar.tohum)
    cihaz = (
        "cuda"
        if torch.cuda.is_available()
        else ("mps" if torch.backends.mps.is_available() else "cpu")
    )
    print(f"cihaz: {cihaz} · omurga: {ayarlar.omurga}")

    egitim, dogrulama = veri_yukle(ayarlar)
    print(f"eğitim: {len(egitim):,} · doğrulama: {len(dogrulama):,}")

    tokenizer = AutoTokenizer.from_pretrained(ayarlar.omurga)
    model = AutoModelForSequenceClassification.from_pretrained(
        ayarlar.omurga,
        num_labels=len(SINIFLAR),
        id2label=dict(enumerate(SINIFLAR)),
        label2id={a: i for i, a in enumerate(SINIFLAR)},
    ).to(cihaz)

    egitim_yukleyici = DataLoader(
        NliVeriKumesi(egitim, tokenizer, ayarlar.maks_uzunluk),
        batch_size=ayarlar.yigin,
        shuffle=True,
    )
    dogrulama_yukleyici = DataLoader(
        NliVeriKumesi(dogrulama, tokenizer, ayarlar.maks_uzunluk), batch_size=ayarlar.yigin
    )

    iyilestirici = torch.optim.AdamW(
        model.parameters(), lr=ayarlar.ogrenme_orani, weight_decay=ayarlar.agirlik_sonumu
    )
    toplam_adim = len(egitim_yukleyici) * ayarlar.epok
    zamanlayici = get_linear_schedule_with_warmup(
        iyilestirici, int(toplam_adim * ayarlar.isinma_orani), toplam_adim
    )
    olcut = nn.CrossEntropyLoss()

    ayarlar.cikti.mkdir(parents=True, exist_ok=True)
    en_iyi, sabirsizlik, gecmis = -1.0, 0, []

    for epok in range(1, ayarlar.epok + 1):
        model.train()
        toplam = 0.0
        for adim, yigin in enumerate(egitim_yukleyici, 1):
            girdi = {k: yigin[k].to(cihaz) for k in ("input_ids", "attention_mask")}
            kayip = olcut(model(**girdi).logits, yigin["labels"].to(cihaz))
            kayip.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            iyilestirici.step()
            zamanlayici.step()
            iyilestirici.zero_grad()
            toplam += kayip.item()
            if adim % 200 == 0:
                print(f"  epok {epok} adım {adim}/{len(egitim_yukleyici)} kayıp {kayip.item():.4f}")

        metrikler = degerlendir(model, dogrulama_yukleyici, cihaz)
        metrikler["epok"] = epok
        metrikler["egitim_kaybi"] = round(toplam / max(len(egitim_yukleyici), 1), 4)
        gecmis.append(metrikler)
        print(f"  → {json.dumps(metrikler, ensure_ascii=False)}")

        if metrikler["dogruluk"] > en_iyi:
            en_iyi, sabirsizlik = metrikler["dogruluk"], 0
            model.save_pretrained(ayarlar.cikti)
            tokenizer.save_pretrained(ayarlar.cikti)
            print(f"  ✓ en iyi kaydedildi (doğruluk {en_iyi:.4f})")
        else:
            sabirsizlik += 1
            if sabirsizlik >= ayarlar.sabir:
                print("  erken durdurma")
                break

    rapor = {
        "omurga": ayarlar.omurga,
        "git_commit": _git_commit(),
        "cihaz": cihaz,
        "egitim_satir": len(egitim),
        "dogrulama_satir": len(dogrulama),
        "en_iyi_dogruluk": round(en_iyi, 4),
        "siniflar": list(SINIFLAR),
        "gecmis": gecmis,
        "hiperparametreler": {
            "epok": ayarlar.epok,
            "yigin": ayarlar.yigin,
            "ogrenme_orani": ayarlar.ogrenme_orani,
            "maks_uzunluk": ayarlar.maks_uzunluk,
            "ornek": ayarlar.ornek,
        },
        "not": (
            "SNLI-TR makine çevirisiyle üretilmiştir ve çeviri gürültüsü taşır. "
            "Alan içi başarım (kriz iddiası ↔ DMM kaydı) ayrıca ölçülmelidir: "
            "scripts/eval/m5_knowledge.py"
        ),
    }
    (ayarlar.cikti / "egitim_raporu.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nÇıktı: {ayarlar.cikti}")
    return rapor


def disa_aktar(kaynak: Path, hedef: Path) -> int:
    """Eğitilmiş modeli int8 ONNX'e çevirir ve çekirdeğin beklediği düzene koyar.

    Çıktı: hedef/{model.onnx, tokenizer.json} — knowledge/nli.py bu adları arar.
    """
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    hedef.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(kaynak)
    model = AutoModelForSequenceClassification.from_pretrained(kaynak).eval()
    tokenizer.backend_tokenizer.save(str(hedef / "tokenizer.json"))

    ornek = tokenizer(
        "örnek öncül", "örnek varsayım", return_tensors="pt", padding="max_length", max_length=256
    )
    ham = hedef / "_model_fp32.onnx"

    class Sinif(nn.Module):
        def __init__(self, govde):
            super().__init__()
            self.govde = govde

        def forward(self, input_ids, attention_mask):
            return self.govde(input_ids=input_ids, attention_mask=attention_mask).logits

    torch.onnx.export(
        Sinif(model).eval(),
        (ornek["input_ids"], ornek["attention_mask"]),
        str(ham),
        input_names=["input_ids", "attention_mask"],
        output_names=["logits"],
        dynamic_axes={
            "input_ids": {0: "yigin", 1: "uzunluk"},
            "attention_mask": {0: "yigin", 1: "uzunluk"},
            "logits": {0: "yigin"},
        },
        opset_version=18,
        # dynamo=False (eski dışa aktarıcı) bilinçli: yeni torch.export tabanlı
        # aktarıcının ürettiği graf, onnxruntime'ın niceleme öncesi şekil
        # çıkarımını düşürüyor ([ShapeInferenceError] 768 vs 3).
        dynamo=False,
    )
    # per_channel: M5 geri getiricide ölçüldü, aynı boyutta belirgin kalite farkı.
    quantize_dynamic(
        str(ham), str(hedef / "model.onnx"), weight_type=QuantType.QInt8, per_channel=True
    )
    # Ara fp32 dosyası 1,1 GB; kalırsa Kaggle çıktısına gereksiz yük biner.
    ham.unlink(missing_ok=True)
    ham.with_suffix(".onnx.data").unlink(missing_ok=True)
    boyut = (hedef / "model.onnx").stat().st_size / 1e6
    print(f"✓ int8 ONNX: {hedef / 'model.onnx'} · {boyut:.0f} MB")
    return 0


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--omurga", default=Ayarlar.omurga)
    a.add_argument("--epok", type=int, default=Ayarlar.epok)
    a.add_argument("--yigin", type=int, default=Ayarlar.yigin)
    a.add_argument("--lr", type=float, default=Ayarlar.ogrenme_orani)
    a.add_argument("--ornek", type=int, default=Ayarlar.ornek)
    a.add_argument("--cikti", type=Path, default=None)
    a.add_argument("--smoke", action="store_true")
    a.add_argument("--disa-aktar", type=Path, default=None, help="eğitilmiş model dizini → ONNX")
    a.add_argument("--onnx-cikti", type=Path, default=None)
    args = a.parse_args()

    if args.disa_aktar:
        return disa_aktar(args.disa_aktar, args.onnx_cikti or (REPO_ROOT / "models" / "m5_nli"))

    ayarlar = Ayarlar(
        omurga=args.omurga,
        epok=args.epok,
        yigin=args.yigin,
        ogrenme_orani=args.lr,
        ornek=args.ornek,
        smoke=args.smoke,
    )
    if args.cikti:
        ayarlar.cikti = args.cikti
    egit(ayarlar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
