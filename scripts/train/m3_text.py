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

#: Kural 0'ın duyarlılık hedefi (rapor 3.2). Bu sınıfta argmax (0,5 eşiği)
#: kullanılmaz: pozitifler verinin %3'ü olduğu için model çoğunlukla "hayır"
#: diyerek yüksek doğruluk alır ama yardım çağrılarının yarısını kaçırır.
#: Eşik, hedef duyarlılığı tutturacak biçimde doğrulama kümesinde aranır.
HEDEF_YARDIM_DUYARLILIK = 0.98

#: Kural 0'ın kabul edilebilir azami yanlış pozitif oranı.
#:
#: Bu sınır olmadan hedef duyarlılık anlamsızdır: her içeriği yardım çağrısı
#: sayan bir model de 1,00 duyarlılık verir. Kural 0 tetiklendiğinde sistem
#: HİÇBİR müdahale uygulamadığı için, yüksek yanlış pozitif doğrudan sistemin
#: kapsamını yok eder — FPR 1,0 demek hiçbir içeriğin asla etiketlenmemesi
#: demektir.
AZAMI_YARDIM_FPR = 0.20

#: Çalışma noktası eğrisinde taranan duyarlılık hedefleri.
DUYARLILIK_NOKTALARI = (0.80, 0.85, 0.90, 0.95, 0.98, 0.99)

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
    yardim_kayip_agirligi: float = 8.0
    #: 2. aşamada karıştırılacak 1. aşama örneği oranı (unutmayı engeller).
    replay: float = 1.0
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


def _nokta(olasiliklar: np.ndarray, pozitif: np.ndarray, esik: float) -> dict[str, float]:
    """Bir eşikteki duyarlılık, kesinlik ve yanlış pozitif oranı."""
    tahmin = olasiliklar >= esik
    tp = int((tahmin & pozitif).sum())
    fp = int((tahmin & ~pozitif).sum())
    negatif = max(int((~pozitif).sum()), 1)
    return {
        "esik": round(float(esik), 6),
        "duyarlilik": round(float(tahmin[pozitif].mean()), 4),
        "kesinlik": round(tp / (tp + fp), 4) if tp + fp else 0.0,
        "yanlis_pozitif_orani": round(fp / negatif, 4),
    }


def calisma_noktalari(olasiliklar: np.ndarray, gercek: np.ndarray) -> list[dict[str, float]]:
    """Duyarlılık hedefi → o hedefi tutturan en yüksek eşiğin maliyeti.

    Tek bir eşik yerine eğri raporlanır: hangi duyarlılığın neye mal olduğu
    görünmeden çalışma noktası seçilemez. Bu eğri rapora doğrudan girer.
    """
    pozitif = gercek == 1
    if not pozitif.any():
        return []

    adaylar = np.unique(np.round(olasiliklar, 6))
    noktalar = []
    for hedef in DUYARLILIK_NOKTALARI:
        uygun = [e for e in adaylar if float((olasiliklar >= e)[pozitif].mean()) >= hedef]
        if not uygun:
            continue
        nokta = _nokta(olasiliklar, pozitif, max(uygun))
        nokta["hedef_duyarlilik"] = hedef
        noktalar.append(nokta)
    return noktalar


def yardim_esigi(olasiliklar: np.ndarray, gercek: np.ndarray) -> dict[str, float]:
    """Kural 0 için kullanılabilir çalışma noktasını seçer.

    İki kısıt BİRLİKTE uygulanır: duyarlılık hedefi ve azami yanlış pozitif
    oranı. Yalnızca duyarlılığa bakmak dejenere çözümü ödüllendirir — her
    içeriği yardım çağrısı sayan model 1,00 duyarlılık verir, ama Kural 0
    tetiklendiğinde sistem hiçbir müdahale uygulamadığı için bu, hiçbir
    içeriğin asla etiketlenmemesi demektir. Sistem kendini kapatır.

    Hedef duyarlılık FPR sınırı içinde tutturulamıyorsa, sınırı aşmayan EN
    YÜKSEK duyarlılık seçilir ve hedefin tutmadığı açıkça işaretlenir.
    """
    pozitif = gercek == 1
    if not pozitif.any():
        return {}

    adaylar = np.unique(np.round(olasiliklar, 6))
    kabul = [
        n
        for n in (_nokta(olasiliklar, pozitif, e) for e in adaylar)
        if n["yanlis_pozitif_orani"] <= AZAMI_YARDIM_FPR
    ]
    if not kabul:
        return {"yardim_kullanilabilir_nokta_yok": 1.0}

    en_iyi = max(kabul, key=lambda n: n["duyarlilik"])
    return {
        "yardim_esik": en_iyi["esik"],
        "yardim_duyarlilik_esikli": en_iyi["duyarlilik"],
        "yardim_kesinlik_esikli": en_iyi["kesinlik"],
        "yardim_yanlis_pozitif_orani": en_iyi["yanlis_pozitif_orani"],
        "yardim_hedef_tutmadi": float(en_iyi["duyarlilik"] < HEDEF_YARDIM_DUYARLILIK),
    }


@torch.no_grad()
def degerlendir(model, yukleyici, cihaz: str) -> dict[str, float]:
    """Üç görev için ayrı metrikler; yardım çağrısında duyarlılık öne çıkar.

    Yardım çağrısı başlığı iki kez raporlanır: argmax ile (karşılaştırma için)
    ve duyarlılık hedefini tutturan eşikle. Üretimde ikincisi kullanılır.
    """
    model.eval()
    biriken: dict[str, list] = {a: [[], []] for a in ("claim", "yanlis", "yardim")}
    yardim_olasilik: list[np.ndarray] = []

    for yigin in yukleyici:
        girdi = {k: yigin[k].to(cihaz) for k in ("input_ids", "attention_mask")}
        ciktilar = model(**girdi)
        for ad in biriken:
            hedef = yigin[ad].numpy()
            maske = hedef != YOK
            if maske.any():
                biriken[ad][0].append(hedef[maske])
                biriken[ad][1].append(ciktilar[ad].argmax(-1).cpu().numpy()[maske])
                if ad == "yardim":
                    olasilik = torch.softmax(ciktilar[ad], dim=-1)[:, 1].cpu().numpy()
                    yardim_olasilik.append(olasilik[maske])

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
            sonuc["yardim_duyarlilik_argmax"] = round(
                float((tahmin[pozitif] == 1).mean()) if pozitif.any() else 0.0, 4
            )
            olasilik = np.concatenate(yardim_olasilik)
            sonuc.update(yardim_esigi(olasilik, gercek))
            sonuc["yardim_egri"] = calisma_noktalari(olasilik, gercek)  # type: ignore[assignment]
    return sonuc


# ─────────────────────────── Eğitim ───────────────────────────


def asama_verisi(
    df: pd.DataFrame, asama: int, replay_orani: float = 0.0, tohum: int = 42
) -> pd.DataFrame:
    """Aşamaya göre kaynak süzgeci; 2. aşamada tekrar (replay) karışımı.

    Neden tekrar gerekli: 2. aşamanın Türkçe verisinde `claim_type` ve
    `yardim_cagrisi` etiketi yoktur. O başlıklar eğitim sinyali almazken
    paylaşılan gövde güncellenir ve 1. aşamada öğrenilen — özellikle Kural 0'ı
    besleyen — bilgi silinebilir. 1. aşamadan bir örneklem karıştırmak bu
    unutmayı engeller; karışım aynı zamanda 2. aşama değerlendirmesinde o
    başlıkların GÖRÜNÜR kalmasını sağlar.
    """
    asama1 = df[df["kaynak"] == "D10"]
    if asama == 1:
        return asama1

    asama2 = df[df["kaynak"] != "D10"]
    if replay_orani <= 0:
        return asama2

    adet = min(int(len(asama2) * replay_orani), len(asama1))
    tekrar = asama1.sample(adet, random_state=tohum)
    return (
        pd.concat([asama2, tekrar], ignore_index=True)
        .sample(frac=1.0, random_state=tohum)
        .reset_index(drop=True)
    )


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
    egitim = asama_verisi(
        pd.read_parquet(islenmis / "train.parquet"),
        ayarlar.asama,
        ayarlar.replay,
        ayarlar.tohum,
    )
    # Doğrulamada tekrar oranı sabittir: 2. aşamada 1. aşamanın başlıkları
    # ölçülemezse unutma fark edilmez.
    dogrulama = asama_verisi(
        pd.read_parquet(islenmis / "val.parquet"),
        ayarlar.asama,
        1.0 if ayarlar.asama == 2 else 0.0,
        ayarlar.tohum,
    )

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
        egri = metrikler.pop("yardim_egri", None)
        print(f"  → {json.dumps(metrikler, ensure_ascii=False)}")
        if egri:
            print("     Kural 0 çalışma noktaları (duyarlılık → maliyet):")
            for n in egri:
                print(
                    f"       hedef {n['hedef_duyarlilik']:.2f} → duyarlılık "
                    f"{n['duyarlilik']:.4f} · kesinlik {n['kesinlik']:.4f} · "
                    f"yanlış pozitif {n['yanlis_pozitif_orani']:.4f}"
                )
            metrikler["yardim_egri"] = egri

        # Seçim ölçütü aşamaya göre değişir. 2. aşamada Türkçe başarım tek başına
        # yeterli değildir: yardım çağrısı başlığını unutmuş bir kontrol noktası
        # seçilmemelidir, bu yüzden ölçüte eşikli duyarlılık de girer.
        if ayarlar.asama == 1:
            olcut = metrikler.get("claim_makro_f1", 0) + metrikler.get(
                "yardim_duyarlilik_esikli", 0
            )
        else:
            olcut = metrikler.get("yanlis_makro_f1", 0) + metrikler.get(
                "yardim_duyarlilik_esikli", 0
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
            "replay": ayarlar.replay,
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
    a.add_argument(
        "--replay",
        type=float,
        default=Ayarlar.replay,
        help="2. aşamaya karıştırılacak 1. aşama örneği oranı (0 = kapalı)",
    )
    a.add_argument(
        "--yardim-agirlik",
        type=float,
        default=Ayarlar.yardim_kayip_agirligi,
        help="Kural 0 başlığının kayıp ağırlığı",
    )
    args = a.parse_args()

    ayarlar = Ayarlar(
        omurga=args.omurga,
        asama=args.asama,
        epok=args.epok,
        yigin=args.yigin,
        ogrenme_orani=args.lr,
        devam=args.devam,
        smoke=args.smoke,
        replay=args.replay,
        yardim_kayip_agirligi=args.yardim_agirlik,
    )
    if args.cikti:
        ayarlar.cikti = args.cikti
    egit(ayarlar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
