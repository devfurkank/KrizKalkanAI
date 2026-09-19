#!/usr/bin/env python
"""M2 sahne–iddia değerlendirmesi — eşli karşılaştırma.

Doğrudan sınıflandırma doğruluğu bu korpusta yanıltıcıdır: görüntülerin %90'ı
deprem olduğu için çoğunluk sınıfını tahmin eden bir model bile yüksek doğruluk
alır. Ölçüm bu yüzden EŞLİdir: her görüntü için doğru olay türü ile YANLIŞ bir
tür yarıştırılır ve doğrunun daha yüksek skor alıp almadığına bakılır. Her
görüntü aynı ağırlıkta katkı verir, sınıf boyutu ölçümü etkilemez.

Bu, sinyalin fiilen yaptığı işin de ölçüsüdür: "metindeki iddia görüntüdekiyle
uyuşuyor mu?" sorusu bir karşılaştırmadır, bir sınıflandırma değil.

Çıktı: docs/metrikler/m2.md + model kartı
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.models.cards import Measurement, ModelCard  # noqa: E402
from krizkalkan_core.multimodal.scene import SahneModeli  # noqa: E402

KAYNAK = REPO_ROOT / "data" / "external" / "provenance"
MODEL_DIZINI = REPO_ROOT / "models" / "m2_scene"
RAPOR = REPO_ROOT / "docs" / "metrikler" / "m2.md"

#: Korpus olay adından sahne türüne eşleme.
TUR_ANAHTARLARI = (("deprem", "deprem"), ("yangın", "yangın"), ("sel", "sel"))


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


def _tur(olay: str) -> str | None:
    alt = olay.lower()
    return next((t for a, t in TUR_ANAHTARLARI if a in alt), None)


def havuz(sinir: int, tohum: int) -> list[tuple[Path, str]]:
    kayitlar = [
        json.loads(s)
        for s in (KAYNAK / "kayitlar.jsonl").read_text(encoding="utf-8").splitlines()
        if s
    ]
    ogeler = [
        (KAYNAK / "goruntuler" / k["dosya"], t)
        for k in kayitlar
        if (t := _tur(k["olay"])) and (KAYNAK / "goruntuler" / k["dosya"]).exists()
    ]
    rastgele = random.Random(tohum)
    rastgele.shuffle(ogeler)
    return ogeler[:sinir]


def olc(model: SahneModeli, ogeler: list[tuple[Path, str]]) -> dict:
    """Eşli doğruluk: doğru tür yanlış türü geçiyor mu?"""
    dogru_cift = toplam_cift = 0
    tur_bazli: dict[str, list[int]] = defaultdict(list)
    ilk_sirada = 0

    for yol, gercek in ogeler:
        sonuc = model.karsilastir(yol, gercek)
        skorlar = sonuc.skorlar
        ilk_sirada += int(sonuc.destekliyor)

        for tur, skor in skorlar.items():
            if tur == gercek:
                continue
            kazandi = int(skorlar[gercek] > skor)
            dogru_cift += kazandi
            toplam_cift += 1
            tur_bazli[gercek].append(kazandi)

    return {
        "n_goruntu": len(ogeler),
        "n_cift": toplam_cift,
        "esli_dogruluk": round(dogru_cift / max(toplam_cift, 1), 4),
        "ilk_sirada_orani": round(ilk_sirada / max(len(ogeler), 1), 4),
        "tur_bazli": {
            t: {"n": len(v), "dogruluk": round(sum(v) / len(v), 4)}
            for t, v in sorted(tur_bazli.items())
        },
    }


def rapor_yaz(sonuc: dict) -> Path:
    simdi = datetime.now(UTC).strftime("%d.%m.%Y %H:%M UTC")
    s = [
        "# M2 — Sahne–İddia Uyumu · Değerlendirme",
        "",
        f"*`scripts/eval/m2_scene.py` tarafından üretildi · {simdi} · commit `{_git_commit()}`*",
        "",
        "Doğrudan sınıflandırma doğruluğu bu korpusta yanıltıcıdır: görüntülerin",
        "büyük çoğunluğu deprem olduğu için çoğunluk sınıfını tahmin eden bir model",
        "bile yüksek doğruluk alır. Ölçüm bu yüzden **eşlidir**: her görüntü için",
        "doğru olay türü ile yanlış bir tür yarıştırılır. Her görüntü aynı ağırlıkta",
        "katkı verir.",
        "",
        "| | |",
        "|---|---|",
        f"| Görüntü | {sonuc['n_goruntu']} |",
        f"| Karşılaştırma çifti | {sonuc['n_cift']} |",
        f"| **Eşli doğruluk** | **{sonuc['esli_dogruluk']:.4f}** |",
        f"| Doğru tür ilk sırada | {sonuc['ilk_sirada_orani']:.4f} |",
        "",
        "## Olay türüne göre",
        "",
        "| Tür | Çift | Eşli doğruluk |",
        "|---|---|---|",
    ]
    s += [f"| {t} | {d['n']} | {d['dogruluk']:.4f} |" for t, d in sonuc["tur_bazli"].items()]
    s += [
        "",
        "## Sınırlar",
        "",
        "Korpus olay türleri arasında ağır biçimde dengesizdir; küçük sınıflarda",
        "çift sayısı azdır ve o satırlar geniş güven aralığı taşır. Eşli ölçüm",
        "çoğunluk sınıfı yanlılığını giderir ama örneklem azlığını gideremez.",
        "",
        "Karar mutlak benzerlik eşiğiyle verilmez: CLIP benzerlikleri dar bir",
        "bantta sıkışır (ölçüldü: 0,17–0,28). İddia, karşıt istemlerle yarıştırılır",
        "ve sıralama kullanılır. Aynı ders M5'te de çıkmıştı — sıkışık benzerlik",
        "dağılımı sıralama verir, karar vermez.",
        "",
        "Metin kulesi çok dillidir; CLIP'in kendi metin kulesi İngilizce",
        "eğitilmiştir ve Türkçe iddialarda kullanılamaz.",
        "",
    ]
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text("\n".join(s), encoding="utf-8")
    return RAPOR


def kart_yaz(sonuc: dict) -> Path:
    kart = ModelCard(
        name="m2_scene",
        module="M2",
        title="Sahne–İddia Uyumu",
        version="0.1.0",
        base_model="openai/clip-vit-base-patch32 + clip-ViT-B-32-multilingual-v1 (int8 ONNX)",
        purpose=(
            "Metindeki iddianın görüntüdekiyle uyuşup uyuşmadığını ölçer. "
            "Karar vermez; çelişki sinyali üretir."
        ),
        training_data=["İnce ayar yok; hazır çok dilli CLIP sıfır-atışlı kullanılır"],
        training_procedure=(
            "Eğitim yok. İki kule int8 ONNX'e aktarıldı; karşıt istemler inşa sırasında gömüldü."
        ),
        split_strategy="Eşli karşılaştırma — sınıf dengesizliğinden bağımsız",
        measurements=[
            Measurement(
                "esli_dogruluk",
                sonuc["esli_dogruluk"],
                "M1 korpusu · doğru tür vs yanlış tür",
                sonuc["n_cift"],
            ),
            Measurement(
                "ilk_sirada_orani",
                sonuc["ilk_sirada_orani"],
                "M1 korpusu",
                sonuc["n_goruntu"],
            ),
        ],
        known_limits=[
            "Korpus olay türleri arasında ağır dengesizdir; yangın ve sel "
            "sınıflarında örneklem azdır ve o satırlar geniş güven aralığı taşır.",
            "Sıfır-atışlı kullanım: model kriz görüntüleri üzerinde ince ayar "
            "görmemiştir. Türkçe iddia metinleri çok dilli metin kulesiyle "
            "işlenir ve o kule de kriz alanına uyarlanmamıştır.",
            "Sinyal karar vermez, çelişki bildirir. Sahne uyuşmazlığı tek başına "
            "içeriğin yanlış olduğu anlamına gelmez: aynı olayın farklı bir "
            "aşamasını gösteren bir görüntü de düşük skor alabilir.",
            "Yalnızca üç olay türü ve bir 'diğer' sınıfı tanımlıdır; bu kümenin "
            "dışındaki afetler için sinyal anlamsızdır.",
        ],
        ethical_notes=[
            "Sahne uyuşmazlığı, kullanıcıya içeriğinin sahte olduğunu söylemek "
            "için yeterli değildir; füzyon katmanı bu sinyali tek başına karar "
            "verdirmeyecek biçimde kullanır.",
        ],
        out_of_scope=[
            "Görüntüden olay türü hükmü vermek",
            "Tanımlı dört tür dışındaki içerikleri değerlendirmek",
        ],
        license="Model: MIT (CLIP) · Apache-2.0 (çok dilli kule)",
        git_commit=_git_commit(),
    )
    kart.save(MODEL_DIZINI)
    return kart.write_markdown(REPO_ROOT / "docs" / "model-kartlari")


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--sinir", type=int, default=200)
    a.add_argument("--tohum", type=int, default=42)
    args = a.parse_args()

    if not (MODEL_DIZINI / "gorsel.onnx").exists():
        print(f"🔴 Model yok: {MODEL_DIZINI}. Önce: python scripts/data/build_scene.py")
        return 1

    ogeler = havuz(args.sinir, args.tohum)
    dagilim: dict[str, int] = defaultdict(int)
    for _, t in ogeler:
        dagilim[t] += 1
    print(f"→ {len(ogeler)} görüntü · {dict(dagilim)}")

    model = SahneModeli(MODEL_DIZINI)
    sonuc = olc(model, ogeler)

    print(f"\n  eşli doğruluk       {sonuc['esli_dogruluk']:.4f} ({sonuc['n_cift']} çift)")
    print(f"  doğru tür ilk sırada {sonuc['ilk_sirada_orani']:.4f}")
    for t, d in sonuc["tur_bazli"].items():
        print(f"    {t:8s} {d['dogruluk']:.4f}  ({d['n']} çift)")

    print(f"\n✓ {rapor_yaz(sonuc).relative_to(REPO_ROOT)}")
    print(f"✓ {kart_yaz(sonuc).relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
