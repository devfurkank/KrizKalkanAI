"""M5 geri getirme katmanı — cümle gömmesi + yaklaşık en yakın komşu araması.

İki aşamalı eşleştirmenin birinci aşamasıdır (rapor 3.1 · M5):

    [1] GERİ GETİRME   iddia → en yakın k kayıt        ← bu modül
    [2] ÇIKARIM (NLI)  (iddia, kayıt) → DESTEKLİYOR / ÇELİŞİYOR / İLGİSİZ

Anahtar terim örtüşmesinin yerini alır ancak onu kaldırmaz: gömme modeli
yüklenemezse `available` False döner ve çağıran katman sözlük yoluna düşer.

Ölçek notu: 2.519 kayıt için tam arama (IndexFlatIP) hem daha hızlı hem daha
doğrudur. Rapordaki IVF-PQ kararı milyon ölçeği içindir; kayıt sayısı
`IVF_ESIGI`'ni aştığında indeks tipi otomatik değişir.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from krizkalkan_core.models import ModelSpec, registry

logger = logging.getLogger(__name__)

#: Ağırlık dizinindeki alt dizin ve dosyalar.
MODEL_ADI = "m5_retriever"
#: Kayıt defterinin varlığını aradığı dosyalar. Nicelenmiş ONNX tek dosyadır;
#: nicelenmemiş dışa aktarımda ağırlıklar `kodlayici.onnx.data` içinde durur ve
#: eksikse oturum açılışta patlar — bu yüzden niceleme inşa adımının parçasıdır.
GEREKLI_DOSYALAR = ("gomme.npy", "kayit_kimlikleri.json", "kodlayici.onnx", "tokenizer.json")

#: Bu kayıt sayısının altında FAISS hiç kullanılmaz: birkaç bin vektörde
#: numpy ile tam arama hem daha hızlı hem tam doğrudur (yaklaşıklık hatası yok)
#: ve macOS'ta faiss/onnxruntime arasındaki OpenMP çalışma zamanı çakışmasını
#: da doğuran ek bağımlılığı devreden çıkarır.
FAISS_ESIGI = 50_000

#: Bu kayıt sayısının üzerinde tam arama yerine IVF-PQ kullanılır.
IVF_ESIGI = 100_000

#: e5 ailesi asimetrik öneklerle eğitilmiştir; öneksiz kullanım başarımı düşürür.
SORGU_ONEKI = "query: "
KAYIT_ONEKI = "passage: "

#: Kesme uzunluğu — indeks inşasıyla çıkarımda aynı olmak zorundadır.
MAKS_UZUNLUK = 192


@dataclass(slots=True)
class Aday:
    """Geri getirme sonucu — tek bir kayıt adayı."""

    record_id: str
    benzerlik: float


class Retriever:
    """Gömme tabanlı kayıt arayıcı.

    Sözleşme dar tutulmuştur: `ara()` yalnızca kayıt kimliği ve benzerlik
    döndürür. Kaydın içeriğini havuzdan çözmek çağıranın işidir; böylece bu
    katman havuz şemasından bağımsız kalır.
    """

    def _kodlayici_kur(self, dizin: Path) -> None:
        """Yalnızca kodlayıcıyı yükler — gömme dosyası gerekmez.

        İndeks inşası sırasında gömmeler henüz yokken de kodlayıcının
        kullanılabilmesi için ayrı tutulmuştur. İndeksin ve sorgunun aynı
        kodlayıcıyı kullanması, niceleme kaymasının iki tarafta da aynı olması
        ve dolayısıyla birbirini götürmesi demektir.
        """
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        from krizkalkan_core.models.runtime import onnx_session_options

        self._np = np
        self.tokenizer = Tokenizer.from_file(str(dizin / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=MAKS_UZUNLUK)
        self.tokenizer.enable_padding()
        self.oturum = ort.InferenceSession(
            str(dizin / "kodlayici.onnx"),
            sess_options=onnx_session_options(),
            providers=["CPUExecutionProvider"],
        )

    def __init__(self, dizin: Path) -> None:
        self._kodlayici_kur(dizin)
        np = self._np

        self.gomme = np.load(dizin / "gomme.npy").astype("float32")
        self.kimlikler: list[str] = json.loads(
            (dizin / "kayit_kimlikleri.json").read_text(encoding="utf-8")
        )
        if len(self.kimlikler) != len(self.gomme):
            raise ValueError(
                f"gömme sayısı ({len(self.gomme)}) ile kimlik sayısı "
                f"({len(self.kimlikler)}) uyuşmuyor"
            )
        self.indeks = self._indeks_kur()

    # ────────────────────────── indeks ──────────────────────────

    def _indeks_kur(self):
        """Ölçek gerektiriyorsa FAISS indeksi kurar; yoksa numpy tam arama.

        Rapordaki IVF-PQ kararı milyar ölçeği içindir ve geçerliliğini korur;
        burada yalnızca kayıt sayısına göre otomatik seçim yapılır.
        """
        if len(self.gomme) < FAISS_ESIGI:
            logger.info(
                "havuz küçük (%d < %d); numpy ile tam arama kullanılıyor",
                len(self.gomme),
                FAISS_ESIGI,
            )
            return None

        try:
            import faiss
        except ImportError:
            logger.info("faiss kurulu değil; numpy ile tam arama kullanılacak")
            return None

        boyut = self.gomme.shape[1]
        if len(self.gomme) > IVF_ESIGI:
            nlist = min(4096, len(self.gomme) // 40)
            quantizer = faiss.IndexFlatIP(boyut)
            indeks = faiss.IndexIVFFlat(quantizer, boyut, nlist, faiss.METRIC_INNER_PRODUCT)
            indeks.train(self.gomme)
            indeks.nprobe = min(32, nlist)
        else:
            indeks = faiss.IndexFlatIP(boyut)
        indeks.add(self.gomme)
        return indeks

    # ────────────────────────── kodlama ──────────────────────────

    def kodla(self, metinler: list[str], *, sorgu: bool) -> object:
        """Metinleri L2-normalize gömmelere çevirir."""
        np = self._np
        onek = SORGU_ONEKI if sorgu else KAYIT_ONEKI
        kodlanmis = self.tokenizer.encode_batch([onek + m for m in metinler])

        ids = np.array([k.ids for k in kodlanmis], dtype="int64")
        maske = np.array([k.attention_mask for k in kodlanmis], dtype="int64")
        (cikti,) = self.oturum.run(None, {"input_ids": ids, "attention_mask": maske})

        # Maskeye duyarlı ortalama havuzlama — dolgu belirteçleri temsile karışmaz.
        m = maske[..., None].astype("float32")
        havuz = (cikti * m).sum(1) / np.clip(m.sum(1), 1e-9, None)
        norm = np.linalg.norm(havuz, axis=1, keepdims=True)
        return (havuz / np.clip(norm, 1e-9, None)).astype("float32")

    # ────────────────────────── arama ──────────────────────────

    def ara(self, iddia: str, k: int = 5) -> list[Aday]:
        """İddiaya en yakın k kaydı benzerlik sırasına göre döndürür."""
        if not iddia.strip():
            return []
        vektor = self.kodla([iddia], sorgu=True)

        if self.indeks is not None:
            skorlar, dizinler = self.indeks.search(vektor, min(k, len(self.kimlikler)))
            ciftler = zip(dizinler[0], skorlar[0], strict=True)
        else:
            tumu = self.gomme @ vektor[0]
            en_iyi = self._np.argsort(-tumu)[:k]
            ciftler = zip(en_iyi, tumu[en_iyi], strict=True)

        return [
            Aday(record_id=self.kimlikler[int(i)], benzerlik=round(float(s), 4))
            for i, s in ciftler
            if i >= 0
        ]


def _yukle(dizin: Path) -> Retriever:
    return Retriever(dizin)


registry.register(
    ModelSpec(
        name=MODEL_ADI,
        module="M5",
        title="Kriz bilgi havuzu geri getirici (e5 + FAISS)",
        files=GEREKLI_DOSYALAR,
        loader=_yukle,
        kabul_metrigi="recall5",
        kabul_esigi=0.6,
    )
)


def get() -> Retriever | None:
    """Yüklü geri getiriciyi döndürür; kullanılamıyorsa None."""
    return registry.get(MODEL_ADI)


def available() -> bool:
    return get() is not None


def reason() -> str:
    return registry.reason(MODEL_ADI)
