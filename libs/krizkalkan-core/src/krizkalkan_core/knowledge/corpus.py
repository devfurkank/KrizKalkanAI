"""Doğrulanmış kriz bilgi havuzu — DMM Dezenformasyon Bültenleri şeması.

Gerçek sistemde bu havuz `iletisim/dezenformasyon-bultenleri` veri kümesinden
(2.810 iddia–tekzip çifti, CC BY 4.0) yüklenir ve üzerine AFAD, valilik, AKOM
ve meteoroloji akışları eklenir. Alan adları veri kümesiyle birebir aynıdır:
claim, fact_check, rating_label, date_published.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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


RECORDS: list[KnowledgeRecord] = [
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
