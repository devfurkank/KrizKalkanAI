#!/usr/bin/env python
"""M3 — Türkçe kriz metin motoru · çok görevli iki aşamalı ince ayar.

Tek gövde, üç başlık (rapor 3.1 · M3):

    Başlık A  claim_type      7 sınıf   → Görev A, iddia tipi
    Başlık B1 yanlis_bilgi    3 sınıf   → alan-genel yanlış bilgi
    Başlık B2 yardim_cagrisi  ikili     → Kural 0'ı besleyen koruma sınıfı

İki aşamalı ince ayar (rapor 3.2). Veri gerçekliği yol haritasındakinden
farklı çıktığı için aşamaların içeriği şöyledir:

    Aşama 1 — kriz alanı (HumAID, İngilizce, 52 bin satır)
              Model kriz söyleminin yapısını ve iddia tiplerini öğrenir.
    Aşama 2 — Türkçe uyarlama (MiDe22 + DMM)
              Model Türkçe kriz diline ve yanlış bilgi etiketlerine uyarlanır.

Türkçe etiketli yardım çağrısı verisi erişilebilir olmadığı için (bkz.
docs/veri-envanteri.md · D3) Başlık B2 çapraz dilli aktarımla öğrenilir:
Aşama 1'de İngilizce örneklerle eğitilir, Aşama 2'de çok dilli gövde
üzerinden Türkçeye taşınır. Bu nedenle omurga çok dilli olmak zorundadır.

Kullanım:

    python scripts/train/m3_text.py --smoke          # yerelde 2 dk doğrulama
    python scripts/train/m3_text.py --asama 1        # Kaggle · aşama 1
    python scripts/train/m3_text.py --asama 2 --devam cikti/asama1
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoConfig, AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.taxonomy import ClaimType  # noqa: E402

# ─────────────────────────── Şema ───────────────────────────

CLAIM_SINIFLARI: tuple[str, ...] = tuple(c.value for c in ClaimType)
YANLIS_SINIFLARI: tuple[str, ...] = ("dogru", "yanlis", "diger")

#: Etiketi olmayan örnekler için kayıp maskesi değeri.
YOK = -100

#: Kaggle'da /kaggle/working, yerelde depo altındaki cikti/ dizini.
VARSAYILAN_CIKTI = (
    Path("/kaggle/working") if Path("/kaggle/working").exists() else REPO_ROOT / "cikti"
)


@dataclass
class Ayarlar:
    omurga: str = "FacebookAI/xlm-roberta-base"
    asama: int = 1
    epok: int = 3
    yigin: int = 32
    ogrenme_orani: float = 3e-5
    maks_uzunluk: int = 128
    isinma_orani: float = 0.06
    agirlik_sonumu: float = 0.01
    #: Kural 0 sınıfı azınlıktadır ve duyarlılığı kritiktir; kaybı ağırlıklanır.
    yardim_kayip_agirligi: float = 3.0
    sabir: int = 2
    tohum: int = 42
    smoke: bool = False
    devam: Path | None = None
    cikti: Path = field(default_factory=lambda: VARSAYILAN_CIKTI / "m3_text")


# ─────────────────────────── Veri ───────────────────────────


class KrizVeriKumesi(Dataset):
    """Çok görevli küme: her örnek yalnızca sahip olduğu etiketlerle katkı verir."""

    def __init__(self, df: pd.DataFrame, tokenizer, maks_uzunluk: int) -> None:
        self.metinler = df["metin"].tolist()
        self.tokenizer = tokenizer
        self.maks_uzunluk = maks_uzunluk

        self.claim = self._kodla(df["claim_type"], CLAIM_SINIFLARI)
        self.yanlis = self._kodla(df["yanlis_bilgi"], YANLIS_SINIFLARI)
        self.yardim = [YOK if pd.isna(v) else int(v) for v in df["yardim_cagrisi"]]

    @staticmethod
    def _kodla(seri: pd.Series, siniflar: tuple[str, ...]) -> list[int]:
        dizin = {s: i for i, s in enumerate(siniflar)}
        return [YOK if pd.isna(v) else dizin.get(str(v), YOK) for v in seri]

    def __len__(self) -> int:
        return len(self.metinler)

    def __getitem__(self, i: int) -> dict[str, torch.Tensor]:
        kodlanmis = self.tokenizer(
            self.metinler[i],
            truncation=True,
            max_length=self.maks_uzunluk,
            padding="max_length",
            return_tensors="pt",
        )
        return {
            "input_ids": kodlanmis["input_ids"].squeeze(0),
            "attention_mask": kodlanmis["attention_mask"].squeeze(0),
            "claim": torch.tensor(self.claim[i]),
            "yanlis": torch.tensor(self.yanlis[i]),
            "yardim": torch.tensor(self.yardim[i]),
        }


# ─────────────────────────── Model ───────────────────────────


class CokGorevliModel(nn.Module):
    """Paylaşılan gövde + üç bağımsız sınıflandırma başlığı.

    Başlıklar bağımsızdır: bir görevin etiketi yoksa o başlığın kaybı
    hesaplanmaz. Bu, farklı kaynakların farklı etiket alt kümeleri taşımasını
    (HumAID'de iddia tipi var, yanlış bilgi yok; MiDe22'de tersi) tek bir
    eğitim koşusunda mümkün kılar.
    """

    def __init__(self, omurga: str, birakma: float = 0.1) -> None:
        super().__init__()
        yapilandirma = AutoConfig.from_pretrained(omurga)
        self.govde = AutoModel.from_pretrained(omurga)
        gizli = yapilandirma.hidden_size
        self.birakma = nn.Dropout(birakma)
        self.bas_claim = nn.Linear(gizli, len(CLAIM_SINIFLARI))
        self.bas_yanlis = nn.Linear(gizli, len(YANLIS_SINIFLARI))
        self.bas_yardim = nn.Linear(gizli, 2)

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> dict:
        cikti = self.govde(input_ids=input_ids, attention_mask=attention_mask)
        # Maskeye duyarlı ortalama havuzlama: dolgu belirteçleri temsile karışmaz.
        maske = attention_mask.unsqueeze(-1).float()
        havuz = (cikti.last_hidden_state * maske).sum(1) / maske.sum(1).clamp(min=1e-9)
        havuz = self.birakma(havuz)
        return {
            "claim": self.bas_claim(havuz),
            "yanlis": self.bas_yanlis(havuz),
            "yardim": self.bas_yardim(havuz),
        }


def kayip_hesapla(ciktilar: dict, yigin: dict, yardim_agirligi: float) -> torch.Tensor:
    """Maskelenmiş çok görevli kayıp — etiketi olmayan başlık katkı vermez."""
    olcut = nn.CrossEntropyLoss(ignore_index=YOK)
    toplam = ciktilar["claim"].new_zeros(())
    for ad, agirlik in (("claim", 1.0), ("yanlis", 1.0), ("yardim", yardim_agirligi)):
        hedef = yigin[ad]
        if (hedef != YOK).any():
            toplam = toplam + agirlik * olcut(ciktilar[ad], hedef)
    return toplam


# ─────────────────────────── Değerlendirme ───────────────────────────


def makro_f1(gercek: np.ndarray, tahmin: np.ndarray, sinif_sayisi: int) -> float:
    """Sınıf başına F1'in ortalaması; kümede hiç görülmeyen sınıf atlanır."""
    skorlar = []
    for c in range(sinif_sayisi):
        tp = int(((tahmin == c) & (gercek == c)).sum())
        fp = int(((tahmin == c) & (gercek != c)).sum())
        fn = int(((tahmin != c) & (gercek == c)).sum())
        if tp + fn == 0:
            continue
        kesinlik = tp / (tp + fp) if tp + fp else 0.0
        duyarlilik = tp / (tp + fn)
        skorlar.append(
            0.0
            if kesinlik + duyarlilik == 0
            else 2 * kesinlik * duyarlilik / (kesinlik + duyarlilik)
        )
    return float(np.mean(skorlar)) if skorlar else 0.0


@torch.no_grad()
def degerlendir(model, yukleyici, cihaz: str) -> dict[str, float]:
    """Üç görev için ayrı metrikler; yardım çağrısında duyarlılık öne çıkar."""
    model.eval()
    biriken: dict[str, list] = {a: [[], []] for a in ("claim", "yanlis", "yardim")}
    for yigin in yukleyici:
        girdi = {k: yigin[k].to(cihaz) for k in ("input_ids", "attention_mask")}
        ciktilar = model(**girdi)
        for ad in biriken:
            hedef = yigin[ad].numpy()
            maske = hedef != YOK
            if maske.any():
                biriken[ad][0].append(hedef[maske])
                biriken[ad][1].append(ciktilar[ad].argmax(-1).cpu().numpy()[maske])

    sonuc: dict[str, float] = {}
    sinif_sayisi = {"claim": len(CLAIM_SINIFLARI), "yanlis": len(YANLIS_SINIFLARI), "yardim": 2}
    for ad, (g, t) in biriken.items():
        if not g:
            continue
        gercek, tahmin = np.concatenate(g), np.concatenate(t)
        sonuc[f"{ad}_makro_f1"] = round(makro_f1(gercek, tahmin, sinif_sayisi[ad]), 4)
        sonuc[f"{ad}_dogruluk"] = round(float((gercek == tahmin).mean()), 4)
        if ad == "yardim":
            pozitif = gercek == 1
            # Kural 0'ın tek anlamlı metriği: yardım çağrılarının kaçını yakaladık.
            sonuc["yardim_duyarlilik"] = round(
                float((tahmin[pozitif] == 1).mean()) if pozitif.any() else 0.0, 4
            )
    return sonuc


# ─────────────────────────── Eğitim ───────────────────────────


def asama_verisi(df: pd.DataFrame, asama: int) -> pd.DataFrame:
    """Aşamaya göre kaynak süzgeci."""
    if asama == 1:
        return df[df["kaynak"] == "D10"]
    return df[df["kaynak"] != "D10"]


def egit(ayarlar: Ayarlar) -> dict:
    torch.manual_seed(ayarlar.tohum)
    np.random.seed(ayarlar.tohum)

    cihaz = (
        "cuda"
        if torch.cuda.is_available()
        else ("mps" if torch.backends.mps.is_available() else "cpu")
    )
    print(f"cihaz: {cihaz} · omurga: {ayarlar.omurga} · aşama: {ayarlar.asama}")

    islenmis = REPO_ROOT / "data" / "processed"
    egitim = asama_verisi(pd.read_parquet(islenmis / "train.parquet"), ayarlar.asama)
    dogrulama = asama_verisi(pd.read_parquet(islenmis / "val.parquet"), ayarlar.asama)

    if ayarlar.smoke:
        egitim, dogrulama = egitim.head(256), dogrulama.head(128)
        ayarlar.epok = 1
    print(f"eğitim: {len(egitim):,} · doğrulama: {len(dogrulama):,}")

    tokenizer = AutoTokenizer.from_pretrained(ayarlar.omurga)
    model = CokGorevliModel(ayarlar.omurga).to(cihaz)
    if ayarlar.devam is not None:
        durum = torch.load(ayarlar.devam / "model.pt", map_location=cihaz)
        model.load_state_dict(durum)
        print(f"aşama {ayarlar.asama - 1} ağırlıkları yüklendi: {ayarlar.devam}")

    egitim_yukleyici = DataLoader(
        KrizVeriKumesi(egitim, tokenizer, ayarlar.maks_uzunluk),
        batch_size=ayarlar.yigin,
        shuffle=True,
        drop_last=False,
    )
    dogrulama_yukleyici = DataLoader(
        KrizVeriKumesi(dogrulama, tokenizer, ayarlar.maks_uzunluk), batch_size=ayarlar.yigin
    )

    iyilestirici = torch.optim.AdamW(
        model.parameters(), lr=ayarlar.ogrenme_orani, weight_decay=ayarlar.agirlik_sonumu
    )
    toplam_adim = len(egitim_yukleyici) * ayarlar.epok
    zamanlayici = get_linear_schedule_with_warmup(
        iyilestirici, int(toplam_adim * ayarlar.isinma_orani), toplam_adim
    )

    ayarlar.cikti.mkdir(parents=True, exist_ok=True)
    en_iyi, sabirsizlik, gecmis = -1.0, 0, []

    for epok in range(1, ayarlar.epok + 1):
        model.train()
        toplam_kayip = 0.0
        for adim, yigin in enumerate(egitim_yukleyici, 1):
            girdi = {k: yigin[k].to(cihaz) for k in ("input_ids", "attention_mask")}
            hedefler = {a: yigin[a].to(cihaz) for a in ("claim", "yanlis", "yardim")}
            kayip = kayip_hesapla(model(**girdi), hedefler, ayarlar.yardim_kayip_agirligi)

            kayip.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            iyilestirici.step()
            zamanlayici.step()
            iyilestirici.zero_grad()

            toplam_kayip += kayip.item()
            if adim % 50 == 0:
                print(f"  epok {epok} adım {adim}/{len(egitim_yukleyici)} kayıp {kayip.item():.4f}")

        metrikler = degerlendir(model, dogrulama_yukleyici, cihaz)
        metrikler["epok"] = epok
        metrikler["egitim_kaybi"] = round(toplam_kayip / max(len(egitim_yukleyici), 1), 4)
        gecmis.append(metrikler)
        print(f"  → {json.dumps(metrikler, ensure_ascii=False)}")

        # Seçim ölçütü aşamaya göre değişir: 1. aşamada iddia tipi ve yardım
        # çağrısı, 2. aşamada Türkçe yanlış bilgi başlığı belirleyicidir.
        olcut = (
            metrikler.get("claim_makro_f1", 0) + metrikler.get("yardim_duyarlilik", 0)
            if ayarlar.asama == 1
            else metrikler.get("yanlis_makro_f1", 0)
        )
        if olcut > en_iyi:
            en_iyi, sabirsizlik = olcut, 0
            torch.save(model.state_dict(), ayarlar.cikti / "model.pt")
            tokenizer.save_pretrained(ayarlar.cikti)
            print(f"  ✓ en iyi kaydedildi (ölçüt {olcut:.4f})")
        else:
            sabirsizlik += 1
            if sabirsizlik >= ayarlar.sabir:
                print(f"  erken durdurma (sabır {ayarlar.sabir})")
                break

    rapor = {
        "asama": ayarlar.asama,
        "omurga": ayarlar.omurga,
        "cihaz": cihaz,
        "egitim_satir": len(egitim),
        "dogrulama_satir": len(dogrulama),
        "en_iyi_olcut": round(en_iyi, 4),
        "gecmis": gecmis,
        "hiperparametreler": {
            "epok": ayarlar.epok,
            "yigin": ayarlar.yigin,
            "ogrenme_orani": ayarlar.ogrenme_orani,
            "maks_uzunluk": ayarlar.maks_uzunluk,
            "yardim_kayip_agirligi": ayarlar.yardim_kayip_agirligi,
        },
    }
    (ayarlar.cikti / "egitim_raporu.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nÇıktı: {ayarlar.cikti}")
    return rapor


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--asama", type=int, default=1, choices=(1, 2))
    a.add_argument("--omurga", default=Ayarlar.omurga)
    a.add_argument("--epok", type=int, default=Ayarlar.epok)
    a.add_argument("--yigin", type=int, default=Ayarlar.yigin)
    a.add_argument("--lr", type=float, default=Ayarlar.ogrenme_orani)
    a.add_argument("--devam", type=Path, default=None, help="önceki aşamanın çıktı dizini")
    a.add_argument("--cikti", type=Path, default=None)
    a.add_argument("--smoke", action="store_true", help="küçük altkümeyle hızlı doğrulama")
    args = a.parse_args()

    ayarlar = Ayarlar(
        omurga=args.omurga,
        asama=args.asama,
        epok=args.epok,
        yigin=args.yigin,
        ogrenme_orani=args.lr,
        devam=args.devam,
        smoke=args.smoke,
    )
    if args.cikti:
        ayarlar.cikti = args.cikti
    egit(ayarlar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
