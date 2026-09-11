"""M4 · üretici üstverisi — asimetrik kanıt ve yanlış pozitife karşı koruma.

Bu modülün tek satışı kesinliğidir: ölçümde 1.678 gerçek görüntüde sıfır yanlış
pozitif verdi (`docs/metrikler/m4-ustveri.md`). Testler o kesinliği koruyan
kuralları kilitler.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from krizkalkan_core.synthetic.metadata import UstveriDurum, incele

pytest.importorskip("PIL", reason="pillow kurulu değil")


def _png(yol: Path, metin: dict[str, str] | None = None) -> Path:
    """İsteğe bağlı `tEXt` blokları taşıyan küçük bir PNG üretir."""
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    bilgi = PngInfo()
    for anahtar, deger in (metin or {}).items():
        bilgi.add_text(anahtar, deger)
    Image.new("RGB", (64, 64), (10, 120, 200)).save(yol, "PNG", pnginfo=bilgi)
    return yol


# ────────────────────────── üretici imzası ──────────────────────────


def test_uretim_parametresi_alan_adindan_yakalanir(tmp_path: Path) -> None:
    """`parameters` alanı bir kamera dosyasında bulunmaz — en güçlü işaret."""
    yol = _png(
        tmp_path / "a.png",
        {"parameters": "a photo of a flooded street\nSteps: 30, Sampler: Euler a, CFG scale: 7"},
    )

    sonuc = incele(yol)

    assert sonuc.durum is UstveriDurum.URETICI_IMZASI
    assert not sonuc.cekinmeli
    assert sonuc.skor > 0.9
    # Kanıtın kendisi taşınmalı: kullanıcıya gömülü istem gösterilecek.
    assert sonuc.alinti and "flooded street" in sonuc.alinti


def test_uretici_adi_alan_degerinden_yakalanir(tmp_path: Path) -> None:
    yol = _png(tmp_path / "b.png", {"Software": "Stable Diffusion WebUI 1.9"})

    sonuc = incele(yol)

    assert sonuc.durum is UstveriDurum.URETICI_IMZASI
    assert sonuc.isaret and "stable diffusion" in sonuc.isaret.casefold()


# ────────────────────────── asimetri ──────────────────────────


def test_ustveri_yoklugu_sucla_degil_cekinme_sebebidir(tmp_path: Path) -> None:
    """Sosyal platformlar üstveriyi siler; yokluk hiçbir şey söylemez.

    Bu, modülün tamamını belirleyen kuraldır. Yokluğun sahtelik yönünde
    puanlanması, her gerçek afet fotoğrafını işaretlemek demektir.
    """
    yol = _png(tmp_path / "c.png")

    sonuc = incele(yol)

    assert sonuc.durum is UstveriDurum.USTVERI_YOK
    assert sonuc.cekinmeli
    assert sonuc.skor == 0.0


def test_kamera_kunyesi_gercek_cekimi_destekler(tmp_path: Path) -> None:
    from PIL import Image

    yol = tmp_path / "d.jpg"
    goruntu = Image.new("RGB", (64, 64), (200, 200, 200))
    exif = goruntu.getexif()
    exif[271] = "Apple"  # Make
    exif[272] = "iPhone 14 Pro"  # Model
    goruntu.save(yol, "JPEG", exif=exif)

    sonuc = incele(yol)

    assert sonuc.durum is UstveriDurum.KAMERA_TELEMETRISI
    assert sonuc.skor < 0.1
    assert sonuc.kamera and "Apple" in sonuc.kamera


def test_tek_basina_make_kamera_sayilmaz(tmp_path: Path) -> None:
    """Tek alan bir dönüştürücü tarafından da yazılmış olabilir."""
    from PIL import Image

    yol = tmp_path / "e.jpg"
    goruntu = Image.new("RGB", (64, 64), (200, 200, 200))
    exif = goruntu.getexif()
    exif[271] = "Apple"
    goruntu.save(yol, "JPEG", exif=exif)

    assert incele(yol).durum is UstveriDurum.USTVERI_YOK


# ────────────────────────── yanlış pozitif koruması ──────────────────────────


def test_ikili_veride_tesaduf_esleme_sayilmaz(tmp_path: Path) -> None:
    """Sıkıştırılmış piksel verisinde geçen kısa üretici adı imza DEĞİLDİR.

    Gerçek bir vakada yaşandı: Wikimedia'daki bir bağış fotoğrafı, yalnızca
    JPEG verisinin içinde tesadüfen "pika" dizisi geçtiği için "üretilmiş"
    sanıldı. Ham tarama bu yüzden yalnızca okunabilir metin blokları içinde
    ve yalnızca uzun, ayırt edici adlar için yapılır.
    """
    from PIL import Image

    yol = tmp_path / "f.jpg"
    Image.new("RGB", (64, 64), (90, 90, 90)).save(yol, "JPEG")
    ham = bytearray(yol.read_bytes())
    # Kısa adı ikili verinin ortasına, metin bloğu OLUŞTURMADAN göm.
    ham[40:44] = b"pika"
    yol.write_bytes(bytes(ham))

    assert incele(yol).durum is not UstveriDurum.URETICI_IMZASI


def test_gercek_xmp_bolumu_yakalanir(tmp_path: Path) -> None:
    """Gerçek bir XMP bölümündeki üretici adı bulunmalı.

    Bölüm, geçerli bir JPEG APP1 kaydı olarak kurulur: SOI işaretinden sonra
    `FFE1`, uzunluk ve XMP ad alanı önekiyle. Baytları gelişigüzel araya
    sıkıştırmak dosyayı bozar ve modül onu hiç açamaz.
    """
    from PIL import Image

    yol = tmp_path / "g.jpg"
    tampon = io.BytesIO()
    Image.new("RGB", (64, 64), (90, 90, 90)).save(tampon, "JPEG")
    ham = tampon.getvalue()

    onek = b"http://ns.adobe.com/xap/1.0/\x00"
    govde = b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><creator>Midjourney v7</creator></x:xmpmeta>'
    yuk = onek + govde
    app1 = b"\xff\xe1" + (len(yuk) + 2).to_bytes(2, "big") + yuk
    yol.write_bytes(ham[:2] + app1 + ham[2:])

    sonuc = incele(yol)

    assert sonuc.durum is UstveriDurum.URETICI_IMZASI
    assert sonuc.isaret and "midjourney" in sonuc.isaret.casefold()


def test_okunamayan_dosya_cekinmeye_duser(tmp_path: Path) -> None:
    bozuk = tmp_path / "h.jpg"
    bozuk.write_bytes(b"bu bir goruntu degil")

    assert incele(bozuk).durum is UstveriDurum.USTVERI_YOK


# ────────────────────────── motor sözleşmesi ──────────────────────────


def test_imza_sentetik_medya_sinifi_kurar(tmp_path: Path) -> None:
    """Uçtan uca: gömülü üretim parametresi SENTETİK_MEDYA üretmeli."""
    from krizkalkan_core.fusion import engine as fusion
    from krizkalkan_core.synthetic import engine as synthetic
    from krizkalkan_core.taxonomy import Verdict

    yol = _png(tmp_path / "i.png", {"parameters": "earthquake rubble, photorealistic"})

    sinyaller = synthetic.analyse(str(yol), "image", has_audio=False)
    fusion.apply_calibration(sinyaller)
    sinif, guven, _ = fusion.fuse(sinyaller, None, None, None)

    assert sinif is Verdict.SENTETIK_MEDYA
    assert guven > 0.6


def test_ustverisiz_goruntu_sentetik_sanilmaz(tmp_path: Path) -> None:
    """Üstverisiz gerçek görüntü hiçbir koşulda SENTETİK_MEDYA olmamalı."""
    from krizkalkan_core.fusion import engine as fusion
    from krizkalkan_core.synthetic import engine as synthetic
    from krizkalkan_core.taxonomy import Verdict

    yol = _png(tmp_path / "j.png")

    sinyaller = synthetic.analyse(str(yol), "image", has_audio=False)
    fusion.apply_calibration(sinyaller)
    sinif, _, _ = fusion.fuse(sinyaller, None, None, None)

    assert sinif is not Verdict.SENTETIK_MEDYA
