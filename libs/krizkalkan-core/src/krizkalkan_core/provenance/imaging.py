"""Görüntü üzerinde algısal karma — M1'in ölçüm tarafı.

`hashing.py` karma *karşılaştırma* mantığını tanımlar (Hamming mesafesi, eşik,
benzerlik); bu modül karmanın kaynağını gerçek piksellerden üretir. Ayrım
bilinçlidir: demo parmak izi dizeleri ile gerçek medya aynı karşılaştırma
mantığını kullanır, yalnızca girdinin nereden geldiği değişir.

İki karma birlikte hesaplanır çünkü farklı saldırılara dayanıklıdırlar:

    dHash — komşu piksel farklarına bakar; parlaklık ve ölçek değişimine
            dayanıklı, yeniden kodlamaya çok dayanıklı
    pHash — DCT tabanlı; kırpma ve sıkıştırmaya dHash'ten daha dayanıklı

Ayna çevirme her ikisini de düşürür — o saldırıyı gömme tabanlı arama yakalar
(bkz. index.py). Bu, iki sinyalli tasarımın gerekçesidir.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from PIL.Image import Image

logger = logging.getLogger(__name__)

#: Desteklenen görüntü uzantıları.
GORUNTU_UZANTILARI = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"})

#: dHash/pHash karma boyutu — 8×8 = 64 bit (hashing.HASH_BITS ile aynı).
KARMA_BOYUTU = 8


def gorsel_mi(yol: Path) -> bool:
    return yol.suffix.lower() in GORUNTU_UZANTILARI


def _yukle(kaynak: Path | Image):
    """Yolu veya açık görüntüyü RGB'ye normalize eder."""
    from PIL import Image as PILImage

    goruntu = PILImage.open(kaynak) if isinstance(kaynak, Path) else kaynak
    return goruntu.convert("RGB")


def dhash(kaynak: Path | Image) -> int:
    """Fark karması — 64 bit tamsayı."""
    import imagehash

    return int(str(imagehash.dhash(_yukle(kaynak), hash_size=KARMA_BOYUTU)), 16)


def phash(kaynak: Path | Image) -> int:
    """Algısal karma (DCT tabanlı) — 64 bit tamsayı."""
    import imagehash

    return int(str(imagehash.phash(_yukle(kaynak), hash_size=KARMA_BOYUTU)), 16)


def karmalar(kaynak: Path | Image) -> tuple[int, int]:
    """(dhash, phash) — tek görüntü açılışıyla ikisi birden."""
    goruntu = _yukle(kaynak)
    return dhash(goruntu), phash(goruntu)


# ─────────────────────────── Video ───────────────────────────


def ffmpeg_var_mi() -> bool:
    """ffmpeg kurulu mu? Yoksa video yolu devre dışı kalır, sistem çökmez."""
    import shutil

    return shutil.which("ffmpeg") is not None


def kare_cikar(video: Path, hedef_dizin: Path, *, fps: float = 1.0, azami: int = 30) -> list[Path]:
    """Videodan saniyede bir anahtar kare çıkarır (rapor 3.1 · M1).

    Kare sayısı üst sınırla kesilir: gecikme hedefi (p50 ≤ 8 sn) uzun videolarda
    ancak örneklemeyle tutar ve 30 kare, bir dakikalık içeriğin kökenini
    belirlemeye yeter.

    ffmpeg yoksa boş liste döner ve çağıran katman medyayı analiz edilemez
    sayar — sistemin çökmesindense çekinmesi tercih edilir (rapor 2.2 · Y2).
    """
    if not ffmpeg_var_mi():
        logger.warning("ffmpeg bulunamadı; video kare çıkarımı atlandı: %s", video)
        return []

    import subprocess

    hedef_dizin.mkdir(parents=True, exist_ok=True)
    kalip = hedef_dizin / "kare_%03d.jpg"
    sonuc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            f"fps={fps}",
            "-frames:v",
            str(azami),
            "-q:v",
            "2",
            str(kalip),
        ],
        capture_output=True,
        text=True,
    )
    if sonuc.returncode != 0:
        logger.warning("ffmpeg kare çıkaramadı (%s): %s", video, sonuc.stderr.strip()[:200])
        return []
    return sorted(hedef_dizin.glob("kare_*.jpg"))
