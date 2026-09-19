"""M4 — Hata seviyesi analizi: görüntüde yerel düzenleme izi.

⛔ **BU MODÜL BORU HATTINA BAĞLI DEĞİLDİR VE BAĞLANMAMALIDIR.**

Kuruldu, ölçüldü ve ölçüm kullanılamayacağını gösterdi. Aynı taban fotoğrafın
yapıştırılmış ve oynanmamış hâli eşli olarak karşılaştırıldığında ayrım gücü
**AUC 0,5805** çıktı — rastgeleden (0,50) neredeyse farksız. Oynanmamış,
yalnızca yeniden kaydedilmiş fotoğrafların **%46'sı** aykırı işaretlendi;
gerçek afet fotoğraflarının **%29,5'i**. Ayrıntı: `docs/metrikler/m4-ela.md`.

Sebebi anlaşıldı: yöntem yapıştırılmış bölgeyi değil, görüntünün **doğal doku
değişimini** ölçüyor. Düz bir gökyüzü ile detaylı bir enkaz alanı yeniden
kaydetmede farklı bozuluyor ve bu fark, yapıştırmanın ürettiğinden büyük.
Eşik oynatmak kurtarmaz: ayrım gücü eşikten bağımsızdır.

Modül ve değerlendirme betiği, olumsuz sonucun kaydı ve ileride daha güçlü bir
adli yöntem (nicemleme tablosu analizi, JPEG hayalet tespiti) denenirse hazır
bir ölçüm koşumu olsun diye tutuluyor.

---

Yöntem basittir ve fiziksel bir gerçeğe dayanır. Bir JPEG yeniden kaydedildiğinde
her bölge, o bölgenin sıkıştırma geçmişine göre farklı miktarda bozulur. Görüntü
baştan sona tek seferde sıkıştırılmışsa bozulma her yerde **benzer** olur. Bir
bölge sonradan yapıştırılmış ya da düzenlenmişse o bölgenin sıkıştırma geçmişi
farklıdır ve yeniden kaydetmede **ayrışır**.

Bu, sentetik üretim değil **yerel oynama** arar: SENTETİK_MEDYA'yı değil,
MANİPÜLE_MEDYA'yı besleyebilecek tek görüntü sinyalidir (rapor 2.2 · taksonomi).

**Ön kabul: kayıplı sıkıştırma geçmişi.** PNG gibi kayıpsız biçimlerde yöntemin
dayanağı yoktur — "fark bulamadım" demek "oynanmamış" demek DEĞİLDİR. Bu
durumda modül çekinir. Kaynak proje sinyali zayıf tutmakla yetiniyor; burada
tümden susuyoruz, çünkü kriz alanında zayıf bir sinyal de sınıf kurabiliyor.

**Yalnızca YEREL aykırılık kanıttır.** Görüntünün tamamının düzgün ya da
gürültülü olması bir şey söylemez; aranan şey, komşularından belirgin biçimde
ayrışan bir bölgedir. Genel tekdüzelik kasten karara katılmaz.

---

**Kaynak ve fark.** Yöntem ve parametreler (yeniden kaydetme kalitesi, ızgara
boyu) takım üyesinin kendi açık kaynak projesi DeepReality'nin hata seviyesi
analizi modülünden alındı (MIT · https://github.com/OmerKurtulus/DeepReality).
Kod kopyalanmadı. İki fark bilinçlidir: kayıpsız biçimlerde çekinme, ve
aykırılık ölçüsünde standart sapma yerine **medyan mutlak sapma** kullanımı —
aranan şeyin kendisi aykırı değer olduğu için standart sapma onların etkisiyle
şişiyor ve aykırılığı gizliyor.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)


class ElaDurum(StrEnum):
    YEREL_AYKIRILIK = "yerel_aykırılık"
    AYKIRILIK_YOK = "aykırılık_yok"
    UYGULANAMAZ = "uygulanamaz"


#: Yeniden kaydetme kalitesi. 90, dokuyu koruyacak kadar yüksek ve sıkıştırma
#: geçmişini görünür kılacak kadar düşüktür.
YENIDEN_KAYIT_KALITESI = 90

#: Görüntü bu ızgaraya bölünür; her hücrenin ortalama hatası ayrı ölçülür.
IZGARA = 8

#: Analiz öncesi azami kenar. Büyük görüntülerde ızgara hücreleri gereksiz
#: büyür ve yerel iz ortalamanın içinde kaybolur.
AZAMI_KENAR = 1024

#: Hücrenin aykırı sayılması için gereken medyan mutlak sapma katı.
#:
#: Standart sapma yerine MAD kullanılıyor: aranan şey aykırı değerin kendisi
#: olduğu için standart sapma o değerin etkisiyle şişer ve aykırılığı gizler.
AYKIRILIK_KATI = 4.0

#: Tam skora karşılık gelen sapma. Eşik ölçümden seçilir; değiştirmeden önce
#: `docs/metrikler/m4-ela.md` okunmalıdır.
TAM_SKOR_SAPMASI = 12.0

#: Kayıplı sıkıştırma geçmişi taşıyan biçimler. Diğerlerinde modül çekinir.
KAYIPLI_BICIMLER = frozenset({"JPEG", "JPG", "MPO", "WEBP"})

#: Bu kenarın altındaki görüntüde ızgara anlamlı hücre üretemez.
ASGARI_KENAR = 128


@dataclass(slots=True)
class ElaSonuc:
    """Hata seviyesi analizinin çıktısı."""

    durum: ElaDurum
    #: En aykırı hücrenin medyan mutlak sapma katı.
    sapma: float = 0.0
    #: Aykırı bulunan hücre sayısı.
    aykiri_hucre: int = 0
    #: En aykırı hücrenin ızgaradaki konumu — kanıt panelinde gösterilir.
    konum: str | None = None
    #: Çekinme gerekçesi.
    gerekce: str | None = None

    @property
    def cekinmeli(self) -> bool:
        return self.durum is not ElaDurum.YEREL_AYKIRILIK

    @property
    def skor(self) -> float:
        """Yerel oynama olasılığı. Çekinme hâlinde 0."""
        if self.cekinmeli:
            return 0.0
        return round(min(self.sapma / TAM_SKOR_SAPMASI, 1.0), 4)

    @property
    def aciklama(self) -> str:
        if self.durum is ElaDurum.YEREL_AYKIRILIK:
            return "Görüntünün bir bölgesi, çevresinden farklı sıkıştırma geçmişi taşıyor"
        if self.durum is ElaDurum.AYKIRILIK_YOK:
            return "Sıkıştırma geçmişi görüntü genelinde tutarlı"
        return "Hata seviyesi analizi bu dosyaya uygulanamıyor"


def incele(yol: Path | str) -> ElaSonuc:
    """Görüntüde yerel düzenleme izi arar.

    Hiçbir koşulda istisna fırlatmaz: okunamayan dosya "uygulanamaz" sayılır ve
    modül çekinir.
    """
    yol = Path(yol)
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return ElaSonuc(durum=ElaDurum.UYGULANAMAZ, gerekce="numpy/pillow kurulu değil")

    try:
        with Image.open(yol) as acik:
            bicim = (acik.format or "").upper()
            # WEBP hem kayıplı hem kayıpsız olabilir; dosyanın kendi bayrağı belirler.
            kayipsiz = bicim not in KAYIPLI_BICIMLER or (
                bicim == "WEBP" and bool(acik.info.get("lossless", False))
            )
            goruntu = acik.convert("RGB")
    except Exception as hata:
        logger.info("ELA için dosya açılamadı (%s): %s", yol, type(hata).__name__)
        return ElaSonuc(durum=ElaDurum.UYGULANAMAZ, gerekce="dosya görüntü olarak okunamadı")

    if kayipsiz:
        # Kayıpsız biçimde sıkıştırma geçmişi yoktur; yöntemin dayanağı yok.
        return ElaSonuc(
            durum=ElaDurum.UYGULANAMAZ,
            gerekce=f"{bicim or 'bilinmeyen'} kayıpsız bir biçim — sıkıştırma geçmişi yok",
        )

    if min(goruntu.size) < ASGARI_KENAR:
        return ElaSonuc(
            durum=ElaDurum.UYGULANAMAZ,
            gerekce=f"çözünürlük ızgara için yetersiz (kısa kenar < {ASGARI_KENAR}px)",
        )

    if max(goruntu.size) > AZAMI_KENAR:
        oran = AZAMI_KENAR / max(goruntu.size)
        yeni = (max(round(goruntu.width * oran), 1), max(round(goruntu.height * oran), 1))
        goruntu = goruntu.resize(yeni, Image.Resampling.BILINEAR)

    # ── Yeniden kaydetme ve fark ──
    tampon = io.BytesIO()
    goruntu.save(tampon, format="JPEG", quality=YENIDEN_KAYIT_KALITESI)
    tampon.seek(0)
    with Image.open(tampon) as yeniden:
        yeniden_dizi = np.asarray(yeniden.convert("RGB"), dtype="int16")

    fark = np.abs(np.asarray(goruntu, dtype="int16") - yeniden_dizi).max(axis=2)

    # ── Izgara hücrelerinin ortalama hatası ──
    yukseklik, genislik = fark.shape
    adim_y, adim_x = yukseklik // IZGARA, genislik // IZGARA
    if adim_y < 1 or adim_x < 1:
        return ElaSonuc(durum=ElaDurum.UYGULANAMAZ, gerekce="ızgara hücresi oluşturulamadı")

    hucreler = np.array(
        [
            [
                fark[sat * adim_y : (sat + 1) * adim_y, sut * adim_x : (sut + 1) * adim_x].mean()
                for sut in range(IZGARA)
            ]
            for sat in range(IZGARA)
        ],
        dtype="float64",
    )

    medyan = float(np.median(hucreler))
    mad = float(np.median(np.abs(hucreler - medyan)))
    if mad < 1e-6:
        # Bütün hücreler birebir aynı: yeniden kodlanmış ya da düz bir görüntü.
        # Ayrım gücü yok; sessiz kalmak doğru cevaptır.
        return ElaSonuc(
            durum=ElaDurum.UYGULANAMAZ,
            gerekce="hata seviyesi görüntü genelinde tamamen düz — ayrım gücü yok",
        )

    sapmalar = (hucreler - medyan) / mad
    en_yuksek = float(sapmalar.max())
    aykiri = int((sapmalar >= AYKIRILIK_KATI).sum())

    if en_yuksek < AYKIRILIK_KATI:
        return ElaSonuc(durum=ElaDurum.AYKIRILIK_YOK, sapma=round(en_yuksek, 3))

    sat, sut = divmod(int(sapmalar.argmax()), IZGARA)
    return ElaSonuc(
        durum=ElaDurum.YEREL_AYKIRILIK,
        sapma=round(en_yuksek, 3),
        aykiri_hucre=aykiri,
        konum=f"ızgara {sat + 1}/{IZGARA} satır · {sut + 1}/{IZGARA} sütun",
    )
