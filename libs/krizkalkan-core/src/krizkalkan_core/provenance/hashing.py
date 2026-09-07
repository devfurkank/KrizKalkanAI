"""Algısal karma yardımcıları.

Gerçek sistemde kareler ffmpeg ile çıkarılıp dHash/pHash hesaplanır. Bu sürümde
medya bir parmak izi dizesiyle temsil edilir; karma üretimi ve karşılaştırma
mantığı gerçektir — yalnızca girdinin kaynağı farklıdır. Bu sayede eşik,
Hamming mesafesi ve benzerlik hesabı modeller geldiğinde değişmeden kalır.
"""

from __future__ import annotations

import hashlib

#: 64 bit karma — dHash'in standart uzunluğu.
HASH_BITS = 64

#: Bu Hamming mesafesinin altındaki eşleşmeler "aynı içerik" sayılır.
#: 64 bitte 10 bit fark ≈ %84 benzerlik; literatürdeki yaygın eşiktir.
MATCH_MAX_DISTANCE = 10


def perceptual_hash(payload: str | bytes) -> int:
    """Girdiden kararlı 64 bitlik algısal karma üretir.

    Aynı girdi her zaman aynı karmayı verir; benzer girdiler (aynı önekle
    başlayanlar) yakın karmalar üretir, böylece Hamming mesafesi anlamlı olur.
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big")


def hamming_distance(a: int, b: int) -> int:
    """İki karma arasındaki bit farkı."""
    return (a ^ b).bit_count()


def similarity(a: int, b: int) -> float:
    """Hamming mesafesinden 0–1 aralığında benzerlik."""
    return round(1.0 - hamming_distance(a, b) / HASH_BITS, 4)


def hex_of(value: int) -> str:
    """Karmayı arayüzde gösterilebilir onaltılık biçime çevirir."""
    return f"{value:016x}"
