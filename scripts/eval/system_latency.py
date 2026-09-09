#!/usr/bin/env python
"""Sistem gecikmesi ve verimi.

Rapor 3.2 iki taahhüt veriyor: p50 ≤ 8 sn, p95 ≤ 20 sn (60 sn video, tek GPU)
ve ≥ 400 içerik/dakika. Bu betik ölçülebilen kısmı ölçer ve ölçülemeyeni açıkça
söyler: video hattı ffmpeg gerektirir ve M2/M4-video kurulmadı, dolayısıyla
"60 sn video" senaryosu henüz koşturulamaz.

Ölçüm, üretimde çalışacak yapılandırmada yapılır: int8 ONNX, CPU. Demo
makinesinde GPU yoktur, dolayısıyla "tek GPU" hedefi bu ölçümden ayrıdır ve
raporda öyle belirtilir.

İki katman ayrı ölçülür:

    soğuk   önbellek boş — her içerik baştan analiz edilir
    sıcak   algısal karma önbelleği devrede (rapor 4.1 · maliyet verimliliği)

Çıktı: docs/metrikler/sistem.md
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.models import describe as runtime_bilgisi  # noqa: E402
from krizkalkan_core.models import registry  # noqa: E402
from krizkalkan_core.pipeline import AnalysisPipeline  # noqa: E402

KUME = REPO_ROOT / "data" / "processed" / "m6_uctan_uca.jsonl"
RAPOR = REPO_ROOT / "docs" / "metrikler" / "sistem.md"

#: Rapor 3.2 hedefleri.
HEDEF_P50 = 8.0
HEDEF_P95 = 20.0
HEDEF_VERIM = 400.0


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


def olc(vakalar: list[dict], *, onbellek: bool) -> dict:
    """Vakaları analiz eder ve gecikme dağılımını çıkarır.

    `onbellek=True` iken aynı içerikler İKİ KEZ koşturulur ve yalnızca ikinci
    geçiş ölçülür. İlk sürümde her vaka benzersiz olduğu için önbellek hiç
    tetiklenmiyordu ve "sıcak hat" ölçümü soğuk hattın aynısını gösteriyordu.
    """
    hat = AnalysisPipeline()
    gecikmeler: list[float] = []

    def calistir(vaka: dict) -> None:
        hat.analyse(
            body=vaka["metin"],
            media_kind=vaka["medya_turu"],
            media_fingerprint=vaka.get("medya"),
        )

    # Isınma: ilk çağrı model yüklemesini içerir ve dağılımı bozar.
    hat.analyse(body="ısınma", media_kind="yok")
    hat.clear_cache()

    if onbellek:
        for vaka in vakalar:  # önbelleği doldur
            calistir(vaka)

    basladi = time.perf_counter()
    for vaka in vakalar:
        if not onbellek:
            hat.clear_cache()
        t0 = time.perf_counter()
        calistir(vaka)
        gecikmeler.append((time.perf_counter() - t0) * 1000)
    toplam = time.perf_counter() - basladi

    dizi = np.array(gecikmeler)
    return {
        "n": len(dizi),
        "p50_ms": round(float(np.percentile(dizi, 50)), 1),
        "p95_ms": round(float(np.percentile(dizi, 95)), 1),
        "p99_ms": round(float(np.percentile(dizi, 99)), 1),
        "ortalama_ms": round(float(dizi.mean()), 1),
        "azami_ms": round(float(dizi.max()), 1),
        "verim_dk": round(len(dizi) / toplam * 60, 1),
    }


def tur_bazli(vakalar: list[dict]) -> dict[str, dict]:
    """İçerik türüne göre ayrı ölçüm — medya hattı metinden pahalıdır."""
    gruplar = {
        "yalnızca metin": [v for v in vakalar if v["medya_turu"] == "yok"],
        "görsel + metin": [v for v in vakalar if v["medya_turu"] == "image"],
    }
    return {ad: olc(grup, onbellek=False) for ad, grup in gruplar.items() if len(grup) >= 10}


def bilesen_dokumu() -> dict[str, float]:
    """Boru hattının pahalı parçalarını ayrı ayrı ölçer.

    Toplam gecikmenin nereden geldiğini göstermeden optimizasyon kararı
    verilemez.
    """
    from krizkalkan_core.knowledge import retriever
    from krizkalkan_core.provenance import imaging
    from krizkalkan_core.text import model as m3

    metin = "İzmir'de yaşananlar. Ekipler bölgede çalışıyor."
    olcumler: dict[str, float] = {}

    def zaman(ad: str, islev, tekrar: int = 20) -> None:
        try:
            islev()
        except Exception:
            return
        t0 = time.perf_counter()
        for _ in range(tekrar):
            islev()
        olcumler[ad] = round((time.perf_counter() - t0) / tekrar * 1000, 2)

    if (model := m3.get()) is not None:
        zaman("M3 · ONNX ileri geçiş", lambda: model.analiz(metin, kanit=False))
        zaman(
            "M3 · örtme tabanlı kanıt",
            lambda: model.analiz("enkaz altındayız yardım edin", kanit=True),
            5,
        )
    if (arayici := retriever.get()) is not None:
        zaman("M5 · gömme kodlama + arama", lambda: arayici.ara(metin, k=5))

    gorsel = next(
        (REPO_ROOT / "data" / "external" / "provenance" / "goruntuler").glob("*.jpg"), None
    )
    if gorsel is not None:
        zaman("M1 · görüntü karması", lambda: imaging.karmalar(gorsel))
    return olcumler


def rapor_yaz(soguk: dict, sicak: dict, turler: dict, model_durumu: dict, bilesenler: dict) -> Path:
    simdi = datetime.now(UTC).strftime("%d.%m.%Y %H:%M UTC")
    hazir = [a for a, b in model_durumu.items() if b["durum"] == "hazır"]

    def isaret(deger: float, hedef: float) -> str:
        return "✓" if deger <= hedef else "✗"

    s = [
        "# Sistem — Gecikme ve Verim",
        "",
        f"*`scripts/eval/system_latency.py` tarafından üretildi · {simdi} · "
        f"commit `{_git_commit()}`*",
        "",
        "| | |",
        "|---|---|",
        f"| Çalışma zamanı | {runtime_bilgisi()['calisma_zamani']} · "
        f"{runtime_bilgisi()['cihaz']} |",
        f"| Yüklü model | {len(hazir)}/{len(model_durumu)} · {', '.join(hazir) or '—'} |",
        f"| Vaka sayısı | {soguk['n']} |",
        "",
        "## Soğuk hat (önbellek kapalı)",
        "",
        "| Metrik | Ölçülen | Hedef | |",
        "|---|---|---|---|",
        f"| p50 | {soguk['p50_ms'] / 1000:.2f} sn | ≤ {HEDEF_P50:.0f} sn | "
        f"{isaret(soguk['p50_ms'] / 1000, HEDEF_P50)} |",
        f"| p95 | {soguk['p95_ms'] / 1000:.2f} sn | ≤ {HEDEF_P95:.0f} sn | "
        f"{isaret(soguk['p95_ms'] / 1000, HEDEF_P95)} |",
        f"| p99 | {soguk['p99_ms'] / 1000:.2f} sn | — | |",
        f"| Verim | {soguk['verim_dk']:.0f} içerik/dk | ≥ {HEDEF_VERIM:.0f} | "
        f"{'✓' if soguk['verim_dk'] >= HEDEF_VERIM else '✗'} |",
        "",
        "## Sıcak hat (algısal karma önbelleği açık)",
        "",
        "Rapor 4.1'deki maliyet verimliliği tezinin ölçümü: aynı içerik yeniden",
        "yüklendiğinde boru hattı baştan çalıştırılmaz.",
        "",
        "| Metrik | Ölçülen |",
        "|---|---|",
        f"| p50 | {sicak['p50_ms'] / 1000:.3f} sn |",
        f"| Verim | {sicak['verim_dk']:.0f} içerik/dk |",
        f"| Hızlanma | {soguk['p50_ms'] / max(sicak['p50_ms'], 0.001):.0f}× |",
        "",
        "## İçerik türüne göre",
        "",
        "| Tür | n | p50 | p95 | Verim |",
        "|---|---|---|---|---|",
    ]
    s += [
        f"| {ad} | {d['n']} | {d['p50_ms'] / 1000:.3f} sn | {d['p95_ms'] / 1000:.3f} sn "
        f"| {d['verim_dk']:.0f}/dk |"
        for ad, d in turler.items()
    ]
    s += [
        "",
        "## Bileşen dökümü",
        "",
        "Toplam gecikmenin nereden geldiği görülmeden optimizasyon kararı",
        "verilemez.",
        "",
        "| Bileşen | Süre |",
        "|---|---|",
    ]
    s += [f"| {ad} | {sure:.2f} ms |" for ad, sure in bilesenler.items()]
    s += [
        "",
        "Örtme tabanlı kanıt yalnızca yardım çağrısı olasılığı eşiği aştığında",
        "çalışır; tipik içerikte bu maliyet ödenmez.",
        "",
        "## Ölçümün sınırları",
        "",
        "Rapor hedefi **60 saniyelik video** ve **tek GPU** içindir. Bu ölçüm",
        "görsel ve metin içeriğini **CPU üzerinde** koşturur:",
        "",
        '- Video hattı ffmpeg gerektirir ve M2/M4-video kurulmadı; "60 sn video"',
        "  senaryosu henüz koşturulamıyor.",
        "- Ölçüm üretimde çalışacak yapılandırmadadır (int8 ONNX, CPU). GPU'da",
        "  daha hızlı olması beklenir, ama bu ölçülmedi ve tahmin raporlanmaz.",
        "",
        "Bu nedenle tablodaki sayılar rapor hedefiyle **doğrudan**",
        "karşılaştırılamaz; aynı eksende olan tek şey verim.",
        "",
    ]
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text("\n".join(s), encoding="utf-8")
    return RAPOR


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--vaka", type=int, default=120, help="kaç vaka ölçülecek")
    args = a.parse_args()

    if not KUME.exists():
        print(f"🔴 {KUME} yok. Önce: python scripts/data/build_m6_set.py")
        return 1

    tum = [json.loads(s) for s in KUME.read_text(encoding="utf-8").splitlines() if s]
    # Türler arasında dengeli örneklem: kümenin başı yalnızca görsel vakalardan
    # oluşuyor ve ilk N'i almak metin hattını ölçüm dışı bırakıyordu.
    gorsel = [v for v in tum if v["medya_turu"] == "image"]
    metin = [v for v in tum if v["medya_turu"] == "yok"]
    yari = args.vaka // 2
    vakalar = gorsel[:yari] + metin[:yari]
    print(f"→ {len(vakalar)} vaka · {runtime_bilgisi()}")

    print("\n→ soğuk hat")
    soguk = olc(vakalar, onbellek=False)
    print(
        f"  p50 {soguk['p50_ms']:.0f} ms · p95 {soguk['p95_ms']:.0f} ms · "
        f"verim {soguk['verim_dk']:.0f}/dk"
    )

    print("→ sıcak hat (önbellek)")
    sicak = olc(vakalar, onbellek=True)
    print(f"  p50 {sicak['p50_ms']:.1f} ms · verim {sicak['verim_dk']:.0f}/dk")

    print("→ içerik türüne göre")
    turler = tur_bazli(vakalar)
    for ad, d in turler.items():
        print(f"  {ad:16s} p50 {d['p50_ms']:7.1f} ms · verim {d['verim_dk']:6.0f}/dk")

    print("→ bileşen dökümü")
    bilesenler = bilesen_dokumu()
    for ad, sure in bilesenler.items():
        print(f"  {ad:30s} {sure:7.2f} ms")

    yol = rapor_yaz(soguk, sicak, turler, registry.report(), bilesenler)
    print(f"\n✓ {yol.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
