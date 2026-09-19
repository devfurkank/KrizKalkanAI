#!/usr/bin/env python
"""M4 video modelini (Keras 2.10 HDF5) ONNX'e aktarır.

Kaynak ağırlığın uzantısı `.keras` olsa da içi HDF5'tir; Keras 3 bu dosyayı
reddeder. Bu yüzden `tf_keras` (Keras 2 uyumluluk paketi) ile açılır.

İki dönüşüm yapılır ve ikisi de modelin matematiğini değiştirmez:

    1. `ffn_expand` katmanının GELU'su TensorFlow'da `erfc` ile hesaplanır ve
       ONNX'te `Erfc` işlemi yoktur. Aynı fonksiyon `erf` ile yazılır:
       0,5·x·erfc(−x/√2) = 0,5·x·(1 + erf(x/√2)).
    2. Başka hiçbir şey. Niceleme YAPILMAZ: M4 görüntü detektöründe int8 karar
       sınırını kaydırmıştı (scripts/train/m4_disa_aktar.py).

Aktarım sayısal olarak doğrulanır: rastgele ve gerçek videolardan üretilen
girdilerde ONNX ile Keras arasındaki en büyük fark `--tolerans` değerini
aşarsa hiçbir dosya yazılmaz.

Kurulum (demo ortamına girmez):
    pip install -e "libs/krizkalkan-core[video-export,models]"

Kullanım:
    TF_USE_LEGACY_KERAS=1 python scripts/train/m4_video_disa_aktar.py \\
        --kaynak data/external/video_afet/kaynak
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("TF_USE_LEGACY_KERAS", "1")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

KAYNAK = REPO_ROOT / "data" / "external" / "video_afet" / "kaynak"
HEDEF = REPO_ROOT / "models" / "m4_video"
AGIRLIK_ADI = "deepfake_final_best_model.keras"


def _keras_modeli(yol: Path):
    import tensorflow as tf
    import tf_keras

    class ResNetPreprocess(tf_keras.layers.Layer):
        """Özgün modeldeki özel katman: [0,1] → ResNet 'caffe' normalizasyonu."""

        def call(self, x, training=None):
            return tf_keras.applications.resnet.preprocess_input(x * 255.0)

        def compute_output_shape(self, input_shape):
            return input_shape

    model = tf_keras.models.load_model(
        str(yol), custom_objects={"ResNetPreprocess": ResNetPreprocess}, compile=False
    )
    return model, tf


def _ornek_girdiler(onisleme: dict, adet_video: int) -> list:
    """Doğrulama girdileri: rastgele tensörler + eğitim kümesinden gerçek videolar."""
    import numpy as np
    from krizkalkan_core.synthetic.video import KareOrnekleyici

    rng = np.random.default_rng(0)
    k, b = onisleme["kare_sayisi"], onisleme["boyut"]
    girdiler = [rng.random((2, k, b, b, 3), dtype=np.float32) for _ in range(2)]

    kume = REPO_ROOT / "data" / "external" / "video_afet"
    videolar = (
        sorted((kume / "real").glob("*"))[:adet_video]
        + sorted((kume / "fake").glob("*"))[:adet_video]
    )
    if not videolar:
        return girdiler

    # Kare seçimi ve okuma, depodaki çıkarım koduyla yapılır: doğrulanan şey
    # yalnızca ağ değil, uçtan uca ön işlemedir.
    import cv2

    ornekleyici = KareOrnekleyici(onisleme)
    for video in videolar:
        kaynak = cv2.VideoCapture(str(video))
        toplam = int(kaynak.get(cv2.CAP_PROP_FRAME_COUNT))
        kaynak.release()
        girdiler.append(ornekleyici.oku(video, ornekleyici.sec(video, toplam))[None, ...])
    return girdiler


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--kaynak", type=Path, default=KAYNAK)
    ap.add_argument("--hedef", type=Path, default=HEDEF)
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--tolerans", type=float, default=1e-4)
    ap.add_argument("--dogrulama-videosu", type=int, default=3, help="sınıf başına")
    args = ap.parse_args()

    import numpy as np
    import onnxruntime as ort
    import tf2onnx

    yapilandirma = json.loads((args.kaynak / "deployment_config.json").read_text(encoding="utf-8"))
    onisleme = {
        "kare_sayisi": int(yapilandirma["num_frames"]),
        "boyut": int(yapilandirma["img_size"]),
        # Aşağıdakiler özgün çıkarım kodunda sabittir (kaynak/gradio_real_time.py).
        "akis_boyutu": 112,
        "hareket_ornekleme": True,
        # cv2.calcOpticalFlowFarneback(pyr_scale, levels, winsize, iterations,
        #                              poly_n, poly_sigma, flags)
        "farneback": [0.5, 3, 15, 3, 5, 1.2, 0],
        "renk": "RGB",
        "olcek": "x/255 · en-boy oranı korunmadan yeniden boyutlandırma (INTER_LINEAR)",
        "normalizasyon": "modelin içinde (ResNetPreprocess · caffe)",
        "cikti": "P(gerçek) · sigmoid",
        "esik_p_gercek": round(float(yapilandirma["threshold"]), 4),
        "etiketler": yapilandirma.get("label_mapping", {"0": "fake", "1": "real"}),
    }

    print(f"→ Keras modeli yükleniyor: {args.kaynak / AGIRLIK_ADI}")
    model, tf = _keras_modeli(args.kaynak / AGIRLIK_ADI)

    girdiler = _ornek_girdiler(onisleme, args.dogrulama_videosu)
    referans = [model.predict(x, verbose=0) for x in girdiler]

    def gelu_erf(x):
        return 0.5 * x * (1.0 + tf.math.erf(x / np.float32(np.sqrt(2.0))))

    model.get_layer("ffn_expand").activation = gelu_erf

    imza = (
        tf.TensorSpec(
            (None, onisleme["kare_sayisi"], onisleme["boyut"], onisleme["boyut"], 3),
            tf.float32,
            name="video",
        ),
    )
    with tempfile.TemporaryDirectory() as gecici:
        aday = Path(gecici) / "model.onnx"
        tf2onnx.convert.from_keras(
            model, input_signature=imza, opset=args.opset, output_path=str(aday)
        )
        oturum = ort.InferenceSession(str(aday), providers=["CPUExecutionProvider"])
        fark = max(
            float(np.abs(oturum.run(None, {"video": x})[0] - r).max())
            for x, r in zip(girdiler, referans, strict=True)
        )
        print(f"→ ONNX ↔ Keras en büyük fark: {fark:.2e} ({len(girdiler)} girdi)")
        if fark > args.tolerans:
            print(f"🔴 Fark toleransı aşıyor ({args.tolerans:.0e}); ağırlık yazılmadı.")
            return 1

        args.hedef.mkdir(parents=True, exist_ok=True)
        (args.hedef / "model.onnx").write_bytes(aday.read_bytes())

    onisleme["aktarim_farki"] = fark
    (args.hedef / "onisleme.json").write_text(
        json.dumps(onisleme, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _kart_yaz(args.hedef, onisleme, model.count_params())
    print(f"✓ {args.hedef}/model.onnx · onisleme.json · kart.json")
    print("  Kabul kapısı için ölçüm: python scripts/eval/m4_video.py")
    return 0


def _kart_yaz(hedef: Path, onisleme: dict, parametre: int) -> None:
    """Model kartının ölçümsüz iskeleti; ölçümleri scripts/eval/m4_video.py ekler.

    Eski ölçümler BİLEREK taşınmaz: yeni aktarılan ağırlık ölçülmemiş bir
    ağırlıktır ve kabul kapısı ölçüm koşturulana kadar kapalı kalmalıdır.
    """
    from krizkalkan_core.models.cards import ModelCard

    kart = ModelCard(
        name="m4_video",
        module="M4",
        title="Sentetik video tespiti",
        version="1.0",
        base_model="ResNet50 (ImageNet) kare kodlayıcı + 2×BiLSTM + çok başlı dikkat",
        purpose=(
            "Afet videolarında yapay zekâ ile üretilmiş içerik izi arar. Çıktı "
            "olasılıksaldır; C2PA imzası ya da üretici üstverisi varsa karar oradan gelir."
        ),
        training_data=[
            "Afet video kümesi · 729 gerçek afet videosu (çığ, deprem, kasırga, "
            "heyelan, yanardağ, sel, orman yangını) + 628 üretilmiş afet videosu",
            "Eğitim/doğrulama ayrımının dosya listesi depoda kayıtlı değil; hangi "
            "videonun hangi bölmede olduğu BİLİNMİYOR.",
        ],
        training_procedure=(
            "Keras 2.10 (TensorFlow) ile eğitildi. Kayıp: "
            "BinaryFocalCrossentropy (α=0,25, γ=2). ResNet50'nin yalnızca conv5 bloğu "
            "eğitilebilir. Ayrıntılı eğitim kodu depoda değil."
        ),
        hyperparameters={
            "giris": f"{onisleme['kare_sayisi']} kare × {onisleme['boyut']}×{onisleme['boyut']}",
            "kare_secimi": "16 eşit aralık + 16 en hareketli (Farneback, 112×112)",
            "parametre": f"{parametre / 1e6:.1f}M",
            "esik_p_gercek": onisleme["esik_p_gercek"],
            "niceleme": "yok — fp32",
            "onnx_aktarim_farki": f"{onisleme.get('aktarim_farki', 0):.1e}",
        },
        split_strategy=(
            "BİLİNMİYOR. Eğitimde bir eğitim/doğrulama ayrımı kullanıldı ancak ayrımın "
            "dosya listesi depoda kayıtlı değil. Bu kümede ölçülen her sayı alan içidir "
            "ve modelin gördüğü videoları içerir."
        ),
        license="Proje içi kullanım",
    )
    kart.save(hedef)


if __name__ == "__main__":
    raise SystemExit(main())
