#!/usr/bin/env python
"""Colab'da eğitilmiş M4 kontrol noktasını ONNX'e aktarır.

**Niceleme bilinçli olarak yapılmıyor.** Dinamik int8, bu modelin kararını
bozuyor: ölçüldü, azami logit sapması 2,4152 ve gerçek afet fotoğraflarında
P(üretilmiş) medyanı 0,0197'den 0,2552'ye kayıyor. Kabul kapısı fp32'de 0,9885
verirken int8'de 0,5466'ya düşüyordu.

Önceki (DeepReality) ağırlık int8'e dayanıyordu çünkü çıktıları zaten doygundu
ve kaydırmanın değiştirecek bir kararı yoktu. Bu model gerçek bir karar sınırına
sahip; niceleme o sınırı kaydırıyor.

Bedeli dosya boyutu: ~95 MB yerine ~370 MB. Gecikme bedeli ölçülüp
`docs/metrikler/sistem.md`'ye yazılır.

Kullanım:
    python scripts/train/m4_disa_aktar.py --kontrol-noktasi en_iyi.pt \\
        --hedef models/m4_synthetic_temiz
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

OMURGA = "google/siglip2-base-patch16-224"
GIRIS = 224


def _model():
    """Colab defterindeki mimarinin birebir aynısı.

    Katman adları `state_dict` ile eşleşmek zorunda; sapma sessizce rastgele
    ağırlıkla çalışan bir model üretir.
    """
    import torch.nn as nn
    from transformers import SiglipVisionModel

    class SentetikDedektor(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.vision_model = SiglipVisionModel.from_pretrained(OMURGA)
            gizli = self.vision_model.config.hidden_size
            self.classifier = nn.Sequential(
                nn.LayerNorm(gizli),
                nn.Dropout(0.2),
                nn.Linear(gizli, 256),
                nn.GELU(),
                nn.Dropout(0.1),
                nn.Linear(256, 2),
            )

        def forward(self, pixel_values):
            return self.classifier(self.vision_model(pixel_values=pixel_values).pooler_output)

    return SentetikDedektor()


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--kontrol-noktasi", type=Path, required=True)
    a.add_argument("--hedef", type=Path, required=True)
    args = a.parse_args()
    args.hedef = args.hedef.resolve()

    import numpy as np
    import torch

    if not args.kontrol_noktasi.exists():
        print(f"🔴 kontrol noktası yok: {args.kontrol_noktasi}")
        return 1

    model = _model()
    eksik, _ = model.load_state_dict(
        torch.load(args.kontrol_noktasi, map_location="cpu"), strict=False
    )
    # Eksik ağırlık sessiz bir felakettir: model rastgele değerlerle çalışır.
    if eksik:
        print(f"🔴 yüklenemeyen {len(eksik)} ağırlık, ilk 5: {eksik[:5]}")
        return 1
    model.eval()

    args.hedef.mkdir(parents=True, exist_ok=True)
    hedef_onnx = args.hedef / "uretim.onnx"
    torch.onnx.export(
        model,
        (torch.zeros(1, 3, GIRIS, GIRIS),),
        str(hedef_onnx),
        input_names=["pixel_values"],
        output_names=["logits"],
        dynamic_axes={"pixel_values": {0: "yigin"}, "logits": {0: "yigin"}},
        opset_version=18,
        dynamo=False,
    )
    boyut = hedef_onnx.stat().st_size
    harici = hedef_onnx.with_suffix(".onnx.data")
    if harici.exists():
        boyut += harici.stat().st_size
    print(f"✓ {hedef_onnx.name} · {boyut / 1e6:.0f} MB (fp32) → {args.hedef.name}")

    # Doğrulama: ONNX çıktısı torch ile örtüşmeli
    import onnxruntime as ort

    oturum = ort.InferenceSession(str(hedef_onnx), providers=["CPUExecutionProvider"])
    ornek = torch.rand(4, 3, GIRIS, GIRIS, generator=torch.Generator().manual_seed(0))
    with torch.no_grad():
        referans = model(ornek).numpy()
    (cikti,) = oturum.run(None, {"pixel_values": ornek.numpy()})
    sapma = float(np.abs(cikti - referans).max())
    print(f"  ONNX ↔ torch azami logit sapması: {sapma:.6f}")
    if sapma > 0.01:
        print("  🔴 sapma beklenenden büyük — dışa aktarım doğrulanamadı")
        return 1

    # Ön işleme sözleşmesi
    (args.hedef / "onisleme.json").write_text(
        json.dumps(
            {
                "uretim": {
                    "boyut": GIRIS,
                    "ortalama": [0.5, 0.5, 0.5],
                    "sapma": [0.5, 0.5, 0.5],
                    "yeniden_ornekleme": "BILINEAR",
                },
                "tur": {
                    "boyut": 224,
                    "ortalama": [0.5, 0.5, 0.5],
                    "sapma": [0.5, 0.5, 0.5],
                    "yeniden_ornekleme": "BILINEAR",
                },
                "etiketler": ["sentetik", "manipüle", "gerçek"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("✓ onisleme.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
