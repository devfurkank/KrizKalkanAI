"""M4 — C2PA / Content Credentials köken üstverisi doğrulaması.

Diğer M4 sinyalleri olasılıksaldır; bu değildir. C2PA imzası kriptografik bir
kayıttır: içerik yapay zekâ ile üretildiyse ve üretici bunu imzaladıysa sistem
tahmin etmez, **doğrular** (rapor 3.1 · M4).

Dört durum ayrılır ve karıştırılmamaları önemlidir:

    AI_IMZALI      üretici içeriği "yapay zekâ üretimi" olarak imzalamış
    CIHAZ_IMZALI   cihaz imzası doğrulandı, üretim zinciri bozulmamış
    IMZA_YOK       üstveri yok — içerik hakkında HİÇBİR ŞEY söylemez
    IMZA_GECERSIZ  imza var ama doğrulanamıyor (kurcalanmış veya kopuk zincir)

`IMZA_YOK` bir suçlama değildir: C2PA yaygın değildir ve imzasız içerik
kuraldır, istisna değil.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)

#: C2PA'nın "yapay zekâ ile üretilmiş" için kullandığı dijital kaynak türleri.
#: Ad alanı sürümler arasında değiştiği için sonek eşleşmesi yapılır.
AI_KAYNAK_TURLERI = (
    "trainedAlgorithmicMedia",
    "compositeSynthetic",
    "algorithmicMedia",
)

#: Üretim eylemini bildiren assertion etiketinin ÖNEKİ.
#:
#: Tam eşleşme kullanılmaz: C2PA assertion etiketleri sürüm eki taşır
#: ("c2pa.actions", "c2pa.actions.v2", …) ve tam eşleşme yeni sürümleri
#: sessizce kaçırır. Bu, imzalı bir AI görüntüsünün "imza yok" sayılmasına
#: yol açıyordu.
EYLEM_ETIKET_ONEKI = "c2pa.actions"


class C2paDurum(StrEnum):
    AI_IMZALI = "ai_imzalı"
    CIHAZ_IMZALI = "cihaz_imzalı"
    IMZA_YOK = "imza_yok"
    IMZA_GECERSIZ = "imza_geçersiz"


#: Durum → kullanıcıya gösterilen açıklama.
ACIKLAMA: dict[C2paDurum, str] = {
    C2paDurum.AI_IMZALI: "C2PA: içerik yapay zekâ üretimi olarak imzalanmış",
    C2paDurum.CIHAZ_IMZALI: "C2PA: cihaz imzası doğrulandı, üretim zinciri bozulmamış",
    C2paDurum.IMZA_YOK: "C2PA üstverisi bulunamadı",
    C2paDurum.IMZA_GECERSIZ: "C2PA imzası doğrulanamadı",
}

#: Durum → sinyal skoru. İmza kriptografik kanıt olduğu için uçlara yakındır;
#: imza yokluğu ise karara girmez (modül çekinir).
SKOR: dict[C2paDurum, float] = {
    C2paDurum.AI_IMZALI: 0.97,
    C2paDurum.CIHAZ_IMZALI: 0.02,
    C2paDurum.IMZA_YOK: 0.0,
    C2paDurum.IMZA_GECERSIZ: 0.55,
}


@dataclass(frozen=True, slots=True)
class C2paSonuc:
    durum: C2paDurum
    uretici: str | None = None
    dijital_kaynak: str | None = None
    ayrinti: str | None = None

    @property
    def aciklama(self) -> str:
        return ACIKLAMA[self.durum]

    @property
    def skor(self) -> float:
        return SKOR[self.durum]

    @property
    def cekinmeli(self) -> bool:
        """İmza yoksa modül karar vermez — yokluk kanıt değildir."""
        return self.durum is C2paDurum.IMZA_YOK


def _uretici_adi(manifest: dict) -> str | None:
    """Üretici adını manifestin farklı sürümlerinden çıkarır."""
    if ad := manifest.get("claim_generator"):
        return str(ad)
    bilgi = manifest.get("claim_generator_info") or []
    if isinstance(bilgi, list) and bilgi and isinstance(bilgi[0], dict):
        parcalar = [str(bilgi[0].get(k)) for k in ("name", "version") if bilgi[0].get(k)]
        if parcalar:
            return " ".join(parcalar)
    return manifest.get("title")


def _ai_uretimi_mi(manifest: dict) -> tuple[bool, str | None]:
    """Manifestteki eylem assertion'ları içeriğin AI üretimi olduğunu söylüyor mu?"""
    for assertion in manifest.get("assertions", []):
        if not str(assertion.get("label", "")).startswith(EYLEM_ETIKET_ONEKI):
            continue
        for eylem in assertion.get("data", {}).get("actions", []):
            kaynak = eylem.get("digitalSourceType", "")
            if any(kaynak.endswith(tur) for tur in AI_KAYNAK_TURLERI):
                return True, kaynak
    return False, None


def dogrula(yol: Path | str) -> C2paSonuc:
    """Dosyanın C2PA üstverisini okur ve doğrular.

    Hiçbir koşulda istisna fırlatmaz: doğrulanamayan dosya IMZA_YOK sayılır ve
    modül çekinir. Köken üstverisi bir yardımcı sinyaldir; okunamaması analizin
    tamamını durdurmamalıdır.
    """
    try:
        import c2pa
    except ImportError:
        logger.info("c2pa paketi kurulu değil; üstveri doğrulaması atlandı")
        return C2paSonuc(durum=C2paDurum.IMZA_YOK, ayrinti="c2pa paketi yok")

    try:
        with c2pa.Reader(str(yol)) as okuyucu:
            ham = json.loads(okuyucu.json())
            # is_valid bir ÖZELLİKTİR, metot değil; çağırmak TypeError üretir ve
            # geniş except bunu "imza yok"a çevirip imzalı dosyayı gizliyordu.
            gecerli = bool(okuyucu.is_valid)
    except Exception as hata:  # ManifestNotFound dahil her şey
        ad = type(hata).__name__
        if "NotFound" in ad or "no JUMBF" in str(hata):
            return C2paSonuc(durum=C2paDurum.IMZA_YOK)
        logger.info("C2PA okunamadı (%s): %s", yol, ad)
        return C2paSonuc(durum=C2paDurum.IMZA_YOK, ayrinti=ad)

    aktif = ham.get("manifests", {}).get(ham.get("active_manifest", ""), {})
    uretici = _uretici_adi(aktif)

    # Kütüphanenin kendi doğrulama durumu ikinci bir kontrol: is_valid ile
    # ayrıştıklarında imza güvenilmez sayılır.
    durum_metni = str(ham.get("validation_state", "")).lower()
    if durum_metni and durum_metni != "valid":
        gecerli = False

    if not gecerli:
        return C2paSonuc(
            durum=C2paDurum.IMZA_GECERSIZ,
            uretici=uretici,
            ayrinti="imza zinciri doğrulanamadı",
        )

    ai, kaynak = _ai_uretimi_mi(aktif)
    return C2paSonuc(
        durum=C2paDurum.AI_IMZALI if ai else C2paDurum.CIHAZ_IMZALI,
        uretici=uretici,
        dijital_kaynak=kaynak,
    )
