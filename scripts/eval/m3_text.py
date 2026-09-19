#!/usr/bin/env python
"""M3 değerlendirmesi — kayıtlı kontrol noktasından Kural 0 çalışma noktası.

Eğitimi tekrarlamaz: eşik seçimi sonradan yapılan bir karardır, kaydedilmiş
ağırlıkla hesaplanabilir. Betik doğrulama kümesinde olasılıkları üretir,
duyarlılık–maliyet eğrisini çıkarır ve kullanılabilir çalışma noktasını seçer.

Kural 0'ın maliyeti asimetriktir ve yönü sezgiye aykırıdır: yanlış pozitif,
bir dezenformasyon içeriğinin korumaya alınıp hiç etiketlenmemesi demektir.
Yanlış pozitif oranı 1,0 olan bir model sistemin tamamını kapatır. Bu yüzden
duyarlılık tek başına değil, maliyetiyle birlikte raporlanır.

Çıktı: docs/metrikler/m3.md + model kartı

Kullanım:
    python scripts/eval/m3_text.py --kontrol-noktasi /kaggle/working/m3_asama2
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "train"))

from krizkalkan_core.models.cards import Measurement, ModelCard  # noqa: E402
from m3_text import (  # noqa: E402
    AZAMI_YARDIM_FPR,
    CLAIM_SINIFLARI,
    HEDEF_YARDIM_DUYARLILIK,
    CokGorevliModel,
    KrizVeriKumesi,
    asama_verisi,
    degerlendir,
)

RAPOR = REPO_ROOT / "docs" / "metrikler" / "m3.md"


class OnnxSarmalayici:
    """int8 ONNX modelini torch modeliyle aynı arayüzle sunar.

    Eşik seçimi fp32 torch modelinde yapılıp üretimde int8 ONNX çalıştırılırsa,
    nicelemenin olasılıkları kaydırması eşiği geçersiz kılar. Aynı değerlendirme
    kodunu iki çalışma zamanında da koşturabilmek bu riski ölçülebilir yapar.
    """

    def __init__(self, dizin: Path, maks_uzunluk: int = 128) -> None:
        import onnxruntime as ort
        from tokenizers import Tokenizer

        self.tokenizer = Tokenizer.from_file(str(dizin / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=maks_uzunluk)
        self.tokenizer.enable_padding(length=maks_uzunluk)
        self.oturum = ort.InferenceSession(
            str(dizin / "model.onnx"), providers=["CPUExecutionProvider"]
        )

    def eval(self) -> OnnxSarmalayici:  # torch API uyumu
        return self

    def __call__(self, input_ids, attention_mask) -> dict[str, torch.Tensor]:
        claim, yanlis, yardim = self.oturum.run(
            None,
            {
                "input_ids": input_ids.cpu().numpy().astype("int64"),
                "attention_mask": attention_mask.cpu().numpy().astype("int64"),
            },
        )
        return {
            "claim": torch.from_numpy(claim),
            "yanlis": torch.from_numpy(yanlis),
            "yardim": torch.from_numpy(yardim),
        }


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=True,
        ).stdout.strip()
    except Exception:
        return "—"


def olc(kontrol_noktasi: Path, omurga: str, yigin: int = 64, onnx: bool = False) -> dict:
    from transformers import AutoTokenizer

    if onnx:
        cihaz = "cpu"
        model = OnnxSarmalayici(kontrol_noktasi)
        tokenizer = AutoTokenizer.from_pretrained(
            omurga if not (kontrol_noktasi / "tokenizer_config.json").exists() else kontrol_noktasi
        )
    else:
        cihaz = (
            "cuda"
            if torch.cuda.is_available()
            else ("mps" if torch.backends.mps.is_available() else "cpu")
        )
        tokenizer = AutoTokenizer.from_pretrained(kontrol_noktasi)
        model = CokGorevliModel(omurga).to(cihaz)
        model.load_state_dict(torch.load(kontrol_noktasi / "model.pt", map_location=cihaz))

    # Değerlendirme karışık kümede yapılır: 2. aşamanın Türkçe verisi tek başına
    # yardım çağrısı ve iddia tipi başlıklarını göremez.
    ham = pd.read_parquet(REPO_ROOT / "data" / "processed" / "val.parquet")
    dogrulama = asama_verisi(ham, asama=2, replay_orani=1.0)
    print(f"cihaz: {cihaz} · doğrulama: {len(dogrulama):,} satır")

    yukleyici = DataLoader(KrizVeriKumesi(dogrulama, tokenizer, 128), batch_size=yigin)
    return degerlendir(model, yukleyici, cihaz)


def rapor_yaz(metrikler: dict, kontrol_noktasi: Path, n: int, calisma_zamani: str) -> Path:
    egri = metrikler.get("yardim_egri", [])
    simdi = datetime.now(UTC).strftime("%d.%m.%Y %H:%M UTC")
    s = [
        "# M3 — Türkçe Kriz Metin Motoru · Değerlendirme",
        "",
        f"*`scripts/eval/m3_text.py` tarafından üretildi · {simdi} · commit `{_git_commit()}`*",
        "",
        "| | |",
        "|---|---|",
        f"| Kontrol noktası | `{kontrol_noktasi.name}` |",
        f"| Çalışma zamanı | **{calisma_zamani}** |",
        f"| Doğrulama kümesi | {n:,} satır (karışık: kriz alanı + Türkçe) |",
        "| Bölünme | Olay bazlı — hiçbir olay iki kümede değil |",
        "",
        "## Görev başarımları",
        "",
        "| Görev | Metrik | Değer |",
        "|---|---|---|",
        f"| A · iddia tipi ({len(CLAIM_SINIFLARI)} sınıf) | makro-F1 | "
        f"{metrikler.get('claim_makro_f1', 0):.4f} |",
        f"| B1 · yanlış bilgi (3 sınıf) | makro-F1 | {metrikler.get('yanlis_makro_f1', 0):.4f} |",
        f"| B2 · yardım çağrısı | makro-F1 | {metrikler.get('yardim_makro_f1', 0):.4f} |",
        "",
        "## Kural 0 — duyarlılık ve maliyeti",
        "",
        "Kural 0 tetiklendiğinde sistem **hiçbir müdahale uygulamaz.** Bu yüzden",
        "yanlış pozitif, zararsız bir hata değildir: bir dezenformasyon içeriğinin",
        "korumaya alınıp hiç etiketlenmemesi demektir. Yanlış pozitif oranı 1,0 olan",
        "bir model duyarlılıkta 1,00 gösterir ama sistemin tamamını kapatır.",
        "",
        "Bu nedenle duyarlılık tek başına değil, maliyetiyle birlikte raporlanır.",
        "",
        "| Hedef duyarlılık | Ulaşılan | Kesinlik | Yanlış pozitif oranı |",
        "|---|---|---|---|",
    ]
    s += [
        f"| {n_['hedef_duyarlilik']:.2f} | {n_['duyarlilik']:.4f} | {n_['kesinlik']:.4f} "
        f"| {n_['yanlis_pozitif_orani']:.4f} |"
        for n_ in egri
    ]

    duyarlilik = metrikler.get("yardim_duyarlilik_esikli")
    fpr = metrikler.get("yardim_yanlis_pozitif_orani")
    s += ["", "### Seçilen çalışma noktası", ""]
    if duyarlilik is None:
        s += [
            f"🔴 Yanlış pozitif oranı ≤ {AZAMI_YARDIM_FPR} kısıtı içinde kullanılabilir "
            "hiçbir eşik yok. Kural 0 bu ağırlıkla model tabanlı çalıştırılamaz; "
            "sözlük tabanlı yol kullanılmalıdır.",
        ]
    else:
        s += [
            f"- Eşik: `{metrikler.get('yardim_esik')}`",
            f"- Duyarlılık: **{duyarlilik:.4f}**",
            f"- Kesinlik: {metrikler.get('yardim_kesinlik_esikli', 0):.4f}",
            f"- Yanlış pozitif oranı: {fpr:.4f} (sınır {AZAMI_YARDIM_FPR})",
            "",
            (
                f"> Rapor hedefi ≥ {HEDEF_YARDIM_DUYARLILIK}. "
                + (
                    "**Tutmuyor.** Bu ağırlıkla hedef duyarlılık ancak yanlış pozitif "
                    "sınırı aşılarak elde edilebiliyor; hedef yerine kısıt içindeki en "
                    "yüksek duyarlılık seçildi ve bu tabloda açıkça raporlandı."
                    if metrikler.get("yardim_hedef_tutmadi")
                    else "Tutuyor."
                )
            ),
        ]

    s += [
        "",
        "## Yöntem notu",
        "",
        "Ölçüm, üretimde çalışacak motorun üzerinde yapılır. Eşik fp32 torch",
        "modelinde seçilip int8 ONNX ile çalıştırılırsa nicelemenin olasılıkları",
        "kaydırması eşiği geçersiz kılar: bu modelde eşik fp32'de 0,000287,",
        "int8'de 0,000317 çıktı (%10 fark). Aradaki metrik sapması 0,003–0,010",
        "bandında kaldı.",
        "",
        "Model çok görevlidir: tek gövde, üç başlık. Eğitim iki aşamalıdır —",
        "1. aşama kriz alanı (HumAID, İngilizce), 2. aşama Türkçe uyarlama.",
        "",
        "Türkçe etiketli yardım çağrısı verisi erişilebilir olmadığı için",
        "(`docs/veri-envanteri.md` · D3) bu sınıf çapraz dilli aktarımla öğrenilir.",
        "2. aşamada 1. aşamadan örneklem karıştırılır (replay): Türkçe veride bu",
        "başlıkların etiketi yoktur ve karışım olmadan hem unutma yaşanır hem de",
        "unutma ölçülemez.",
        "",
    ]
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text("\n".join(s), encoding="utf-8")
    return RAPOR


def yardim_pozitif_bilesimi() -> tuple[int, dict[str, int]]:
    """Yardım çağrısı pozitiflerinin hangi kaynaktan geldiğini sayar.

    Metriğin hangi dil üzerinde ölçüldüğü, metriğin kendisi kadar önemlidir:
    Türkçe kaynaklarda bu etiket yoktur, dolayısıyla duyarlılık sayısı çapraz
    dilli aktarımı ölçer, ürünün çalışacağı dildeki başarımı değil.
    """
    ham = pd.read_parquet(REPO_ROOT / "data" / "processed" / "val.parquet")
    val = asama_verisi(ham, asama=2, replay_orani=1.0)
    pozitifler = val[val["yardim_cagrisi"] == 1]
    return len(pozitifler), pozitifler.groupby("dil").size().to_dict()


def kart_yaz(metrikler: dict, kontrol_noktasi: Path, omurga: str, n: int) -> Path:
    duyarlilik = metrikler.get("yardim_duyarlilik_esikli", 0.0)
    fpr = metrikler.get("yardim_yanlis_pozitif_orani")
    pozitif_sayisi, dil_dagilimi = yardim_pozitif_bilesimi()
    yardim_kumesi = (
        "yardım pozitifleri: "
        + ", ".join(f"{d}={s}" for d, s in sorted(dil_dagilimi.items()))
        + f" (toplam {pozitif_sayisi})"
    )

    sinirlar = [
        "🔴 Modelin yardım çağrısı başlığı KURAL 0'A BAĞLI DEĞİLDİR. Kural 0 "
        "kararı sözlük tabanlı yolda kalır. Gerekçe ölçüldü: model Türkçe'de "
        "seferberlik söylemini yardım çağrısından ayıramıyor — "
        "“hepimiz sokağa dökülelim” metni sınanan tüm çalışma noktalarında "
        "(duyarlılık 0,80–0,95) korumaya alınıyor. Aynı metinlerde sözlük "
        "kusursuz ayırıyor.",
        f"Yardım çağrısı duyarlılığı ({duyarlilik:.4f}) yalnızca İNGİLİZCE "
        f"üzerinde ölçülmüştür — {yardim_kumesi}. Türkçe kaynaklarda bu etiket "
        "yoktur (docs/veri-envanteri.md · D3). Sayı çapraz dilli aktarımı ölçer, "
        "ürünün çalışacağı dildeki başarımı DEĞİL.",
        "Türkçe yardım çağrısı başarımını ölçmek için elle etiketlenmiş bir "
        "Türkçe test kümesi gerekir; bu küme henüz yoktur.",
        "8 sınıflı manipülatif söylem başlığı (Görev B1) eğitilmemiştir; sistemde "
        "hâlâ sözlük tabanlı yol kullanılır.",
        "Bölgesel ağız ve Türkçe dışı diller için alt grup analizi yapılmamıştır.",
    ]
    if metrikler.get("yardim_hedef_tutmadi"):
        sinirlar.insert(
            0,
            f"Kural 0 rapor hedefi ({HEDEF_YARDIM_DUYARLILIK}) TUTMUYOR: yanlış pozitif "
            f"sınırı içinde ulaşılabilen en yüksek duyarlılık {duyarlilik:.4f}. "
            "Hedef duyarlılık ancak sistemin etiketleme kapsamı yok edilerek elde "
            "edilebiliyor; bu bilinçli olarak yapılmadı.",
        )

    kart = ModelCard(
        name="m3_text",
        module="M3",
        title="Türkçe Kriz Metin Motoru",
        version="0.1.0",
        base_model=omurga,
        purpose=(
            "Metinden iddia yapısı çıkarır, yanlış bilgi ve manipülatif söylem "
            "sınıflandırır, Kural 0'ı besleyen yardım çağrısı sınıfını üretir."
        ),
        training_data=[
            "HumAID (CC BY-NC-SA, araştırma) — kriz alanı, İngilizce, 19 olay",
            "MiDe22 (MIT) — Türkçe yanlış bilgi",
            "DMM Dezenformasyon Bültenleri (CC BY 4.0) — iddia ve tekzip metinleri",
        ],
        training_procedure=(
            "İki aşamalı ince ayar: kriz alanı (İngilizce) → Türkçe uyarlama. "
            "2. aşamada 1. aşamadan örneklem karıştırılır (replay) — unutmayı "
            "hem engeller hem ölçülebilir kılar. Maskelenmiş çok görevli kayıp: "
            "etiketi olmayan başlık kayba katkı vermez."
        ),
        split_strategy="Olay bazlı bölünme, kaynak içi katmanlı",
        measurements=[
            Measurement("claim_makro_f1", metrikler.get("claim_makro_f1", 0), "karışık val", n),
            Measurement("yanlis_makro_f1", metrikler.get("yanlis_makro_f1", 0), "karışık val", n),
            Measurement(
                "yardim_duyarlilik",
                duyarlilik,
                f"HumAID İngilizce alt kümesi · FPR ≤ {AZAMI_YARDIM_FPR}",
                pozitif_sayisi,
                "Türkçe ölçüm YOK — Kural 0 bu başlığa bağlı değildir",
            ),
        ]
        + (
            [Measurement("yardim_yanlis_pozitif_orani", fpr, "karışık val", n)]
            if fpr is not None
            else []
        )
        + (
            # Eşik bir ölçüm değil bir karardır; ama ağırlıkla birlikte taşınması
            # gerekir: çıkarım katmanı bunu karttan okur, kodda sabit tutmaz.
            [
                Measurement(
                    "yardim_esik",
                    metrikler["yardim_esik"],
                    "karışık val",
                    n,
                    "Kural 0 karar eşiği — çıkarım katmanı bu değeri kullanır",
                )
            ]
            if "yardim_esik" in metrikler
            else []
        ),
        known_limits=sinirlar,
        ethical_notes=[
            "Kural 0'da yanlış pozitif, içeriğin korumaya alınıp etiketlenmemesi "
            "demektir; sistemin kapsamını doğrudan azaltır. Bu yüzden duyarlılık "
            "yanlış pozitif sınırıyla birlikte seçilir.",
            "Yanlış negatif ise gerçek bir yardım çağrısının etiketlenmesi demektir "
            "ve etik maliyeti daha ağırdır; eşik bu asimetriyi gözetir.",
        ],
        out_of_scope=[
            "Tek başına doğruluk hükmü vermek",
            "Kural 0'ı model tabanlı çalıştırmak — çalışma noktası kabul edilebilir "
            "değilse sözlük yolu kullanılmalıdır",
        ],
        license="Model: MIT · Veri: karışık (bkz. docs/veri-envanteri.md)",
        git_commit=_git_commit(),
    )
    kart.save(kontrol_noktasi)
    return kart.write_markdown(REPO_ROOT / "docs" / "model-kartlari")


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--kontrol-noktasi", type=Path, required=True)
    a.add_argument("--omurga", default="FacebookAI/xlm-roberta-base")
    a.add_argument(
        "--onnx",
        action="store_true",
        help="model.pt yerine int8 model.onnx ile ölç (üretimde çalışacak olan budur)",
    )
    a.add_argument("--rapor-yazma", action="store_true", help="yalnızca ölç, belge üretme")
    args = a.parse_args()

    metrikler = olc(args.kontrol_noktasi, args.omurga, onnx=args.onnx)
    egri = metrikler.get("yardim_egri", [])

    print("\n═══ Kural 0 çalışma noktaları ═══")
    print(f"{'hedef':>7s} {'duyarlılık':>11s} {'kesinlik':>9s} {'yanlış poz.':>12s}")
    for n_ in egri:
        print(
            f"{n_['hedef_duyarlilik']:7.2f} {n_['duyarlilik']:11.4f} "
            f"{n_['kesinlik']:9.4f} {n_['yanlis_pozitif_orani']:12.4f}"
        )

    print(f"\n═══ Seçilen nokta (FPR ≤ {AZAMI_YARDIM_FPR}) ═══")
    print(
        json.dumps(
            {k: v for k, v in metrikler.items() if k != "yardim_egri"}, ensure_ascii=False, indent=2
        )
    )

    n = int(metrikler.get("_n", 0)) or 0
    ham = pd.read_parquet(REPO_ROOT / "data" / "processed" / "val.parquet")
    n = len(asama_verisi(ham, asama=2, replay_orani=1.0))

    if args.rapor_yazma:
        return 0
    calisma_zamani = "int8 ONNX (üretim)" if args.onnx else "fp32 torch"
    print(
        f"\n✓ {rapor_yaz(metrikler, args.kontrol_noktasi, n, calisma_zamani).relative_to(REPO_ROOT)}"
    )
    print(f"✓ {kart_yaz(metrikler, args.kontrol_noktasi, args.omurga, n).relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
