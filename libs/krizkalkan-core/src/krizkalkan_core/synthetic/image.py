"""M4 — Görüntüde sentetik üretim izi (iki bağımsız detektör).

Modül iki soruyu ayrı ayrı sorar, çünkü bunlar aynı soru değildir:

    1. **Üretim izi var mı?**  → ikili detektör (`uretim.onnx`)
    2. **Varsa hangi tür?**    → üç sınıflı detektör (`tur.onnx`)
       tam sentetik üretim mi, gerçek içerik üzerinde oynama mı?

İkinci soru taksonomiye doğrudan bağlıdır: SENTETİK_MEDYA ile MANİPÜLE_MEDYA
farklı sınıflardır ve farklı müdahale tetikler (rapor 2.2). Tek skorlu bir
detektör bu ayrımı yapısal olarak yapamaz — raporun ticari araçlara yönelttiği
eleştirinin tam olarak kendisi budur.

**İki detektörün bağımsızlığı bilinçlidir.** İkili detektör OpenDeepfake-Preview
üzerinde ince ayarlanmıştır; üç sınıflı detektör başka bir korpusta eğitilmiş
harici bir ağırlıktır. Eğitim kümeleri ayrık olduğu için hemfikir olmaları
gerçek bir doğrulamadır, çelişmeleri ise bilgi taşır: bu modül çelişki hâlinde
skor üretmez, **çekinir** (rapor 2.2 · Y2).

**Kanıt hiyerarşisi.** Bu modülün ürettiği her şey olasılıksal çıkarımdır.
C2PA imzası ise üreticinin kendi beyanıdır ve kriptografik olarak doğrulanır
(`synthetic/c2pa.py`). İmza varsa karar oradan gelir; bu detektörler onu
geçersiz kılamaz — köken önceliği ilkesi (rapor 1.2) modül içinde de geçerlidir.

Ağırlıklar `DeepReality` projesinden gelir (MIT, https://github.com/OmerKurtulus/DeepReality).
Dışa aktarım ve niceleme: `scripts/data/build_synthetic.py`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from krizkalkan_core.models import ModelSpec, registry

logger = logging.getLogger(__name__)

MODEL_ADI = "m4_synthetic"
GEREKLI_DOSYALAR = ("uretim.onnx", "tur.onnx", "onisleme.json")

#: Üç sınıflı detektörün etiketleri — taksonomiye eşlenmiş hâlleri.
#:
#: Kaynak model "AI / Deepfake / Real" üretir. Bu adlar KrizKalkan sınıflarına
#: birebir karşılık gelir ve çeviri burada, tek yerde yapılır.
TUR_ETIKETLERI = ("sentetik", "manipüle", "gerçek")

# ─────────────────────────── çekinme eşikleri ───────────────────────────
#
# Bu eşikler `scripts/eval/m4_synthetic.py` tarafından ölçülür; değiştirilmeden
# önce o betiğin ürettiği tablo okunmalıdır.

#: Kısa kenarı bunun altındaki görüntü, küçük detektörün doğal giriş boyutunun
#: (224 piksel) altındadır: modele giden her piksel ara değerlemeyle üretilmiş
#: olur ve üretim artefaktı aranan yüksek frekans bandı tamamen uydurmadır.
ASGARI_KENAR = 224

#: Piksel başına bayt. Aşırı sıkıştırma üretim izlerini fiilen siler; bu
#: durumda "iz bulamadım" demek "temiz" demek DEĞİLDİR.
ASGARI_BAYT_PIKSEL = 0.05

#: İki detektör bu güvenin üzerinde ZIT yönde karar verirse modül çekinir.
#: Eğitim kümeleri ayrık olduğundan böyle bir çelişki, ikisinden birinin
#: dağılım dışında kaldığının işaretidir.
UYUSMAZLIK_ESIGI = 0.70


@dataclass(slots=True)
class GoruntuSonucu:
    """Tek bir görüntünün sentetik medya incelemesi."""

    #: P(içerik üretilmiş) — ikili detektörün çıktısı.
    uretim_skoru: float = 0.0
    #: Üç sınıflı detektörün en yüksek skorlu etiketi.
    tur: str = "gerçek"
    #: Etiket → olasılık. Kanıt panelinde ham hâliyle gösterilir.
    tur_skorlari: dict[str, float] = field(default_factory=dict)
    #: Çekinme gerekçesi; None ise skor anlamlıdır.
    cekinme_nedeni: str | None = None
    #: İki detektör zıt yönde mi karar verdi?
    uyusmazlik: bool = False
    #: Görüntünün ölçülen özellikleri — kanıt ve denetim kaydı için.
    genislik: int = 0
    yukseklik: int = 0
    bayt_piksel: float = 0.0

    @property
    def cekindi(self) -> bool:
        return self.cekinme_nedeni is not None

    @property
    def manipulasyon_skoru(self) -> float:
        """Gerçek içerik üzerinde oynama olasılığı.

        SENTETİK_MEDYA'dan ayrı raporlanır: tam üretim ile kurcalama farklı
        sınıflardır ve MANİPÜLE_MEDYA dalını yalnızca bu skor besleyebilir.
        """
        if self.cekindi:
            return 0.0
        return self.tur_skorlari.get("manipüle", 0.0)

    @property
    def sentetik_skoru(self) -> float:
        """Tam sentetik üretim olasılığı — üç sınıflı detektörün "sentetik" dalı."""
        if self.cekindi:
            return 0.0
        return self.tur_skorlari.get("sentetik", 0.0)


class SentetikGoruntuModeli:
    """int8 ONNX ikili + üç sınıflı görüntü detektörü.

    Ön işleme parametreleri tahmin edilmez, ağırlıkla birlikte gelen
    `onisleme.json` dosyasından okunur. Kare boyutu, normalizasyon ortalaması
    ve yeniden örnekleme yöntemi eğitimdekinden saptığında model sessizce
    yanlış cevap verir; bu, entegrasyonda en sık yapılan hatadır.
    """

    def __init__(self, dizin: Path) -> None:
        import numpy as np
        import onnxruntime as ort

        from krizkalkan_core.models.runtime import onnx_session_options

        self._np = np
        secenek = onnx_session_options()
        self.uretim = ort.InferenceSession(
            str(dizin / "uretim.onnx"), sess_options=secenek, providers=["CPUExecutionProvider"]
        )
        self.tur = ort.InferenceSession(
            str(dizin / "tur.onnx"), sess_options=secenek, providers=["CPUExecutionProvider"]
        )
        self._onisleme = json.loads((dizin / "onisleme.json").read_text(encoding="utf-8"))

    # ────────────────────────── ön işleme ──────────────────────────

    def _hazirla(self, goruntu, anahtar: str):
        """Görüntüyü ilgili detektörün beklediği tensöre çevirir."""
        np = self._np
        from PIL import Image

        ayar = self._onisleme[anahtar]
        boyut = int(ayar["boyut"])
        ortalama = np.asarray(ayar["ortalama"], dtype="float32")
        sapma = np.asarray(ayar["sapma"], dtype="float32")
        yontem = getattr(Image.Resampling, ayar.get("yeniden_ornekleme", "BILINEAR"))

        kare = goruntu.convert("RGB").resize((boyut, boyut), yontem)
        dizi = np.asarray(kare, dtype="float32") / 255.0
        dizi = (dizi - ortalama) / sapma
        return dizi.transpose(2, 0, 1)[None, ...]

    @staticmethod
    def _softmax(np, logit):
        kaydirilmis = logit - logit.max(axis=-1, keepdims=True)
        us = np.exp(kaydirilmis)
        return us / us.sum(axis=-1, keepdims=True)

    # ────────────────────────── inceleme ──────────────────────────

    def incele(self, yol: Path | str) -> GoruntuSonucu:
        """Bir görüntü dosyasını iki detektörden geçirir.

        Dağılım dışı girdilerde model hiç çalıştırılmaz: çalıştırılıp skoru
        yok saymak, hem boşuna hesaptır hem de skorun bir yerde sızma riskidir.
        """
        np = self._np
        from PIL import Image

        yol = Path(yol)
        with Image.open(yol) as acik:
            genislik, yukseklik = acik.size
            goruntu = acik.convert("RGB")

        bayt_piksel = yol.stat().st_size / max(genislik * yukseklik, 1)
        olcum = {
            "genislik": genislik,
            "yukseklik": yukseklik,
            "bayt_piksel": round(bayt_piksel, 4),
        }

        if (kisa_kenar := min(genislik, yukseklik)) < ASGARI_KENAR:
            return GoruntuSonucu(
                cekinme_nedeni=(
                    f"çözünürlük modelin çalışma aralığının altında "
                    f"(kısa kenar {kisa_kenar}px < {ASGARI_KENAR}px)"
                ),
                **olcum,
            )

        if bayt_piksel < ASGARI_BAYT_PIKSEL:
            return GoruntuSonucu(
                cekinme_nedeni=(
                    f"aşırı sıkıştırma üretim izlerini siliyor "
                    f"({bayt_piksel:.3f} bayt/piksel < {ASGARI_BAYT_PIKSEL})"
                ),
                **olcum,
            )

        (uretim_logit,) = self.uretim.run(None, {"pixel_values": self._hazirla(goruntu, "uretim")})
        (tur_logit,) = self.tur.run(None, {"pixel_values": self._hazirla(goruntu, "tur")})

        # İkili detektörün etiket sırası: 0 = üretilmiş, 1 = gerçek.
        uretim_olasilik = self._softmax(np, uretim_logit)[0]
        uretim_skoru = round(float(uretim_olasilik[0]), 4)

        tur_olasilik = self._softmax(np, tur_logit)[0]
        tur_skorlari = {
            etiket: round(float(deger), 4)
            for etiket, deger in zip(TUR_ETIKETLERI, tur_olasilik, strict=True)
        }
        tur = max(tur_skorlari, key=lambda k: tur_skorlari[k])

        # Çelişki kontrolü: iki detektör ayrı korpuslarda eğitildiği için
        # güvenli bir zıtlık, ikisinden birinin dağılım dışında olduğunu söyler.
        gercek_skoru = tur_skorlari["gerçek"]
        uyusmazlik = (uretim_skoru >= UYUSMAZLIK_ESIGI and gercek_skoru >= UYUSMAZLIK_ESIGI) or (
            1.0 - uretim_skoru >= UYUSMAZLIK_ESIGI and 1.0 - gercek_skoru >= UYUSMAZLIK_ESIGI
        )

        if uyusmazlik:
            return GoruntuSonucu(
                uretim_skoru=uretim_skoru,
                tur=tur,
                tur_skorlari=tur_skorlari,
                cekinme_nedeni=(
                    "iki bağımsız detektör zıt yönde karar verdi "
                    f"(üretim {uretim_skoru:.2f} · gerçek {gercek_skoru:.2f})"
                ),
                uyusmazlik=True,
                **olcum,
            )

        return GoruntuSonucu(
            uretim_skoru=uretim_skoru,
            tur=tur,
            tur_skorlari=tur_skorlari,
            **olcum,
        )


def _yukle(dizin: Path) -> SentetikGoruntuModeli:
    return SentetikGoruntuModeli(dizin)


registry.register(
    ModelSpec(
        name=MODEL_ADI,
        module="M4",
        title="Sentetik görüntü tespiti (ikili + üç sınıflı)",
        files=GEREKLI_DOSYALAR,
        loader=_yukle,
        # Kabul ölçütü **afet alanındaki özgüllük**tür — AUC değil.
        #
        # İlk tasarımda kapı `capraz_auc ≥ 0,72` idi (raporun M4 taahhüdü) ve
        # ölçüm bu eşiği geçti: 0,7818. Kapı açılacaktı. Aynı koşuda ikinci bir
        # ölçüm bunun tehlikeli olduğunu gösterdi: **gerçek afet fotoğraflarının
        # %99,71'i 0,50 eşiğinde "üretilmiş" çıkıyor** (docs/metrikler/m4.md).
        #
        # İkisi çelişmiyor. AUC bir SIRALAMA ölçüsüdür ve model gerçekten
        # sıralıyor; ama skorlar 0,93–0,97 bandına sıkışmış durumda ve mutlak
        # eşik anlamını yitiriyor. Aynı ders M2 ve M5'te de çıkmıştı (bkz.
        # docs/mimari.md · karşılaştırmalı karar).
        #
        # Bu yüzden kapı, yetenek metriğine değil **zarar metriğine** bağlandı:
        # sistemin fiilen göreceği içerikte gerçek bir afet fotoğrafını sentetik
        # sanma oranı. Bir afet fotoğrafını yanlış işaretlemek, bir sentetik
        # görüntüyü kaçırmaktan daha zararlıdır — ve geçen bir AUC'nin kapıyı
        # kazara açmasına izin verilemez.
        #
        # `capraz_auc` model kartında yetenek göstergesi olarak durmaya devam
        # eder; kapıyı o değil, bu metrik açar.
        kabul_metrigi="afet_ozgulluk",
        kabul_esigi=0.95,
    )
)


def get() -> SentetikGoruntuModeli | None:
    return registry.get(MODEL_ADI)


def available() -> bool:
    return get() is not None


def reason() -> str:
    return registry.reason(MODEL_ADI)
