"""Doğrulanmış kriz bilgi havuzu — DMM Dezenformasyon Bültenleri.

Havuz iki katmandan oluşur:

* **Tohum kayıtlar** — demo senaryolarının dayandığı, elle yazılmış az sayıda
  kayıt. Her zaman yüklüdür; AFAD ve Meteoroloji örnekleriyle DESTEKLİYOR
  sınıfını da temsil eder.
* **DMM kayıtları** — `iletisim/dezenformasyon-bultenleri` (CC BY 4.0)
  kümesinden `scripts/data/build_knowledge.py` ile üretilen JSONL. Dosya yoksa
  havuz yalnızca tohum kayıtlarla çalışır; sistem çökmez.

Ağır bağımlılık kullanılmaz: JSONL stdlib `json` ile okunur, böylece çekirdek
kütüphane pandas/pyarrow olmadan da içe aktarılabilir kalır.

Önemli: DMM yalnızca **tekzip** yayımlar; kümedeki her kaydın derecesi
"Yanlış"tır. DESTEKLİYOR sınıfı bu kaynaktan üretilemez, AFAD/valilik
duyuruları ayrı kaynak olarak gerekir (bkz. docs/veri-envanteri.md · D1).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class KnowledgeRecord:
    record_id: str
    claim: str
    fact_check: str
    rating_label: str
    date_published: str
    source: str
    #: Eşleştirme skorunu belirleyen anahtar terimler.
    keywords: tuple[str, ...] = field(default_factory=tuple)
    #: Ayırt edici çapa terimler. Kaydın eşleşebilmesi için bunlardan EN AZ
    #: BİRİ metinde geçmelidir. Çapa olmadan yalnızca genel terimlerle
    #: ("yıkıldı", şehir adı) eşleşmek, alakasız bir tekzibi içeriğe
    #: iliştirilmesine yol açar.
    anchors: tuple[str, ...] = field(default_factory=tuple)


SEEDED_RECORDS: list[KnowledgeRecord] = [
    KnowledgeRecord(
        record_id="DMM-2026-0904-11",
        claim="Şanlıurfa'da baraj yıkıldı, şehir su altında kalacak",
        fact_check=(
            "DSİ ve Şanlıurfa Valiliği, bölgedeki barajlarda yapısal hasar "
            "bulunmadığını, su seviyelerinin normal aralıkta olduğunu bildirmiştir."
        ),
        rating_label="YANLIŞ",
        date_published="04.09.2026",
        source="İletişim Başkanlığı DMM",
        keywords=("baraj", "yikil", "su altinda", "sanliurfa"),
        anchors=("baraj",),
    ),
    KnowledgeRecord(
        record_id="DMM-2026-0904-12",
        claim="AFAD ikinci büyük deprem uyarısı yaptı",
        fact_check=(
            "AFAD, deprem tahmininin bilimsel olarak mümkün olmadığını ve "
            "kurum adına böyle bir uyarı yapılmadığını duyurmuştur."
        ),
        rating_label="YANLIŞ",
        date_published="04.09.2026",
        source="İletişim Başkanlığı DMM",
        keywords=("ikinci", "deprem", "afad", "uyari", "bekleniyor"),
        anchors=("ikinci deprem", "ikinci buyuk deprem", "artci bekleniyor"),
    ),
    KnowledgeRecord(
        record_id="AFAD-2026-0904-03",
        claim="Bölgede arama kurtarma çalışmaları sürüyor",
        fact_check=(
            "AFAD koordinasyonunda 42 ekip sahada görev yapmaktadır; "
            "çalışmalar kesintisiz sürmektedir."
        ),
        rating_label="DOĞRU",
        date_published="04.09.2026",
        source="AFAD",
        keywords=("arama", "kurtarma", "ekip", "saha"),
        anchors=("arama kurtarma", "ekipler sahada"),
    ),
    KnowledgeRecord(
        record_id="MGM-2026-0903-08",
        claim="Bölge için kuvvetli yağış uyarısı verildi",
        fact_check=(
            "Meteoroloji Genel Müdürlüğü, bölge için sarı kodlu kuvvetli yağış "
            "uyarısı yayımlamıştır."
        ),
        rating_label="DOĞRU",
        date_published="03.09.2026",
        source="Meteoroloji Genel Müdürlüğü",
        keywords=("yagis", "uyari", "sari kod", "meteoroloji"),
        anchors=("yagis", "sari kod"),
    ),
    KnowledgeRecord(
        record_id="DMM-2026-0902-05",
        claim="Şehir tahliye ediliyor, valilik boşaltma kararı aldı",
        fact_check=(
            "Valilik, herhangi bir tahliye kararı alınmadığını, vatandaşların "
            "resmî hesapları takip etmesi gerektiğini açıklamıştır."
        ),
        rating_label="YANLIŞ",
        date_published="02.09.2026",
        source="İletişim Başkanlığı DMM",
        keywords=("tahliye", "bosalt", "valilik", "terk"),
        anchors=("tahliye", "sehri terk", "bosalt"),
    ),
]


#: JSONL havuzunun ağırlık dizinindeki konumu.
KNOWLEDGE_DIR = "m5_knowledge"
KNOWLEDGE_FILE = "kayitlar.jsonl"


def _dmm_yolu() -> Path:
    from krizkalkan_core.models.runtime import model_root

    return model_root() / KNOWLEDGE_DIR / KNOWLEDGE_FILE


def load_dmm(path: Path | None = None) -> list[KnowledgeRecord]:
    """DMM kayıtlarını JSONL'den okur; dosya yoksa boş liste döner.

    Bozuk satırlar atlanır ve loglanır: tek bir hatalı kayıt tüm havuzu
    düşürmemelidir.
    """
    hedef = path or _dmm_yolu()
    if not hedef.exists():
        logger.info("DMM havuzu bulunamadı (%s); yalnızca tohum kayıtlar kullanılıyor", hedef)
        return []

    kayitlar: list[KnowledgeRecord] = []
    with hedef.open(encoding="utf-8") as f:
        for satir_no, satir in enumerate(f, 1):
            satir = satir.strip()
            if not satir:
                continue
            try:
                ham = json.loads(satir)
                kayitlar.append(
                    KnowledgeRecord(
                        record_id=ham["record_id"],
                        claim=ham["claim"],
                        fact_check=ham["fact_check"],
                        rating_label=ham["rating_label"],
                        date_published=ham["date_published"],
                        source=ham["source"],
                        keywords=tuple(ham.get("keywords", ())),
                        anchors=tuple(ham.get("anchors", ())),
                    )
                )
            except (json.JSONDecodeError, KeyError) as exc:
                logger.warning("Bozuk havuz kaydı atlandı (%s:%d): %s", hedef, satir_no, exc)

    logger.info("DMM havuzu yüklendi: %d kayıt", len(kayitlar))
    return kayitlar


@lru_cache(maxsize=1)
def records() -> tuple[KnowledgeRecord, ...]:
    """Havuzun tamamı — tohum kayıtlar önce, DMM kayıtları sonra.

    Sıra anlamlıdır: eşit benzerlikte tohum kayıt kazanır, böylece demo
    senaryoları DMM havuzu yüklendiğinde de aynı sonucu üretir.
    """
    return (*SEEDED_RECORDS, *load_dmm())


def reset_cache() -> None:
    """Havuz önbelleğini temizler (testler ve havuz yeniden inşası için)."""
    records.cache_clear()
