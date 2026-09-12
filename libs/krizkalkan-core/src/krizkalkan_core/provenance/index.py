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
        self.uyumsuz_dosya = self._korpus_tutarliligi(dizin)

    def _korpus_tutarliligi(self, dizin: Path) -> int:
        """İndeksin, yanındaki görüntü korpusuyla aynı görüntülere baktığını doğrular.

        **Neden gerekli.** `fetch_provenance.py` dosyaları indirme sırasına göre
        numaralandırıyor (`00000.jpg`, `00001.jpg`, …). Commons kategorilerinin
        içeriği zamanla değiştiği için iki ayrı koşu aynı adı **başka bir
        görüntüye** verebiliyor. İndeks ile görüntüler ayrı taşındığında
        (ağırlıklar bir kanaldan, veri başka kanaldan) bu sessiz bir bozulma
        üretir: sistem çökmez, yalnızca yanlış cevap verir.

        Yaşandı: iki makine arasında ortak 514 dosya adının %43,8'i farklı
        görüntüye işaret ediyordu ve temiz Recall@1 0,9950 yerine 0,5333 ölçüldü.

        Karşılaştırma `kaynak_url` üzerinden yapılır: aynı ad, aynı kaynak mı?
        """
        kayit_dosyasi = dizin.parent.parent / "data" / "external" / "provenance" / "kayitlar.jsonl"
        # Yol tahmini tutmazsa sessizce geç: bu bir doğrulama, zorunluluk değil.
        if not kayit_dosyasi.exists():
            return 0

        try:
            korpus = {}
            for satir in kayit_dosyasi.read_text(encoding="utf-8").splitlines():
                if satir:
                    kayit = json.loads(satir)
                    korpus[kayit["dosya"]] = kayit.get("kaynak_url")
        except (OSError, json.JSONDecodeError, KeyError):
            return 0

        ortak = uyumsuz = 0
        for kayit in self.kayitlar:
            if (kaynak := korpus.get(kayit.dosya)) is None:
                continue
            ortak += 1
            if kayit.kaynak_url and kaynak != kayit.kaynak_url:
                uyumsuz += 1

        if ortak and uyumsuz / ortak > 0.01:
            logger.error(
                "KÖKEN İNDEKSİ KORPUSLA UYUMSUZ: ortak %d kaydın %d'i (%.1f%%) başka bir "
                "görüntüye işaret ediyor. İndeks ile görüntüler AYNI koşudan gelmeli; "
                "aksi hâlde M1 ölçümleri sessizce yanlış çıkar.",
                ortak,
                uyumsuz,
                100 * uyumsuz / ortak,
            )
        return uyumsuz

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
