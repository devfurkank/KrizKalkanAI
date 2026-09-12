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

**Manifest zincirinin tamamı taranır.** Bazı üreticiler belirleyici kaydı
aktif manifeste değil, köken zincirindeki bir üst manifeste koyuyor; yalnızca
aktife bakmak o kanıtı tamamen kaçırır (ayrıntı: `_zincirde_ai_ara`).
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
    #: Dosyada C2PA verisi var ama kriptografik olarak okunamadı.
    #: `IMZA_YOK`tan ayrıdır: orada hiç veri yok, burada var ama doğrulanamıyor.
    IMZA_OKUNAMADI = "imza_okunamadı"


#: Durum → kullanıcıya gösterilen açıklama.
ACIKLAMA: dict[C2paDurum, str] = {
    C2paDurum.AI_IMZALI: "C2PA: içerik yapay zekâ üretimi olarak imzalanmış",
    C2paDurum.CIHAZ_IMZALI: "C2PA: cihaz imzası doğrulandı, üretim zinciri bozulmamış",
    C2paDurum.IMZA_YOK: "C2PA üstverisi bulunamadı",
    C2paDurum.IMZA_GECERSIZ: "C2PA imzası doğrulanamadı",
    C2paDurum.IMZA_OKUNAMADI: "İçerikte C2PA verisi var ancak doğrulanamadı",
}

#: Durum → sinyal skoru. İmza kriptografik kanıt olduğu için uçlara yakındır;
#: imza yokluğu ise karara girmez (modül çekinir).
#:
#: `IMZA_OKUNAMADI` bilinçli olarak **0,0**'dır ve karara girmez. İşaret taraması
#: ham baytlarda dize arar; o dizeler gerçek bir fotoğrafın içine kolayca
#: yazılabilir. Skor verilseydi, herkesin bir başkasının gerçek fotoğrafını
#: birkaç bayt ekleyerek işaretletebileceği bir enjeksiyon yolu açılırdı.
#: Bulgu yalnızca **bilgi** olarak taşınır.
SKOR: dict[C2paDurum, float] = {
    C2paDurum.AI_IMZALI: 0.97,
    C2paDurum.CIHAZ_IMZALI: 0.02,
    C2paDurum.IMZA_YOK: 0.0,
    C2paDurum.IMZA_GECERSIZ: 0.55,
    C2paDurum.IMZA_OKUNAMADI: 0.0,
}

#: Ham baytlarda aranan C2PA/JUMBF işaretleri.
#:
#: Bu tarama **sezgiseldir ve yetkili değildir**: yetkili olan kriptografik
#: ayrıştırmadır. Yalnızca ayrıştırma başarısız olduğunda, "hiç veri yok" ile
#: "veri var ama okuyamadım" durumlarını ayırmak için çalışır.
IKILI_ISARETLER: tuple[bytes, ...] = (
    b"c2pa.actions",
    b"c2pa.hash.data",
    b"trainedAlgorithmicMedia",
    b"c2pa-rs",
    b"jumbf",
)

#: İşaret taramasının okuyacağı azami bayt. C2PA bloğu kapsayıcının başında
#: ya da sonunda durur.
ISARET_TARAMA_BAYT = 512 * 1024


@dataclass(frozen=True, slots=True)
class C2paSonuc:
    durum: C2paDurum
    uretici: str | None = None
    dijital_kaynak: str | None = None
    ayrinti: str | None = None
    #: Kanıt aktif manifestte mi, yoksa üst manifestlerden birinde mi bulundu?
    #: Zincirden gelen kanıt da kriptografik olarak imzalıdır; fark yalnızca
    #: kullanıcıya gösterilen açıklamadadır.
    zincirden: bool = False
    #: Dosyadaki toplam manifest sayısı — tanılama ve kanıt paneli için.
    manifest_sayisi: int = 0

    @property
    def aciklama(self) -> str:
        return ACIKLAMA[self.durum]

    @property
    def skor(self) -> float:
        return SKOR[self.durum]

    @property
    def cekinmeli(self) -> bool:
        """İmza yoksa ya da okunamadıysa modül karar vermez.

        Yokluk kanıt değildir; okunamama da değildir. İkisi ayrı raporlanır
        çünkü ikincisi operatöre "bu dosyada bir şey var, bakılmalı" der.
        """
        return self.durum in (C2paDurum.IMZA_YOK, C2paDurum.IMZA_OKUNAMADI)


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


def _zincirde_ai_ara(manifestler: dict, aktif_kimlik: str) -> tuple[bool, str | None, str | None]:
    """Aktif manifest dışındaki manifestlerde AI üretim kaydı arar.

    **Neden gerekli.** Bazı üreticiler belirleyici kaydı aktif manifeste değil,
    köken zincirindeki bir ÜST manifeste koyuyor. OpenAI görsellerinde tipik
    dizilim şudur:

        1. manifest (üst)  : c2pa.created · GPT-4o · trainedAlgorithmicMedia
        2. manifest (aktif): c2pa.opened  · bilgi taşımıyor

    Yalnızca aktif manifeste bakmak, belirleyici kanıtı tamamen kaçırır. Bu
    fonksiyon eklenmeden önce sistem bu dosyaları "cihaz imzalı" sayıyordu.

    Zincirden gelen kayıt da kriptografik olarak aynı imzanın kapsamındadır;
    güvenilirliği aktif manifesttekinden düşük değildir. Fark yalnızca
    kullanıcıya gösterilen açıklamada belirtilir.

    ⚠ Sınır: bu tarama zincirdeki **herhangi bir** AI kaydını belirleyici
    sayar. Gerçek bir fotoğrafın içine AI üretimi bir öğe yerleştirilmiş
    bileşik içerikte de tetiklenir. Ayrım için öğe (ingredient) ilişkilerinin
    izlenmesi gerekir; bu sürümde yapılmıyor ve model kartında yazılı.
    """
    for kimlik, manifest in manifestler.items():
        if kimlik == aktif_kimlik:
            continue
        ai, kaynak = _ai_uretimi_mi(manifest)
        if ai:
            return True, kaynak, _uretici_adi(manifest)
    return False, None, None


def _ikili_isaret_ara(yol: Path) -> str | None:
    """Ham baytlarda C2PA işareti arar; bulursa hangisini bulduğunu döndürür.

    Kriptografik ayrıştırma başarısız olduğunda devreye girer ve tek bir işi
    vardır: "dosyada hiç C2PA verisi yok" ile "veri var ama okuyamadım"
    durumlarını ayırmak. İkincisi, desteklenmeyen bir kapsayıcı biçimi ya da
    kesilmiş bir dosya anlamına gelir ve operatöre bildirilmeye değer.

    **Karara girmez.** Gerekçesi `SKOR` sözlüğünde yazılı: aranan şey ham
    dizelerdir ve gerçek bir fotoğrafın içine yazılabilir.
    """
    try:
        boyut = yol.stat().st_size
        with yol.open("rb") as dosya:
            bas = dosya.read(min(ISARET_TARAMA_BAYT, boyut))
            son = b""
            if boyut > 2 * ISARET_TARAMA_BAYT:
                dosya.seek(-ISARET_TARAMA_BAYT, 2)
                son = dosya.read(ISARET_TARAMA_BAYT)
    except OSError:
        return None

    ham = bas + son
    for isaret in IKILI_ISARETLER:
        if isaret in ham:
            return isaret.decode("ascii", errors="replace")
    return None


def _okunamadi(yol: Path, ayrinti: str) -> C2paSonuc:
    """Ayrıştırma başarısız — dosyada yine de C2PA izi var mı?"""
    if (isaret := _ikili_isaret_ara(yol)) is not None:
        return C2paSonuc(
            durum=C2paDurum.IMZA_OKUNAMADI,
            ayrinti=f"ham baytlarda '{isaret}' işareti bulundu · {ayrinti}",
        )
    return C2paSonuc(durum=C2paDurum.IMZA_YOK, ayrinti=ayrinti or None)


def dogrula(yol: Path | str) -> C2paSonuc:
    """Dosyanın C2PA üstverisini okur ve doğrular.

    Hiçbir koşulda istisna fırlatmaz: doğrulanamayan dosya IMZA_YOK sayılır ve
    modül çekinir. Köken üstverisi bir yardımcı sinyaldir; okunamaması analizin
    tamamını durdurmamalıdır.
    """
    yol = Path(yol)
    try:
        import c2pa
    except ImportError:
        logger.info("c2pa paketi kurulu değil; üstveri doğrulaması atlandı")
        return _okunamadi(yol, "c2pa paketi kurulu değil")

    try:
        with c2pa.Reader(str(yol)) as okuyucu:
            ham = json.loads(okuyucu.json())
            # is_valid bir ÖZELLİKTİR, metot değil; çağırmak TypeError üretir ve
            # geniş except bunu "imza yok"a çevirip imzalı dosyayı gizliyordu.
            gecerli = bool(okuyucu.is_valid)
    except Exception as hata:  # ManifestNotFound dahil her şey
        ad = type(hata).__name__
        if "NotFound" in ad or "no JUMBF" in str(hata):
            # Kütüphane "manifest yok" diyor. Yine de ham tarama yapılır:
            # desteklenmeyen bir kapsayıcıda veri durabilir.
            return _okunamadi(yol, "")
        logger.info("C2PA okunamadı (%s): %s", yol, ad)
        return _okunamadi(yol, ad)

    manifestler = ham.get("manifests", {}) or {}
    aktif_kimlik = ham.get("active_manifest", "")
    aktif = manifestler.get(aktif_kimlik, {})
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
            manifest_sayisi=len(manifestler),
        )

    # ── Önce aktif manifest, sonra zincirin tamamı ──
    ai, kaynak = _ai_uretimi_mi(aktif)
    zincirden = False
    if not ai:
        ai, kaynak, zincir_ureticisi = _zincirde_ai_ara(manifestler, aktif_kimlik)
        if ai:
            zincirden = True
            uretici = uretici or zincir_ureticisi

    return C2paSonuc(
        durum=C2paDurum.AI_IMZALI if ai else C2paDurum.CIHAZ_IMZALI,
        uretici=uretici,
        dijital_kaynak=kaynak,
        ayrinti=(
            "kayıt aktif manifestte değil, köken zincirindeki bir üst manifestte bulundu"
            if zincirden
            else None
        ),
        zincirden=zincirden,
        manifest_sayisi=len(manifestler),
    )
