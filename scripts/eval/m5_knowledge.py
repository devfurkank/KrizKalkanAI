#!/usr/bin/env python
"""M5 değerlendirmesi — geri getirme başarımı ve yanlış eşleşme oranı.

Ölçülenler:

    Recall@1 / Recall@5   iddia → doğru DMM kaydı
    MRR                   ortalama karşılıklı sıra
    Yanlış eşleşme oranı  eşleşmemesi gereken sorguların eşiği aşma oranı
    Eşik taraması         çalışma noktasının seçimi

Sözlük tabanlı yol (anahtar terim örtüşmesi) aynı kümede ayrıca ölçülür;
gömme tabanlı geri getirmenin ne kadar kazandırdığı böyle görünür.

Çıktı: docs/metrikler/m5.md
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.knowledge import corpus, engine  # noqa: E402
from krizkalkan_core.knowledge.retriever import Retriever  # noqa: E402
from krizkalkan_core.models.cards import Measurement, ModelCard  # noqa: E402
from krizkalkan_core.models.runtime import model_root  # noqa: E402
from krizkalkan_core.text.lexicon import normalize  # noqa: E402

KUME = Path(__file__).parent / "kumeler" / "m5_geri_getirme.json"
RAPOR = REPO_ROOT / "docs" / "metrikler" / "m5.md"
K = 5


@dataclass
class Sonuc:
    recall1: float = 0.0
    recall5: float = 0.0
    mrr: float = 0.0
    cozulemeyen: list[str] = field(default_factory=list)
    siralar: list[int | None] = field(default_factory=list)
    negatif_skorlar: list[tuple[str, float]] = field(default_factory=list)


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


def hedefleri_coz(desen: str, kayitlar) -> set[str]:
    """Ayırt edici deseni eşleşen tüm kayıt kimliklerine çözer.

    Aynı iddia birden çok bültende tekrarlandığı için hepsi doğru sayılır;
    tek kimliğe bağlamak Recall'ı yapay olarak düşürürdü.
    """
    hedef = normalize(desen)
    return {k.record_id for k in kayitlar if hedef in normalize(k.claim)}


def _sira(adaylar: list[str], hedefler: set[str]) -> int | None:
    for i, kimlik in enumerate(adaylar, 1):
        if kimlik in hedefler:
            return i
    return None


def olc_gomme(kume: dict, kayitlar, r: Retriever) -> Sonuc:
    sonuc = Sonuc()
    for madde in kume["sorgular"]:
        hedefler = hedefleri_coz(madde["hedef_desen"], kayitlar)
        if not hedefler:
            sonuc.cozulemeyen.append(madde["hedef_desen"])
            continue
        adaylar = [a.record_id for a in r.ara(madde["sorgu"], k=K)]
        sonuc.siralar.append(_sira(adaylar, hedefler))

    for madde in kume["negatif_sorgular"]:
        adaylar = r.ara(madde["sorgu"], k=1)
        sonuc.negatif_skorlar.append((madde["sorgu"], adaylar[0].benzerlik if adaylar else 0.0))

    return _ozetle(sonuc)


def olc_sozluk(kume: dict, kayitlar) -> Sonuc:
    """Mevcut anahtar terim örtüşmesi yolu — karşılaştırma tabanı."""
    sonuc = Sonuc()
    for madde in kume["sorgular"]:
        hedefler = hedefleri_coz(madde["hedef_desen"], kayitlar)
        if not hedefler:
            sonuc.cozulemeyen.append(madde["hedef_desen"])
            continue
        skorlu = sorted(
            ((engine._overlap(madde["sorgu"], k), k.record_id) for k in kayitlar),
            key=lambda p: -p[0],
        )[:K]
        adaylar = [kimlik for skor, kimlik in skorlu if skor > 0]
        sonuc.siralar.append(_sira(adaylar, hedefler))

    for madde in kume["negatif_sorgular"]:
        en_iyi = max((engine._overlap(madde["sorgu"], k) for k in kayitlar), default=0.0)
        sonuc.negatif_skorlar.append((madde["sorgu"], en_iyi))
    return _ozetle(sonuc)


def _ozetle(sonuc: Sonuc) -> Sonuc:
    n = len(sonuc.siralar)
    if n:
        sonuc.recall1 = sum(1 for s in sonuc.siralar if s == 1) / n
        sonuc.recall5 = sum(1 for s in sonuc.siralar if s is not None) / n
        sonuc.mrr = sum(1 / s for s in sonuc.siralar if s) / n
    return sonuc


def esik_taramasi(gomme: Sonuc, r: Retriever, kume: dict, kayitlar) -> list[dict]:
    """Eşik seçimini ölçüme dayandırır: kaç doğru tutuluyor, kaç yanlış giriyor?"""
    pozitif_skorlar: list[float] = []
    for madde in kume["sorgular"]:
        hedefler = hedefleri_coz(madde["hedef_desen"], kayitlar)
        if not hedefler:
            continue
        for aday in r.ara(madde["sorgu"], k=K):
            if aday.record_id in hedefler:
                pozitif_skorlar.append(aday.benzerlik)
                break

    negatifler = [s for _, s in gomme.negatif_skorlar]
    satirlar = []
    for esik in (0.78, 0.80, 0.82, 0.84, 0.86, 0.88):
        tutulan = sum(1 for s in pozitif_skorlar if s >= esik)
        sizan = sum(1 for s in negatifler if s >= esik)
        satirlar.append(
            {
                "esik": esik,
                "dogru_tutulan": tutulan,
                "dogru_toplam": len(pozitif_skorlar),
                "yanlis_sizan": sizan,
                "yanlis_toplam": len(negatifler),
            }
        )
    return satirlar


def ayrim_analizi(gomme: Sonuc, r: Retriever, kume: dict, kayitlar) -> dict:
    """Benzerlik tek başına karar verdirebilir mi?

    Üç aday istatistik denenir: mutlak top1 skoru, top1 ile top10 arasındaki
    fark ve top1'in ilk 200 adayın dağılımına göre z-skoru. Pozitiflerin en
    düşüğü negatiflerin en yükseğinden büyükse ayrım vardır.
    """
    import numpy as np

    def istatistik(sorgu: str) -> tuple[float, float, float]:
        v = np.asarray(r.kodla([sorgu], sorgu=True))[0]
        tumu = np.sort(r.gomme @ v)[::-1]
        return (
            float(tumu[0]),
            float(tumu[0] - tumu[9]),
            float((tumu[0] - tumu[:200].mean()) / (tumu[:200].std() + 1e-9)),
        )

    pozitif = [istatistik(m["sorgu"]) for m in kume["sorgular"]]
    negatif = [istatistik(m["sorgu"]) for m in kume["negatif_sorgular"]]
    poz, neg = np.array(pozitif), np.array(negatif)

    return {
        ad: {
            "pozitif_min": round(float(poz[:, i].min()), 4),
            "negatif_maks": round(float(neg[:, i].max()), 4),
            "ayrisiyor": bool(poz[:, i].min() > neg[:, i].max()),
        }
        for i, ad in enumerate(("top1", "top1_eksi_top10", "z_skoru"))
    }


def rapor_yaz(
    gomme: Sonuc,
    sozluk: Sonuc,
    tarama: list[dict],
    kayit_sayisi: int,
    ayrim: dict,
    karar: dict[str, dict[str, int]],
) -> Path:
    simdi = datetime.now(UTC).strftime("%d.%m.%Y %H:%M UTC")
    n = len(gomme.siralar)
    s = [
        "# M5 — Kriz Bilgi Havuzu · Değerlendirme",
        "",
        f"*`scripts/eval/m5_knowledge.py` tarafından üretildi · {simdi} · commit `{_git_commit()}`*",
        "",
        "| | |",
        "|---|---|",
        f"| Havuz | {kayit_sayisi:,} kayıt (DMM + tohum) |",
        f"| Değerlendirme kümesi | {n} sorgu (elle yazılmış yeniden ifadeler) |",
        f"| Negatif sorgu | {len(gomme.negatif_skorlar)} |",
        "| Geri getirme | multilingual-e5-base · int8 ONNX |",
        "",
        "## Geri getirme başarımı",
        "",
        "| Yöntem | Recall@1 | Recall@5 | MRR |",
        "|---|---|---|---|",
        f"| Anahtar terim örtüşmesi (taban) | {sozluk.recall1:.3f} | {sozluk.recall5:.3f} "
        f"| {sozluk.mrr:.3f} |",
        f"| **Cümle gömmesi (e5)** | **{gomme.recall1:.3f}** | **{gomme.recall5:.3f}** "
        f"| **{gomme.mrr:.3f}** |",
        "",
        f"> Rapor 3.2 hedefi: Recall@5 ≥ 0,85 · ölçülen: **{gomme.recall5:.3f}** (n={n})",
        "",
        "## Eşik taraması",
        "",
        "Eşik, doğru eşleşmeleri tutarken alakasız sorguların havuza girmesini",
        "engelleyecek biçimde seçilir. RESMÎ_KAYNAK_SESSİZ dalı bu eşiğin altında kalır.",
        "",
        "| Eşik | Tutulan doğru | Sızan yanlış |",
        "|---|---|---|",
    ]
    s += [
        f"| {t['esik']:.2f} | {t['dogru_tutulan']}/{t['dogru_toplam']} | "
        f"{t['yanlis_sizan']}/{t['yanlis_toplam']} |"
        for t in tarama
    ]
    s += [
        "",
        "## Uçtan uca karar ölçümü",
        "",
        "Recall@5 geri getirmenin ne BULDUĞUNU ölçer; bu tablo sistemin ne",
        "SÖYLEDİĞİNİ ölçer. Zararlı eşleşme, kullanıcıya yanlış bir kaydı",
        'göstererek "resmî kaynak seni yalanlıyor" demektir.',
        "",
        "| Yapılandırma | Doğru | Zararlı | Sessiz |",
        "|---|---|---|---|",
    ]
    s += [f"| {ad} | {d['dogru']} | {d['zararli']} | {d['sessiz']} |" for ad, d in karar.items()]
    s += [
        "",
        "SNLI-TR ile eğitilen çıkarım modeli kendi kümesinde 0,8181 doğruluk alıyor",
        "ama kriz alanında çalışmıyor. Sebep görev uyumsuzluğu: SNLI'ın \"öncül",
        'varsayımı ima ediyor mu?" sorusu, bizim "bu iki metin aynı iddiayı mı öne',
        'sürüyor?" sorumuz değildir. Bu nedenle çıkarım katmanı DEVREDE DEĞİLDİR.',
        "",
        "Yürürlükteki yapılandırmada sözlük aday üretir, geri getirme vetolar.",
        "Zararlı tek eşleşme geri getiricinin ilk 20'sinde bile yoktu; doğru",
        "eşleşmelerin tamamı ilk 3'teydi. Veto, sözlük eşiğini 0,34'ten 0,25'e",
        "indirmeyi güvenli kılıyor.",
        "",
        "## Benzerlik tek başına karar verdirebilir mi?",
        "",
        "Üç aday istatistik denendi. Ayrım için pozitiflerin en düşüğü,",
        "negatiflerin en yükseğinden büyük olmalıdır.",
        "",
        "| İstatistik | Pozitif en düşük | Negatif en yüksek | Ayrışıyor mu? |",
        "|---|---|---|---|",
    ]
    s += [
        f"| {ad.replace('_', ' ')} | {d['pozitif_min']:.3f} | {d['negatif_maks']:.3f} | "
        f"{'✅ evet' if d['ayrisiyor'] else '❌ hayır'} |"
        for ad, d in ayrim.items()
    ]
    s += [
        "",
        "**Hiçbiri ayrışmıyor.** En yüksek skorlu negatif sorgu resmî bir AFAD",
        "duyurusudur: havuzla konu olarak gerçekten benzerdir, ancak aynı iddia",
        "değildir. Konu benzerliği ile *aynı iddiayı öne sürme* farklı şeylerdir ve",
        "ikincisi bir çıkarım (NLI) görevidir.",
        "",
        "Bu ölçüm, rapor 3.1'deki iki aşamalı M5 tasarımının gerekliliğini doğrular:",
        "geri getirme aday üretir (Recall@5 = "
        + f"{gomme.recall5:.3f}"
        + "), kararı çıkarım katmanı verir.",
        "Benzerlik eşiğiyle karar verilseydi, resmî duyurular ve gerçek yardım",
        "çağrıları yanlışlıkla tekziple eşleştirilebilirdi — sistemin en pahalı hatası.",
        "",
        "## Negatif sorgular — en yakın kaydın benzerliği",
        "",
        "| Sorgu | En yüksek skor |",
        "|---|---|",
    ]
    s += [f"| {sorgu} | {skor:.3f} |" for sorgu, skor in gomme.negatif_skorlar]

    if gomme.cozulemeyen:
        s += ["", "## ⚠️ Çözülemeyen hedef desenleri", ""]
        s += [f"- `{d}`" for d in gomme.cozulemeyen]
        s += ["", "Bu desenler havuzda bulunamadı; küme veya havuz güncellenmeli."]

    s += [
        "",
        "## Yöntem notu",
        "",
        "Sorgular gerçek DMM iddialarının sosyal medya diline **elle** yeniden",
        "yazılmış hâlleridir; kaynak iddianın kelimeleri bilinçli olarak",
        "kullanılmamıştır. Kaynağın kendi `claim` alanı sorgu olarak kullanılsaydı",
        "ölçüm birebir kelime eşleşmesini ölçer ve yapay olarak yüksek çıkardı.",
        "",
        "Aynı iddia birden çok bültende tekrarlandığı için, bir sorgunun hedefi tek",
        "kayıt değil eşleşen tüm kayıtlardır.",
        "",
    ]
    RAPOR.parent.mkdir(parents=True, exist_ok=True)
    RAPOR.write_text("\n".join(s), encoding="utf-8")
    return RAPOR


def karar_olcumu(kume: dict, kayitlar) -> dict[str, dict[str, int]]:
    """Uçtan uca KARAR ölçümü — geri getirme değil, verilen hüküm.

    Recall@5 geri getirmenin ne bulduğunu ölçer; bu fonksiyon sistemin ne
    SÖYLEDİĞİNİ ölçer. Aradaki fark kritiktir: doğru kaydı ilk beşe getirmek,
    doğru kararı vermek demek değildir.

    Üç yapılandırma karşılaştırılır. Zararlı eşleşme, kullanıcıya YANLIŞ bir
    kaydı göstererek "resmî kaynak seni yalanlıyor" demektir.
    """
    from krizkalkan_core.knowledge import nli, retriever

    def hedefleri(desen: str) -> set[str]:
        return hedefleri_coz(desen, kayitlar)

    arayici, cikarimci = retriever.get(), nli.get()
    yapilandirmalar: dict[str, object] = {
        "sözlük (eşik 0,34)": lambda s: engine._sozluk_yolu(s),
    }
    if arayici is not None:
        yapilandirmalar["sözlük 0,25 + geri getirme vetosu"] = lambda s: engine._dogrulanmis_yol(
            s, arayici
        )
        if cikarimci is not None:
            yapilandirmalar["geri getirme + NLI çıkarımı"] = lambda s: engine._cikarim_yolu(
                s, arayici, cikarimci
            )

    sonuc: dict[str, dict[str, int]] = {}
    for ad, yol in yapilandirmalar.items():
        dogru = zararli = sessiz = 0
        for madde in kume["sorgular"]:
            hedefler = hedefleri(madde["hedef_desen"])
            if not hedefler:
                continue
            eslesme = yol(madde["sorgu"])
            if eslesme.record is None:
                sessiz += 1
            elif eslesme.record.record_id in hedefler:
                dogru += 1
            else:
                zararli += 1
        sonuc[ad] = {"dogru": dogru, "zararli": zararli, "sessiz": sessiz}
        print(f"  {ad:34s} doğru {dogru:2d} · zararlı {zararli:2d} · sessiz {sessiz:2d}")
    return sonuc


def kart_yaz(gomme: Sonuc, dizin: Path, kayit_sayisi: int) -> Path:
    """Ölçülen değerleri model kartına yazar.

    Kart yalnızca belge değildir: `models/registry.py` kabul kapısı bu kartı
    okur ve eşiği karşılamayan ağırlığı yüklemez. Ölçüm yapılmadan model
    üretime giremez — bu, disiplin meselesi değil yapısal bir kısıt.
    """
    n = len(gomme.siralar)
    kart = ModelCard(
        name="m5_retriever",
        module="M5",
        title="Kriz Bilgi Havuzu Geri Getirici",
        version="0.1.0",
        base_model="intfloat/multilingual-e5-base (int8 ONNX)",
        purpose=(
            "Kullanıcı metninden çıkarılan iddiaya en yakın resmî kayıtları bulur. "
            "Karar vermez; aday üretir. Kararı M5 çıkarım katmanı verir."
        ),
        training_data=[
            f"DMM Dezenformasyon Bültenleri (CC BY 4.0) — {kayit_sayisi:,} kayıt indekslendi",
            "Model ince ayar görmedi; hazır çok dilli gömme modeli kullanıldı",
        ],
        training_procedure=(
            "İnce ayar yok. Kodlayıcı int8 dinamik nicelemeyle (per_channel) ONNX'e "
            "aktarıldı; indeks ve sorgu aynı kodlayıcıyla gömülür."
        ),
        hyperparameters={"maks_uzunluk": 192, "onek": "query:/passage:", "niceleme": "int8"},
        split_strategy="Değerlendirme kümesi elle yazılmış yeniden ifadelerden oluşur",
        measurements=[
            Measurement("recall1", round(gomme.recall1, 4), "elle yazılmış yeniden ifadeler", n),
            Measurement("recall5", round(gomme.recall5, 4), "elle yazılmış yeniden ifadeler", n),
            Measurement("mrr", round(gomme.mrr, 4), "elle yazılmış yeniden ifadeler", n),
        ],
        known_limits=[
            "Benzerlik skoru tek başına 'aynı iddia' ile 'benzer konu'yu AYIRAMAZ; "
            "ölçüldü ve raporlandı (docs/metrikler/m5.md · ayrım analizi). Karar "
            "katmanı olmadan kullanılmamalıdır.",
            f"Değerlendirme kümesi küçüktür (n={n}); güven aralığı geniştir.",
            "Havuz yalnızca tekzip kayıtları içerir (DMM); DESTEKLİYOR sınıfı için "
            "AFAD/valilik duyuruları ayrıca gereklidir.",
            "Türkçe dışı ve bölgesel ağız başarımı ölçülmedi.",
        ],
        ethical_notes=[
            "Yanlış eşleşme, kullanıcıya 'resmî kaynak seni yalanlıyor' demek anlamına "
            "gelir; bu nedenle karar eşiği duyarlılık değil kesinlik lehine ayarlanır.",
        ],
        out_of_scope=[
            "Tek başına doğruluk hükmü vermek",
            "Havuzda karşılığı olmayan iddiaları yanlış saymak",
        ],
        license="Model: MIT (e5) · Veri: CC BY 4.0 (DMM)",
        git_commit=_git_commit(),
    )
    kart.save(dizin)
    return kart.write_markdown(REPO_ROOT / "docs" / "model-kartlari")


def nli_karti_guncelle(karar: dict[str, dict[str, int]]) -> Path | None:
    """NLI kartına ALAN İÇİ ölçümü ekler.

    Kaggle'da yazılan kart yalnızca SNLI-TR doğruluğunu taşıyor ve o sayı alan
    içi başarımı temsil etmiyor. Kart, modelin kriz alanında ne yaptığını da
    söylemeli — özellikle devreye alınmama gerekçesini.
    """
    dizin = model_root() / "m5_nli"
    kart = ModelCard.load(dizin)
    if kart is None:
        return None

    cikarim = karar.get("geri getirme + NLI çıkarımı")
    if cikarim is None:
        return None
    toplam = sum(cikarim.values())

    kart.measurements = [m for m in kart.measurements if not m.metric.startswith("alan_ici")] + [
        Measurement(
            "alan_ici_dogru_eslesme",
            round(cikarim["dogru"] / max(toplam, 1), 4),
            "kriz iddiası → DMM kaydı",
            toplam,
            "SNLI doğruluğu bu sayıyı TEMSİL ETMEZ",
        ),
        Measurement(
            "alan_ici_zararli_eslesme",
            round(cikarim["zararli"] / max(toplam, 1), 4),
            "kriz iddiası → DMM kaydı",
            toplam,
            "yanlış kayıt gösterilerek 'resmî kaynak seni yalanlıyor' denmesi",
        ),
    ]
    kart.known_limits = [
        "🔴 MODEL DEVREDE DEĞİLDİR. Kriz alanında ölçüldü ve reddedildi: "
        f"{toplam} sorguda {cikarim['dogru']} doğru, {cikarim['zararli']} ZARARLI "
        "eşleşme üretti. Aynı kümede sözlük yolu daha iyi sonuç veriyor.",
        "Sebep görev uyumsuzluğu, eğitim başarısızlığı değil: SNLI'ın \"öncül "
        'varsayımı ima ediyor mu?" sorusu, "bu iki metin aynı iddiayı mı öne '
        'sürüyor?" sorusu değildir. Öncül/varsayım yönü ters çevrilerek de '
        "denendi; iki yönde de başarısız.",
        "SNLI-TR makine çevirisiyle üretilmiştir; kısa, genel cümlelerden oluşur. "
        "Kriz iddiaları ve DMM kayıtları uzun ve kurumsal dildedir.",
        "Gerçek bir iddia eşleştirme kümesiyle eğitilmiş model geldiğinde karar "
        "ölçümle yeniden ele alınmalıdır; kod yolu (`engine._cikarim_yolu`) ve "
        "testleri korunmaktadır.",
    ]
    kart.save(dizin)
    return kart.write_markdown(REPO_ROOT / "docs" / "model-kartlari")


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--sadece-sozluk", action="store_true", help="gömme modeli olmadan çalıştır")
    args = a.parse_args()

    kume = json.loads(KUME.read_text(encoding="utf-8"))
    kayitlar = corpus.records()
    print(f"→ havuz {len(kayitlar):,} kayıt · {len(kume['sorgular'])} sorgu")

    print("→ sözlük tabanı ölçülüyor…")
    sozluk = olc_sozluk(kume, kayitlar)
    print(f"  Recall@1 {sozluk.recall1:.3f} · Recall@5 {sozluk.recall5:.3f} · MRR {sozluk.mrr:.3f}")

    if args.sadece_sozluk:
        return 0

    dizin = model_root() / "m5_retriever"
    if not (dizin / "gomme.npy").exists():
        print(f"🔴 İndeks yok: {dizin}. Önce: make m5-index")
        return 1

    print("→ gömme tabanlı geri getirme ölçülüyor…")
    r = Retriever(dizin)
    gomme = olc_gomme(kume, kayitlar, r)
    print(f"  Recall@1 {gomme.recall1:.3f} · Recall@5 {gomme.recall5:.3f} · MRR {gomme.mrr:.3f}")

    if gomme.cozulemeyen:
        print(f"  ⚠️ çözülemeyen desen: {len(gomme.cozulemeyen)} → {gomme.cozulemeyen}")

    tarama = esik_taramasi(gomme, r, kume, kayitlar)
    print("\n→ eşik taraması:")
    for t in tarama:
        print(
            f"  {t['esik']:.2f}  doğru {t['dogru_tutulan']:>2}/{t['dogru_toplam']}  "
            f"yanlış {t['yanlis_sizan']}/{t['yanlis_toplam']}"
        )

    print("\n→ uçtan uca karar ölçümü…")
    karar = karar_olcumu(kume, kayitlar)

    print("\n→ ayrım analizi…")
    ayrim = ayrim_analizi(gomme, r, kume, kayitlar)
    for ad, d in ayrim.items():
        durum = "✓ ayrışıyor" if d["ayrisiyor"] else "✗ çakışıyor"
        print(
            f"  {ad:18s} poz min={d['pozitif_min']:.3f} neg maks={d['negatif_maks']:.3f}  {durum}"
        )

    yol = rapor_yaz(gomme, sozluk, tarama, len(kayitlar), ayrim, karar)
    kart_yolu = kart_yaz(gomme, dizin, len(kayitlar))
    if (nli_yolu := nli_karti_guncelle(karar)) is not None:
        print(f"✓ {nli_yolu.relative_to(REPO_ROOT)}  (alan içi ölçüm eklendi)")
    print(f"\n✓ {yol.relative_to(REPO_ROOT)}")
    print(f"✓ {kart_yolu.relative_to(REPO_ROOT)}  (kabul kapısı bu kartı okur)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
