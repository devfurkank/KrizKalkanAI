"""Veri kümesi kayıt defteri — tek doğruluk kaynağı.

Her kümenin kimliği, lisansı, hedef modülü ve **dağıtım biçimi** burada
tanımlıdır. Dağıtım biçimi kritik alandır: `TAM_METIN` olan kümeler doğrudan
kullanılabilir, `KIMLIK` olanlar X API hidrasyonu gerektirir ve pratikte
kullanılamaz (ücretli API + silinmiş içerik kaybı).

`fetch_text.py` bu tanımları indirir ve doğrular; `docs/veri-envanteri.md`
bu tablodan üretilir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Bicim(StrEnum):
    """Dağıtım biçimi — kullanılabilirliği belirleyen tek alan."""

    TAM_METIN = "tam metin"
    KIMLIK = "yalnızca kimlik (hidrasyon gerekir)"
    GORSEL_URL = "görsel bağlantısı"


class Durum(StrEnum):
    KULLANILIYOR = "kullanılıyor"
    DEGERLENDIRME = "yalnızca değerlendirme"
    KULLANILAMAZ = "kullanılamaz"


@dataclass(frozen=True, slots=True)
class VeriKumesi:
    kod: str
    ad: str
    repo: str
    dosya: str
    lisans: str
    bicim: Bicim
    durum: Durum
    moduller: tuple[str, ...]
    beklenen_satir: int | None = None
    beklenen_sutunlar: tuple[str, ...] = ()
    repo_tipi: str = "dataset"
    #: HF dal/etiket. Betik tabanlı kümelerde "refs/convert/parquet" otomatik
    #: dönüştürülmüş parquet sürümüne erişim sağlar (datasets>=4 betik desteğini kaldırdı).
    revision: str | None = None
    #: `load_dataset` ile yüklenecekse bölüm adı; parquet/tsv ise None.
    split: str | None = None
    not_: str = ""
    uyarilar: tuple[str, ...] = field(default_factory=tuple)


KUMELER: tuple[VeriKumesi, ...] = (
    VeriKumesi(
        kod="D1",
        ad="DMM Dezenformasyon Bültenleri",
        repo="iletisim/dezenformasyon-bultenleri",
        dosya="data/train-00000-of-00001.parquet",
        lisans="CC BY 4.0",
        bicim=Bicim.TAM_METIN,
        durum=Durum.KULLANILIYOR,
        moduller=("M5", "M3"),
        beklenen_satir=2810,
        beklenen_sutunlar=("claim", "fact_check", "rating_label", "bulletin_number"),
        not_="Bilgi havuzunun çekirdeği. Resmî kurum kaynağı, ticari kullanıma açık.",
        uyarilar=(
            "rating_label TEK DEĞER içerir ('Yanlış') — DMM yalnızca tekzip yayımlar. "
            "DESTEKLİYOR sınıfı için AFAD/valilik duyuruları ayrıca gerekir.",
            "date_published yalnızca 5 benzersiz değer taşır; bunlar bülten tarihi değil "
            "derleme tarihidir. Gerçek zaman sinyali bulletin_number alanıdır (6–1020).",
            "Metinler PDF çıkarımı kaynaklı satır sonları içerir; normalizasyon zorunlu.",
        ),
    ),
    VeriKumesi(
        kod="D2",
        ad="MiDe22 (Türkçe yanlış bilgi)",
        repo="ogozcelik/turkish-fake-news-detection",
        dosya="mide22_all_tr.tsv",
        lisans="MIT",
        bicim=Bicim.TAM_METIN,
        durum=Durum.KULLANILIYOR,
        moduller=("M3", "M8"),
        beklenen_satir=5066,
        beklenen_sutunlar=("tweet", "label"),
        not_=(
            "Yol haritasında hidrasyon riski taşıdığı varsayılmıştı; bu ayna TAM METİN "
            "içerir ve riski ortadan kaldırır. LREC-COLING 2024 kıyası bu küme üzerinden."
        ),
        uyarilar=(
            "Konular Rusya-Ukrayna, COVID-19, mülteciler — afet alanı DEĞİL. "
            "İki aşamalı ince ayarın yalnızca 1. aşamasında kullanılır.",
            "Sınıf dengesizliği: Other 2663 / False 1732 / True 669.",
        ),
    ),
    VeriKumesi(
        kod="D10",
        ad="HumAID (İngilizce kriz tweetleri)",
        repo="QCRI/HumAID-all",
        dosya="",
        lisans="CC BY-NC-SA 4.0 (araştırma)",
        bicim=Bicim.TAM_METIN,
        durum=Durum.KULLANILIYOR,
        moduller=("M3",),
        beklenen_satir=53531,
        beklenen_sutunlar=("tweet_text", "class_label"),
        split="train",
        not_=(
            "Görev A (iddia tipi) ve Görev B2 (yardım_çağrısı) için çapraz dilli "
            "taşıyıcı küme. Etiket şeması ClaimType ile neredeyse birebir eşleşir; "
            "Türkçe etiketli yardım çağrısı verisi bulunmadığı için kritik hâle geldi."
        ),
        uyarilar=(
            "İngilizce — yalnızca çok dilli omurga (XLM-R) ile kullanılabilir.",
            "CC BY-NC-SA: araştırma/değerlendirme amaçlıdır, ticari modele girmez. "
            "Bu ayrım raporda beyan edilir.",
        ),
    ),
    VeriKumesi(
        kod="D5",
        ad="Turkish Disaster News GeoNLP",
        repo="FatmaElik/turkish-disaster-news-geonlp",
        dosya="train.csv",
        lisans="CC BY-NC 4.0",
        bicim=Bicim.TAM_METIN,
        durum=Durum.DEGERLENDIRME,
        moduller=("M3",),
        beklenen_sutunlar=(),
        not_="Konum/hasar/aciliyet etiketleri — Görev A değerlendirmesi için.",
        uyarilar=(
            "🔴 CC BY-NC 4.0: TİCARİ KULLANIM YASAK. Üretim modeline SOKULMAZ, "
            "yalnızca değerlendirme kümesi olarak kullanılır.",
        ),
    ),
    VeriKumesi(
        kod="D3",
        ad="deprem-ml / Açık Yazılım Ağı — niyet",
        repo="deprem-private/intent_train_v13_anonymized",
        dosya="data/train-00000-of-00001-9ed7e0e7781e4925.parquet",
        lisans="belirtilmemiş",
        bicim=Bicim.GORSEL_URL,
        durum=Durum.KULLANILAMAZ,
        moduller=("M3",),
        beklenen_satir=8112,
        not_="Yol haritasında yardım_çağrısı kaynağı olarak planlanmıştı.",
        uyarilar=(
            "🔴 İçerik METİN DEĞİL: alanlar image_url + görsel etiketi "
            "(ör. 'Enkaz Kaldırma'). Metin niyet/NER verisi erişilebilir değil.",
            "Sonuç: yardım_çağrısı sınıfı HumAID çapraz dilli aktarımı + elle "
            "etiketlenmiş altın küme ile öğrenilecek.",
        ),
    ),
    VeriKumesi(
        kod="D3b",
        ad="ctoraman/deprem-tweet-dataset",
        repo="ctoraman/deprem-tweet-dataset",
        dosya="deprem-tweet-dataset.tsv",
        lisans="CC",
        bicim=Bicim.KIMLIK,
        durum=Durum.KULLANILAMAZ,
        moduller=("M3",),
        beklenen_satir=1000,
        beklenen_sutunlar=("label", "entities", "tweet_id"),
        not_="Adres/kişi/şehir NER aralıkları içerir — metin olsaydı ideal olurdu.",
        uyarilar=(
            "🔴 Yalnızca tweet_id: metin için X API hidrasyonu gerekir (ücretli, "
            "silinmiş içerik geri gelmez). Kullanılmıyor.",
        ),
    ),
    VeriKumesi(
        kod="D8",
        ad="NLI-TR · SNLI-TR (eğitim)",
        repo="boun-tabi/nli_tr",
        dosya="snli_tr/train/0000.parquet",
        revision="refs/convert/parquet",
        lisans="araştırma (SNLI türevi)",
        bicim=Bicim.TAM_METIN,
        durum=Durum.KULLANILIYOR,
        moduller=("M5",),
        beklenen_sutunlar=("premise", "hypothesis", "label"),
        not_=(
            "M5'in DESTEKLİYOR/ÇELİŞİYOR/İLGİSİZ çıkarımını eğitir. Rapor atıfı [15] "
            "ile aynı özgün kümedir."
        ),
        uyarilar=(
            "Küme betik tabanlı dağıtılır ve datasets>=4 betikleri desteklemez; "
            "HF'in otomatik ürettiği `refs/convert/parquet` dalı kullanılır.",
            "Eğitimde tamamı değil, dengeli altörnekleme (~120k) kullanılacak — "
            "Kaggle kotası bütünüyle eğitmeye yetmez.",
        ),
    ),
    VeriKumesi(
        kod="D8b",
        ad="NLI-TR · SNLI-TR (doğrulama)",
        repo="boun-tabi/nli_tr",
        dosya="snli_tr/validation/0000.parquet",
        revision="refs/convert/parquet",
        lisans="araştırma (SNLI türevi)",
        bicim=Bicim.TAM_METIN,
        durum=Durum.KULLANILIYOR,
        moduller=("M5",),
        beklenen_sutunlar=("premise", "hypothesis", "label"),
        not_="NLI 3 sınıf doğruluğu bu küme üzerinde raporlanır (rapor hedefi ≥ 0,80).",
    ),
)


def kume(kod: str) -> VeriKumesi:
    """Koduna göre küme tanımını döndürür."""
    for k in KUMELER:
        if k.kod == kod:
            return k
    raise KeyError(f"Tanımsız veri kümesi kodu: {kod}")


def kullanilabilir() -> tuple[VeriKumesi, ...]:
    """Eğitimde fiilen kullanılan kümeler."""
    return tuple(k for k in KUMELER if k.durum is Durum.KULLANILIYOR)
