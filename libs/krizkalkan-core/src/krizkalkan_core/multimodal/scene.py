"""M2 — sahne–iddia uyumu (görsel-dil eşleştirmesi).

Soru: **metindeki iddia, görüntüdekiyle uyuşuyor mu?** Bir sel iddiasıyla
paylaşılan yangın görüntüsü, köken eşleşmesi olmasa bile bir tutarsızlıktır.

Karar mutlak benzerlik skoruyla verilmez. CLIP benzerlikleri dar bir bantta
sıkışır (ölçüldü: 0,17–0,28) ve eşik seçmek anlamsızdır. Bunun yerine iddia,
**karşıt istemlerle** yarıştırılır: iddianın olay türü diğerlerinden daha
yüksek skor alıyorsa sahne iddiayı destekliyor demektir. Aynı ders M5'te de
çıkmıştı — sıkışık benzerlik dağılımı sıralama verir, karar vermez.

Metin kodlayıcısı çok dillidir: CLIP'in kendi metin kulesi İngilizce
eğitilmiştir ve Türkçe iddialarda kullanılamaz.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from krizkalkan_core.models import ModelSpec, registry

logger = logging.getLogger(__name__)

MODEL_ADI = "m2_scene"
GEREKLI_DOSYALAR = (
    "gorsel.onnx",
    "metin.onnx",
    "metin_tokenizer.json",
    "istemler.json",
)

#: Görsel kodlayıcının beklediği giriş boyutu (ViT-B/32).
GORSEL_BOYUT = 224

#: CLIP ön işleme sabitleri.
ORTALAMA = (0.48145466, 0.4578275, 0.40821073)
SAPMA = (0.26862954, 0.26130258, 0.27577711)

MAKS_METIN = 128

#: Afet dışı sahneleri temsil eden karşıt tür. Karar KARŞILAŞTIRMASINA girmez.
#:
#: Ölçüldü: "diğer" istemleri afet türleriyle yarıştırıldığında doğru türün ilk
#: sırada olma oranı 0,725'ten 0,630'a düşüyor — enkaz sahneleri "gündelik sokak
#: görüntüsü" istemine de benziyor. Bu tür, sahnenin afet görüntüsü OLMADIĞINI
#: bildirmek için tutulur; afet iddiasını veto etmek için değil.
AFET_DISI_TUR = "diğer"


@dataclass(slots=True)
class SahneSonucu:
    """Sahne–iddia karşılaştırmasının çıktısı."""

    #: İddianın olay türü, diğer AFET türleri arasında birinci mi?
    destekliyor: bool
    #: En yüksek skorlu afet türü ile iddianın türü arasındaki fark.
    ustunluk: float
    en_yakin_tur: str
    iddia_turu: str | None
    skorlar: dict[str, float]
    #: Sahne hiçbir afet türüne benzemiyor mu? Karara girmez, bilgi olarak
    #: raporlanır: grafik, ekran görüntüsü veya toplantı fotoğrafı olabilir.
    afet_disi: bool = False

    @property
    def celiski_skoru(self) -> float:
        """Sahne–iddia çelişkisi olarak raporlanan skor.

        İddianın türü bilinmiyorsa sinyal üretilmez (0.0): sistem neyi
        aradığını bilmeden çelişki olduğunu söyleyemez.
        """
        if self.iddia_turu is None:
            return 0.0
        if self.destekliyor:
            return 0.0
        # Üstünlük ne kadar büyükse çelişki o kadar güçlü. Ölçek gözleme
        # dayanır: doğru iddiada üstünlük medyanı 0,0000, yanlış iddiada 0,0337
        # ölçüldü; 0,08 tam çelişki kabul edilir.
        return round(min(self.ustunluk / 0.08, 1.0), 4)


class SahneModeli:
    """int8 ONNX görsel + çok dilli metin kodlayıcı."""

    def __init__(self, dizin: Path) -> None:
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        from krizkalkan_core.models.runtime import onnx_session_options

        self._np = np
        secenek = onnx_session_options()
        self.gorsel = ort.InferenceSession(
            str(dizin / "gorsel.onnx"), sess_options=secenek, providers=["CPUExecutionProvider"]
        )
        self.metin = ort.InferenceSession(
            str(dizin / "metin.onnx"), sess_options=secenek, providers=["CPUExecutionProvider"]
        )
        self.tokenizer = Tokenizer.from_file(str(dizin / "metin_tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=MAKS_METIN)
        self.tokenizer.enable_padding()

        # İstemler ve gömmeleri inşa sırasında hesaplanır: her sorguda yeniden
        # kodlamak, sabit bir metni tekrar tekrar işlemek olurdu.
        ham = json.loads((dizin / "istemler.json").read_text(encoding="utf-8"))
        self.turler: list[str] = ham["turler"]
        self.istem_gomme = np.asarray(ham["gomme"], dtype="float32")
        self.tur_indeksi: list[str] = ham["tur_indeksi"]

        # Görsel kule birden çok çıktı döndürebilir (gizli durumlar + izdüşüm).
        # Doğru olanı ada göre değil ŞEKLE göre seçiyoruz: çıktı adları
        # transformers sürümleri arasında kayıyor ve yanlış çıktı, sessizce
        # 768 boyutlu gizli durumu gömme sanmaya yol açıyordu.
        self._gorsel_cikti = self._gomme_cikti_indeksi(self.istem_gomme.shape[1])

    def _gomme_cikti_indeksi(self, boyut: int) -> int:
        """Metin gömmesiyle aynı boyutu veren görsel çıktının sırası."""
        for sira, cikti in enumerate(self.gorsel.get_outputs()):
            sekil = cikti.shape
            if len(sekil) == 2 and isinstance(sekil[1], int) and sekil[1] == boyut:
                return sira
        # Şekil bilgisi yoksa son çıktı izdüşüm katmanıdır.
        logger.warning("Görsel kule çıktısı şekilden seçilemedi; sonuncusu kullanılıyor")
        return len(self.gorsel.get_outputs()) - 1

    # ────────────────────────── kodlama ──────────────────────────

    def gorsel_gomme(self, goruntu) -> object:
        """Görüntüyü L2-normalize gömmeye çevirir."""
        np = self._np
        from PIL import Image

        if isinstance(goruntu, Path | str):
            goruntu = Image.open(goruntu)
        goruntu = goruntu.convert("RGB").resize(
            (GORSEL_BOYUT, GORSEL_BOYUT), Image.Resampling.BICUBIC
        )
        dizi = np.asarray(goruntu, dtype="float32") / 255.0
        dizi = (dizi - np.array(ORTALAMA, dtype="float32")) / np.array(SAPMA, dtype="float32")
        girdi = dizi.transpose(2, 0, 1)[None, ...]

        ciktilar = self.gorsel.run(None, {"pixel_values": girdi})
        cikti = ciktilar[self._gorsel_cikti]
        return cikti / np.clip(np.linalg.norm(cikti, axis=1, keepdims=True), 1e-9, None)

    def metin_gomme(self, metinler: list[str]) -> object:
        np = self._np
        kodlanmis = self.tokenizer.encode_batch(metinler)
        ids = np.array([k.ids for k in kodlanmis], dtype="int64")
        maske = np.array([k.attention_mask for k in kodlanmis], dtype="int64")
        (cikti,) = self.metin.run(None, {"input_ids": ids, "attention_mask": maske})
        return cikti / np.clip(np.linalg.norm(cikti, axis=1, keepdims=True), 1e-9, None)

    # ────────────────────────── karşılaştırma ──────────────────────────

    def karsilastir(self, goruntu, iddia_turu: str | None) -> SahneSonucu:
        """Görüntüyü karşıt istemlerle yarıştırır."""
        np = self._np
        gomme = np.asarray(self.gorsel_gomme(goruntu))
        skorlar = (gomme @ self.istem_gomme.T)[0]

        tur_skoru: dict[str, float] = {}
        for tur in self.turler:
            ait = [i for i, t in enumerate(self.tur_indeksi) if t == tur]
            tur_skoru[tur] = round(float(max(skorlar[i] for i in ait)), 4)

        # Karşılaştırma yalnızca afet türleri arasında yapılır; afet dışı tür
        # bilgi olarak taşınır ama iddiayı veto etmez (ölçüm gerekçesi yukarıda).
        afet_skorlari = {t: s for t, s in tur_skoru.items() if t != AFET_DISI_TUR}
        if not afet_skorlari:
            return SahneSonucu(False, 0.0, AFET_DISI_TUR, iddia_turu, tur_skoru)

        en_yakin = max(afet_skorlari, key=lambda k: afet_skorlari[k])
        afet_disi = tur_skoru.get(AFET_DISI_TUR, 0.0) > afet_skorlari[en_yakin]

        if iddia_turu is None or iddia_turu not in afet_skorlari:
            return SahneSonucu(False, 0.0, en_yakin, None, tur_skoru, afet_disi)

        ustunluk = round(afet_skorlari[en_yakin] - afet_skorlari[iddia_turu], 4)
        return SahneSonucu(
            # Eşitlik destek sayılır: skorlar dar bantta olduğu için tam eşitlik
            # sık görülür ve iddiayı cezalandırmak için sebep değildir.
            destekliyor=ustunluk <= 0.0,
            ustunluk=max(ustunluk, 0.0),
            en_yakin_tur=en_yakin,
            iddia_turu=iddia_turu,
            skorlar=tur_skoru,
            afet_disi=afet_disi,
        )


def _yukle(dizin: Path) -> SahneModeli:
    return SahneModeli(dizin)


registry.register(
    ModelSpec(
        name=MODEL_ADI,
        module="M2",
        title="Sahne–iddia uyumu (çok dilli CLIP)",
        files=GEREKLI_DOSYALAR,
        loader=_yukle,
        kabul_metrigi="esli_dogruluk",
        kabul_esigi=0.65,
    )
)


def get() -> SahneModeli | None:
    return registry.get(MODEL_ADI)


def available() -> bool:
    return get() is not None


def reason() -> str:
    return registry.reason(MODEL_ADI)
