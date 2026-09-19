"""Yüklenen medyanın geçici ele alınışı.

Etik protokol ham medyanın analiz sonrası saklanmamasını taahhüt eder
(docs/etik-protokol.md · KVKK). Medya modülleri — M1 köken indeksi, M2
sahne–iddia, M4 sentetik görüntü/video ve C2PA doğrulaması — dosya yolu
beklediği için baytlar yalnızca analiz süresince sahibine özel (0600) geçici bir
dosyada tutulur ve iş biter bitmez silinir. Sunucuda kopya kalmaz; akışta
medyayı yalnızca yükleyen tarayıcı kendi belleğinden gösterir.

Dosyanın türü baytlarından tanınır; istemcinin bildirdiği içerik türüne ve
dosya adına güvenilmez.
"""

from __future__ import annotations

import io
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, UploadFile

#: Kabul edilen biçimler: PIL'in baytlardan okuduğu biçim → dosya uzantısı.
#: İstemcinin bildirdiği içerik türüne ve dosya adına güvenilmez.
ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}

#: Tek görsel için üst sınır. Sosyal medya görselleri bunun çok altındadır.
MAX_BYTES = 15 * 1024 * 1024

#: Tek video için üst sınır. 60 sn'lik 1080p bir sosyal medya videosu tipik
#: olarak 10–40 MB'tır. Süre sınırı ayrıca M4 video modülünde uygulanır.
MAX_VIDEO_BYTES = 100 * 1024 * 1024

#: ISO BMFF (`ftyp`) kutusu yalnızca videoda değil, HEIC/AVIF görsellerde de
#: bulunur. Bu markalar video sayılmaz.
_GORSEL_MARKALARI = {b"heic", b"heix", b"hevc", b"mif1", b"msf1", b"avif", b"avis"}

MediaKind = Literal["image", "video"]

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


def _video_format(data: bytes) -> str | None:
    """Baytlar bir video kapsayıcısıysa dosya uzantısını, değilse None döndürür."""
    if len(data) >= 12 and data[4:8] == b"ftyp":
        marka = data[8:12]
        if marka in _GORSEL_MARKALARI:
            return None
        return ".mov" if marka == b"qt  " else ".mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3":  # EBML: WebM / Matroska
        return ".webm" if b"webm" in data[:64] else ".mkv"
    if data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return ".avi"
    return None


def _video_cozulebilir(path: Path) -> bool:
    """Video en az bir kare çözülebiliyor mu? OpenCV yoksa karar analize bırakılır."""
    try:
        import cv2
    except ImportError:
        return True
    kaynak = cv2.VideoCapture(str(path))
    try:
        return bool(kaynak.isOpened() and kaynak.read()[0])
    finally:
        kaynak.release()


@contextmanager
def temporary_upload(file: UploadFile) -> Iterator[tuple[Path, MediaKind]]:
    """Yüklenen görseli ya da videoyu doğrular ve yalnızca blok süresince diskte tutar."""
    data = file.file.read(max(MAX_BYTES, MAX_VIDEO_BYTES) + 1)

    kind: MediaKind
    if (video_suffix := _video_format(data)) is not None:
        if len(data) > MAX_VIDEO_BYTES:
            raise HTTPException(413, f"Video {MAX_VIDEO_BYTES // (1024 * 1024)} MB sınırını aşıyor")
        kind, suffix = "video", video_suffix
    else:
        if len(data) > MAX_BYTES:
            raise HTTPException(413, f"Görsel {MAX_BYTES // (1024 * 1024)} MB sınırını aşıyor")
        image_format = _image_format(data)
        if image_format not in ALLOWED_FORMATS:
            raise HTTPException(
                415,
                "Yalnızca JPEG, PNG ve WebP görseller ile MP4, MOV ve WebM videolar "
                "analiz edilebilir",
            )
        kind, suffix = "image", ALLOWED_FORMATS[image_format]

    # mkstemp dosyayı yalnızca sahibinin okuyabileceği izinlerle (0600) açar.
    handle, name = tempfile.mkstemp(prefix=TEMP_PREFIX, suffix=suffix)
    path = Path(name)
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        if kind == "video" and not _video_cozulebilir(path):
            raise HTTPException(
                415, "Video çözümlenemedi — dosya bozuk ya da kodlaması desteklenmiyor"
            )
        yield path, kind
    finally:
        path.unlink(missing_ok=True)
