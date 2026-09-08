#!/usr/bin/env python
"""Veri kümelerini ortak şemaya uyumlaştırır ve olay bazlı böler.

Rapor 3.2'de taahhüt edilen dört adım burada uygulanır:

    1. Tekilleştirme      — aynı metnin farklı kimliklerle tekrarı temizlenir
    2. Normalizasyon      — URL/kullanıcı adı yer tutucuları, boşluk düzeltmesi
    3. Etiket uyumlaştırma — farklı kaynakların etiketleri projenin şemasına
                             `krizkalkan_core.taxonomy` üzerinden haritalanır
    4. Olay bazlı bölünme — aynı afet olayına ait içerikler tek kümede toplanır

Dördüncü adım kritiktir: rastgele bölünmede aynı olayın neredeyse aynı
metinleri hem eğitimde hem testte yer alır ve metrikler yapay olarak şişer.

Çıktı: data/processed/{train,val,test}.parquet
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.taxonomy import ClaimType  # noqa: E402

HAM = REPO_ROOT / "data" / "raw"
ISLENMIS = REPO_ROOT / "data" / "processed"
ARA = REPO_ROOT / "data" / "interim"


# ─────────────────────────── Etiket haritaları ───────────────────────────

#: HumAID sınıfı → projenin ClaimType şeması.
#: Kaynak etiketler İngilizce kriz taksonomisinden gelir ve bizim yedi
#: iddia tipimizle büyük ölçüde örtüşür; örtüşmeyenler BELIRSIZ'e düşer.
HUMAID_CLAIM: dict[str, ClaimType] = {
    "requests_or_urgent_needs": ClaimType.YARDIM_CAGRISI,
    "missing_or_found_people": ClaimType.YARDIM_CAGRISI,
    "rescue_volunteering_or_donation_effort": ClaimType.YARDIM_CAGRISI,
    "infrastructure_and_utility_damage": ClaimType.ALTYAPI_HASARI,
    "injured_or_dead_people": ClaimType.CAN_KAYBI,
    "displaced_people_and_evacuations": ClaimType.TAHLIYE,
    "caution_and_advice": ClaimType.IKINCIL_AFET_UYARISI,
    "sympathy_and_support": ClaimType.BELIRSIZ,
    "other_relevant_information": ClaimType.BELIRSIZ,
    "not_humanitarian": ClaimType.BELIRSIZ,
}

#: Görev B2 — Kural 0'ı besleyen DAR tanım.
#: Yalnızca doğrudan yardım talebi ve kayıp kişi bildirimi. Bağış/gönüllülük
#: çağrıları buraya girmez; onlar `yardim_ilgili` sütununda tutulur ve eşik
#: analizinde ayrı değerlendirilir.
HELP_CORE = {"requests_or_urgent_needs", "missing_or_found_people"}
HELP_BROAD = HELP_CORE | {"rescue_volunteering_or_donation_effort"}

#: MiDe22 etiketi → Aşama 1 yanlış bilgi etiketi.
MIDE_LABEL = {"True": "dogru", "False": "yanlis", "Other": "diger"}

#: MiDe22'de olay meta verisi yoktur; konu, kümenin bilinen üç temasından
#: anahtar terimlerle çıkarılır. Bu bir yaklaşıklıktır ve olay bazlı bölünmeyi
#: konu bazlı bölünmeye indirger — rastgele bölünmeden yine de üstündür.
MIDE_KONU: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("rusya_ukrayna", ("ukrayna", "rusya", "putin", "zelensky", "zelenski", "savaş")),
    ("covid", ("covid", "korona", "aşı", "asi ", "pandemi", "virüs", "virus")),
    ("multeci", ("mülteci", "multeci", "suriyeli", "göçmen", "gocmen", "sığınmacı")),
)


# ─────────────────────────── Normalizasyon ───────────────────────────

_URL = re.compile(r"https?://\S+|www\.\S+")
_KULLANICI = re.compile(r"@\w+")
_TELEFON = re.compile(r"\b0?\d{3}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}\b")
_UZUN_SAYI = re.compile(r"\b\d{7,}\b")
_BOSLUK = re.compile(r"\s+")


def normalize(metin: str) -> str:
    """Metni eğitime hazır hâle getirir.

    Sayılar bilinçli olarak KORUNUR. Rapor 3.2 "sayı yer tutucuları" der ancak
    büyüklük (7,8) ve saat bilgisi Görev A'nın çıkardığı alanlardır; hepsini
    yer tutucuya çevirmek iddia çıkarımını imkânsız kılar. Yalnızca telefon
    numarası ve uzun kimlik dizileri maskelenir — bunlar hem KVKK açısından
    kişisel veri hem de model için gürültüdür.
    """
    if not isinstance(metin, str):
        return ""
    metin = _URL.sub("<bağlantı>", metin)
    metin = _KULLANICI.sub("<kullanıcı>", metin)
    metin = _TELEFON.sub("<telefon>", metin)
    metin = _UZUN_SAYI.sub("<sayı>", metin)
    # DMM metinleri PDF çıkarımı kaynaklı satır sonları taşır.
    return _BOSLUK.sub(" ", metin).strip()


# ─────────────────────────── Kaynak yükleyiciler ───────────────────────────


def _ortak(
    metinler: list[str],
    kaynak: str,
    dil: str,
    olaylar: list[str],
    **sutunlar: list,
) -> pd.DataFrame:
    """Ortak şemada bir çerçeve kurar."""
    veri = {
        "metin": [normalize(m) for m in metinler],
        "kaynak": kaynak,
        "dil": dil,
        "olay": olaylar,
        "claim_type": sutunlar.get("claim_type", [None] * len(metinler)),
        "yardim_cagrisi": sutunlar.get("yardim_cagrisi", [None] * len(metinler)),
        "yardim_ilgili": sutunlar.get("yardim_ilgili", [None] * len(metinler)),
        "yanlis_bilgi": sutunlar.get("yanlis_bilgi", [None] * len(metinler)),
    }
    return pd.DataFrame(veri)


def yukle_humaid() -> pd.DataFrame:
    """D10 — olay adlarıyla birlikte yüklenir (olay bazlı bölünmenin dayanağı)."""
    from datasets import get_dataset_config_names, load_dataset

    parcalar = []
    for olay in get_dataset_config_names("QCRI/HumAID-events"):
        for bolum in ("train", "dev", "test"):
            try:
                ds = load_dataset(
                    "QCRI/HumAID-events", olay, split=bolum, verification_mode="no_checks"
                )
            except ValueError:
                continue
            etiketler = list(ds["class_label"])
            parcalar.append(
                _ortak(
                    list(ds["tweet_text"]),
                    kaynak="D10",
                    dil="en",
                    olaylar=[olay] * len(ds),
                    claim_type=[HUMAID_CLAIM.get(e, ClaimType.BELIRSIZ).value for e in etiketler],
                    yardim_cagrisi=[int(e in HELP_CORE) for e in etiketler],
                    yardim_ilgili=[int(e in HELP_BROAD) for e in etiketler],
                )
            )
    return pd.concat(parcalar, ignore_index=True)


def _mide_konu(metin: object) -> str:
    """Konuyu anahtar terimlerden çıkarır; metin yoksa 'diğer'."""
    if not isinstance(metin, str):
        return "mide_diger"
    alt = metin.casefold()
    for konu, terimler in MIDE_KONU:
        if any(t in alt for t in terimler):
            return f"mide_{konu}"
    return "mide_diger"


def yukle_mide22() -> pd.DataFrame:
    """D2 — Aşama 1 (alan-genel yanlış bilgi) kaynağı."""
    df = pd.read_parquet(HAM / "d2_turkish-fake-news-detection.parquet")
    # Kaynakta boş satırlar var; metin sütunu tek doğruluk alanı olduğu için
    # eksik olanlar burada, birleştirmeden önce ayıklanır.
    df = df[df["tweet"].notna()].reset_index(drop=True)
    metinler = df["tweet"].tolist()
    return _ortak(
        metinler,
        kaynak="D2",
        dil="tr",
        olaylar=[_mide_konu(m) for m in metinler],
        yanlis_bilgi=[MIDE_LABEL.get(str(e), "diger") for e in df["label"]],
    )


def yukle_dmm() -> pd.DataFrame:
    """D1 — iddia metinleri yanlış bilgi örneği, tekzip metinleri kurumsal dil.

    Bülten numarası olay anahtarı olarak kullanılır: aynı bültendeki iddialar
    aynı döneme aittir ve birbirinin çok yakın varyantı olabilir; bölünmede
    birlikte kalmaları gerekir. Bülten başına gruplama (161 grup), kaba
    kovalamaya göre hedef oranlara çok daha iyi yaklaşır.
    """
    df = pd.read_parquet(HAM / "d1_dezenformasyon-bultenleri.parquet")
    kova = df["bulletin_number"].astype(int)

    iddialar = _ortak(
        df["claim"].tolist(),
        kaynak="D1_iddia",
        dil="tr",
        olaylar=[f"dmm_b{k}" for k in kova],
        yanlis_bilgi=["yanlis"] * len(df),
    )
    tekzipler = _ortak(
        df["fact_check"].tolist(),
        kaynak="D1_tekzip",
        dil="tr",
        olaylar=[f"dmm_b{k}" for k in kova],
        # Tekzip metni iddiayı öne sürmez, düzeltir: yanlış bilgi örneği DEĞİLDİR.
        yanlis_bilgi=["dogru"] * len(df),
    )
    return pd.concat([iddialar, tekzipler], ignore_index=True)


# ─────────────────────────── Bölme ───────────────────────────


#: Aynı olay anahtarlarını paylaşan kaynaklar tek aile sayılır; birlikte bölünürler.
KAYNAK_AILESI = {"D1_iddia": "D1", "D1_tekzip": "D1"}


def _greedy_ata(boyutlar: pd.Series, oranlar: dict[str, float]) -> dict[str, str]:
    """Olayları hedef oranlara göre kümelere dağıtır.

    Olaylar büyükten küçüğe sıralanır ve her biri, hedefine göre en düşük
    doluluğa sahip kümeye verilir. Bir olay yalnızca tek kümeye gider.
    """
    toplam = int(boyutlar.sum())
    hedef = {k: max(toplam * o, 1.0) for k, o in oranlar.items()}
    mevcut = dict.fromkeys(oranlar, 0)
    atama: dict[str, str] = {}
    for olay, boyut in boyutlar.sort_values(ascending=False).items():
        kume = min(mevcut, key=lambda k: mevcut[k] / hedef[k])
        atama[str(olay)] = kume
        mevcut[kume] += int(boyut)
    return atama


def olay_bazli_bol(
    df: pd.DataFrame, *, val_orani: float = 0.15, test_orani: float = 0.15
) -> pd.DataFrame:
    """Olayları kümelere dağıtır — hiçbir olay iki kümede birden bulunmaz.

    Bölme **her kaynak ailesi içinde ayrı ayrı** yapılır. Tek havuzda yapıldığında
    büyük İngilizce küme (D10) bölünmeye hâkim oluyor ve Türkçe kaynakların tamamı
    eğitime düşüyordu; bu durumda projenin asıl metriği olan Türkçe başarım
    ölçülemez hâle gelir. Kaynak içi bölme, hem olay bütünlüğünü hem de her
    kümede her dilin temsilini korur.
    """
    oranlar = {"train": 1 - val_orani - test_orani, "val": val_orani, "test": test_orani}
    df = df.copy()
    df["aile"] = df["kaynak"].map(lambda k: KAYNAK_AILESI.get(k, k))

    atama: dict[tuple[str, str], str] = {}
    for aile, grup in df.groupby("aile"):
        for olay, kume in _greedy_ata(grup.groupby("olay").size(), oranlar).items():
            atama[(str(aile), olay)] = kume

    df["bolum"] = [atama[(a, o)] for a, o in zip(df["aile"], df["olay"], strict=True)]
    return df.drop(columns=["aile"])


def main() -> int:
    print("→ Kaynaklar yükleniyor…")
    parcalar = [yukle_humaid(), yukle_mide22(), yukle_dmm()]
    df = pd.concat(parcalar, ignore_index=True)
    print(f"  ham birleşim: {len(df):,} satır")

    # ── Tekilleştirme ──
    once = len(df)
    df = df[df["metin"].str.len() >= 15]
    df = df.drop_duplicates(subset=["metin"]).reset_index(drop=True)
    print(f"  tekilleştirme + kısa metin ayıklama: {once:,} → {len(df):,}")

    ARA.mkdir(parents=True, exist_ok=True)
    df.to_parquet(ARA / "birlesik_v1.parquet", index=False)

    # ── Olay bazlı bölme ──
    df = olay_bazli_bol(df)
    ISLENMIS.mkdir(parents=True, exist_ok=True)
    for bolum in ("train", "val", "test"):
        alt = df[df["bolum"] == bolum].drop(columns=["bolum"])
        alt.to_parquet(ISLENMIS / f"{bolum}.parquet", index=False)
        print(f"  {bolum:5s}: {len(alt):>7,} satır · {alt['olay'].nunique():>3} olay")

    # ── Sızıntı denetimi ──
    df["_aile"] = df["kaynak"].map(lambda k: KAYNAK_AILESI.get(k, k))
    olay_bolum = df.groupby(["_aile", "olay"])["bolum"].nunique()
    sizinti = olay_bolum[olay_bolum > 1]
    if len(sizinti):
        print(f"  🔴 SIZINTI: {len(sizinti)} olay birden fazla bölümde!")
        return 1
    print("  ✅ Sızıntı denetimi: hiçbir olay birden fazla bölümde değil")

    print("\n═══ Bölüm × kaynak ═══")
    print(
        df.pivot_table(
            index="bolum", columns="kaynak", values="metin", aggfunc="count", fill_value=0
        ).to_string()
    )

    print("\n═══ Sınıf dağılımları ═══")
    print("\nclaim_type:")
    print(df["claim_type"].value_counts().to_string())
    print("\nyardım çağrısı (dar tanım, Kural 0):")
    print(df["yardim_cagrisi"].value_counts(dropna=False).to_string())
    print("\nyanlış bilgi (Aşama 1):")
    print(df["yanlis_bilgi"].value_counts(dropna=False).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
