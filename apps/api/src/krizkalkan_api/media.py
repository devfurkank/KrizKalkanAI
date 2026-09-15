"""Yüklenen medyanın geçici ele alınışı.

Etik protokol ham medyanın analiz sonrası saklanmamasını taahhüt eder
(docs/etik-protokol.md · KVKK). Görsel modüller — M1 köken indeksi, M2
sahne–iddia, M4 sentetik görüntü ve C2PA doğrulaması — dosya yolu beklediği
için baytlar yalnızca analiz süresince sahibine özel (0600) geçici bir dosyada
tutulur ve iş biter bitmez silinir. Sunucuda kopya kalmaz; akışta görseli
yalnızca yükleyen tarayıcı kendi belleğinden gösterir.
"""

from __future__ import annotations

import io
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException, UploadFile

#: Kabul edilen biçimler: PIL'in baytlardan okuduğu biçim → dosya uzantısı.
#: İstemcinin bildirdiği içerik türüne ve dosya adına güvenilmez.
ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

#: Tek dosya için üst sınır. Sosyal medya görselleri bunun çok altındadır.
MAX_BYTES = 15 * 1024 * 1024

#: Geçici dosyaların adı bu önekle başlar (testler ve denetim için).
TEMP_PREFIX = "kk-medya-"


def _image_format(data: bytes) -> str | None:
    """Baytlar geçerli bir görselse PIL biçim adını, değilse None döndürür."""
    from PIL import Image, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
            return image.format
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
        return None


@contextmanager
def temporary_upload(file: UploadFile) -> Iterator[Path]:
    """Yüklenen görseli doğrular ve yalnızca blok süresince diskte tutar."""
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"Görsel {MAX_BYTES // (1024 * 1024)} MB sınırını aşıyor")

    image_format = _image_format(data)
    if image_format not in ALLOWED_FORMATS:
        raise HTTPException(415, "Yalnızca JPEG, PNG ve WebP görseller analiz edilebilir")

    # mkstemp dosyayı yalnızca sahibinin okuyabileceği izinlerle (0600) açar.
    handle, name = tempfile.mkstemp(prefix=TEMP_PREFIX, suffix=ALLOWED_FORMATS[image_format])
    path = Path(name)
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        yield path
    finally:
        path.unlink(missing_ok=True)
