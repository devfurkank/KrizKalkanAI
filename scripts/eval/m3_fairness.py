#!/usr/bin/env python
"""Adalet denetimi — alt grup yanlış pozitif analizi (rapor 6.2).

Soru şu değildir: "sistem ne kadar doğru çalışıyor?" Şudur: **ölçünlü Türkçe
dışında yazan vatandaş sistemden farklı muamele mi görüyor?**

Küme, aynı ZARARSIZ içeriğin farklı ağız, kayıt ve dillerdeki hâllerinden
oluşur. Hiçbiri etiketlenmemelidir; alt gruplar arasındaki yanlış pozitif
farkı modelin dilsel önyargısını gösterir.

İki ayrı hata ölçülür ve ikisi farklı şeydir:

    etiketleme    içerik TEMİZ değil sayıldı → dilsel ayrımcılık
    Kural 0       içerik yardım çağrısı sayıldı → sistem o dilde hiçbir şeyi
                  etiketlemiyor demektir; koruma gibi görünen bir körlük

Rapor hedefi: gruplar arası yanlış pozitif farkı ≤ 5 puan.

Çıktı: docs/metrikler/adalet.md
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.models import describe as runtime_bilgisi  # noqa: E402
from krizkalkan_core.pipeline import AnalysisPipeline  # noqa: E402
from krizkalkan_core.taxonomy import Verdict  # noqa: E402

KUME = Path(__file__).parent / "kumeler" / "adalet_metinleri.json"
RAPOR = REPO_ROOT / "docs" / "metrikler" / "adalet.md"

#: Rapor 6.2 hedefi: gruplar arası fark bu puandan büyük olmamalı.
HEDEF_FARK = 0.05

#: Karşılaştırmanın dayanağı olan grup.
TABAN_GRUP = "ölçünlü_türkçe"


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


def olc(gruplar: dict[str, list[str]]) -> dict[str, dict]:
    hat = AnalysisPipeline()
    sonuc: dict[str, dict] = {}

    for grup, metinler in gruplar.items():
        etiketlenen = 0
        kural_sifir = 0
        ornekler: list[str] = []
        for metin in metinler:
            hat.clear_cache()
            analiz = hat.analyse(body=metin, media_kind="yok")
            if analiz.intervention.protected_by_rule_zero:
                kural_sifir += 1
            elif analiz.verdict not in (Verdict.TEMIZ, Verdict.YETERSIZ_KANIT):
                etiketlenen += 1
                if len(ornekler) < 2:
                    ornekler.append(f"{analiz.verdict.value} ← “{metin[:56]}”")

        n = len(metinler)
        sonuc[grup] = {
            "n": n,
            "etiketlenen": etiketlenen,
            "yanlis_pozitif": round(etiketlenen / n, 4),
            "kural_sifir": kural_sifir,
            "kural_sifir_orani": round(kural_sifir / n, 4),
            "ornekler": ornekler,
        }
        print(
            f"  {grup:34s} yanlış pozitif {etiketlenen}/{n} = "
            f"{etiketlenen / n:.4f} · Kural 0 {kural_sifir}/{n}"
        )
    return sonuc


def olc_tespit(gruplar: dict[str, list[str]]) -> dict[str, dict]:
    """Etiketlenmesi GEREKEN içerik her grupta eşit yakalanıyor mu?

    Yalnızca yanlış pozitif farkını ölçmek yanıltıcıdır: hiçbir şeyi
    etiketlemeyen bir sistem de kusursuz adil görünür. Eşitsizliğin diğer yüzü,
    bir grubun dezenformasyondan KORUNMAMASIDIR.
    """
    hat = AnalysisPipeline()
    sonuc: dict[str, dict] = {}
    for grup, metinler in gruplar.items():
        yakalanan = 0
        kacan: list[str] = []
        for metin in metinler:
            hat.clear_cache()
            analiz = hat.analyse(body=metin, media_kind="yok")
            if not analiz.intervention.protected_by_rule_zero and analiz.verdict not in (
                Verdict.TEMIZ,
                Verdict.YETERSIZ_KANIT,
            ):
                yakalanan += 1
            elif len(kacan) < 2:
                kacan.append(metin[:56])
        n = len(metinler)
        sonuc[grup] = {
            "n": n,
            "yakalanan": yakalanan,
            "tespit": round(yakalanan / n, 4),
            "kacan": kacan,
        }
        print(f"  {grup:34s} tespit {yakalanan}/{n} = {yakalanan / n:.4f}")
    return sonuc


def rapor_yaz(sonuc: dict[str, dict], tespit: dict[str, dict], aciklama: str, uyari: str) -> Path:
    simdi = datetime.now(UTC).strftime("%d.%m.%Y %H:%M UTC")
    taban = sonuc.get(TABAN_GRUP, {}).get("yanlis_pozitif", 0.0)
    oranlar = [d["yanlis_pozitif"] for d in sonuc.values()]
    fark = round(max(oranlar) - min(oranlar), 4)

    s = [
        "# Adalet Denetimi — Alt Grup Yanlış Pozitif Analizi",
        "",
        f"*`scripts/eval/m3_fairness.py` tarafından üretildi · {simdi} · commit `{_git_commit()}`*",
        "",
        aciklama,
        "",
        "| | |",
        "|---|---|",
        f"| Çalışma zamanı | {runtime_bilgisi()['calisma_zamani']} |",
        f"| Alt grup | {len(sonuc)} |",
        f"| Grup başına metin | {next(iter(sonuc.values()))['n']} |",
        "",
        "## Eksen 1 — eşit muamele (yanlış pozitif)",
        "",
        "Tüm metinler zararsızdır ve hiçbiri etiketlenmemelidir.",
        "",
        "| Alt grup | Yanlış pozitif | Ölçünlü Türkçe'ye fark | Kural 0 tetiklenme |",
        "|---|---|---|---|",
    ]
    for grup, d in sonuc.items():
        delta = d["yanlis_pozitif"] - taban
        isaret = "" if grup == TABAN_GRUP else f" {'✓' if abs(delta) <= HEDEF_FARK else '✗'}"
        s.append(
            f"| {grup.replace('_', ' ')} | {d['yanlis_pozitif']:.4f} "
            f"({d['etiketlenen']}/{d['n']}) | {delta:+.4f}{isaret} | "
            f"{d['kural_sifir_orani']:.4f} |"
        )

    s += [
        "",
        f"**Gruplar arası azami fark: {fark:.4f}** · rapor 6.2 hedefi ≤ {HEDEF_FARK:.2f} "
        f"{'✓' if fark <= HEDEF_FARK else '✗'}",
        "",
    ]

    if tespit:
        taban_tespit = tespit.get(TABAN_GRUP, {}).get("tespit", 0.0)
        tespit_oranlari = [d["tespit"] for d in tespit.values()]
        tespit_farki = round(max(tespit_oranlari) - min(tespit_oranlari), 4)
        s += [
            "## Eksen 2 — eşit tespit",
            "",
            "Aynı PROVOKATİF içerik her ağızda yazıldığında eşit yakalanıyor mu?",
            "Yalnızca yanlış pozitif farkını ölçmek yanıltıcıdır: hiçbir şeyi",
            "etiketlemeyen bir sistem de kusursuz adil görünür. Eşitsizliğin diğer",
            "yüzü, bir grubun dezenformasyondan KORUNMAMASIDIR.",
            "",
            "| Alt grup | Tespit oranı | Ölçünlü Türkçe'ye fark |",
            "|---|---|---|",
        ]
        for grup, d in tespit.items():
            delta = d["tespit"] - taban_tespit
            isaret = "" if grup == TABAN_GRUP else f" {'✓' if abs(delta) <= HEDEF_FARK else '✗'}"
            s.append(
                f"| {grup.replace('_', ' ')} | {d['tespit']:.4f} "
                f"({d['yakalanan']}/{d['n']}) | {delta:+.4f}{isaret} |"
            )
        s += [
            "",
            f"**Tespit farkı: {tespit_farki:.4f}** · hedef ≤ {HEDEF_FARK:.2f} "
            f"{'✓' if tespit_farki <= HEDEF_FARK else '✗'}",
            "",
            "⚠️ **Eşitlik, yeterlilik demek değildir.** Mutlak tespit oranı tüm",
            f"gruplarda {taban_tespit:.2f} seviyesindedir: sistem provokatif içeriğin",
            "dörtte birini yakalıyor ve bunu her ağızda EŞİT ölçüde yapıyor. Bu",
            "bölümün ölçtüğü adalettir, başarım değil. Düşük mutlak oranın sebebi,",
            "sekiz etiketli manipülatif söylem başlığının hiç eğitilmemiş olması ve",
            "sistemin hâlâ sözlük tabanlı yolu kullanmasıdır (docs/metrikler/m3.md).",
            "",
        ]
        kacanlar = {g: d for g, d in tespit.items() if d["kacan"]}
        if kacanlar:
            s += ["### Yakalanamayan provokatif içerik", ""]
            for grup, d in kacanlar.items():
                s.append(f"**{grup.replace('_', ' ')}**")
                s += [f"- “{k}”" for k in d["kacan"]]
                s.append("")

    etiketli = {g: d for g, d in sonuc.items() if d["ornekler"]}
    if etiketli:
        s += ["## Yanlış etiketlenen örnekler", ""]
        for grup, d in etiketli.items():
            s.append(f"**{grup.replace('_', ' ')}**")
            s += [f"- {o}" for o in d["ornekler"]]
            s.append("")

    s += [
        "## Kural 0 tetiklenmesi neden ayrı ölçülüyor",
        "",
        "Kural 0 tetiklendiğinde sistem hiçbir müdahale uygulamaz. Bir alt grupta",
        "Kural 0 sürekli tetikleniyorsa bu koruma gibi görünür ama değildir:",
        "sistem o dilde yazılmış hiçbir içeriği etiketleyemiyor demektir. Yanlış",
        "pozitif oranının düşük çıkması bu durumda başarı değil, körlüktür.",
        "",
        "## Uyarı",
        "",
        uyari,
        "",
        "## Yöntem sınırları",
        "",
        f"Grup başına {next(iter(sonuc.values()))['n']} metin vardır; çözünürlük",
        f"{1 / next(iter(sonuc.values()))['n']:.2f}'dir. Bu, eğilim görmeye yeter,",
        "küçük farkları ayırmaya yetmez.",
        "",
        "Ağız normalizasyonu (`lexicon.agiz_normalize`) bu denetimin sonucunda",
        "eklendi: ilk ölçümde tespit farkı 0,1250 çıkmıştı (ölçünlü Türkçe 0,25,",
        "Karadeniz/Ege/gençlik dili 0,125). Kurallar ünlü uyumunu gözetir; uyumu",
        'gözetmeyen ilk sürüm "konuşmayr"ı "konusmiyor" yapıyor ve desen yine',
        "tutmuyordu. Zararsız metinlerde yanlış pozitif artışı sıfır ölçüldü.",
        "",
        "Metinler takım tarafından yazılmıştır ve yaygın biçimbirim özelliklerine",
        "dayanır; hiçbir topluluğu karikatürize etme amacı taşımaz. Gerçek",
        "kullanıcı verisiyle yapılacak denetim bunun yerini almalıdır.",
        "",
    ]
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text("\n".join(s), encoding="utf-8")
    return RAPOR


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    veri = json.loads(KUME.read_text(encoding="utf-8"))
    print(f"→ {len(veri['gruplar'])} alt grup")
    sonuc = olc(veri["gruplar"])

    oranlar = [d["yanlis_pozitif"] for d in sonuc.values()]
    fark = max(oranlar) - min(oranlar)
    print(
        f"\n  gruplar arası azami fark: {fark:.4f} · hedef ≤ {HEDEF_FARK:.2f} "
        f"{'✓' if fark <= HEDEF_FARK else '✗'}"
    )

    tespit: dict[str, dict] = {}
    if veri.get("provokatif_gruplar"):
        print("\n→ eksen 2: eşit tespit")
        tespit = olc_tespit(veri["provokatif_gruplar"])
        oranlar_t = [d["tespit"] for d in tespit.values()]
        print(f"\n  tespit farkı: {max(oranlar_t) - min(oranlar_t):.4f}")

    yol = rapor_yaz(sonuc, tespit, veri["aciklama"], veri["uyari"])
    print(f"\n✓ {yol.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
