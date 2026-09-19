#!/usr/bin/env python
"""M4 video değerlendirmesi — çalışırlık, dayanıklılık ve gecikme.

**Bu betik bir genelleme ölçümü DEĞİLDİR ve öyle raporlanamaz.** Elimizdeki tek
video kümesi modelin eğitim/doğrulama verisidir (ayrım bilinmiyor ·
scripts/data/kumeler/video_afet.json). Bu
kümede ölçülen yüksek bir başarım, modelin görmediği bir videoda da aynı şekilde
çalışacağını göstermez. Betik bu yüzden dört ayrı ve dar soruyu sorar:

    1. ÇALIŞIRLIK    ONNX aktarımı + depodaki ön işleme özgün Keras modelini doğru
                     yeniden üretiyor mu? Kendi eğitim kümesinde gerçek videoları
                     "gerçek" bulamayan bir kurulum yanlış kurulmuştur. Kabul
                     kapısı (`alan_ici_ozgulluk`) BUNU ölçer, başka bir şeyi değil.
    2. DAYANIKLILIK  Aynı videolar sosyal medyadaki dönüşümlerden geçince karar
                     değişiyor mu? Dönüştürülmüş video bayt düzeyinde modelin
                     gördüğü video değildir; ama içerik aynıdır, dolayısıyla bu
                     da genelleme kanıtı sayılmaz. Yalnızca KIRILGANLIĞI gösterir.
    3. DOĞRULAMA     Manifestte eğitimdeki doğrulama bölmesi işaretliyse
                     (`--dogrulama-listesi`), o bölme ayrıca raporlanır.
    4. GECİKME       Video başına uçtan uca süre (kare seçimi + çıkarım).

Gerçek bir genelleme ölçümü için modelin hiç görmediği, farklı kaynaklı gerçek
afet videoları ve farklı üreticilerden gelen sentetik videolar gerekir
(docs/metrikler/m4-video.md · "Eksik ölçüm").

Çıktı: docs/metrikler/m4-video.md · models/m4_video/kart.json ·
       docs/model-kartlari/m4-video.md
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.models.cards import Measurement, ModelCard  # noqa: E402
from krizkalkan_core.synthetic.video import MODEL_ADI, SentetikVideoModeli  # noqa: E402

MODEL_DIZINI = REPO_ROOT / "models" / MODEL_ADI
KUME = REPO_ROOT / "data" / "external" / "video_afet"
MANIFEST = REPO_ROOT / "scripts" / "data" / "kumeler" / "video_afet.json"
RAPOR = REPO_ROOT / "docs" / "metrikler" / "m4-video.md"
KART_DOC = REPO_ROOT / "docs" / "model-kartlari"

KUME_ADI = "Afet video kümesi (modelin eğitim/doğrulama verisi · ayrım bilinmiyor)"


@dataclass(slots=True)
class Sonuc:
    dosya: str
    etiket: int  # 1 = üretilmiş
    yon: str
    skor: float
    cekindi: bool
    sure_ms: float


# ────────────────────────── dönüşümler ──────────────────────────


def _bantla(kare, hedef_g: int, hedef_y: int):
    import cv2
    import numpy as np

    y, g = kare.shape[:2]
    olcek = min(hedef_g / g, hedef_y / y)
    yg, yy = round(g * olcek), round(y * olcek)
    tuval = np.zeros((hedef_y, hedef_g, 3), np.uint8)
    x0, y0 = (hedef_g - yg) // 2, (hedef_y - yy) // 2
    tuval[y0 : y0 + yy, x0 : x0 + yg] = cv2.resize(kare, (yg, yy))
    return tuval


def _kirp(kare, oran_g: int, oran_y: int, hedef_g: int, hedef_y: int):
    import cv2

    y, g = kare.shape[:2]
    if g / y > oran_g / oran_y:
        yeni = int(y * oran_g / oran_y)
        x0 = (g - yeni) // 2
        kare = kare[:, x0 : x0 + yeni]
    else:
        yeni = int(g * oran_y / oran_g)
        y0 = (y - yeni) // 2
        kare = kare[y0 : y0 + yeni]
    return cv2.resize(kare, (hedef_g, hedef_y))


def _sikistir(kare):
    import cv2

    y, g = kare.shape[:2]
    olcek = 360 / min(y, g)
    kucuk = cv2.resize(
        kare, (int(g * olcek) // 2 * 2, int(y * olcek) // 2 * 2), interpolation=cv2.INTER_AREA
    )
    _, bayt = cv2.imencode(".jpg", kucuk, [cv2.IMWRITE_JPEG_QUALITY, 35])
    return cv2.imdecode(bayt, cv2.IMREAD_COLOR)


#: Dönüşüm adı → (açıklama, kare işlevi). "yeniden_kodlama" kontrol koşuludur:
#: yalnızca mp4v ile yeniden yazmanın etkisini diğerlerinden ayırır.
DONUSUMLER: dict[str, tuple[str, Callable]] = {
    "yeniden_kodlama": ("kontrol · aynı kareler mp4v ile yeniden yazılır", lambda k: k),
    "dikey_kirpma": (
        "yatay video ortadan 9:16 kırpılır (Reels/TikTok)",
        lambda k: _kirp(k, 9, 16, 720, 1280),
    ),
    "dikey_bant": (
        "yatay video siyah bantla 9:16 çerçeveye konur",
        lambda k: _bantla(k, 720, 1280),
    ),
    "sikistirma": ("360p + JPEG kalite 35 (platform sıkıştırması)", _sikistir),
    "yatay_kirpma": ("dikey video ortadan 16:9 kırpılır", lambda k: _kirp(k, 16, 9, 1280, 720)),
}


def _donustur(kaynak: Path, hedef: Path, islev: Callable) -> None:
    import cv2

    okuyucu = cv2.VideoCapture(str(kaynak))
    fps = okuyucu.get(cv2.CAP_PROP_FPS) or 25.0
    yazici = None
    try:
        while True:
            okundu, kare = okuyucu.read()
            if not okundu:
                break
            kare = islev(kare)
            if yazici is None:
                yazici = cv2.VideoWriter(
                    str(hedef), cv2.VideoWriter_fourcc(*"mp4v"), fps, (kare.shape[1], kare.shape[0])
                )
            yazici.write(kare)
    finally:
        okuyucu.release()
        if yazici is not None:
            yazici.release()


# ────────────────────────── ölçüm ──────────────────────────


def _auc(skorlar: list[float], etiketler: list[int]) -> float:
    poz = [s for s, e in zip(skorlar, etiketler, strict=True) if e == 1]
    neg = [s for s, e in zip(skorlar, etiketler, strict=True) if e == 0]
    if not poz or not neg:
        return float("nan")
    kazanc = sum((p > n) + 0.5 * (p == n) for p in poz for n in neg)
    return kazanc / (len(poz) * len(neg))


def _kos(model: SentetikVideoModeli, videolar: list[dict], yol_fn=None) -> list[Sonuc]:
    sonuclar = []
    for i, v in enumerate(videolar, 1):
        yol = yol_fn(v) if yol_fn else KUME / v["dosya"]
        r = model.incele(yol)
        sonuclar.append(
            Sonuc(
                dosya=v["dosya"],
                etiket=int(v["etiket"] == "uretilmis"),
                yon=v["yon"],
                skor=r.uretim_skoru,
                cekindi=r.cekindi,
                sure_ms=r.sure_ms,
            )
        )
        if i % 50 == 0:
            print(f"  {i}/{len(videolar)}", flush=True)
    return sonuclar


def _ozet(sonuclar: list[Sonuc], esik: float) -> dict:
    gecerli = [s for s in sonuclar if not s.cekindi]
    gercek = [s for s in gecerli if s.etiket == 0]
    uretilmis = [s for s in gecerli if s.etiket == 1]
    return {
        "n": len(sonuclar),
        "cekinme": len(sonuclar) - len(gecerli),
        "n_gercek": len(gercek),
        "n_uretilmis": len(uretilmis),
        "ozgulluk": sum(s.skor <= esik for s in gercek) / len(gercek) if gercek else None,
        "duyarlilik": sum(s.skor > esik for s in uretilmis) / len(uretilmis) if uretilmis else None,
        "auc": _auc([s.skor for s in gecerli], [s.etiket for s in gecerli]),
        "yanlislar": [
            (s.dosya, round(s.skor, 4)) for s in gecerli if (s.skor > esik) != bool(s.etiket)
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sinir", type=int, default=150, help="sınıf başına video (0 = tümü)")
    ap.add_argument("--dayaniklilik", type=int, default=30, help="dönüşüm başına video")
    ap.add_argument("--tohum", type=int, default=13)
    ap.add_argument("--kart-yazma", action="store_true", help="yalnızca rapor üret")
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    videolar = manifest["videolar"]
    rng = random.Random(args.tohum)

    def ornekle(liste: list[dict], n: int) -> list[dict]:
        return list(liste) if n <= 0 or n >= len(liste) else rng.sample(liste, n)

    gercek = [v for v in videolar if v["etiket"] == "gercek"]
    uretilmis = [v for v in videolar if v["etiket"] == "uretilmis"]
    ornek = ornekle(gercek, args.sinir) + ornekle(uretilmis, args.sinir)

    model = SentetikVideoModeli(MODEL_DIZINI)
    esik = model.karar_esigi
    print(f"→ Model: {MODEL_DIZINI} · karar eşiği P(üretilmiş) > {esik}")

    # ── 1. Çalışırlık (alan içi) ──
    print(f"→ Alan içi: {len(ornek)} video")
    alan = _kos(model, ornek)
    alan_ozet = _ozet(alan, esik)
    dikey_gercek = [s for s in alan if s.etiket == 0 and s.yon == "dikey"]
    dikey_ozet = _ozet(dikey_gercek, esik) if dikey_gercek else None

    # ── 2. Dayanıklılık ──
    dayanim: dict[str, dict] = {}
    if args.dayaniklilik > 0:
        yatay_gercek = ornekle([v for v in gercek if v["yon"] == "yatay"], args.dayaniklilik)
        dikey_uretilmis = ornekle([v for v in uretilmis if v["yon"] == "dikey"], args.dayaniklilik)
        plan = {
            "yeniden_kodlama": yatay_gercek + dikey_uretilmis,
            "dikey_kirpma": yatay_gercek,
            "dikey_bant": yatay_gercek,
            "sikistirma": yatay_gercek + dikey_uretilmis,
            "yatay_kirpma": dikey_uretilmis,
        }
        with tempfile.TemporaryDirectory(prefix="kk-m4v-") as gecici:
            for ad, liste in plan.items():
                print(f"→ Dayanıklılık · {ad}: {len(liste)} video")
                islev = DONUSUMLER[ad][1]

                def yol_fn(v, islev=islev):
                    hedef = Path(gecici) / "x.mp4"
                    _donustur(KUME / v["dosya"], hedef, islev)
                    return hedef

                dayanim[ad] = _ozet(_kos(model, liste, yol_fn), esik)

    # ── 3. Eğitimdeki doğrulama bölmesi (varsa) ──
    dogrulama = [v for v in videolar if v.get("bolum") == "dogrulama"]
    dogrulama_ozet = None
    if dogrulama:
        print(f"→ Doğrulama bölmesi: {len(dogrulama)} video")
        dogrulama_ozet = _ozet(_kos(model, dogrulama), esik)

    sureler = [s.sure_ms for s in alan if not s.cekindi]
    gecikme = {
        "medyan_ms": round(statistics.median(sureler), 1),
        "p95_ms": round(sorted(sureler)[int(0.95 * (len(sureler) - 1))], 1),
    }

    _rapor_yaz(args, esik, alan_ozet, dikey_ozet, dayanim, dogrulama_ozet, gecikme)
    if not args.kart_yazma:
        _kart_guncelle(alan_ozet, dikey_ozet, dayanim, dogrulama_ozet, gecikme, esik)

    print(
        f"✓ alan içi özgüllük {alan_ozet['ozgulluk']:.4f} · duyarlılık "
        f"{alan_ozet['duyarlilik']:.4f} · AUC {alan_ozet['auc']:.4f} (n={alan_ozet['n']})"
    )
    return 0


# ────────────────────────── çıktılar ──────────────────────────


def _yuzde(x: float | None) -> str:
    return "—" if x is None else f"%{x * 100:.1f}".replace(".", ",")


def _rapor_yaz(args, esik, alan, dikey, dayanim, dogrulama, gecikme) -> None:
    satirlar = [
        "# M4 video — ölçüm raporu",
        "",
        f"*`scripts/eval/m4_video.py` tarafından üretildi · {datetime.now(UTC):%Y-%m-%d %H:%M} UTC · "
        f"tohum {args.tohum}. Elle düzenlenmez.*",
        "",
        "> **Bu rapordaki sayıların hiçbiri genelleme ölçüsü değildir.** Ölçüm kümesi "
        "modelin **eğitim/doğrulama verisidir**; hangi videonun hangi bölmede olduğu "
        "depoda kayıtlı değil. Model bu videoların hepsini ya da "
        "çoğunu eğitimde gördü. Aşağıdaki başarım, modelin görmediği bir videoda "
        "beklenecek başarım olarak **sunulamaz**.",
        "",
        f"Karar eşiği: P(üretilmiş) > {f'{esik:.2f}'.replace('.', ',')} (dağıtım "
        "yapılandırmasındaki P(gerçek) ≥ 0,45 eşiğinin karşılığı).",
        "",
        "## 1. Çalışırlık — kurulum özgün modeli doğru yeniden üretiyor mu?",
        "",
        "Kabul kapısı bu bölümdeki **özgüllüğü** okur. Kapının sorduğu soru dardır: ONNX "
        "aktarımı ve depodaki kare seçimi doğru mu? Hatalı bir ön işleme (BGR/RGB karışması, "
        "çift normalizasyon, farklı kare seçimi) gerçek videoları kendi eğitim kümesinde "
        'bile "üretilmiş" gösterir ve bu kapıdan geçemez.',
        "",
        "| Metrik | Değer | n |",
        "|---|---|---|",
        f"| Özgüllük (gerçek → gerçek) | {_yuzde(alan['ozgulluk'])} | {alan['n_gercek']} |",
        f"| Duyarlılık (üretilmiş → üretilmiş) | {_yuzde(alan['duyarlilik'])} | {alan['n_uretilmis']} |",
        f"| AUC | {alan['auc']:.4f} | {alan['n'] - alan['cekinme']} |".replace(".", ","),
        f"| Çekinme | {alan['cekinme']} | {alan['n']} |",
    ]
    if dikey:
        satirlar.append(
            f"| Özgüllük · doğal dikey gerçek videolar | {_yuzde(dikey['ozgulluk'])} | {dikey['n_gercek']} |"
        )
    if alan["yanlislar"]:
        satirlar += ["", "Yanlış sınıflananlar:", ""]
        satirlar += [f"- `{d}` · P(üretilmiş) {s:.4f}" for d, s in alan["yanlislar"]]

    if dayanim:
        satirlar += [
            "",
            "## 2. Dayanıklılık — sosyal medya dönüşümleri",
            "",
            "Aynı videolar dönüştürülüp yeniden ölçüldü. İçerik modelin eğitimde gördüğü "
            "içeriktir; bu tablo genelleme değil **kırılganlık** gösterir. Kontrol satırı "
            "yalnızca yeniden kodlamanın etkisini ayırır.",
            "",
            "| Dönüşüm | Açıklama | Gerçek → gerçek | Üretilmiş → üretilmiş |",
            "|---|---|---|---|",
        ]
        for ad, o in dayanim.items():
            gercek_h = f"{_yuzde(o['ozgulluk'])} (n={o['n_gercek']})" if o["n_gercek"] else "—"
            uret_h = (
                f"{_yuzde(o['duyarlilik'])} (n={o['n_uretilmis']})" if o["n_uretilmis"] else "—"
            )
            satirlar.append(f"| `{ad}` | {DONUSUMLER[ad][0]} | {gercek_h} | {uret_h} |")
        satirlar += [
            "",
            "**Okuma.** Eğitim kümesindeki *doğal* dikey gerçek videolarda model doğru "
            "çalışıyor (bölüm 1). Kırılganlık dikeyliğin kendisinden değil, yatay bir videonun "
            "**sonradan** yeniden çerçevelenmesinden geliyor. Model kareleri en-boy oranını "
            "korumadan 224×224'e ezer; kırpma ve bant, karelerin geometrisini eğitimde "
            "görülmemiş biçimde değiştirir. Sosyal medyada gerçek afet görüntüleri bu dönüşümle "
            'sık dolaşır: bu satırlar, gerçek bir videoya "üretilmiş" denmesinin en olası yolunu '
            "gösterir.",
        ]

    if dogrulama:
        satirlar += [
            "",
            "## Eğitimdeki doğrulama bölmesi",
            "",
            "Bu videolar eğitimde kullanılmadı. Ancak eşik ve en iyi kontrol noktası bu "
            "bölmede seçildiği için sayı hafif iyimserdir.",
            "",
            "| Metrik | Değer | n |",
            "|---|---|---|",
            f"| Özgüllük | {_yuzde(dogrulama['ozgulluk'])} | {dogrulama['n_gercek']} |",
            f"| Duyarlılık | {_yuzde(dogrulama['duyarlilik'])} | {dogrulama['n_uretilmis']} |",
            f"| AUC | {dogrulama['auc']:.4f} | {dogrulama['n']} |".replace(".", ","),
        ]

    satirlar += [
        "",
        "## Gecikme",
        "",
        f"Video başına uçtan uca (kare seçimi + ONNX çıkarımı, CPU): medyan "
        f"{gecikme['medyan_ms']:.0f} ms · p95 {gecikme['p95_ms']:.0f} ms. Hareket analizi "
        "videonun her karesini çözdüğü için süre video uzunluğuyla doğrusal artar.",
        "",
        "## Eksik ölçüm — genelleme",
        "",
        "Modelin görmediği videolarda ölçüm **yapılmadı**, çünkü böyle bir küme henüz yok. "
        "Yapılması gereken:",
        "",
        "1. Eğitim/doğrulama ayrımının dosya listesini depoya eklemek "
        "(`scripts/data/build_video_afet.py --dogrulama-listesi`). Bu, eğitimde "
        "kullanılmamış videolarda ilk dürüst sayıyı verir.",
        "2. Eğitim kümesiyle hiç örtüşmeyen bir test kümesi kurmak: farklı kaynaktan gerçek "
        "afet videoları (ör. Wikimedia Commons, kamu kurumu arşivleri) ve kümede olmayan "
        "üreticilerle üretilmiş afet videoları. M4 görüntü modelindeki gibi **üretici bazında** "
        "ayrım yapılmalı: görülmemiş üreticide duyarlılık, literatürdeki asıl açıktır.",
        "",
    ]
    RAPOR.write_text("\n".join(satirlar), encoding="utf-8")
    print(f"✓ {RAPOR.relative_to(REPO_ROOT)}")


def _kart_guncelle(alan, dikey, dayanim, dogrulama, gecikme, esik) -> None:
    """Ölçümleri model kartına işler — kabul kapısı bu kartı okur."""
    kart = ModelCard.load(MODEL_DIZINI)
    if kart is None:
        print(f"🔴 model kartı yok: {MODEL_DIZINI / 'kart.json'} — önce aktarım betiği")
        return

    notu = "eğitim/doğrulama verisi · genelleme ölçüsü DEĞİL"
    olcumler = [
        Measurement(
            "alan_ici_ozgulluk",
            round(alan["ozgulluk"], 4),
            KUME_ADI,
            alan["n_gercek"],
            f"kabul kapısı · çalışırlık kontrolü · eşik P(üretilmiş) > {esik:.2f} · {notu}",
        ),
        Measurement(
            "alan_ici_duyarlilik", round(alan["duyarlilik"], 4), KUME_ADI, alan["n_uretilmis"], notu
        ),
        Measurement(
            "alan_ici_auc", round(alan["auc"], 4), KUME_ADI, alan["n"] - alan["cekinme"], notu
        ),
    ]
    if dikey:
        olcumler.append(
            Measurement(
                "alan_ici_ozgulluk_dogal_dikey",
                round(dikey["ozgulluk"], 4),
                KUME_ADI,
                dikey["n_gercek"],
                notu,
            )
        )
    for ad in ("dikey_kirpma", "dikey_bant", "sikistirma"):
        if ad in dayanim and dayanim[ad]["ozgulluk"] is not None:
            olcumler.append(
                Measurement(
                    f"dayaniklilik_ozgulluk_{ad}",
                    round(dayanim[ad]["ozgulluk"], 4),
                    f"{KUME_ADI} · {DONUSUMLER[ad][0]}",
                    dayanim[ad]["n_gercek"],
                    "kırılganlık ölçüsü · içerik eğitimde görüldü",
                )
            )
    if "yatay_kirpma" in dayanim and dayanim["yatay_kirpma"]["duyarlilik"] is not None:
        olcumler.append(
            Measurement(
                "dayaniklilik_duyarlilik_yatay_kirpma",
                round(dayanim["yatay_kirpma"]["duyarlilik"], 4),
                f"{KUME_ADI} · {DONUSUMLER['yatay_kirpma'][0]}",
                dayanim["yatay_kirpma"]["n_uretilmis"],
                "kırılganlık ölçüsü · içerik eğitimde görüldü",
            )
        )
    if dogrulama:
        olcumler.append(
            Measurement(
                "dogrulama_auc",
                round(dogrulama["auc"], 4),
                "Eğitimdeki doğrulama bölmesi",
                dogrulama["n"],
                "eğitimde kullanılmadı · eşik bu bölmede seçildi",
            )
        )
    olcumler.append(
        Measurement(
            "gecikme_medyan_ms",
            gecikme["medyan_ms"],
            KUME_ADI,
            alan["n"] - alan["cekinme"],
            "CPU · uçtan uca",
        )
    )
    kart.measurements = olcumler

    sinirlar = [
        "Genelleme ÖLÇÜLMEDİ. Tüm ölçümler modelin eğitim/doğrulama verisinde yapıldı; "
        "görülmemiş videoda başarım bilinmiyor.",
    ]
    if "dikey_kirpma" in dayanim:
        sinirlar.append(
            "Yatay gerçek bir video sonradan dikeye kırpıldığında ya da bantlandığında "
            '"üretilmiş" sanılma oranı belirgin biçimde artıyor (özgüllük '
            f"{_yuzde(dayanim['dikey_kirpma']['ozgulluk'])} kırpma · "
            f"{_yuzde(dayanim['dikey_bant']['ozgulluk'])} bant). Sosyal medyada yaygın bir dönüşümdür."
        )
    sinirlar += [
        "Kareler en-boy oranı korunmadan 224×224'e ezilir; bu, eğitimdeki ön işlemedir ve "
        "değiştirilemez (model yeniden eğitilmeden).",
        "Ses kanalı incelenmez; model yalnızca görüntüye bakar.",
        f"{180} sn'den uzun videolarda çekinilir (hareket analizi her kareyi çözer).",
        "Eğitim kümesindeki üretici araçları bilinmiyor; kümede olmayan bir üreticinin "
        "videolarında duyarlılık bilinmiyor.",
    ]
    kart.known_limits = sinirlar
    kart.out_of_scope = [
        "Tek başına kanıt olarak kullanılamaz; çıktı olasılıksaldır ve füzyonda diğer "
        "sinyallerle birlikte değerlendirilir.",
        "Yüz değiştirme (face-swap) deepfake'leri için eğitilmedi; afet sahnesi üretimine yöneliktir.",
    ]
    kart.save(MODEL_DIZINI)
    yol = kart.write_markdown(KART_DOC)
    print(f"✓ {MODEL_DIZINI.relative_to(REPO_ROOT)}/kart.json · {yol.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
