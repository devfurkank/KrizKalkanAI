#!/usr/bin/env python
"""M5 geri getirme indeksini inşa eder: e5 → int8 ONNX → gömme → indeks.

Çıktı: models/m5_retriever/{kodlayici.onnx, gomme.npy, kayit_kimlikleri.json,
       tokenizer.json}

Akış dört adımdır ve her adım **ayrı süreçte** çalışır. Bunun nedeni macOS'ta
torch, onnxruntime ve faiss'in her birinin kendi libomp'unu getirmesi ve aynı
süreçte OpenMP çalışma zamanının çakışıp süreci düşürmesidir:

    1. (torch)  fp32 ONNX dışa aktarımı + tokenizer + doğrulama referansı
    2. (ort)    int8 dinamik niceleme            → 1110 MB'tan 278 MB'a
    3. (ort)    havuzun int8 kodlayıcıyla gömülmesi
    4. (ort)    doğrulama: kosinüs örtüşmesi + sıralama tutarlılığı

Üçüncü adım kritik: gömmeler **çıkarımda kullanılacak kodlayıcının aynısıyla**
üretilmelidir. İndeks torch ile, sorgu ONNX ile gömülürse aradaki niceleme
kayması iki uzayı birbirinden ayırır ve geri getirme sessizce bozulur.

Kullanım:
    python scripts/data/build_index.py              # tam akış
    python scripts/data/build_index.py --gom        # yalnızca yeniden gömme
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.knowledge import corpus  # noqa: E402
from krizkalkan_core.knowledge.retriever import KAYIT_ONEKI  # noqa: E402

OMURGA = "intfloat/multilingual-e5-base"
CIKTI = REPO_ROOT / "models" / "m5_retriever"
MAKS_UZUNLUK = 192

HAM_ONNX = CIKTI / "_kodlayici_fp32.onnx"
INT8_ONNX = CIKTI / "kodlayici.onnx"
REFERANS = CIKTI / "_dogrulama_referansi.npy"
REFERANS_METIN = CIKTI / "_dogrulama_metinleri.json"

#: Nicelenmiş gömme, fp32 referansla en az bu kosinüs benzerliğini tutmalıdır.
#: Ölçüt bileşen bazlı sapma değil kosinüstür: geri getirmeyi belirleyen tek
#: büyüklük vektörler arasındaki açıdır.
KOSINUS_ESIGI = 0.99
#: Doğrulama sorgularında ilk 5 sonucun fp32 ile örtüşme oranı alt sınırı.
SIRALAMA_ESIGI = 0.80


def _boyut(yol: Path) -> float:
    toplam = yol.stat().st_size
    harici = yol.with_suffix(yol.suffix + ".data")
    if harici.exists():
        toplam += harici.stat().st_size
    return toplam / 1e6


def _kayit_metinleri() -> tuple[list[str], list[str]]:
    """Havuzun gömülecek metinleri ve kayıt kimlikleri.

    İddia ve tekzip birlikte gömülür: yalnızca iddia gömüldüğünde, düzeltme
    metnini paylaşan kullanıcıların içeriği hiçbir kayıtla eşleşmiyor.
    """
    kayitlar = corpus.records()
    return [f"{k.claim} {k.fact_check}" for k in kayitlar], [k.record_id for k in kayitlar]


# ───────────────────────── 1 · dışa aktarım (torch) ─────────────────────────


def disa_aktar() -> int:
    import torch
    from transformers import AutoModel, AutoTokenizer

    print(f"→ {OMURGA} yükleniyor…")
    tokenizer = AutoTokenizer.from_pretrained(OMURGA)
    model = AutoModel.from_pretrained(OMURGA).eval()

    CIKTI.mkdir(parents=True, exist_ok=True)
    tokenizer.backend_tokenizer.save(str(CIKTI / "tokenizer.json"))

    class Kodlayici(torch.nn.Module):
        """Son gizli katmanı döndürür; havuzlama çıkarım tarafında yapılır."""

        def __init__(self, govde):
            super().__init__()
            self.govde = govde

        def forward(self, input_ids, attention_mask):
            return self.govde(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state

    ornek = tokenizer(
        ["örnek metin"], return_tensors="pt", padding="max_length", max_length=MAKS_UZUNLUK
    )
    print("→ fp32 ONNX dışa aktarımı…")
    torch.onnx.export(
        Kodlayici(model).eval(),
        (ornek["input_ids"], ornek["attention_mask"]),
        str(HAM_ONNX),
        input_names=["input_ids", "attention_mask"],
        output_names=["last_hidden_state"],
        dynamic_axes={
            "input_ids": {0: "yigin", 1: "uzunluk"},
            "attention_mask": {0: "yigin", 1: "uzunluk"},
            "last_hidden_state": {0: "yigin", 1: "uzunluk"},
        },
        opset_version=18,
    )
    print(f"  ✓ fp32: {_boyut(HAM_ONNX):.0f} MB")

    # Doğrulama referansı: nicelemenin kaliteyi ne kadar bozduğunu ölçmek için
    # torch tarafından üretilmiş "altın" gömmeler.
    with torch.no_grad():
        metinler, _ = _kayit_metinleri()
        ornekler = metinler[:64]
        kodlanmis = tokenizer(
            [KAYIT_ONEKI + m for m in ornekler],
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=MAKS_UZUNLUK,
        )
        cikti = model(**kodlanmis).last_hidden_state
        maske = kodlanmis["attention_mask"].unsqueeze(-1).float()
        havuz = (cikti * maske).sum(1) / maske.sum(1).clamp(min=1e-9)
        np.save(REFERANS, torch.nn.functional.normalize(havuz, p=2, dim=1).numpy())
    REFERANS_METIN.write_text(json.dumps(ornekler, ensure_ascii=False), encoding="utf-8")
    return 0


# ───────────────────────── 2 · niceleme (ort) ─────────────────────────


def nicele() -> int:
    from onnxruntime.quantization import QuantType, quantize_dynamic

    if not HAM_ONNX.exists():
        print(f"🔴 {HAM_ONNX} yok — önce dışa aktarım gerekiyor")
        return 1
    # per_channel=True bedava kazanç: aynı dosya boyutunda kosinüs örtüşmesini
    # 0,978'den 0,991'e çıkarır. (reduce_range=True denendi, kaliteyi düşürdü.)
    quantize_dynamic(str(HAM_ONNX), str(INT8_ONNX), weight_type=QuantType.QInt8, per_channel=True)
    print(f"  ✓ int8: {_boyut(INT8_ONNX):.0f} MB  (fp32: {_boyut(HAM_ONNX):.0f} MB)")
    return 0


# ───────────────────────── 3 · gömme (ort) ─────────────────────────


def gom() -> int:
    from krizkalkan_core.knowledge.retriever import Retriever

    metinler, kimlikler = _kayit_metinleri()
    print(f"→ {len(metinler):,} kayıt int8 kodlayıcıyla gömülüyor…")

    r = Retriever.__new__(Retriever)
    Retriever._kodlayici_kur(r, CIKTI)

    basladi = time.perf_counter()
    parcalar = []
    for i in range(0, len(metinler), 32):
        parcalar.append(np.asarray(r.kodla(metinler[i : i + 32], sorgu=False)))
        if (i // 32) % 20 == 0:
            print(f"    {min(i + 32, len(metinler)):>5,}/{len(metinler):,}")
    gomme = np.vstack(parcalar).astype("float32")

    np.save(CIKTI / "gomme.npy", gomme)
    (CIKTI / "kayit_kimlikleri.json").write_text(
        json.dumps(kimlikler, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  ✓ {gomme.shape} · {time.perf_counter() - basladi:.0f} sn")
    return 0


# ───────────────────────── 4 · doğrulama (ort) ─────────────────────────


def dogrula() -> int:
    """Nicelemenin geri getirmeyi bozup bozmadığını ölçer.

    İki ölçüt: gömmelerin fp32 ile kosinüs örtüşmesi ve — asıl önemlisi —
    aynı sorgular için ilk 5 sonucun fp32 sıralamasıyla ne kadar örtüştüğü.
    """
    from krizkalkan_core.knowledge.retriever import Retriever

    referans = np.load(REFERANS)
    metinler = json.loads(REFERANS_METIN.read_text(encoding="utf-8"))

    r = Retriever(CIKTI)
    int8_gomme = np.asarray(r.kodla(metinler, sorgu=False))

    kosinus = float((int8_gomme * referans).sum(axis=1).mean())
    en_dusuk = float((int8_gomme * referans).sum(axis=1).min())
    print(f"  kosinüs örtüşmesi (int8 ↔ fp32): ortalama {kosinus:.4f} · en düşük {en_dusuk:.4f}")

    # Sıralama tutarlılığı: fp32 referans gömmeleriyle kurulan mini indekste
    # aynı sorguların ilk 5'i ne kadar örtüşüyor?
    ortusme = []
    for i in range(len(metinler)):
        fp32_sira = set(np.argsort(-(referans @ referans[i]))[:5])
        int8_sira = set(np.argsort(-(int8_gomme @ int8_gomme[i]))[:5])
        ortusme.append(len(fp32_sira & int8_sira) / 5)
    sira_skoru = float(np.mean(ortusme))
    print(f"  ilk-5 sıralama örtüşmesi        : {sira_skoru:.4f}")

    tamam = kosinus >= KOSINUS_ESIGI and sira_skoru >= SIRALAMA_ESIGI
    print(f"  {'✓ niceleme kabul edilebilir' if tamam else '🔴 niceleme kaliteyi bozuyor'}")

    kayitlar = {k.record_id: k for k in corpus.records()}
    print("\n→ örnek sorgular:")
    for sorgu in (
        "baraj yıkıldı şehir su altında kalacak",
        "afad ikinci deprem uyarısı yaptı",
        "kızılay kan merkezi yıkıldı mı",
    ):
        print(f"  “{sorgu}”")
        for aday in r.ara(sorgu, k=2):
            print(f"    {aday.benzerlik:.3f}  {kayitlar[aday.record_id].claim[:72]}")
    return 0 if tamam else 1


# ───────────────────────── akış ─────────────────────────


def _alt_surec(bayrak: str) -> int:
    sonuc = subprocess.run([sys.executable, __file__, bayrak], capture_output=True, text=True)
    print(sonuc.stdout.rstrip() or sonuc.stderr.strip()[-400:])
    return sonuc.returncode


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    for bayrak, yardim in (
        ("--disa-aktar", "yalnızca fp32 ONNX (torch)"),
        ("--nicele", "yalnızca int8 niceleme"),
        ("--gom", "yalnızca havuzu yeniden gömme"),
        ("--dogrula", "yalnızca doğrulama"),
    ):
        a.add_argument(bayrak, action="store_true", help=yardim)
    a.add_argument("--temizle", action="store_true", help="ara dosyaları sil")
    args = a.parse_args()

    if args.disa_aktar:
        return disa_aktar()
    if args.nicele:
        return nicele()
    if args.gom:
        return gom()
    if args.dogrula:
        return dogrula()

    kayitlar = corpus.records()
    print(f"→ havuz: {len(kayitlar):,} kayıt")
    if len(kayitlar) < 100:
        print("🔴 Havuz çok küçük. Önce: python scripts/data/build_knowledge.py")
        return 1

    for bayrak, baslik in (
        ("--disa-aktar", "1/4 dışa aktarım"),
        ("--nicele", "2/4 niceleme"),
        ("--gom", "3/4 gömme"),
        ("--dogrula", "4/4 doğrulama"),
    ):
        print(f"\n═══ {baslik} ═══")
        if (kod := _alt_surec(bayrak)) != 0:
            return kod

    if args.temizle:
        for gecici in (HAM_ONNX, HAM_ONNX.with_suffix(".onnx.data"), REFERANS, REFERANS_METIN):
            gecici.unlink(missing_ok=True)
        print("\n  ara dosyalar silindi")

    print(f"\n✓ İndeks hazır: {CIKTI.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
