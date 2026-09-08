#!/usr/bin/env python
"""Metin veri kümelerini indirir, doğrular ve envanter üretir.

Kullanım:

    python scripts/data/fetch_text.py            # indir + doğrula + envanter yaz
    python scripts/data/fetch_text.py --kontrol  # indirme, yalnızca erişimi sına

Betiğin asıl işi indirmek değil **doğrulamak**: her kümenin satır sayısı,
sütunları ve dağıtım biçimi beklenenle karşılaştırılır. Bir küme sessizce
değiştiğinde (kaynak güncellemesi, şema değişikliği) bunu eğitim sırasında
değil, burada öğreniriz.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import kumeler

REPO_ROOT = Path(__file__).resolve().parents[2]
HAM_DIZIN = REPO_ROOT / "data" / "raw"
ENVANTER = REPO_ROOT / "docs" / "veri-envanteri.md"


@dataclass(slots=True)
class Sonuc:
    kume: kumeler.VeriKumesi
    basarili: bool
    satir: int | None = None
    sutunlar: tuple[str, ...] = ()
    yol: Path | None = None
    hata: str | None = None
    uyusmazlik: list[str] | None = None


def _yukle(kume: kumeler.VeriKumesi):
    """Kümeyi indirir ve bir pandas DataFrame döndürür."""
    import pandas as pd

    if kume.split is not None:
        from datasets import load_dataset

        ds = load_dataset(kume.repo, split=kume.split, verification_mode="no_checks")
        return ds.to_pandas()

    from huggingface_hub import hf_hub_download

    yol = hf_hub_download(
        repo_id=kume.repo,
        filename=kume.dosya,
        repo_type=kume.repo_tipi,
        revision=kume.revision,
    )
    if kume.dosya.endswith(".parquet"):
        return pd.read_parquet(yol)
    if kume.dosya.endswith(".tsv"):
        return pd.read_csv(yol, sep="\t")
    return pd.read_csv(yol)


def indir(kume: kumeler.VeriKumesi, *, kaydet: bool = True) -> Sonuc:
    """Tek bir kümeyi indirir ve beklenen şemayla karşılaştırır."""
    if kume.durum is kumeler.Durum.KULLANILAMAZ:
        return Sonuc(kume=kume, basarili=False, hata="kullanılamaz olarak işaretli — atlandı")

    try:
        df = _yukle(kume)
    # Envanter raporu hatayı yutmamalı, yazmalı: erişilemeyen küme de bir bulgudur.
    except Exception as exc:
        return Sonuc(kume=kume, basarili=False, hata=f"{type(exc).__name__}: {exc}")

    uyusmazlik: list[str] = []
    if kume.beklenen_satir is not None and len(df) != kume.beklenen_satir:
        uyusmazlik.append(f"satır sayısı {len(df):,} (beklenen {kume.beklenen_satir:,})")
    eksik = [s for s in kume.beklenen_sutunlar if s not in df.columns]
    if eksik:
        uyusmazlik.append(f"eksik sütun: {', '.join(eksik)}")

    yol = None
    if kaydet:
        HAM_DIZIN.mkdir(parents=True, exist_ok=True)
        yol = HAM_DIZIN / f"{kume.kod.lower()}_{kume.repo.split('/')[-1]}.parquet"
        df.to_parquet(yol, index=False)

    return Sonuc(
        kume=kume,
        basarili=True,
        satir=len(df),
        sutunlar=tuple(df.columns),
        yol=yol,
        uyusmazlik=uyusmazlik or None,
    )


def envanter_yaz(sonuclar: list[Sonuc]) -> Path:
    """docs/veri-envanteri.md dosyasını üretir."""
    simdi = datetime.now(UTC).strftime("%d.%m.%Y %H:%M UTC")
    satirlar = [
        "# Veri Envanteri",
        "",
        f"*Bu dosya `scripts/data/fetch_text.py` tarafından üretilmiştir. Son güncelleme: {simdi}*",
        "",
        "Her kümenin **dağıtım biçimi** kullanılabilirliği belirleyen alandır: yalnızca",
        "tweet kimliği dağıtan kümeler X API hidrasyonu gerektirir ve pratikte",
        "kullanılamaz (ücretli erişim + silinmiş içerik kaybı).",
        "",
        "## Özet",
        "",
        "| Kod | Küme | Lisans | Biçim | Satır | Durum | Modül |",
        "|---|---|---|---|---|---|---|",
    ]
    for s in sonuclar:
        k = s.kume
        satir = f"{s.satir:,}" if s.satir else "—"
        isaret = {
            kumeler.Durum.KULLANILIYOR: "✅",
            kumeler.Durum.DEGERLENDIRME: "⚠️",
            kumeler.Durum.KULLANILAMAZ: "🔴",
        }[k.durum]
        satirlar.append(
            f"| **{k.kod}** | {k.ad} | {k.lisans} | {k.bicim.value} | {satir} | "
            f"{isaret} {k.durum.value} | {', '.join(k.moduller)} |"
        )

    satirlar += ["", "## Ayrıntılar", ""]
    for s in sonuclar:
        k = s.kume
        satirlar += [f"### {k.kod} — {k.ad}", "", f"- **Kaynak:** `{k.repo}`"]
        if k.dosya:
            satirlar.append(f"- **Dosya:** `{k.dosya}`")
        satirlar += [
            f"- **Lisans:** {k.lisans}",
            f"- **Dağıtım biçimi:** {k.bicim.value}",
            f"- **Hedef modül:** {', '.join(k.moduller)}",
        ]
        if s.basarili:
            satirlar += [
                f"- **Doğrulama:** ✅ {s.satir:,} satır · sütunlar: "
                f"{', '.join(f'`{c}`' for c in s.sutunlar)}"
            ]
            if s.uyusmazlik:
                satirlar.append(f"- **⚠️ Beklenenden sapma:** {'; '.join(s.uyusmazlik)}")
        else:
            satirlar.append(f"- **Doğrulama:** 🔴 {s.hata}")
        if k.not_:
            satirlar += ["", k.not_]
        if k.uyarilar:
            satirlar += ["", "**Uyarılar:**", ""]
            satirlar += [f"- {u}" for u in k.uyarilar]
        satirlar += [""]

    ENVANTER.parent.mkdir(parents=True, exist_ok=True)
    ENVANTER.write_text("\n".join(satirlar), encoding="utf-8")
    return ENVANTER


def main() -> int:
    ayrıştırıcı = argparse.ArgumentParser(description=__doc__)
    ayrıştırıcı.add_argument(
        "--kontrol", action="store_true", help="indirme, yalnızca erişimi sına"
    )
    args = ayrıştırıcı.parse_args()

    sonuclar: list[Sonuc] = []
    for k in kumeler.KUMELER:
        print(f"→ {k.kod} {k.ad} … ", end="", flush=True)
        s = indir(k, kaydet=not args.kontrol)
        sonuclar.append(s)
        if s.basarili:
            ek = f"  ⚠️ {'; '.join(s.uyusmazlik)}" if s.uyusmazlik else ""
            print(f"✅ {s.satir:,} satır{ek}")
        else:
            print(f"🔴 {s.hata}")

    yol = envanter_yaz(sonuclar)
    basarili = sum(1 for s in sonuclar if s.basarili)
    print(f"\nEnvanter yazıldı: {yol.relative_to(REPO_ROOT)}")
    print(f"Kullanılabilir küme: {basarili}/{len(sonuclar)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
