"""Gerçek medya dosyası yardımcıları — modüller arası ortak.

Boru hattı medyayı iki biçimde alır: demo senaryolarında bir dize parmak izi,
gerçek kullanımda bir dosya yolu. Bu ayrım her modülde ayrı ayrı yapılıyordu;
video desteğiyle birlikte üçüncü bir soru eklendi ("dosya video mu?") ve
cevabın tek yerde verilmesi gerekti.

Görüntü tabanlı modüller (M1 köken indeksi, M2 sahne–iddia) videoyu doğrudan
okuyamaz. Onlara videonun **anahtar karesi** verilir; kare yalnızca analiz
süresince diskte durur ve silinir (docs/etik-protokol.md · KVKK).
"""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

#: Parmak izi bundan uzunsa bir dosya yolu değil, demo tanımlayıcısıdır.
YOL_UZUNLUK_SINIRI = 400

#: Video kabul edilen uzantılar. API yüklenen dosyayı baytlarından tanır ve bu
#: uzantılardan biriyle yazar; istemcinin bildirdiği ada güvenilmez.
VIDEO_UZANTILARI = frozenset({".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi"})

#: Anahtar karenin geçici dosya öneki (testler ve denetim için).
KARE_ONEKI = "kk-kare-"


def dosya_yolu(parmak_izi: str | None) -> Path | None:
    """Parmak izi diskte var olan bir dosyayı gösteriyorsa yolunu döndürür."""
    if not parmak_izi or len(parmak_izi) >= YOL_UZUNLUK_SINIRI or "\n" in parmak_izi:
        return None
    try:
        yol = Path(parmak_izi)
        return yol if yol.is_file() else None
    except (OSError, ValueError):
        return None


def video_mu(yol: Path) -> bool:
    """Dosya uzantısına göre video mu? İçerik doğrulaması API'de yapılır."""
    return yol.suffix.lower() in VIDEO_UZANTILARI


@contextmanager
def anahtar_kare(yol: Path) -> Iterator[Path | None]:
    """Videonun ortadaki karesini geçici bir JPEG olarak verir; blok bitince siler.

    İlk kare seçilmez: sosyal medya videolarında sıklıkla siyah geçiş ya da
    başlık kartıdır. Kare okunamazsa (OpenCV yok, bozuk dosya) None verilir;
    çağıran modül çekinir.
    """
    kare_yolu: Path | None = None
    try:
        import cv2

        kaynak = cv2.VideoCapture(str(yol))
        try:
            toplam = int(kaynak.get(cv2.CAP_PROP_FRAME_COUNT))
            if toplam > 1:
                kaynak.set(cv2.CAP_PROP_POS_FRAMES, toplam // 2)
            okundu, kare = kaynak.read()
        finally:
            kaynak.release()

        if okundu:
            tutamac, ad = tempfile.mkstemp(prefix=KARE_ONEKI, suffix=".jpg")
            os.close(tutamac)
            kare_yolu = Path(ad)
            if not cv2.imwrite(str(kare_yolu), kare, [cv2.IMWRITE_JPEG_QUALITY, 95]):
                kare_yolu.unlink(missing_ok=True)
                kare_yolu = None
    # Kare çıkarımı yardımcı bir adımdır; başarısızlığı analizi durdurmamalı.
    except Exception:
        logger.warning("Videodan anahtar kare çıkarılamadı: %s", yol)
        kare_yolu = None

    try:
        yield kare_yolu
    finally:
        if kare_yolu is not None:
            kare_yolu.unlink(missing_ok=True)
