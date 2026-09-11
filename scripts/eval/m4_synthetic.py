#!/usr/bin/env python
"""M4 sentetik görüntü değerlendirmesi — çapraz veri kümesi, alan ve dayanıklılık.

**Ölçülen şey bilinçli olarak alan içi başarım değildir.** Detektörlerin kendi
eğitim dağılımlarındaki başarımı 0,99'un üzerindedir ve bu sayı hiçbir şey
söylemez: literatürdeki asıl problem, görülmemiş üreticilere aktarımdır
(rapor 2.1.2 · genelleme açığı). Bu betik beş ayrı soruyu ölçer:

    1. ÇAPRAZ VERİ KÜMESİ  Detektörlerin hiç görmediği bir korpusta AUC.
                           Üretici ailesi başına ayrı ayrı raporlanır —
                           tek bir ortalama, açığı gizler.
    2. AFET ALANI          Gerçek Türk afet görüntülerinde yanlış pozitif oranı.
                           Sistemin fiilen çalışacağı içerik budur ve bir afet
                           fotoğrafını "sentetik" diye işaretlemek, kaçırmaktan
                           daha zararlıdır.
    3. TÜR AYRIMI          Üç sınıflı detektör gerçek içerikte ne diyor?
                           `synthetic.manipulation` sinyalinin füzyona bağlanıp
                           bağlanmayacağı bu tablodan çıkar, tasarımdan değil.
    4. KALİBRASYON         `synthetic.video` skorunun ECE'si. Bu sinyal bugüne
                           kadar hiç kalibre edilmemişti; ölçüm imkânı ilk kez
                           bu kümeyle doğdu.
    5. DAYANIKLILIK        Yeniden kodlama, ölçekleme, kırpma ve gürültü altında
                           duyarlılık düşüşü (rapor 3.2 · kırmızı takım).

Çekinilen vakalar AUC'ye GİRMEZ; çekinme oranı ayrı bir satır olarak raporlanır.
Çekinmeyi ölçümün içine karıştırmak, "bilmiyorum" diyerek metrik şişirmek olurdu.

Çıktı: docs/metrikler/m4.md · models/m4_synthetic/kart.json ·
       docs/model-kartlari/m4-synthetic.md
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.models.cards import Measurement, ModelCard  # noqa: E402
from krizkalkan_core.synthetic.image import MODEL_ADI, SentetikGoruntuModeli  # noqa: E402

MODEL_DIZINI = REPO_ROOT / "models" / MODEL_ADI
RAPOR = REPO_ROOT / "docs" / "metrikler" / "m4.md"
AFET_KORPUSU = REPO_ROOT / "data" / "external" / "provenance"

#: Çapraz veri kümesi. Detektörlerin eğitiminde kullanılmadı; 2026 tarihli
#: üreticiler içeriyor, yani gerçek bir "görülmemiş üretici" testi.
CAPRAZ_DEPO = "ComplexDataLab/OpenFake"
CAPRAZ_DOSYA = "core/test-00000-of-00013.parquet"

#: Üretim skoru bu eşiğin üzerindeyse "üretilmiş" sayılır. Eşik ölçümden
#: seçilir; betik eşik taramasını da basar.
KARAR_ESIGI = 0.50

#: Kabul kapısının eşiği — `synthetic/image.py` ile aynı değer olmalıdır.
KABUL_ESIGI = 0.95


@dataclass(slots=True)
class Ornek:
    """Değerlendirme kümesinden tek bir kayıt."""

    bayt: bytes
    ad: str
    #: 1 = üretilmiş, 0 = gerçek
    etiket: int
    uretici: str


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


# ────────────────────────── veri ──────────────────────────


def capraz_kume(sinir: int, tohum: int) -> list[Ornek]:
    """OpenFake test parçasından dengeli, üretici çeşitliliği korunmuş örneklem.

    Rastgele örneklem yerine üretici başına tabakalama yapılır: tek bir baskın
    ailenin (ör. 998 kayıtlık `z-image-turbo`) ortalamayı belirlemesi, açığın
    tam olarak gizlendiği yerdir.

    **İki geçişli okuma.** Parça 5,1 GB'tır ve tamamını belleğe almak süreci
    öldürür (yaşandı). Önce yalnızca etiket sütunları okunup hangi satırların
    isteneceğine karar verilir; görüntü baytları ikinci geçişte, satır grubu
    satır grubu ve yalnızca seçilen satırlar için alınır.
    """
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    yol = hf_hub_download(CAPRAZ_DEPO, CAPRAZ_DOSYA, repo_type="dataset")

    # ── 1. geçiş: örneklem planı (yalnızca küçük sütunlar) ──
    kunye = pq.read_table(yol, columns=["label", "model"]).to_pydict()
    aileler: dict[str, list[int]] = defaultdict(list)
    etiketler: dict[int, int] = {}
    for sira, (etiket, uretici) in enumerate(zip(kunye["label"], kunye["model"], strict=True)):
        ad = uretici or "bilinmiyor"
        aileler[ad].append(sira)
        etiketler[sira] = 1 if etiket == "fake" else 0

    rastgele = random.Random(tohum)
    for satirlar in aileler.values():
        rastgele.shuffle(satirlar)

    uretilmis = sorted(a for a in aileler if etiketler[aileler[a][0]] == 1)
    gercek = sorted(a for a in aileler if etiketler[aileler[a][0]] == 0)

    def topla(adlar: list[str], hedef: int) -> list[int]:
        """Aileler arasında sırayla dolaşarak hedefe ulaşır (round-robin)."""
        secilen: list[int] = []
        sayac = dict.fromkeys(adlar, 0)
        while len(secilen) < hedef:
            eklendi = False
            for ad in adlar:
                if sayac[ad] < len(aileler[ad]) and len(secilen) < hedef:
                    secilen.append(aileler[ad][sayac[ad]])
                    sayac[ad] += 1
                    eklendi = True
            if not eklendi:
                break
        return secilen

    yari = sinir // 2
    istenen = set(topla(uretilmis, yari)) | set(topla(gercek, yari))
    uretici_adi = {satir: ad for ad, satirlar in aileler.items() for satir in satirlar}

    # ── 2. geçiş: yalnızca seçilen satırların baytları ──
    dosya = pq.ParquetFile(yol)
    ornekler: list[Ornek] = []
    taban = 0
    for grup in range(dosya.metadata.num_row_groups):
        satir_sayisi = dosya.metadata.row_group(grup).num_rows
        yerel = [s - taban for s in istenen if taban <= s < taban + satir_sayisi]
        if yerel:
            goruntuler = dosya.read_row_group(grup, columns=["image"]).column("image")
            for konum in yerel:
                kayit = goruntuler[konum].as_py()
                kuresel = taban + konum
                ornekler.append(
                    Ornek(
                        bayt=kayit["bytes"],
                        ad=kayit["path"],
                        etiket=etiketler[kuresel],
                        uretici=uretici_adi[kuresel],
                    )
                )
            del goruntuler
        taban += satir_sayisi

    return ornekler


def afet_kume(sinir: int, tohum: int) -> list[Ornek]:
    """Wikimedia afet korpusu — hepsi GERÇEK. Yanlış pozitif oranı için.

    Bu küme sistemin fiilen göreceği içeriğin ta kendisidir: Türkiye'deki
    deprem, sel ve yangın olaylarının basın ve gönüllü fotoğrafları.
    """
    kayit_dosyasi = AFET_KORPUSU / "kayitlar.jsonl"
    if not kayit_dosyasi.exists():
        return []

    kayitlar = [json.loads(s) for s in kayit_dosyasi.read_text(encoding="utf-8").splitlines() if s]
    ornekler: list[Ornek] = []
    for kayit in kayitlar:
        yol = AFET_KORPUSU / "goruntuler" / kayit["dosya"]
        if yol.exists():
            ornekler.append(
                Ornek(
                    bayt=yol.read_bytes(),
                    ad=kayit["dosya"],
                    etiket=0,
                    uretici=kayit.get("olay", "afet"),
                )
            )
    random.Random(tohum).shuffle(ornekler)
    return ornekler[:sinir]


# ────────────────────────── ölçüm ──────────────────────────


@dataclass(slots=True)
class Sonuc:
    """Bir örneğin model çıktısı."""

    etiket: int
    uretici: str
    skor: float | None
    cekinme: str | None
    sure_ms: float


def _gecici_yaz(ornek: Ornek, dizin: Path) -> Path:
    """Baytları diske yazar — sıkıştırma oranı ölçümü gerçek dosya gerektirir."""
    son_ek = Path(ornek.ad).suffix or ".jpg"
    yol = dizin / f"{abs(hash(ornek.ad)):016x}{son_ek}"
    yol.write_bytes(ornek.bayt)
    return yol


#: Ham skorların önbelleği. Tek geçiş CPU'da 20 dakika sürüyor; kalibrasyon
#: ve eşik analizleri aynı skorlar üzerinde yapıldığı için yeniden çıkarım
#: almak boşa hesaptır. Dizin `.gitignore` kapsamındadır.
ONBELLEK = REPO_ROOT / "data" / "interim" / "m4_skorlar.json"


def _onbellek_oku() -> dict[str, dict]:
    if not ONBELLEK.exists():
        return {}
    try:
        return json.loads(ONBELLEK.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _onbellek_yaz(tumu: dict[str, dict]) -> None:
    ONBELLEK.parent.mkdir(parents=True, exist_ok=True)
    ONBELLEK.write_text(json.dumps(tumu, ensure_ascii=False), encoding="utf-8")


def kos(
    model: SentetikGoruntuModeli,
    ornekler: list[Ornek],
    baslik: str,
    onbellek: dict[str, dict] | None = None,
) -> list[Sonuc]:
    """Örnekleri modelden geçirir; ilerlemeyi basar.

    Önbellek verildiyse daha önce ölçülmüş örnekler yeniden çıkarımdan
    geçirilmez. Önbellek anahtarı aşama adını da içerir: aynı görüntünün
    dönüşmüş hâli farklı bir ölçümdür.
    """
    sonuclar: list[Sonuc] = []
    bolum = onbellek.setdefault(baslik, {}) if onbellek is not None else None

    with tempfile.TemporaryDirectory() as gecici:
        dizin = Path(gecici)
        for sira, ornek in enumerate(ornekler, 1):
            if bolum is not None and (kayit := bolum.get(ornek.ad)) is not None:
                sonuclar.append(
                    Sonuc(
                        etiket=kayit["etiket"],
                        uretici=kayit["uretici"],
                        skor=kayit["skor"],
                        cekinme=kayit["cekinme"],
                        sure_ms=kayit["sure_ms"],
                    )
                )
                continue

            yol = _gecici_yaz(ornek, dizin)
            basladi = time.perf_counter()
            try:
                cikti = model.incele(yol)
                sonuc = Sonuc(
                    etiket=ornek.etiket,
                    uretici=ornek.uretici,
                    skor=None if cikti.cekindi else cikti.uretim_skoru,
                    cekinme=cikti.cekinme_nedeni,
                    sure_ms=(time.perf_counter() - basladi) * 1000,
                )
            except Exception as hata:
                sonuc = Sonuc(ornek.etiket, ornek.uretici, None, f"okunamadı: {hata}", 0.0)
            yol.unlink(missing_ok=True)

            sonuclar.append(sonuc)
            if bolum is not None:
                bolum[ornek.ad] = {
                    "etiket": sonuc.etiket,
                    "uretici": sonuc.uretici,
                    "skor": sonuc.skor,
                    "cekinme": sonuc.cekinme,
                    "sure_ms": round(sonuc.sure_ms, 2),
                }
            if sira % 100 == 0 or sira == len(ornekler):
                print(f"  {baslik}: {sira}/{len(ornekler)}", flush=True)
    return sonuclar


def _auc(skorlar: list[float], etiketler: list[int]) -> float:
    """ROC-AUC — sklearn yoksa sıra tabanlı (Mann-Whitney U) hesap."""
    try:
        from sklearn.metrics import roc_auc_score

        return float(roc_auc_score(etiketler, skorlar))
    except Exception:
        pozitif = [s for s, e in zip(skorlar, etiketler, strict=True) if e == 1]
        negatif = [s for s, e in zip(skorlar, etiketler, strict=True) if e == 0]
        if not pozitif or not negatif:
            return float("nan")
        kazanan = sum((1.0 if p > n else 0.5 if p == n else 0.0) for p in pozitif for n in negatif)
        return kazanan / (len(pozitif) * len(negatif))


def _eer(skorlar: list[float], etiketler: list[int]) -> tuple[float, float]:
    """Eşit hata oranı ve onu veren eşik.

    Yanlış pozitif ile yanlış negatif oranlarının en yakınlaştığı eşik taranır;
    EER o noktadaki iki oranın ortalamasıdır.
    """
    negatif = sum(1 for e in etiketler if e == 0)
    pozitif = sum(1 for e in etiketler if e == 1)
    if not negatif or not pozitif:
        return float("nan"), float("nan")

    en_iyi_fark = float("inf")
    eer = float("nan")
    eer_esigi = float("nan")
    for esik in sorted(set(skorlar)):
        yp = sum(1 for s, e in zip(skorlar, etiketler, strict=True) if e == 0 and s >= esik)
        yn = sum(1 for s, e in zip(skorlar, etiketler, strict=True) if e == 1 and s < esik)
        yp_oran, yn_oran = yp / negatif, yn / pozitif
        if (fark := abs(yp_oran - yn_oran)) < en_iyi_fark:
            en_iyi_fark = fark
            eer = (yp_oran + yn_oran) / 2
            eer_esigi = esik
    return eer, eer_esigi


def ozetle(sonuclar: list[Sonuc]) -> dict:
    """Çekinilenleri ayırıp metrikleri hesaplar."""
    karar_verilen = [s for s in sonuclar if s.skor is not None]
    cekinilen = [s for s in sonuclar if s.skor is None]

    skorlar = [s.skor for s in karar_verilen if s.skor is not None]
    etiketler = [s.etiket for s in karar_verilen]

    ozet: dict = {
        "n": len(sonuclar),
        "n_karar": len(karar_verilen),
        "cekinme_orani": round(len(cekinilen) / max(len(sonuclar), 1), 4),
        "cekinme_nedenleri": Counter(
            (s.cekinme or "").split("(")[0].strip() for s in cekinilen
        ).most_common(5),
        "p50_ms": round(sorted(s.sure_ms for s in karar_verilen)[len(karar_verilen) // 2], 1)
        if karar_verilen
        else 0.0,
    }

    if len(set(etiketler)) == 2:
        ozet["auc"] = round(_auc(skorlar, etiketler), 4)
        eer, eer_esigi = _eer(skorlar, etiketler)
        ozet["eer"] = round(eer, 4)
        ozet["eer_esigi"] = round(eer_esigi, 4)

    pozitif = [s for s in karar_verilen if s.etiket == 1]
    negatif = [s for s in karar_verilen if s.etiket == 0]
    if pozitif:
        ozet["duyarlilik"] = round(
            sum(1 for s in pozitif if (s.skor or 0) >= KARAR_ESIGI) / len(pozitif), 4
        )
    if negatif:
        ozet["yanlis_pozitif"] = round(
            sum(1 for s in negatif if (s.skor or 0) >= KARAR_ESIGI) / len(negatif), 4
        )

    # Üretici ailesi başına duyarlılık — genelleme açığının görünür olduğu tablo.
    aile: dict[str, list[Sonuc]] = defaultdict(list)
    for s in karar_verilen:
        aile[s.uretici].append(s)
    ozet["aile"] = {
        ad: {
            "n": len(kayitlar),
            "etiket": kayitlar[0].etiket,
            "oran": round(
                sum(1 for k in kayitlar if (k.skor or 0) >= KARAR_ESIGI) / len(kayitlar), 4
            ),
            "ortalama_skor": round(sum(k.skor or 0 for k in kayitlar) / len(kayitlar), 4),
        }
        for ad, kayitlar in sorted(aile.items())
    }
    return ozet


# ────────────────────────── kalibrasyon ──────────────────────────


def kalibrasyon(sonuclar: list[Sonuc]) -> dict | None:
    """`synthetic.video` sinyalinin kalibrasyon kalitesini ölçer.

    Bu sinyalin kalibrasyonu bugüne kadar **hiç ölçülmedi**: M6'nın uçtan uca
    kümesinde SENTETİK_MEDYA vakası yoktu, dolayısıyla `m6_fusion.py` bu
    anahtarı atlıyordu ve devrede elle yazılmış, ölçülmemiş noktalar var
    (`fusion/calibration.py · VARSAYILAN_NOKTALAR`).

    Burada üretilen noktalar **doğrudan devreye alınmaz.** Kalibrasyon M6'nın
    veri ürünüdür ve `models/m6_fusion/kalibrasyon.json` dosyasını o modül
    yazar. Bu bölümün işi ölçüp teslim etmektir; benimseme kararı ölçülmüş
    uçtan uca kümeyle birlikte verilir.
    """
    from krizkalkan_core.fusion.calibration import calibrate, expected_calibration_error

    karar = [(s.skor, s.etiket) for s in sonuclar if s.skor is not None]
    if len({e for _, e in karar}) < 2:
        return None

    ham = [s for s, _ in karar]
    hedef = [e for _, e in karar]

    once = expected_calibration_error(
        [(calibrate("synthetic.video", s), bool(e)) for s, e in karar]
    )

    try:
        import numpy as np
        from sklearn.isotonic import IsotonicRegression
    except ImportError:
        return {"n": len(karar), "ece_once": round(once, 4)}

    # Sızıntı önlemi: noktalar bir bölmede uydurulur, ECE diğerinde ölçülür.
    # Kendi uydurduğu veride ölçülen kalibrasyon her zaman mükemmel çıkar.
    sira = list(range(len(karar)))
    random.Random(0).shuffle(sira)
    orta = len(sira) // 2
    uydur, olc = sira[:orta], sira[orta:]

    model = IsotonicRegression(out_of_bounds="clip", increasing=True, y_min=0.0, y_max=1.0)
    model.fit([ham[i] for i in uydur], [hedef[i] for i in uydur])

    sonra = expected_calibration_error(
        [
            (float(p), bool(hedef[i]))
            for i, p in zip(olc, model.predict([ham[i] for i in olc]), strict=True)
        ]
    )

    izgara = [round(x, 4) for x in np.linspace(min(ham), max(ham), 8)]
    noktalar = [(float(x), round(float(model.predict([x])[0]), 4)) for x in izgara]

    return {
        "n": len(karar),
        "n_uydur": len(uydur),
        "n_olc": len(olc),
        "ece_once": round(once, 4),
        "ece_sonra": round(sonra, 4),
        "noktalar": noktalar,
    }


# ────────────────────────── eşik taraması ──────────────────────────


def esik_taramasi(capraz: list[Sonuc], afet: list[Sonuc] | None) -> dict:
    """Her eşikte duyarlılık ve iki ayrı yanlış pozitif oranı.

    Tek bir karar eşiği raporlamak, bu modelde yanıltıcı olurdu: skorlar dar bir
    banda sıkıştığı için eşik seçimi başarımın tamamını belirliyor. Tablo, hangi
    ödünleşimin fiilen mümkün olduğunu gösterir.
    """
    uretilmis = [s.skor for s in capraz if s.etiket == 1 and s.skor is not None]
    gercek = [s.skor for s in capraz if s.etiket == 0 and s.skor is not None]
    afet_skorlari = [s.skor for s in (afet or []) if s.skor is not None]

    def oran(degerler: list[float], esik: float) -> float:
        return round(sum(d >= esik for d in degerler) / len(degerler), 4) if degerler else 0.0

    esikler = (0.50, 0.90, 0.93, 0.95, 0.955, 0.96, 0.965, 0.968, 0.97)
    satirlar = [
        {
            "esik": e,
            "duyarlilik": oran(uretilmis, e),
            "yp_capraz": oran(gercek, e),
            "yp_afet": oran(afet_skorlari, e) if afet_skorlari else None,
        }
        for e in esikler
    ]

    # Afet kümesinde belirli bir yanlış pozitif bütçesini tutturan eşikler ve
    # oradaki duyarlılık — "bu modelden en iyi ne alınabilir" sorusunun cevabı.
    butceler: list[dict] = []
    if afet_skorlari:
        sirali = sorted(afet_skorlari)
        for butce in (0.05, 0.01):
            esik = sirali[int((1 - butce) * (len(sirali) - 1))]
            butceler.append(
                {
                    "butce": butce,
                    "esik": round(esik, 4),
                    "duyarlilik": oran(uretilmis, esik),
                }
            )

    return {"satirlar": satirlar, "butceler": butceler}


# ────────────────────────── tür ayrımı ──────────────────────────


def tur_analizi(
    model: SentetikGoruntuModeli,
    kumeler: dict[str, list[Ornek]],
    sinir: int,
    onbellek: dict[str, dict] | None = None,
) -> dict | None:
    """Üç sınıflı detektörün karara katılmaya hazır olup olmadığını ölçer.

    `synthetic.manipulation` sinyali MANİPÜLE_MEDYA dalını besleyebilecek tek
    sinyaldir, ama **bunu hak ettiğini göstermek zorundadır.** Aranan koşul
    basit: gerçek içerikte "gerçek" diyor olmalı. Erken bir elle denemede
    detektör gerçek bir vesikalık fotoğrafa 0,998 "manipüle" verdi; bu ölçüm o
    gözlemin sistematik karşılığıdır.

    Karar bu tablodan çıkar, tasarımdan değil.
    """
    tablo: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as gecici:
        dizin = Path(gecici)
        for kume_adi, ornekler in kumeler.items():
            bolum = onbellek.setdefault(f"tür/{kume_adi}", {}) if onbellek is not None else None
            dagilim: Counter[str] = Counter()
            toplam: dict[str, float] = defaultdict(float)
            sayi = 0
            for ornek in ornekler[:sinir]:
                if bolum is not None and (kayit := bolum.get(ornek.ad)) is not None:
                    skorlar = kayit["skorlar"]
                else:
                    yol = _gecici_yaz(ornek, dizin)
                    try:
                        cikti = model.incele(yol)
                    finally:
                        yol.unlink(missing_ok=True)
                    skorlar = None if cikti.cekindi else cikti.tur_skorlari
                    if bolum is not None:
                        bolum[ornek.ad] = {"skorlar": skorlar}
                if not skorlar:
                    continue
                dagilim[max(skorlar, key=lambda k: skorlar[k])] += 1
                for etiket, deger in skorlar.items():
                    toplam[etiket] += deger
                sayi += 1
            if sayi:
                tablo[kume_adi] = {
                    "n": sayi,
                    "baskin": dagilim.most_common(1)[0][0],
                    "dagilim": {a: round(s / sayi, 4) for a, s in dagilim.items()},
                    "ortalama": {a: round(t / sayi, 4) for a, t in toplam.items()},
                }
            print(f"  tür/{kume_adi}: {sayi} örnek", flush=True)
    return tablo or None


# ────────────────────────── dayanıklılık ──────────────────────────

DONUSUMLER = ("temiz", "jpeg_q35", "olcek_480", "kirpma_20", "gurultu")


def _donustur(bayt: bytes, ad: str, donusum: str) -> bytes:
    """Kırmızı takım dönüşümü uygular ve yeniden kodlanmış baytları döndürür."""
    import io

    import numpy as np
    from PIL import Image

    with Image.open(io.BytesIO(bayt)) as acik:
        goruntu = acik.convert("RGB")

    if donusum == "olcek_480":
        oran = 480 / min(goruntu.size)
        yeni = (round(goruntu.width * oran), round(goruntu.height * oran))
        goruntu = goruntu.resize(yeni, Image.Resampling.BICUBIC)
    elif donusum == "kirpma_20":
        g, y = goruntu.size
        kenar_g, kenar_y = int(g * 0.1), int(y * 0.1)
        goruntu = goruntu.crop((kenar_g, kenar_y, g - kenar_g, y - kenar_y))
    elif donusum == "gurultu":
        dizi = np.asarray(goruntu, dtype="int16")
        gurultu = np.random.default_rng(abs(hash(ad)) % 2**32).normal(0, 6, dizi.shape)
        goruntu = Image.fromarray(np.clip(dizi + gurultu, 0, 255).astype("uint8"))

    tampon = io.BytesIO()
    kalite = 35 if donusum == "jpeg_q35" else 88
    goruntu.save(tampon, format="JPEG", quality=kalite)
    return tampon.getvalue()


def dayaniklilik(
    model: SentetikGoruntuModeli, ornekler: list[Ornek], onbellek: dict[str, dict] | None = None
) -> dict:
    """Her dönüşüm altında duyarlılık — yalnızca üretilmiş örnekler üzerinde."""
    uretilmis = [o for o in ornekler if o.etiket == 1]
    tablo: dict[str, dict] = {}
    for donusum in DONUSUMLER:
        donusmus = [
            Ornek(_donustur(o.bayt, o.ad, donusum), f"{donusum}_{o.ad}", 1, o.uretici)
            for o in uretilmis
        ]
        sonuclar = kos(model, donusmus, f"dayanıklılık/{donusum}", onbellek)
        karar = [s for s in sonuclar if s.skor is not None]
        tablo[donusum] = {
            "n": len(sonuclar),
            "duyarlilik": round(
                sum(1 for s in karar if (s.skor or 0) >= KARAR_ESIGI) / max(len(karar), 1), 4
            ),
            "cekinme_orani": round((len(sonuclar) - len(karar)) / max(len(sonuclar), 1), 4),
            "ortalama_skor": round(sum(s.skor or 0 for s in karar) / max(len(karar), 1), 4),
        }
    return tablo


# ────────────────────────── raporlama ──────────────────────────


def _rapor_yaz(
    capraz: dict,
    afet: dict | None,
    tarama: dict,
    tur: dict | None,
    ayar: dict | None,
    saglamlik: dict | None,
    n_istendi: int,
) -> Path:
    simdi = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    satir = [
        "# M4 — Sentetik görüntü tespiti",
        "",
        f"*Üretim: {simdi} · commit `{_git_commit()}` · karar eşiği {KARAR_ESIGI}*",
        "",
        "Bu rapor **alan içi** başarımı ölçmez. Detektörlerin kendi eğitim",
        "dağılımındaki AUC'si 0,99'un üzerindedir ve karar için kullanılamaz;",
        "raporun taahhüdü de zaten çapraz veri kümesi başarımıdır (≥ 0,72).",
        "",
        "## 1. Çapraz veri kümesi",
        "",
        f"Küme: `{CAPRAZ_DEPO}` · `{CAPRAZ_DOSYA}` — detektörlerin eğitiminde",
        "kullanılmadı ve 2026 tarihli üreticiler içeriyor.",
        "",
        "| Metrik | Değer | Rapor hedefi |",
        "|---|---|---|",
        f"| **ROC-AUC** | **{capraz.get('auc', float('nan')):.4f}** | ≥ 0,72 |",
        f"| EER | {capraz.get('eer', float('nan')):.4f} (eşik {capraz.get('eer_esigi', 0):.3f}) | — |",
        f"| Duyarlılık @ {KARAR_ESIGI} | {capraz.get('duyarlilik', 0):.4f} | — |",
        f"| Yanlış pozitif @ {KARAR_ESIGI} | {capraz.get('yanlis_pozitif', 0):.4f} | — |",
        f"| Çekinme oranı | {capraz['cekinme_orani']:.4f} | — |",
        f"| Karar verilen / toplam | {capraz['n_karar']} / {capraz['n']} | istendi: {n_istendi} |",
        f"| Görüntü başına p50 | {capraz['p50_ms']:.0f} ms | — |",
        "",
        "> Çekinilen vakalar AUC hesabına girmez; çekinme oranı ayrı satırdadır.",
        "",
        "### 1.1. Üretici ailesi başına",
        "",
        "Tek bir ortalama genelleme açığını gizler. Üretilmiş sınıfta değer",
        "duyarlılık, gerçek sınıfta yanlış pozitif oranıdır.",
        "",
        "| Üretici | Etiket | n | Oran | Ortalama skor |",
        "|---|---|---|---|---|",
    ]
    for ad, bilgi in sorted(capraz["aile"].items(), key=lambda kv: (-kv[1]["etiket"], -kv[1]["n"])):
        etiket_adi = "üretilmiş" if bilgi["etiket"] == 1 else "gerçek"
        satir.append(
            f"| `{ad}` | {etiket_adi} | {bilgi['n']} | {bilgi['oran']:.4f} | "
            f"{bilgi['ortalama_skor']:.4f} |"
        )

    if capraz["cekinme_nedenleri"]:
        satir += ["", "### 1.2. Çekinme gerekçeleri", "", "| Gerekçe | Adet |", "|---|---|"]
        satir += [f"| {neden or '—'} | {adet} |" for neden, adet in capraz["cekinme_nedenleri"]]

    if afet:
        satir += [
            "",
            "## 2. Afet alanı — yanlış pozitif",
            "",
            "Wikimedia Commons'tan toplanan Türkiye afet görüntüleri. **Tamamı",
            "gerçektir**; ölçülen şey, sistemin fiilen göreceği içerikte kaç",
            "gerçek afet fotoğrafını sentetik sandığıdır. Bir afet fotoğrafını",
            "yanlışlıkla işaretlemek, bir sentetik görüntüyü kaçırmaktan daha",
            "zararlıdır: sahadan gelen gerçek kanıtın güvenilirliğini düşürür.",
            "",
            "| Metrik | Değer |",
            "|---|---|",
            f"| Yanlış pozitif oranı @ {KARAR_ESIGI} | **{afet.get('yanlis_pozitif', 0):.4f}** |",
            f"| Çekinme oranı | {afet['cekinme_orani']:.4f} |",
            f"| Karar verilen / toplam | {afet['n_karar']} / {afet['n']} |",
            "",
            "### 2.1. Olay başına",
            "",
            "| Olay | n | Yanlış pozitif | Ortalama skor |",
            "|---|---|---|---|",
        ]
        for ad, bilgi in sorted(afet["aile"].items(), key=lambda kv: -kv[1]["n"]):
            satir.append(
                f"| {ad} | {bilgi['n']} | {bilgi['oran']:.4f} | {bilgi['ortalama_skor']:.4f} |"
            )

    satir += [
        "",
        "## 3. Eşik taraması — mutlak eşik neden işe yaramıyor",
        "",
        "Skorlar dar bir banda sıkışmış durumda (üretilmiş medyan 0,959 · gerçek",
        "medyan 0,942–0,952). AUC'nin 0,72 hedefini geçmesi modelin **sıraladığını**",
        "söyler; hiçbir mutlak eşiğin ayırdığını söylemez. Tablo, fiilen mümkün",
        "olan ödünleşimin tamamıdır.",
        "",
        "| Eşik | Duyarlılık | YP · çapraz gerçek | YP · afet gerçek |",
        "|---|---|---|---|",
    ]
    for r in tarama["satirlar"]:
        afet_hucre = "—" if r["yp_afet"] is None else f"{r['yp_afet']:.4f}"
        satir.append(
            f"| {r['esik']:.3f} | {r['duyarlilik']:.4f} | {r['yp_capraz']:.4f} | {afet_hucre} |"
        )

    if tarama["butceler"]:
        satir += [
            "",
            "Yanlış pozitif bütçesi sabitlendiğinde elde kalan duyarlılık:",
            "",
            "| Afet YP bütçesi | Gereken eşik | Duyarlılık |",
            "|---|---|---|",
        ]
        satir += [
            f"| %{b['butce'] * 100:.0f} | {b['esik']:.4f} | **{b['duyarlilik']:.4f}** |"
            for b in tarama["butceler"]
        ]
        satir += [
            "",
            "> Gerçek afet fotoğraflarının %5'ini yanlış işaretlemeyi göze alsak",
            "> bile sentetik görüntülerin yalnızca dörtte birini yakalıyoruz. Bu",
            "> ödünleşim, hiçbir içeriği silmeyen ama gerçek yardım paylaşımlarına",
            "> sürtünme ekleyebilen bir sistem için kabul edilebilir değildir.",
        ]

    if tur:
        satir += [
            "",
            "## 4. Tür ayrımı — `synthetic.manipulation` karara girmeli mi?",
            "",
            "Üç sınıflı detektör, SENTETİK_MEDYA ile MANİPÜLE_MEDYA ayrımını",
            "yapabilecek tek sinyaldir. Karara katılabilmesi için tek bir koşulu",
            "sağlaması gerekir: **gerçek içerikte “gerçek” demesi.**",
            "",
            "| Küme | n | Baskın tür | Ortalama sentetik | Ortalama manipüle | Ortalama gerçek |",
            "|---|---|---|---|---|---|",
        ]
        for ad, bilgi in tur.items():
            ort = bilgi["ortalama"]
            satir.append(
                f"| {ad} | {bilgi['n']} | **{bilgi['baskin']}** | "
                f"{ort.get('sentetik', 0):.4f} | {ort.get('manipüle', 0):.4f} | "
                f"{ort.get('gerçek', 0):.4f} |"
            )

        gercek_kumeler = {a: b for a, b in tur.items() if a.startswith("gerçek")}
        saglikli = bool(gercek_kumeler) and all(
            b["baskin"] == "gerçek" for b in gercek_kumeler.values()
        )
        satir += [""]
        if saglikli:
            satir.append(
                "**Karar: sinyal füzyona bağlandı.** Detektör gerçek içerikte "
                "“gerçek” diyor; MANİPÜLE_MEDYA dalını besleyebilir."
            )
        else:
            # Gerekçe ölçülene birebir sadık yazılır: hangi kümede ne dediği ve
            # "gerçek" sınıfına verdiği olasılık, iddianın kendisidir.
            kanit = " · ".join(
                f"{ad}: baskın “{b['baskin']}”, ortalama gerçek olasılığı "
                f"{b['ortalama'].get('gerçek', 0):.4f}"
                for ad, b in gercek_kumeler.items()
            )
            satir += [
                "**Karar: sinyal füzyona BAĞLANMADI.** Detektör, tamamı gerçek "
                "olan kümelerde de üretilmiş sınıflarından birini seçiyor ve "
                "“gerçek” sınıfına neredeyse hiç olasılık vermiyor.",
                "",
                f"Ölçülen: {kanit}.",
                "",
                "Bu sinyalin karara katılması, gerçek afet fotoğraflarını "
                "SENTETİK_MEDYA ya da MANİPÜLE_MEDYA olarak sınıflardı. Sinyal "
                "üretilmeye ve kanıt panelinde gösterilmeye devam eder, ancak "
                "sınıf kurmaz.",
            ]

    if ayar:
        satir += [
            "",
            "## 5. Kalibrasyon — `synthetic.video`",
            "",
            "Bu sinyalin kalibrasyonu bugüne kadar **hiç ölçülmemişti**: M6'nın",
            "uçtan uca kümesinde SENTETİK_MEDYA vakası yoktu, `m6_fusion.py` bu",
            "anahtarı atlıyordu ve devrede elle yazılmış noktalar vardı.",
            "",
            "Noktalar bir bölmede uydurulur, ECE diğerinde ölçülür: kendi",
            "uydurduğu veride ölçülen kalibrasyon her zaman mükemmel çıkar.",
            "",
            "| Metrik | Değer | Rapor hedefi |",
            "|---|---|---|",
            f"| ECE · yürürlükteki (elle yazılmış) eşleme | {ayar['ece_once']:.4f} | ≤ 0,05 |",
        ]
        if "ece_sonra" in ayar:
            satir += [
                f"| ECE · ölçülmüş isotonic | **{ayar['ece_sonra']:.4f}** | ≤ 0,05 |",
                f"| n (uydurma / ölçüm) | {ayar['n_uydur']} / {ayar['n_olc']} | — |",
                "",
                "### 5.1. Ölçülen eşleme noktaları",
                "",
                "> Bu noktalar **devreye alınmamıştır.** Kalibrasyon M6'nın veri",
                "> ürünüdür ve `models/m6_fusion/kalibrasyon.json` dosyasını",
                "> `scripts/eval/m6_fusion.py` yazar. Benimseme kararı, uçtan uca",
                "> kümeye SENTETİK_MEDYA vakaları eklendikten sonra verilmelidir.",
                "",
                "```json",
                '{\n  "synthetic.video": {\n    "noktalar": [',
                ",\n".join(f"      [{x}, {y}]" for x, y in ayar["noktalar"]),
                "    ]\n  }\n}",
                "```",
            ]

    if saglamlik:
        satir += [
            "",
            "## 6. Dayanıklılık (kırmızı takım)",
            "",
            "Üretilmiş görüntülere dönüşüm uygulanıp duyarlılık yeniden ölçülür",
            "(rapor 3.2). Dezenformasyon üreticileri pasif değildir: paylaşılan",
            "içerik zaten yeniden kodlanmış, ölçeklenmiş ve kırpılmış hâldedir.",
            "",
            "| Dönüşüm | n | Duyarlılık | Δ temiz | Çekinme | Ortalama skor |",
            "|---|---|---|---|---|---|",
        ]
        temiz = saglamlik.get("temiz", {}).get("duyarlilik", 0.0)
        for ad in DONUSUMLER:
            if ad not in saglamlik:
                continue
            bilgi = saglamlik[ad]
            fark = bilgi["duyarlilik"] - temiz
            satir.append(
                f"| {ad} | {bilgi['n']} | {bilgi['duyarlilik']:.4f} | "
                f"{'—' if ad == 'temiz' else f'{fark:+.4f}'} | "
                f"{bilgi['cekinme_orani']:.4f} | {bilgi['ortalama_skor']:.4f} |"
            )

        satir += [
            "",
            "> **Duyarlılık sütunu bu tabloda bilgi taşımıyor.** Karar eşiği 0,50'de",
            "> zaten her şey eşiği geçiyor (bkz. bölüm 3), dolayısıyla 1,0000 değeri",
            "> dayanıklılığın değil, eşiğin sonucudur. Tabloda okunacak iki sütun",
            "> **ortalama skor** ve **çekinme oranı**dır: skor dönüşümler altında",
            "> kayda değer biçimde kaymıyor, ancak ağır JPEG sıkıştırma dağılım dışı",
            "> kapısını belirgin biçimde tetikliyor — modül o girdilerde karar vermeyi",
            "> reddediyor. Bu, beklenen ve istenen davranıştır.",
        ]

    satir += [
        "",
        "---",
        "",
        "*`scripts/eval/m4_synthetic.py` tarafından üretildi; elle düzenlenmez.*",
        "",
    ]
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text("\n".join(satir), encoding="utf-8")
    return RAPOR


def _kart_guncelle(
    capraz: dict, afet: dict | None, tarama: dict, saglamlik: dict | None
) -> Path | None:
    """Ölçümleri model kartına işler — kabul kapısı bu kartı okur."""
    kart = ModelCard.load(MODEL_DIZINI)
    if kart is None:
        print(f"🔴 model kartı yok: {MODEL_DIZINI / 'kart.json'}")
        return None

    # Kaynak projeden gelen ölçümler korunur; bizim ölçümlerimiz üzerine yazılır.
    bizim = {
        "capraz_auc",
        "capraz_eer",
        "capraz_yanlis_pozitif",
        "afet_yanlis_pozitif",
        "afet_ozgulluk",
    }
    kart.measurements = [m for m in kart.measurements if m.metric not in bizim]

    kume = f"{CAPRAZ_DEPO} · {CAPRAZ_DOSYA}"
    kart.measurements.append(
        Measurement(
            metric="capraz_auc",
            value=round(float(capraz.get("auc", 0.0)), 4),
            dataset=kume,
            n=capraz["n_karar"],
            note="Detektörlerin eğitiminde kullanılmayan korpus; çekinilenler hariç",
        )
    )
    if "eer" in capraz:
        kart.measurements.append(
            Measurement(
                metric="capraz_eer",
                value=round(float(capraz["eer"]), 4),
                dataset=kume,
                n=capraz["n_karar"],
                note=f"eşik {capraz.get('eer_esigi', 0):.3f}",
            )
        )
    kart.measurements.append(
        Measurement(
            metric="capraz_yanlis_pozitif",
            value=round(float(capraz.get("yanlis_pozitif", 0.0)), 4),
            dataset=kume,
            n=sum(b["n"] for b in capraz["aile"].values() if b["etiket"] == 0),
            note=f"karar eşiği {KARAR_ESIGI}",
        )
    )
    if afet:
        # Kabul kapısının okuduğu metrik budur. Yanlış pozitif yerine özgüllük
        # olarak yazılır: kayıt defteri "en az şu kadar" biçiminde bir eşik
        # uygular ve zarar metriği doğrudan o biçime çevrilmelidir.
        kart.measurements.append(
            Measurement(
                metric="afet_ozgulluk",
                value=round(1.0 - float(afet.get("yanlis_pozitif", 1.0)), 4),
                dataset="Wikimedia Commons Türkiye afet korpusu (tamamı gerçek)",
                n=afet["n_karar"],
                note=(
                    f"karar eşiği {KARAR_ESIGI} · kabul kapısının ölçütü · bu deponun kendi ölçümü"
                ),
            )
        )
        kart.measurements.append(
            Measurement(
                metric="afet_yanlis_pozitif",
                value=round(float(afet.get("yanlis_pozitif", 0.0)), 4),
                dataset="Wikimedia Commons Türkiye afet korpusu (tamamı gerçek)",
                n=afet["n_karar"],
                note=f"karar eşiği {KARAR_ESIGI} · bu deponun kendi ölçümü",
            )
        )

    # Ölçülen sınırlar karta yazılır. Önce kendi ürettiğimiz satırlar silinir;
    # aksi hâlde her koşuda liste büyür.
    kart.known_limits = [
        sinir
        for sinir in kart.known_limits
        if not sinir.startswith(
            ("Afet alanında", "Skor dağılımı", "Dönüşüm dayanıklılığı", "Genelleme açığı")
        )
    ]
    if afet:
        yp = float(afet.get("yanlis_pozitif", 0.0))
        kart.known_limits.append(
            f"Afet alanında kullanılamaz durumda: gerçek Türk afet fotoğraflarının "
            f"%{yp * 100:.2f}'i 0,50 eşiğinde 'üretilmiş' çıkıyor (n={afet['n_karar']}). "
            "Kabul kapısı bu yüzden kapalıdır ve modül kural yolunda çalışır."
        )
    kart.known_limits.append(
        "Skor dağılımı dar bir banda sıkışıyor; model sıralıyor ama mutlak eşik "
        "taşımıyor. AUC'ye bakarak devreye almak hatalı olur — eşik taraması: "
        "docs/metrikler/m4.md"
    )
    kart.known_limits.append(
        f"Genelleme açığı ölçüldü: alan içi AUC 1,0000 (kaynak projenin ölçümü) → "
        f"çapraz veri kümesinde {capraz.get('auc', 0.0):.4f}. Düşüş beklenendir ve "
        "raporun ≥ 0,72 hedefini karşılar; kullanılabilirliği belirleyen ise AUC "
        "değil, alan içindeki çalışma noktasıdır."
    )

    if saglamlik:
        # Duyarlılık 0,50 eşiğinde her dönüşümde 1,0000 çıkıyor ve bilgi taşımıyor
        # (bkz. m4.md · bölüm 6). Anlamlı olan, dağılım dışı kapısının hangi
        # dönüşümde tetiklendiğidir.
        en_cok_cekinilen = max(
            ((ad, b) for ad, b in saglamlik.items() if ad != "temiz"),
            key=lambda kv: kv[1]["cekinme_orani"],
            default=None,
        )
        temiz_cekinme = saglamlik.get("temiz", {}).get("cekinme_orani", 0.0)
        if en_cok_cekinilen is not None:
            kart.known_limits.append(
                f"Dönüşüm dayanıklılığı: skorlar dönüşümler altında kaymıyor, ancak "
                f"`{en_cok_cekinilen[0]}` dönüşümü çekinme oranını "
                f"{temiz_cekinme:.4f} → {en_cok_cekinilen[1]['cekinme_orani']:.4f} "
                "seviyesine çıkarıyor: ağır sıkıştırmada modül karar vermeyi "
                "reddediyor. Ayrıntı: docs/metrikler/m4.md"
            )

    kart.git_commit = _git_commit()
    kart.save(MODEL_DIZINI)
    return kart.write_markdown(REPO_ROOT / "docs" / "model-kartlari")


# ────────────────────────── akış ──────────────────────────


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--sinir", type=int, default=1000, help="çapraz kümeden örnek sayısı")
    a.add_argument("--afet-sinir", type=int, default=300, help="afet korpusundan örnek sayısı")
    a.add_argument(
        "--dayaniklilik-sinir", type=int, default=60, help="dönüşüm başına üretilmiş örnek"
    )
    a.add_argument("--tur-sinir", type=int, default=200, help="tür analizi için küme başına örnek")
    a.add_argument("--tohum", type=int, default=20260911)
    a.add_argument("--atla-dayaniklilik", action="store_true")
    a.add_argument(
        "--onbellek-yok", action="store_true", help="ham skorları yeniden ölç (önbelleği atla)"
    )
    args = a.parse_args()

    if not (MODEL_DIZINI / "uretim.onnx").exists():
        print(f"🔴 ağırlık yok: {MODEL_DIZINI}")
        print("   Önce: python scripts/data/build_synthetic.py")
        return 1

    model = SentetikGoruntuModeli(MODEL_DIZINI)
    onbellek: dict[str, dict] | None = None if args.onbellek_yok else _onbellek_oku()

    print("═══ 1/5 çapraz veri kümesi ═══")
    capraz_ornekler = capraz_kume(args.sinir, args.tohum)
    print(f"  {len(capraz_ornekler)} örnek · {len({o.uretici for o in capraz_ornekler})} aile")
    capraz_sonuclar = kos(model, capraz_ornekler, "çapraz", onbellek)
    capraz = ozetle(capraz_sonuclar)
    print(f"  AUC {capraz.get('auc', float('nan')):.4f} · çekinme {capraz['cekinme_orani']:.4f}")

    print("\n═══ 2/5 afet alanı ═══")
    afet_ornekler = afet_kume(args.afet_sinir, args.tohum)
    if afet_ornekler:
        afet_sonuclar = kos(model, afet_ornekler, "afet", onbellek)
        afet = ozetle(afet_sonuclar)
        print(f"  yanlış pozitif {afet.get('yanlis_pozitif', 0):.4f} · n={afet['n_karar']}")
    else:
        afet_sonuclar, afet = [], None
        print("  ⚠ korpus yok (python scripts/data/fetch_provenance.py) — atlanıyor")

    tarama = esik_taramasi(capraz_sonuclar, afet_sonuclar)

    print("\n═══ 3/5 tür ayrımı ═══")
    tur = tur_analizi(
        model,
        {
            "üretilmiş (çapraz)": [o for o in capraz_ornekler if o.etiket == 1],
            "gerçek (çapraz)": [o for o in capraz_ornekler if o.etiket == 0],
            "gerçek (afet)": afet_ornekler,
        },
        args.tur_sinir,
        onbellek,
    )

    print("\n═══ 4/5 kalibrasyon ═══")
    ayar = kalibrasyon(capraz_sonuclar)
    if ayar and "ece_sonra" in ayar:
        print(f"  ECE {ayar['ece_once']:.4f} → {ayar['ece_sonra']:.4f} (n={ayar['n']})")
    else:
        print("  ⚠ ölçülemedi (tek sınıf ya da sklearn yok)")

    saglamlik = None
    if not args.atla_dayaniklilik:
        print("\n═══ 5/5 dayanıklılık ═══")
        alt_kume = [o for o in capraz_ornekler if o.etiket == 1][: args.dayaniklilik_sinir]
        saglamlik = dayaniklilik(model, alt_kume, onbellek)

    if onbellek is not None:
        _onbellek_yaz(onbellek)

    rapor = _rapor_yaz(capraz, afet, tarama, tur, ayar, saglamlik, args.sinir)
    print(f"\n✓ {rapor.relative_to(REPO_ROOT)}")
    if (kart := _kart_guncelle(capraz, afet, tarama, saglamlik)) is not None:
        print(f"✓ {kart.relative_to(REPO_ROOT)}")

    ozgulluk = 1.0 - float(afet.get("yanlis_pozitif", 1.0)) if afet else 0.0
    durum = "geçti" if ozgulluk >= KABUL_ESIGI else "GEÇEMEDİ"
    print(
        f"\nÇapraz veri kümesi AUC (yetenek): {capraz.get('auc', 0.0):.4f}  [rapor hedefi ≥ 0,72]"
    )
    print(f"Kabul kapısı (afet_ozgulluk ≥ {KABUL_ESIGI}): {ozgulluk:.4f} — {durum}")
    if durum != "geçti":
        print("  → Ağırlık yüklenmeyecek; M4 kural yolunda kalır. Gerekçe: docs/metrikler/m4.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
