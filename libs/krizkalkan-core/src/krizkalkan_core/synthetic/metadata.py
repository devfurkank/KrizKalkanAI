"""M4 — Üretici üstverisi: görüntünün içine gömülü üretim izleri.

Üretici araçlar ürettikleri dosyaya çoğu zaman kendi parametrelerini yazar:
Stable Diffusion ve ComfyUI, PNG `tEXt` bloklarına `parameters`, `prompt`,
`workflow` alanlarını gömer; kimi araçlar EXIF `Software` alanına adını
bırakır. Bu bir **tahmin değil, beyandır** — bulunduğunda kullanıcıya gömülü
istemin kendisi gösterilebilir.

Sinyal bu yüzden C2PA ile aynı ailededir: olasılıksal değil, belgesel.
Sinir ağı detektörünün yanında değil, **onun yerine** güvenilir olan yol budur
(bkz. `docs/metrikler/m4-ustveri.md`).

**Kanıt asimetriktir ve bu modülün tamamını belirler:**

    üretici imzası VAR   → güçlü kanıt: içerik üretilmiş
    kamera telemetrisi VAR → destekleyici kanıt: gerçek çekim
    üstveri YOK          → HİÇBİR ŞEY söylemez → modül çekinir

Son satır pazarlık konusu değildir. Ölçüldü: Wikimedia afet korpusundaki 200
görüntünün **hiçbirinde** kamera alanı yok, yalnızca 30'unda herhangi bir EXIF
var — sosyal platformlar yüklemede üstveriyi siler. Yokluğu kanıt saymak, her
gerçek afet fotoğrafını işaretlemek demekti.

---

**Kaynak ve fark.** Aranacak üretici imzalarının listesi, takım üyesinin kendi
açık kaynak projesi DeepReality'nin üstveri analiz modülünden alındı
(MIT · https://github.com/OmerKurtulus/DeepReality). Kod kopyalanmadı; imza
listesi alındı ve modül bu deponun sözleşmelerine göre sıfırdan yazıldı.

Bilinçli bir tasarım farkı var: kaynak modül, üstveri YOKLUĞUNU da ağırlıklı
toplamda sahtelik yönünde puanlıyor. Burada bu uygulanmadı. Adli inceleme
bağlamında "üstveri silinmiş" zayıf bir şüphe işareti olabilir; kriz
moderasyonunda ise her gerçek afet fotoğrafını işaretlemek demektir. Aynı
ölçüt, iki alanda farklı sonuç doğuruyor.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)


class UstveriDurum(StrEnum):
    """Üstverinin söylediği şey."""

    URETICI_IMZASI = "üretici_imzası"
    KAMERA_TELEMETRISI = "kamera_telemetrisi"
    USTVERI_YOK = "üstveri_yok"


#: Durum → sinyal skoru.
#:
#: Üretici imzası C2PA'dan (0,97) bir tık düşüktür: C2PA kriptografik olarak
#: imzalıdır, `tEXt` bloğu ise değildir ve elle yazılabilir. Ama tehdit modeli
#: asimetriktir — kimse kendi gerçek fotoğrafına "bunu Stable Diffusion üretti"
#: yazmaz. Gerçek risk imzanın SİLİNMESİDİR ve o da sessizliğe yol açar,
#: yanlış suçlamaya değil.
SKOR: dict[UstveriDurum, float] = {
    UstveriDurum.URETICI_IMZASI: 0.92,
    UstveriDurum.KAMERA_TELEMETRISI: 0.03,
    UstveriDurum.USTVERI_YOK: 0.0,
}

#: Üretici araçların üstveriye bıraktığı ALAN ADLARI.
#:
#: Ölçüldü (n=592, OpenFake): üretilmiş görüntülerin %8,3'ü bu alanlardan
#: birini taşıyor; gerçek görüntülerin **%0,0'ı**. Yakalama düşük, kesinlik tam.
IMZA_ALANLARI: tuple[str, ...] = (
    "parameters",
    "prompt",
    "negative_prompt",
    "workflow",
    "sd-metadata",
    "dream",
    "generation_data",
    "comfy",
    "aigc",
)

#: Üstveri DEĞERLERİNDE aranan üretici adları. Alan adı genel olabilir
#: ("Software"), değer ise ele verir.
IMZA_DEGERLERI: tuple[str, ...] = (
    "stable diffusion",
    "automatic1111",
    "comfyui",
    "invoke ai",
    "diffusionbee",
    "sd.next",
    "midjourney",
    "dall-e",
    "dalle",
    "openai",
    "adobe firefly",
    "leonardo.ai",
    "black forest labs",
    "novelai",
    "nightcafe",
    "generative fill",
    "neural filters",
    "runway",
    "kling",
    "pika",
)

#: Gerçek çekimi destekleyen EXIF alanları. İkisi birden aranır: tek başına
#: `Make` bir dönüştürücü tarafından da yazılmış olabilir.
KAMERA_ALANLARI: tuple[str, ...] = ("Make", "Model")

#: Ham bayt taramasının sınırı. XMP ve JPEG COM bölümleri dosyanın başında ya
#: da sonunda durur; tamamını okumak büyük dosyalarda gereksiz maliyettir.
HAM_TARAMA_BAYT = 256 * 1024

#: Ham baytlarda aranacak asgari metin bloğu uzunluğu.
#:
#: Sıkıştırılmış görüntü verisi rastgele bayt dizileridir ve kısa bir üretici
#: adı orada tesadüfen belirir. Ölçümde yaşandı: bir Wikimedia bağış fotoğrafı
#: yalnızca JPEG verisinin içinde "pika" geçtiği için üretilmiş sanıldı. Bu
#: yüzden ham tarama, **okunabilir metin bloklarının içinde** yapılır —
#: XMP ve COM bölümleri böyledir, sıkıştırılmış piksel verisi değildir.
ASGARI_METIN_BLOGU = 24

#: Ham baytlarda aranmasına izin verilen üretici adları.
#:
#: Kısa ve genel adlar (pika, kling, dalle, flux, dream) yalnızca YAPILANDIRILMIŞ
#: alanlarda aranır; ham metinde aranmaları yanlış pozitif üretiyor.
HAM_TARAMADA_ARANANLAR: tuple[str, ...] = (
    "stable diffusion",
    "automatic1111",
    "comfyui",
    "midjourney",
    "adobe firefly",
    "black forest labs",
    "leonardo.ai",
    "novelai",
    "nightcafe",
    "generative fill",
    "neural filters",
)


@dataclass(slots=True)
class UstveriSonuc:
    """Üstveri incelemesinin çıktısı."""

    durum: UstveriDurum
    #: Eşleşen alan adı ya da üretici adı — kanıt panelinde gösterilir.
    isaret: str | None = None
    #: Gömülü metnin kısaltılmış hâli. Kanıtın kendisi budur.
    alinti: str | None = None
    #: Bulunan kamera künyesi (varsa).
    kamera: str | None = None
    #: Tanılama: okunan alan sayıları.
    alanlar: dict[str, int] = field(default_factory=dict)

    @property
    def skor(self) -> float:
        return SKOR[self.durum]

    @property
    def cekinmeli(self) -> bool:
        """Üstveri yoksa modül karar vermez — yokluk kanıt değildir."""
        return self.durum is UstveriDurum.USTVERI_YOK

    @property
    def aciklama(self) -> str:
        if self.durum is UstveriDurum.URETICI_IMZASI:
            return "Dosyanın üstverisinde yapay üretim aracının izi var"
        if self.durum is UstveriDurum.KAMERA_TELEMETRISI:
            return "Dosya kamera çekim künyesi taşıyor"
        return "Dosyada üretim üstverisi bulunamadı"


def _metin_alanlari(goruntu) -> dict[str, str]:
    """PNG `tEXt`/`iTXt` blokları ve PIL'in yüzeye çıkardığı metin alanları."""
    ham = getattr(goruntu, "info", None) or {}
    return {
        str(anahtar): str(deger)
        for anahtar, deger in ham.items()
        # İkili bloklar metin değildir ve ayrı ayrı ele alınır.
        if isinstance(anahtar, str) and anahtar not in ("exif", "icc_profile")
    }


def _exif_alanlari(goruntu) -> dict[str, str]:
    """Etiket adlarına çözülmüş EXIF alanları."""
    try:
        from PIL.ExifTags import TAGS

        ham = goruntu.getexif()
    except Exception:
        return {}
    if not ham:
        return {}
    return {str(TAGS.get(etiket, etiket)): str(deger) for etiket, deger in ham.items()}


def _ham_metin(yol: Path) -> str:
    """Dosyanın baş ve son kısmındaki **okunabilir metin blokları**.

    PIL, JPEG `COM` bölümlerini ve gömülü XMP'yi her zaman yüzeye çıkarmaz;
    üreticiler parametrelerini sıklıkla oraya yazar.

    Ham baytlar olduğu gibi taranmaz: sıkıştırılmış piksel verisi rastgele bayt
    dizisidir ve kısa bir üretici adı orada tesadüfen belirir (ölçümde yaşandı).
    Yalnızca `ASGARI_METIN_BLOGU` uzunluğunda ardışık yazdırılabilir karakter
    dizileri alınır; XMP ve COM bölümleri bu koşulu sağlar, piksel verisi sağlamaz.
    """
    try:
        boyut = yol.stat().st_size
        with yol.open("rb") as dosya:
            bas = dosya.read(min(HAM_TARAMA_BAYT, boyut))
            son = b""
            if boyut > 2 * HAM_TARAMA_BAYT:
                dosya.seek(-HAM_TARAMA_BAYT, 2)
                son = dosya.read(HAM_TARAMA_BAYT)
    except OSError:
        return ""

    bloklar: list[str] = []
    gecerli: list[str] = []
    for bayt in bas + son:
        # Yazdırılabilir ASCII ve temel boşluklar metin sayılır.
        if 32 <= bayt < 127 or bayt in (9, 10, 13):
            gecerli.append(chr(bayt))
            continue
        if len(gecerli) >= ASGARI_METIN_BLOGU:
            bloklar.append("".join(gecerli))
        gecerli.clear()
    if len(gecerli) >= ASGARI_METIN_BLOGU:
        bloklar.append("".join(gecerli))

    return "\n".join(bloklar).casefold()


def _imza_ara(metin: dict[str, str], exif: dict[str, str], ham: str) -> tuple[str, str] | None:
    """Üretici imzasını arar; bulursa (işaret, alıntı) döndürür."""
    # 1. Alan ADI eşleşmesi — en güçlüsü: "parameters" alanı bir kamera
    #    dosyasında bulunmaz.
    for anahtar, deger in metin.items():
        alt = anahtar.casefold()
        if any(alan == alt or alan in alt for alan in IMZA_ALANLARI):
            return anahtar, deger[:220]

    # 2. Alan DEĞERİ eşleşmesi — alan adı genel, değeri ele veriyor.
    for anahtar, deger in list(metin.items()) + list(exif.items()):
        alt = deger.casefold()
        for ad in IMZA_DEGERLERI:
            if ad in alt:
                return f"{anahtar}: {ad}", deger[:220]

    # 3. Ham metin blokları — PIL'in çıkarmadığı XMP/COM bölümleri.
    #    Yalnızca uzun ve ayırt edici adlar aranır; kısa olanlar burada
    #    yanlış pozitif üretiyor.
    for ad in HAM_TARAMADA_ARANANLAR:
        if ad in ham:
            konum = ham.find(ad)
            return f"gömülü metin: {ad}", ham[max(0, konum - 40) : konum + 120].strip()

    return None


def incele(yol: Path | str) -> UstveriSonuc:
    """Dosyanın üstverisini okur ve ne söylediğini sınıflar.

    Hiçbir koşulda istisna fırlatmaz: okunamayan dosya "üstveri yok" sayılır ve
    modül çekinir. Üstveri yardımcı bir sinyaldir; okunamaması analizi
    durdurmamalıdır.
    """
    yol = Path(yol)
    try:
        from PIL import Image

        with Image.open(yol) as goruntu:
            metin = _metin_alanlari(goruntu)
            exif = _exif_alanlari(goruntu)
    except Exception as hata:
        logger.info("Üstveri okunamadı (%s): %s", yol, type(hata).__name__)
        return UstveriSonuc(durum=UstveriDurum.USTVERI_YOK)

    ham = _ham_metin(yol)
    alanlar = {"metin": len(metin), "exif": len(exif)}

    if (bulgu := _imza_ara(metin, exif, ham)) is not None:
        isaret, alinti = bulgu
        return UstveriSonuc(
            durum=UstveriDurum.URETICI_IMZASI,
            isaret=isaret,
            alinti=alinti,
            alanlar=alanlar,
        )

    # Kamera künyesi ancak iki alan birden varsa sayılır: tek başına `Make`
    # bir dönüştürücü tarafından da yazılmış olabilir.
    if all(exif.get(alan) for alan in KAMERA_ALANLARI):
        kamera = " ".join(exif[alan] for alan in KAMERA_ALANLARI).strip()
        return UstveriSonuc(
            durum=UstveriDurum.KAMERA_TELEMETRISI,
            isaret="EXIF kamera künyesi",
            kamera=kamera,
            alanlar=alanlar,
        )

    return UstveriSonuc(durum=UstveriDurum.USTVERI_YOK, alanlar=alanlar)
