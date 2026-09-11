"""M4 · hata seviyesi analizi — çekinme kuralları ve boru hattından uzak durma.

Modül ölçüldü ve **kullanılamaz bulundu** (ayrım gücü AUC 0,5805 ·
`docs/metrikler/m4-ela.md`). Testlerin iki işi var: yöntemin ön kabulü
sağlanmadığında sustuğunu doğrulamak, ve modülün boru hattına sızmadığını
kilitlemek.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from krizkalkan_core.synthetic.ela import ElaDurum, incele

pytest.importorskip("PIL", reason="pillow kurulu değil")
pytest.importorskip("numpy", reason="numpy kurulu değil")


def _gurultulu(kenar: int = 512):
    """Dokusu olan bir görüntü — düz renk ELA'da dejenere sonuç verir."""
    import random

    from PIL import Image

    rastgele = random.Random(0)
    goruntu = Image.new("RGB", (kenar, kenar))
    goruntu.putdata(
        [
            (rastgele.randrange(256), rastgele.randrange(256), rastgele.randrange(256))
            for _ in range(kenar * kenar)
        ]
    )
    return goruntu


def test_kayipsiz_bicimde_cekinilir(tmp_path: Path) -> None:
    """PNG'de sıkıştırma geçmişi yoktur; yöntemin dayanağı yok.

    Bu, kaynak projeden bilinçli ayrıldığımız noktadır: orada sinyal zayıf
    tutuluyor, burada tümden susuluyor. Kriz alanında zayıf bir sinyal de
    sınıf kurabiliyor.
    """
    yol = tmp_path / "a.png"
    _gurultulu().save(yol, "PNG")

    sonuc = incele(yol)

    assert sonuc.durum is ElaDurum.UYGULANAMAZ
    assert sonuc.cekinmeli
    assert sonuc.skor == 0.0
    assert "kayıpsız" in (sonuc.gerekce or "")


def test_kucuk_goruntude_cekinilir(tmp_path: Path) -> None:
    yol = tmp_path / "b.jpg"
    _gurultulu(kenar=64).save(yol, "JPEG", quality=92)

    sonuc = incele(yol)

    assert sonuc.durum is ElaDurum.UYGULANAMAZ
    assert "çözünürlük" in (sonuc.gerekce or "")


def test_okunamayan_dosyada_cekinilir(tmp_path: Path) -> None:
    bozuk = tmp_path / "c.jpg"
    bozuk.write_bytes(b"bu bir goruntu degil")

    assert incele(bozuk).durum is ElaDurum.UYGULANAMAZ


def test_cekinilen_sonucta_skor_sifirdir(tmp_path: Path) -> None:
    """Çekinme hâlinde hiçbir skor karara sızmamalı."""
    yol = tmp_path / "d.png"
    _gurultulu().save(yol, "PNG")

    assert incele(yol).skor == 0.0


def test_modul_boru_hattina_bagli_degildir() -> None:
    """Ölçüm kullanılamaz dediği için ELA hiçbir sinyal üretmemeli.

    Kilit bilinçlidir: ayrım gücü 0,5805 ile rastgeleden farksız çıktı ve
    oynanmamış fotoğrafların %46'sını aykırı işaretledi. İleride biri modülü
    devreye almak isterse önce ölçümü düzeltmek zorunda kalsın.
    """
    from krizkalkan_core.synthetic import engine as synthetic

    kaynak = Path(synthetic.__file__).read_text(encoding="utf-8")

    assert "import ela" not in kaynak
    assert "synthetic.ela" not in kaynak
