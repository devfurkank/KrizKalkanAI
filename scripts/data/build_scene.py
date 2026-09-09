#!/usr/bin/env python
"""M2 sahne–iddia modelini kurar: çok dilli CLIP → int8 ONNX + istem gömmeleri.

Metin kodlayıcısı çok dillidir; CLIP'in kendi metin kulesi İngilizce eğitilmiştir
ve Türkçe iddialarda kullanılamaz. İki kule ayrı ONNX dosyasına aktarılır çünkü
görsel kodlayıcı her kare için, metin kodlayıcı yalnızca inşa sırasında çalışır.

Karşıt istemler burada gömülür ve dosyaya yazılır: sabit bir metni her sorguda
yeniden kodlamanın anlamı yok.

Çıktı: models/m2_scene/{gorsel.onnx, metin.onnx, metin_tokenizer.json,
       istemler.json}
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.multimodal.scene import GORSEL_BOYUT, MAKS_METIN  # noqa: E402

GORSEL_MODEL = "openai/clip-vit-base-patch32"
METIN_MODEL = "sentence-transformers/clip-ViT-B-32-multilingual-v1"
CIKTI = REPO_ROOT / "models" / "m2_scene"

#: Karşıt istemler. Her olay türü için birden çok ifade tutulur; en yükseği
#: alınır. Tek istem, ifade seçimine aşırı duyarlı olurdu.
ISTEMLER: dict[str, tuple[str, ...]] = {
    "deprem": (
        "depremde yıkılan bina ve enkaz yığını",
        "çöken binanın kalıntıları arasında arama kurtarma çalışması",
        "deprem sonrası hasar görmüş yapılar",
    ),
    "yangın": (
        "orman yangını, alevler ve duman",
        "yanan ağaçlar ve ilerleyen alev hattı",
        "yangın söndürme çalışması yapan itfaiye",
    ),
    "sel": (
        "sel suları altında kalan cadde",
        "taşkın sularına gömülmüş araçlar ve evler",
        "su baskını sonrası çamurla kaplı sokak",
    ),
    "diğer": (
        "gündelik bir sokak görüntüsü",
        "kalabalık bir toplantı veya basın açıklaması",
        "haritalar, grafikler veya ekran görüntüsü",
    ),
}


def _boyut(yol: Path) -> float:
    toplam = yol.stat().st_size
    harici = yol.with_suffix(yol.suffix + ".data")
    if harici.exists():
        toplam += harici.stat().st_size
    return toplam / 1e6


def disa_aktar() -> int:
    """İki kuleyi fp32 ONNX'e aktarır ve tokenizer'ı kaydeder."""
    import torch
    from sentence_transformers import SentenceTransformer
    from transformers import CLIPModel

    CIKTI.mkdir(parents=True, exist_ok=True)

    print(f"→ {GORSEL_MODEL}")
    clip = CLIPModel.from_pretrained(GORSEL_MODEL).to("cpu").eval()

    class GorselKule(torch.nn.Module):
        def __init__(self, model):
            super().__init__()
            self.model = model

        def forward(self, pixel_values):
            return self.model.get_image_features(pixel_values=pixel_values)

    ornek = torch.zeros(1, 3, GORSEL_BOYUT, GORSEL_BOYUT)
    torch.onnx.export(
        GorselKule(clip).eval(),
        (ornek,),
        str(CIKTI / "_gorsel_fp32.onnx"),
        input_names=["pixel_values"],
        output_names=["image_embeds"],
        dynamic_axes={"pixel_values": {0: "yigin"}, "image_embeds": {0: "yigin"}},
        opset_version=18,
        dynamo=False,
    )
    print(f"  fp32: {_boyut(CIKTI / '_gorsel_fp32.onnx'):.0f} MB")

    print(f"→ {METIN_MODEL}")
    # device="cpu" zorunlu: SentenceTransformer macOS'ta modeli MPS'e yüklüyor
    # ve ONNX dışa aktarımının CPU örnek tensörleriyle çakışıyor
    # ("Passed CPU tensor to MPS op").
    st = SentenceTransformer(METIN_MODEL, device="cpu")
    govde = st[0].auto_model.eval()
    yogun = st[2] if len(st) > 2 else None
    st.tokenizer.backend_tokenizer.save(str(CIKTI / "metin_tokenizer.json"))

    class MetinKule(torch.nn.Module):
        """Ortalama havuzlama + CLIP uzayına projeksiyon.

        Projeksiyon katmanı (Dense) atlanırsa gömme 768 boyutlu kalır ve
        512 boyutlu görsel gömmeyle çarpılamaz — sessiz bir boyut hatası.
        """

        def __init__(self, govde, yogun):
            super().__init__()
            self.govde = govde
            self.yogun = yogun

        def forward(self, input_ids, attention_mask):
            cikti = self.govde(input_ids=input_ids, attention_mask=attention_mask)
            gizli = cikti.last_hidden_state
            maske = attention_mask.unsqueeze(-1).float()
            havuz = (gizli * maske).sum(1) / maske.sum(1).clamp(min=1e-9)
            if self.yogun is not None:
                havuz = self.yogun({"sentence_embedding": havuz})["sentence_embedding"]
            return havuz

    kodlanmis = st.tokenizer(
        ["örnek"], return_tensors="pt", padding="max_length", max_length=MAKS_METIN
    )
    torch.onnx.export(
        MetinKule(govde, yogun).eval(),
        (kodlanmis["input_ids"], kodlanmis["attention_mask"]),
        str(CIKTI / "_metin_fp32.onnx"),
        input_names=["input_ids", "attention_mask"],
        output_names=["text_embeds"],
        dynamic_axes={
            "input_ids": {0: "yigin", 1: "uzunluk"},
            "attention_mask": {0: "yigin", 1: "uzunluk"},
            "text_embeds": {0: "yigin"},
        },
        opset_version=18,
        dynamo=False,
    )
    print(f"  fp32: {_boyut(CIKTI / '_metin_fp32.onnx'):.0f} MB")
    return 0


def nicele() -> int:
    from onnxruntime.quantization import QuantType, quantize_dynamic

    for ad in ("gorsel", "metin"):
        ham = CIKTI / f"_{ad}_fp32.onnx"
        if not ham.exists():
            print(f"🔴 {ham} yok")
            return 1
        quantize_dynamic(
            str(ham), str(CIKTI / f"{ad}.onnx"), weight_type=QuantType.QInt8, per_channel=True
        )
        print(f"  ✓ {ad}: {_boyut(ham):.0f} MB → {_boyut(CIKTI / f'{ad}.onnx'):.0f} MB")
        ham.unlink(missing_ok=True)
        ham.with_suffix(".onnx.data").unlink(missing_ok=True)
    return 0


def istemleri_gom() -> int:
    """Karşıt istemleri int8 metin kulesiyle gömer ve dosyaya yazar."""
    from krizkalkan_core.multimodal.scene import SahneModeli

    model = SahneModeli.__new__(SahneModeli)
    import numpy as np
    import onnxruntime as ort
    from tokenizers import Tokenizer

    model._np = np
    model.metin = ort.InferenceSession(
        str(CIKTI / "metin.onnx"), providers=["CPUExecutionProvider"]
    )
    model.tokenizer = Tokenizer.from_file(str(CIKTI / "metin_tokenizer.json"))
    model.tokenizer.enable_truncation(max_length=MAKS_METIN)
    model.tokenizer.enable_padding()

    duz = [i for tur in ISTEMLER for i in ISTEMLER[tur]]
    sahip = [tur for tur in ISTEMLER for _ in ISTEMLER[tur]]
    gomme = np.asarray(model.metin_gomme(duz))

    (CIKTI / "istemler.json").write_text(
        json.dumps(
            {
                "turler": list(ISTEMLER),
                "tur_indeksi": sahip,
                "gomme": gomme.tolist(),
                "istemler": duz,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"  ✓ {len(duz)} istem gömüldü · boyut {gomme.shape}")
    return 0


def _alt_surec(bayrak: str) -> int:
    sonuc = subprocess.run([sys.executable, __file__, bayrak], capture_output=True, text=True)
    if sonuc.stdout.strip():
        print(sonuc.stdout.rstrip())
    # Hata durumunda stderr HER ZAMAN basılır: stdout doluyken gizlemek,
    # başarısızlığı sessiz bir duruşa çeviriyordu.
    if sonuc.returncode != 0 and sonuc.stderr.strip():
        print(sonuc.stderr.strip()[-800:])
    return sonuc.returncode


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    for bayrak, yardim in (
        ("--disa-aktar", "yalnızca fp32 ONNX (torch)"),
        ("--nicele", "yalnızca int8 niceleme"),
        ("--istem", "yalnızca istem gömmeleri"),
    ):
        a.add_argument(bayrak, action="store_true", help=yardim)
    args = a.parse_args()

    if args.disa_aktar:
        return disa_aktar()
    if args.nicele:
        return nicele()
    if args.istem:
        return istemleri_gom()

    # Adımlar ayrı süreçlerde: macOS'ta torch ve onnxruntime aynı süreçte
    # OpenMP çalışma zamanını çakıştırıyor (M5'te de aynı sorun yaşandı).
    for bayrak, baslik in (
        ("--disa-aktar", "1/3 dışa aktarım"),
        ("--nicele", "2/3 niceleme"),
        ("--istem", "3/3 istem gömmeleri"),
    ):
        print(f"\n═══ {baslik} ═══")
        if (kod := _alt_surec(bayrak)) != 0:
            return kod
    print(f"\n✓ {CIKTI.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
