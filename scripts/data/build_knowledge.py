#!/usr/bin/env python
"""M5 bilgi havuzunu inşa eder: DMM parquet → JSONL + anahtar/çapa terimler.

Neden ara biçim? Çekirdek kütüphane (`krizkalkan_core`) pandas/pyarrow'a
bağlanmamalıdır — demo makinesinde ağır bağımlılık olmadan da çalışabilmesi
gerekir. Bu betik ağır işi bir kez yapar, çekirdek yalnızca stdlib `json` ile
okur.

Anahtar terim ve çapa üretimi elle değil, **ters belge sıklığından** (IDF)
türetilir: bir kaydın çapası, o kaydı korpustaki diğerlerinden ayıran en nadir
terimlerdir. Çapa mekanizması olmadan "yıkıldı" gibi genel bir terim, baraj
tekzibini bina çökmesi haberine iliştirir.

Çıktı: models/m5_knowledge/kayitlar.jsonl
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.text.lexicon import normalize  # noqa: E402

HAM = REPO_ROOT / "data" / "raw" / "d1_dezenformasyon-bultenleri.parquet"
CIKTI = REPO_ROOT / "models" / "m5_knowledge"

#: Ayırt ediciliği olmayan yüksek frekanslı terimler.
DURAK = {
    "bir",
    "bu",
    "su",
    "ve",
    "ile",
    "icin",
    "gibi",
    "daha",
    "cok",
    "var",
    "yok",
    "olarak",
    "sonra",
    "once",
    "kadar",
    "ama",
    "ancak",
    "de",
    "da",
    "ki",
    "mi",
    "iddia",
    "iddiasi",
    "iddialari",
    "gercek",
    "disidir",
    "dogru",
    "degildir",
    "oldugu",
    "olan",
    "edilmistir",
    "edildigi",
    "yapilan",
    "uzere",
    "tarafindan",
    "bulunan",
    "eden",
    "ise",
    "her",
    "tum",
    "bazi",
    "kendi",
    "soz",
    "konu",
    "konusu",
    "ilgili",
    "yer",
    "alan",
    "gore",
    "buyuk",
    "yeni",
}

_KELIME = re.compile(r"[a-z0-9]+")

# ── PDF çıkarımı kaynaklı kirlilik ──
# Kaynak veri bülten PDF'lerinden çıkarılmıştır ve kayıtların bir kısmı iddia
# değil, bültenin kapak/içindekiler sayfasıdır: birden çok iddia başlığını art
# arda taşır ve fact_check alanı bunların hiçbirine karşılık gelmez. Bu kayıtlar
# havuza girerse tek bir tekzip, alakasız onlarca iddiayla eşleşir.
_IDDIA_BASLIGI = re.compile(r'["\u201d]\s*İddias[ıi]')
_KAPAK = re.compile(r"Dezenformasyon\s*\n?\s*Bülteni")
#: PDF madde imi artefaktı.
_ARTEFAKT = "˿"


def kirli_mi(claim: str) -> bool:
    """Kayıt bülten kapağı/içindekiler sayfası mı?"""
    return (
        len(_IDDIA_BASLIGI.findall(claim)) >= 2
        or claim.count(_ARTEFAKT) > 2
        or bool(_KAPAK.search(claim))
    )


def temizle(metin: str) -> str:
    """PDF artefaktlarını atar, satır sonlarını tek boşluğa indirir."""
    return " ".join(str(metin).replace(_ARTEFAKT, " ").split())


#: Bir kayıt için tutulacak anahtar terim ve çapa sayısı.
ANAHTAR_SAYISI = 8
CAPA_SAYISI = 3
#: Çapa olabilmek için terimin en fazla bu oranda belgede geçmesi gerekir.
CAPA_MAKS_BELGE_ORANI = 0.02


def terimler(metin: str) -> list[str]:
    """Normalize edilmiş metinden anlamlı terimleri çıkarır."""
    return [k for k in _KELIME.findall(normalize(metin)) if len(k) > 3 and k not in DURAK]


def main() -> int:
    if not HAM.exists():
        print(f"🔴 {HAM} yok. Önce: python scripts/data/fetch_text.py")
        return 1

    df = pd.read_parquet(HAM)
    ham_sayi = len(df)
    print(f"→ {ham_sayi:,} DMM kaydı okundu")

    df = df[~df["claim"].map(kirli_mi)].reset_index(drop=True)
    print(f"  kapak/içindekiler sayfası ayıklandı: {ham_sayi - len(df)} kayıt")

    belgeler = [terimler(f"{r.claim} {r.fact_check}") for r in df.itertuples()]
    belge_sayisi = len(belgeler)

    # ── IDF ──
    gecen = Counter()
    for b in belgeler:
        gecen.update(set(b))
    idf = {t: math.log(belge_sayisi / (1 + n)) for t, n in gecen.items()}

    kayitlar = []
    for satir, terim_listesi in zip(df.itertuples(), belgeler, strict=True):
        if not terim_listesi:
            continue
        sirali = sorted(set(terim_listesi), key=lambda t: -idf[t])
        anahtarlar = sirali[:ANAHTAR_SAYISI]
        # Çapa yalnızca gerçekten nadir terimlerden seçilir; korpusun %2'sinden
        # fazlasında geçen bir terim ayırt edici sayılmaz.
        capalar = [t for t in sirali if gecen[t] <= belge_sayisi * CAPA_MAKS_BELGE_ORANI][
            :CAPA_SAYISI
        ]
        if not capalar:
            # Çapasız kayıt eşleşemez; bu bilinçli bir güvenlik tercihidir.
            continue

        kayitlar.append(
            {
                "record_id": f"DMM-B{int(satir.bulletin_number)}-{satir.id}",
                "claim": temizle(satir.claim),
                "fact_check": temizle(satir.fact_check),
                # Kaynakta tek değer var ('Yanlış'); yine de veriden okunur,
                # sabit yazılmaz — kaynak zenginleşirse kod değişmesin.
                "rating_label": str(satir.rating_label),
                # Kaynağın date_published alanı derleme tarihidir, bülten tarihi
                # değildir; yanıltıcı olmaması için bülten numarası gösterilir.
                "date_published": f"Bülten {int(satir.bulletin_number)}",
                "source": "İletişim Başkanlığı DMM",
                "keywords": anahtarlar,
                "anchors": capalar,
                "claim_url": str(satir.claim_url),
            }
        )

    CIKTI.mkdir(parents=True, exist_ok=True)
    hedef = CIKTI / "kayitlar.jsonl"
    with hedef.open("w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")

    print(f"✓ {len(kayitlar):,} kayıt yazıldı → {hedef.relative_to(REPO_ROOT)}")
    print(f"  çapasız olduğu için atlanan: {len(df) - len(kayitlar)}")
    print(f"  toplam eleme: {ham_sayi} → {len(kayitlar)}")
    print(f"  örnek çapa: {kayitlar[0]['anchors']} · {kayitlar[0]['claim'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
