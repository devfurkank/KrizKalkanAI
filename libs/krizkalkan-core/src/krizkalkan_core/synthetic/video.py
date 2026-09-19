"""M4 — Videoda sentetik üretim izi.

Görüntü detektörü (`synthetic/image.py`) tek kareye bakar. Bu modül videonun
tamamına bakar: 32 kare seçilir, her kare ResNet50 ile kodlanır, kareler arası
ilişki çift yönlü LSTM ve çok başlı dikkatle toplanır (rapor 3.1 · M4 · kare
düzeyi omurga + zamansal toplama).

**Kaynak.** Ağırlık Keras 2.10 ile eğitildi ve
`scripts/train/m4_video_disa_aktar.py` ile ONNX'e aktarıldı. Aktarım sayısal
olarak doğrulanır: ONNX çıktısı Keras çıktısından 1e-4'ten fazla saparsa betik
ağırlığı yazmaz.

**Ön işleme eğitimdekiyle birebir aynıdır** ve parametreleri ağırlıkla gelen
`onisleme.json` dosyasından okunur. Kare seçimi özgün çıkarım kodundaki
hareket duyarlı örneklemenin birebir kopyasıdır: kareler 112×112 gri tonda
Farneback optik akışından geçirilir; 16 kare eşit aralıkla, 16 kare en yüksek
hareketli anlardan seçilir. Tek bir parametrenin farklı olması modelin sessizce
yanlış cevap vermesine yol açar.

**Etiket yönü.** Modelin çıktısı P(gerçek)'tir; bu modül P(üretilmiş) =
1 − P(gerçek) raporlar, çünkü füzyon her sentetik sinyali "üretim kanıtı"
yönünde okur.

**Bilinen sınır** (docs/metrikler/m4-video.md): eğitim kümesindeki doğal dikey
gerçek videolarda model doğru çalışıyor; ancak YATAY bir videonun sonradan
dikeye kırpılması ya da siyah bantla çerçevelenmesi, gerçek videonun "üretilmiş"
sanılma oranını belirgin biçimde artırıyor. Sosyal medyada bu dönüşüm yaygındır.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

from krizkalkan_core.models import ModelSpec, registry

logger = logging.getLogger(__name__)

MODEL_ADI = "m4_video"
GEREKLI_DOSYALAR = ("model.onnx", "onisleme.json")

#: Bundan uzun videolar incelenmez. Hareket analizi her kareyi çözer; sınırsız
#: süre, tek bir yüklemenin analiz kuyruğunu kilitlemesi demektir. Eğitim
#: kümesindeki en uzun video 87,5 sn'dir; sınır onun iki katından fazladır.
AZAMI_SURE_SN = 180.0


@dataclass(slots=True)
class VideoSonucu:
    """Tek bir videonun sentetik medya incelemesi."""

    #: P(içerik üretilmiş) = 1 − modelin P(gerçek) çıktısı.
    uretim_skoru: float = 0.0
    #: Çekinme gerekçesi; None ise skor anlamlıdır.
    cekinme_nedeni: str | None = None
    #: Dağıtım yapılandırmasındaki (onisleme.json) karar eşiği, P(üretilmiş) yönünde.
    karar_esigi: float = 0.55
    #: Videonun ölçülen özellikleri — kanıt ve denetim kaydı için.
    genislik: int = 0
    yukseklik: int = 0
    kare_sayisi: int = 0
    fps: float = 0.0
    #: Modele giren karelerin video içindeki sıra numaraları.
    secilen_kareler: list[int] = field(default_factory=list)
    sure_ms: float = 0.0

    @property
    def cekindi(self) -> bool:
        return self.cekinme_nedeni is not None

    @property
    def sure_sn(self) -> float:
        return self.kare_sayisi / self.fps if self.fps > 0 else 0.0

    @property
    def uretilmis(self) -> bool:
        """Modelin kendi eşiğine göre karar. Füzyon bunu değil, kalibre skoru kullanır."""
        return not self.cekindi and self.uretim_skoru > self.karar_esigi


class KareOrnekleyici:
    """Eğitimdeki kare seçimi ve okuması — ağdan bağımsız.

    Ayrı bir sınıftır çünkü üç yer aynı kodu kullanmak zorundadır: çıkarım,
    ONNX aktarımının doğrulaması ve ölçüm betiği. Üçünün ayrı kopyası olsaydı
    biri sessizce sapabilirdi.
    """

    def __init__(self, ayar: dict) -> None:
        import numpy as np

        self._np = np
        self.kare_sayisi = int(ayar["kare_sayisi"])
        self.boyut = int(ayar["boyut"])
        self.akis_boyutu = int(ayar["akis_boyutu"])
        self.hareket_ornekleme = bool(ayar["hareket_ornekleme"])
        self.farneback = tuple(ayar["farneback"])

    def _esit_aralik(self, toplam: int, adet: int) -> list[int]:
        if toplam <= 0:
            return [0] * adet
        if toplam <= adet:
            dizin = list(range(toplam))
            dizin += [dizin[-1]] * (adet - len(dizin))
            return dizin
        return self._np.linspace(0, toplam - 1, adet, dtype=int).tolist()

    def sec(self, yol: Path, toplam: int) -> list[int]:
        """Hareket duyarlı kare seçimi — özgün çıkarım kodundaki `compute_motion_aware_indices`."""
        import cv2

        np = self._np
        adet = self.kare_sayisi

        if toplam <= 0:
            return [0] * adet
        if not self.hareket_ornekleme or toplam <= adet:
            return self._esit_aralik(toplam, adet)

        kaynak = cv2.VideoCapture(str(yol))
        if not kaynak.isOpened():
            kaynak.release()
            return self._esit_aralik(toplam, adet)

        hareket = np.zeros(toplam, dtype=np.float32)
        onceki = None
        sira = 0
        try:
            while True:
                okundu, kare = kaynak.read()
                if not okundu:
                    break
                # Özgün kod bozuk tek bir kareyi atlayıp devam eder; aynısı.
                with contextlib.suppress(Exception):
                    kucuk = cv2.resize(kare, (self.akis_boyutu, self.akis_boyutu))
                    gri = cv2.cvtColor(kucuk, cv2.COLOR_BGR2GRAY)
                    if onceki is not None:
                        akis = cv2.calcOpticalFlowFarneback(onceki, gri, None, *self.farneback)
                        hareket[sira] = np.mean(np.abs(akis))
                    onceki = gri
                sira += 1
                if sira >= toplam:
                    break
        finally:
            kaynak.release()

        yari_esit = adet // 2
        yari_hareket = adet - yari_esit
        esit = np.linspace(0, toplam - 1, yari_esit, dtype=int).tolist()
        if hareket.sum() > 0:
            hareketli = np.argsort(hareket)[-yari_hareket:].tolist()
        else:
            hareketli = np.linspace(0, toplam - 1, yari_hareket, dtype=int).tolist()

        secilen = sorted(set(esit + hareketli))
        if len(secilen) < adet:
            for i in self._esit_aralik(toplam, adet * 2):
                if i not in secilen:
                    secilen.append(i)
                if len(secilen) >= adet:
                    break
        secilen = sorted(secilen)
        if len(secilen) > adet:
            konum = np.linspace(0, len(secilen) - 1, adet, dtype=int).tolist()
            secilen = [secilen[k] for k in konum]
        while len(secilen) < adet:
            secilen.append(secilen[-1] if secilen else 0)
        return [int(i) for i in secilen[:adet]]

    def oku(self, yol: Path, dizin: list[int]):
        """Seçilen kareleri modelin girişine çevirir — `load_video_frames_for_prediction`.

        BGR → RGB, en-boy oranı korunmadan boyut×boyut, [0, 1] aralığı. ResNet
        normalizasyonu modelin içindedir (ResNetPreprocess katmanı), burada
        yapılmaz; iki kez yapılması girdiyi bozar.
        """
        import cv2

        np = self._np
        bos = np.zeros((self.boyut, self.boyut, 3), dtype=np.float32)
        gerekli = set(dizin)
        okunan: dict[int, object] = {}

        kaynak = cv2.VideoCapture(str(yol))
        try:
            if kaynak.isOpened():
                sira = 0
                son = max(gerekli)
                while sira <= son:
                    okundu, kare = kaynak.read()
                    if not okundu:
                        break
                    if sira in gerekli:
                        try:
                            rgb = cv2.cvtColor(kare, cv2.COLOR_BGR2RGB)
                            rgb = cv2.resize(rgb, (self.boyut, self.boyut))
                            okunan[sira] = rgb.astype(np.float32) / 255.0
                        except Exception:
                            okunan[sira] = bos
                    sira += 1
        finally:
            kaynak.release()

        kareler = []
        for i in dizin:
            if i in okunan:
                kareler.append(okunan[i])
            else:
                kareler.append(kareler[-1] if kareler else bos)
        return np.asarray(kareler[: self.kare_sayisi], dtype=np.float32)


class SentetikVideoModeli:
    """fp32 ONNX video detektörü + eğitimle aynı kare seçimi."""

    def __init__(self, dizin: Path) -> None:
        # OpenCV burada istenir: yoksa yükleme başarısız olur ve kayıt defteri
        # bunu "yükleme hatası" olarak raporlar (`make model-durum`). Aksi hâlde
        # model "hazır" görünür ve her videoda ayrı ayrı çekinirdi.
        import cv2  # noqa: F401
        import onnxruntime as ort

        from krizkalkan_core.models.runtime import onnx_session_options

        self.oturum = ort.InferenceSession(
            str(dizin / "model.onnx"),
            sess_options=onnx_session_options(),
            providers=["CPUExecutionProvider"],
        )
        self._giris = self.oturum.get_inputs()[0].name

        ayar = json.loads((dizin / "onisleme.json").read_text(encoding="utf-8"))
        self.ornekleyici = KareOrnekleyici(ayar)
        # Yapılandırmadaki eşik P(gerçek) yönündedir.
        self.karar_esigi = round(1.0 - float(ayar["esik_p_gercek"]), 4)

    # ────────────────────────── inceleme ──────────────────────────

    def incele(self, yol: Path | str) -> VideoSonucu:
        """Bir video dosyasını modelden geçirir.

        Çözülemeyen ya da çalışma aralığı dışındaki videolarda model hiç
        çalıştırılmaz ve çekinilir.
        """
        import cv2

        baslangic = time.perf_counter()
        yol = Path(yol)

        kaynak = cv2.VideoCapture(str(yol))
        try:
            acildi = kaynak.isOpened()
            toplam = int(kaynak.get(cv2.CAP_PROP_FRAME_COUNT)) if acildi else 0
            fps = float(kaynak.get(cv2.CAP_PROP_FPS)) if acildi else 0.0
            genislik = int(kaynak.get(cv2.CAP_PROP_FRAME_WIDTH)) if acildi else 0
            yukseklik = int(kaynak.get(cv2.CAP_PROP_FRAME_HEIGHT)) if acildi else 0
        finally:
            kaynak.release()

        olcum = {
            "karar_esigi": self.karar_esigi,
            "genislik": genislik,
            "yukseklik": yukseklik,
            "kare_sayisi": toplam,
            "fps": round(fps, 3),
        }

        if not acildi or toplam <= 0 or genislik <= 0 or yukseklik <= 0:
            return VideoSonucu(cekinme_nedeni="video çözümlenemedi (kare okunamadı)", **olcum)

        sure = toplam / fps if fps > 0 else 0.0
        if sure > AZAMI_SURE_SN:
            return VideoSonucu(
                cekinme_nedeni=(
                    f"video süresi modelin çalışma aralığının dışında "
                    f"({sure:.0f} sn > {AZAMI_SURE_SN:.0f} sn)"
                ),
                **olcum,
            )

        dizin = self.ornekleyici.sec(yol, toplam)
        kareler = self.ornekleyici.oku(yol, dizin)
        (cikti,) = self.oturum.run(None, {self._giris: kareler[None, ...]})
        p_gercek = float(cikti.reshape(-1)[0])

        return VideoSonucu(
            uretim_skoru=round(min(max(1.0 - p_gercek, 0.0), 1.0), 4),
            secilen_kareler=dizin,
            sure_ms=round((time.perf_counter() - baslangic) * 1000, 1),
            **olcum,
        )


def _yukle(dizin: Path) -> SentetikVideoModeli:
    return SentetikVideoModeli(dizin)


registry.register(
    ModelSpec(
        name=MODEL_ADI,
        module="M4",
        title="Sentetik video tespiti (ResNet50 + BiLSTM + dikkat)",
        files=GEREKLI_DOSYALAR,
        loader=_yukle,
        # Kapı bir ÇALIŞIRLIK kontrolüdür, genelleme iddiası değildir.
        #
        # Ölçüm, modelin eğitim kümesinde yapılır: bu videolar modelin eğitim ve
        # doğrulama verisidir ve ayrımın dosya listesi depoda kayıtlı değil.
        # Bu yüzden oradaki başarım "model görmediği videoda da çalışır"
        # anlamına GELMEZ. Kapının sorduğu soru daha dardır: ONNX aktarımı ve bu
        # depodaki ön işleme, özgün Keras modelini doğru yeniden üretiyor mu?
        # Yanlış yeniden üretim (ör. BGR/RGB karışması, çift normalizasyon)
        # gerçek videoları kendi eğitim kümesinde bile "üretilmiş" gösterir ve
        # bu kapıdan geçemez.
        #
        # Genelleme ölçümü ayrı bir kümede yapılmalıdır (docs/metrikler/m4-video.md).
        kabul_metrigi="alan_ici_ozgulluk",
        kabul_esigi=0.95,
    )
)


def get() -> SentetikVideoModeli | None:
    return registry.get(MODEL_ADI)


def available() -> bool:
    return get() is not None


def reason() -> str:
    return registry.reason(MODEL_ADI)
