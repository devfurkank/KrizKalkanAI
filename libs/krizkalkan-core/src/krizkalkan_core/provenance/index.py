"""M1 köken indeksi — algısal karma üzerinde en yakın komşu araması.

İki karma birlikte sorgulanır ve **en iyisi** alınır. Gerekçe ölçüldü
(docs/metrikler/m1-dayaniklilik.md): dHash ölçekleme ve yeniden kodlamaya
neredeyse bağışık, pHash ise kırpma ve sıkıştırmada daha iyi tutunuyor.
Tek karmayla çalışan bir indeks, saldırı türüne göre ya birinde ya diğerinde
kör kalır.

Arama, kayıt sayısı birkaç bin mertebesindeyken numpy ile tam taramadır:
64 bitlik XOR + popcount, on binlerce kayıtta bile mikrosaniyeler sürer ve
yaklaşıklık hatası taşımaz. FAISS'in IVF-PQ'su milyon ölçeği içindir
(rapor 3.1 · M1) ve kayıt sayısı `IVF_ESIGI`'ni aştığında gerekir.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from krizkalkan_core.models import ModelSpec, registry
from krizkalkan_core.provenance.hashing import HASH_BITS, MATCH_MAX_DISTANCE

logger = logging.getLogger(__name__)

MODEL_ADI = "m1_provenance"
GEREKLI_DOSYALAR = ("index.jsonl",)

#: Bu kayıt sayısının üzerinde tam tarama yerine yaklaşık indeks gerekir.
IVF_ESIGI = 1_000_000


@dataclass(frozen=True, slots=True)
class Kayit:
    """İndeksteki tek bir referans görüntü."""

    kayit_id: str
    olay: str
    konum: str
    ilk_yayin: str | None
    kaynak_url: str | None
    lisans: str | None
    dosya: str
    #: Hangi görünümden üretildi ("tam", "merkez_%80" …). Aynı kayıt birden
    #: çok görünümle indekslenir; kırpma saldırısını bu yakalar.
    gorunum: str = "tam"


@dataclass(frozen=True, slots=True)
class Eslesme:
    """Sorgunun indekste bulduğu en yakın kayıt."""

    kayit: Kayit
    mesafe: int
    benzerlik: float
    #: Eşleşmeyi hangi karma sağladı — kanıt panelinde gösterilir.
    karma_turu: str

    @property
    def eslesti(self) -> bool:
        return self.mesafe <= MATCH_MAX_DISTANCE


class ProvenanceIndex:
    """Algısal karma indeksi."""

    def __init__(self, dizin: Path) -> None:
        import numpy as np

        self._np = np
        self.kayitlar: list[Kayit] = []
        dhashler: list[int] = []
        phashler: list[int] = []

        with (dizin / "index.jsonl").open(encoding="utf-8") as f:
            for satir_no, satir in enumerate(f, 1):
                satir = satir.strip()
                if not satir:
                    continue
                try:
                    ham = json.loads(satir)
                    self.kayitlar.append(
                        Kayit(
                            kayit_id=ham["kayit_id"],
                            olay=ham["olay"],
                            konum=ham["konum"],
                            ilk_yayin=ham.get("ilk_yayin"),
                            kaynak_url=ham.get("kaynak_url"),
                            lisans=ham.get("lisans"),
                            dosya=ham["dosya"],
                            gorunum=ham.get("gorunum", "tam"),
                        )
                    )
                    dhashler.append(int(ham["dhash"], 16))
                    phashler.append(int(ham["phash"], 16))
                except (json.JSONDecodeError, KeyError, ValueError) as hata:
                    logger.warning("Bozuk indeks satırı atlandı (%d): %s", satir_no, hata)

        if not self.kayitlar:
            raise ValueError(f"indeks boş: {dizin / 'index.jsonl'}")

        self.dhash = np.array(dhashler, dtype=np.uint64)
        self.phash = np.array(phashler, dtype=np.uint64)
        logger.info("Köken indeksi yüklendi: %d kayıt", len(self.kayitlar))

    def __len__(self) -> int:
        return len(self.kayitlar)

    def _mesafeler(self, dizi, sorgu: int):
        """Vektörize Hamming mesafesi."""
        np = self._np
        farklar = np.bitwise_xor(dizi, np.uint64(sorgu))
        return np.bitwise_count(farklar).astype(np.int32)

    def ara(self, dhash: int, phash: int, k: int = 3) -> list[Eslesme]:
        """En yakın k kaydı döndürür; iki karmanın iyisi kazanır."""
        np = self._np
        d_mesafe = self._mesafeler(self.dhash, dhash)
        p_mesafe = self._mesafeler(self.phash, phash)

        en_iyi = np.minimum(d_mesafe, p_mesafe)
        tur = np.where(d_mesafe <= p_mesafe, "dHash", "pHash")
        sira = np.argsort(en_iyi, kind="stable")[:k]

        return [
            Eslesme(
                kayit=self.kayitlar[int(i)],
                mesafe=int(en_iyi[i]),
                benzerlik=round(1.0 - int(en_iyi[i]) / HASH_BITS, 4),
                karma_turu=f"{tur[i]} · {self.kayitlar[int(i)].gorunum}",
            )
            for i in sira
        ]


def _yukle(dizin: Path) -> ProvenanceIndex:
    return ProvenanceIndex(dizin)


registry.register(
    ModelSpec(
        name=MODEL_ADI,
        module="M1",
        title="Köken referans indeksi (dHash + pHash)",
        files=GEREKLI_DOSYALAR,
        loader=_yukle,
        # İndeks bir model değil, veri yapısıdır: çalışma zamanı gerektirmez.
        requires_runtime=None,
        kabul_metrigi="recall1_temiz",
        kabul_esigi=0.80,
    )
)


def get() -> ProvenanceIndex | None:
    return registry.get(MODEL_ADI)


def available() -> bool:
    return get() is not None


def reason() -> str:
    return registry.reason(MODEL_ADI)
