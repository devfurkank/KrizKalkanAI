#!/usr/bin/env python
"""M4 sentetik görüntü detektörlerini kurar: DeepReality ağırlıkları → int8 ONNX.

İki detektör ayrı dosyaya aktarılır çünkü farklı sorulara cevap verirler ve
farklı giriş boyutlarında çalışırlar:

    uretim.onnx   512×512  ikili       → P(içerik üretilmiş)
    tur.onnx      224×224  üç sınıflı  → sentetik / manipüle / gerçek

Kaynak: DeepReality (MIT · https://github.com/OmerKurtulus/DeepReality)
    models/pin_b2_siglip2_finetune_final.pt   — SigLIP2-512 ince ayar
    models/pin_b4_ai_deepfake_real/           — SigLIP2-224 üç sınıflı

**Gövde mimarisi ağırlıktan türetilir, indirilmez.** `pin_b2` bir `state_dict`
olarak dağıtılır; mimariyi kurmak için normalde temel modelin 1,5 GB'lık
ağırlığı indirilir. Buna gerek yok: katman sayısı, gizli boyut ve kare sayısı
tensör şekillerinden okunabilir. Yalnızca ön işleme yapılandırması (birkaç yüz
bayt) ağdan alınır, o da bulunamazsa yerel SigLIP2 yapılandırmasından türetilir.

Çıktı: models/m4_synthetic/{uretim.onnx, tur.onnx, onisleme.json, kart.json}
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "libs" / "krizkalkan-core" / "src"))

from krizkalkan_core.models.cards import Measurement, ModelCard  # noqa: E402
from krizkalkan_core.synthetic.image import MODEL_ADI, TUR_ETIKETLERI  # noqa: E402

CIKTI = REPO_ROOT / "models" / MODEL_ADI

#: DeepReality deposunun `models/` dizini. Ortam değişkeniyle de verilebilir:
#: depo iki makinede farklı yerlerde duruyor ve yol sabitlenemez.
VARSAYILAN_KAYNAK = Path(
    os.environ.get("KK_DEEPREALITY_DIR", Path.home() / "Desktop" / "DeepReality" / "models")
)

IKILI_AGIRLIK = "pin_b2_siglip2_finetune_final.pt"
UCUL_DIZIN = "pin_b4_ai_deepfake_real"

#: Ön işleme yapılandırması ağdan alınamazsa kullanılacak SigLIP ailesi
#: değerleri. Yerel üç sınıflı modelin `preprocessor_config.json` dosyasıyla
#: doğrulanır; sapma varsa betik durur.
SIGLIP_ORTALAMA = [0.5, 0.5, 0.5]
SIGLIP_SAPMA = [0.5, 0.5, 0.5]
SIGLIP_ORNEKLEME = "BILINEAR"


def _boyut(yol: Path) -> float:
    toplam = yol.stat().st_size
    harici = yol.with_suffix(yol.suffix + ".data")
    if harici.exists():
        toplam += harici.stat().st_size
    return toplam / 1e6


def _ornek_girdi(boyut: int):
    """Niceleme kaybı ölçümü için tekrarlanabilir girdi.

    Tohum giriş boyutundan türetilir; böylece dışa aktarım ve niceleme adımları
    aynı tensörü bağımsız olarak yeniden üretebilir.
    """
    import torch

    return torch.rand(2, 3, boyut, boyut, generator=torch.Generator().manual_seed(boyut))


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=True,
        ).stdout.strip()
    except Exception:
        return "—"


# ────────────────────────── mimari türetimi ──────────────────────────


def _gorsel_yapilandirma(durum: dict):
    """`state_dict` tensör şekillerinden SigLIP görsel kulesi yapılandırması.

    Temel modeli indirmemek için yazıldı. Yanlış bir varsayım sessiz kalmasın
    diye her değer tek bir tensörden okunur, hiçbiri "bilinen" kabul edilmez.
    """
    from transformers import SiglipVisionConfig

    yama = durum["vision_model.embeddings.patch_embedding.weight"]
    gizli, kanal, yama_boyu, _ = yama.shape
    konum = durum["vision_model.embeddings.position_embedding.weight"]
    yama_sayisi = konum.shape[0]
    kenar = round(yama_sayisi**0.5)
    if kenar * kenar != yama_sayisi:
        raise ValueError(f"kare olmayan yama ızgarası: {yama_sayisi}")

    katmanlar = 1 + max(
        int(ad.split(".")[3]) for ad in durum if ad.startswith("vision_model.encoder.layers.")
    )
    ara = durum["vision_model.encoder.layers.0.mlp.fc1.weight"].shape[0]

    return SiglipVisionConfig(
        hidden_size=gizli,
        intermediate_size=ara,
        num_hidden_layers=katmanlar,
        # Başlık sayısı ağırlıktan okunamaz (birleşik in_proj); SigLIP ailesinde
        # başlık boyutu 64'tür ve bu, gizli boyuttan türetilebilir.
        num_attention_heads=gizli // 64,
        num_channels=kanal,
        image_size=kenar * yama_boyu,
        patch_size=yama_boyu,
    )


def _onisleme_yaz(ikili_boyut: int, ucul_dizin: Path) -> dict:
    """Ön işleme parametrelerini yetkili kaynaktan okur ve dosyaya dondurur.

    Çalışma zamanının tahmin yürütmesine izin verilmez: kare boyutu ya da
    normalizasyon sabiti eğitimdekinden saptığında model hata vermez, sessizce
    yanlış cevap verir. Bu, entegrasyonda en sık yapılan hatadır.
    """
    yerel = json.loads((ucul_dizin / "preprocessor_config.json").read_text(encoding="utf-8"))
    ucul_boyut = int(yerel["size"]["height"])
    ortalama = [float(v) for v in yerel["image_mean"]]
    sapma = [float(v) for v in yerel["image_std"]]

    if ortalama != SIGLIP_ORTALAMA or sapma != SIGLIP_SAPMA:
        raise ValueError(
            f"üç sınıflı modelin normalizasyonu beklenenden farklı: {ortalama} / {sapma}"
        )

    ayar = {
        "uretim": {
            "boyut": ikili_boyut,
            "ortalama": ortalama,
            "sapma": sapma,
            "yeniden_ornekleme": SIGLIP_ORNEKLEME,
        },
        "tur": {
            "boyut": ucul_boyut,
            "ortalama": ortalama,
            "sapma": sapma,
            "yeniden_ornekleme": SIGLIP_ORNEKLEME,
        },
        "etiketler": list(TUR_ETIKETLERI),
    }
    (CIKTI / "onisleme.json").write_text(
        json.dumps(ayar, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return ayar


# ────────────────────────── dışa aktarım ──────────────────────────


def disa_aktar(kaynak: Path) -> int:
    """İki detektörü fp32 ONNX'e aktarır ve torch referans çıktısını saklar."""
    import torch
    from torch import nn

    CIKTI.mkdir(parents=True, exist_ok=True)

    # ── İkili detektör (PIN-B2) ──
    agirlik = kaynak / IKILI_AGIRLIK
    if not agirlik.exists():
        print(f"🔴 bulunamadı: {agirlik}")
        return 1

    print(f"→ ikili detektör · {agirlik.name}")
    paket = torch.load(agirlik, map_location="cpu", weights_only=False)
    durum = paket["model_state_dict"]
    yapilandirma = _gorsel_yapilandirma(durum)
    print(
        f"  mimari ağırlıktan türetildi: {yapilandirma.num_hidden_layers} katman · "
        f"{yapilandirma.hidden_size} gizli · {yapilandirma.image_size}px"
    )

    from transformers import SiglipVisionModel

    class IkiliDedektor(nn.Module):
        """Görsel kule + sınıflandırma başlığı.

        Metin kulesi taşınmaz: sınıflandırmada kullanılmıyor ve ağırlığın
        %75'ini o oluşturuyor (375,8M → 93,7M).
        """

        def __init__(self, config, gizli: int) -> None:
            super().__init__()
            # Alt modülün adı `vision_model` OLMAK ZORUNDA: `state_dict`
            # anahtarları bu adla eşleşiyor (208/208 doğrulandı).
            self.vision_model = SiglipVisionModel(config)
            self.classifier = nn.Sequential(
                nn.LayerNorm(gizli),
                nn.Dropout(0.15),
                nn.Linear(gizli, 256),
                nn.GELU(),
                nn.Dropout(0.1),
                nn.Linear(256, 2),
            )

        def forward(self, pixel_values):
            return self.classifier(self.vision_model(pixel_values=pixel_values).pooler_output)

    model = IkiliDedektor(yapilandirma, yapilandirma.hidden_size)
    ilgili = {ad: t for ad, t in durum.items() if ad.startswith(("vision_model.", "classifier."))}
    eksik, fazla = model.load_state_dict(ilgili, strict=False)
    # Eksik ağırlık sessiz bir felakettir: model rastgele başlangıç değerleriyle
    # çalışır ve hiçbir hata vermez. Bu yüzden tolerans sıfırdır.
    if eksik:
        print(f"🔴 yüklenemeyen {len(eksik)} ağırlık, ilk 5: {eksik[:5]}")
        return 1
    if fazla:
        print(f"  not: {len(fazla)} kullanılmayan anahtar atlandı")
    model.eval()

    ornek = torch.zeros(1, 3, yapilandirma.image_size, yapilandirma.image_size)
    torch.onnx.export(
        model,
        (ornek,),
        str(CIKTI / "_uretim_fp32.onnx"),
        input_names=["pixel_values"],
        output_names=["logits"],
        dynamic_axes={"pixel_values": {0: "yigin"}, "logits": {0: "yigin"}},
        opset_version=18,
        dynamo=False,
    )
    print(f"  fp32: {_boyut(CIKTI / '_uretim_fp32.onnx'):.0f} MB")

    # ── Üç sınıflı detektör (PIN-B4) ──
    ucul_dizin = kaynak / UCUL_DIZIN
    if not ucul_dizin.exists():
        print(f"🔴 bulunamadı: {ucul_dizin}")
        return 1

    print(f"→ üç sınıflı detektör · {UCUL_DIZIN}")
    from transformers import SiglipForImageClassification

    ucul = SiglipForImageClassification.from_pretrained(str(ucul_dizin), local_files_only=True)
    ucul.eval()

    # Etiket sırası varsayılmaz, yapılandırmadan doğrulanır: sıra kayarsa
    # "sentetik" ile "gerçek" yer değiştirir ve hiçbir hata görünmez.
    beklenen = {0: "AI", 1: "Deepfake", 2: "Real"}
    gercek = {int(k): v for k, v in ucul.config.id2label.items()}
    if gercek != beklenen:
        print(f"🔴 etiket sırası beklenenden farklı: {gercek}")
        return 1
    print(f"  etiket sırası doğrulandı: {gercek} → {TUR_ETIKETLERI}")

    class UculDedektor(nn.Module):
        def __init__(self, govde) -> None:
            super().__init__()
            self.govde = govde

        def forward(self, pixel_values):
            return self.govde(pixel_values=pixel_values).logits

    ucul_boyut = int(ucul.config.vision_config.image_size)
    ornek = torch.zeros(1, 3, ucul_boyut, ucul_boyut)
    torch.onnx.export(
        UculDedektor(ucul).eval(),
        (ornek,),
        str(CIKTI / "_tur_fp32.onnx"),
        input_names=["pixel_values"],
        output_names=["logits"],
        dynamic_axes={"pixel_values": {0: "yigin"}, "logits": {0: "yigin"}},
        opset_version=18,
        dynamo=False,
    )
    print(f"  fp32: {_boyut(CIKTI / '_tur_fp32.onnx'):.0f} MB")

    ayar = _onisleme_yaz(yapilandirma.image_size, ucul_dizin)
    print(f"  ön işleme donduruldu: üretim {ayar['uretim']['boyut']}px · tur {ucul_boyut}px")

    # Niceleme kaybını ölçebilmek için fp32 referans çıktıları saklanır.
    # Sabit bir girdi yeterli: aranan şey mutlak doğruluk değil, int8'in fp32'den
    # ne kadar saptığı.
    import numpy as np

    # Her detektör KENDİ tohumundan üretilmiş girdiyi görür: tek bir üreteci
    # paylaşmak, niceleme adımının ikinci girdiyi yeniden üretememesine yol açar.
    with torch.no_grad():
        referans = {
            "uretim": model(_ornek_girdi(yapilandirma.image_size)),
            "tur": UculDedektor(ucul)(_ornek_girdi(ucul_boyut)),
        }
    np.savez(
        CIKTI / "_referans.npz",
        **{ad: t.numpy() for ad, t in referans.items()},
    )

    _kart_yaz(paket, yapilandirma, ucul_dizin)
    return 0


def nicele() -> int:
    """fp32 ONNX → int8 ve niceleme kaybının doğrulanması."""
    import numpy as np
    import onnxruntime as ort
    from onnxruntime.quantization import QuantType, quantize_dynamic

    referans = np.load(CIKTI / "_referans.npz") if (CIKTI / "_referans.npz").exists() else None

    for ad, boyut_anahtari in (("uretim", "uretim"), ("tur", "tur")):
        ham = CIKTI / f"_{ad}_fp32.onnx"
        if not ham.exists():
            print(f"🔴 {ham} yok — önce --disa-aktar")
            return 1
        hedef = CIKTI / f"{ad}.onnx"
        quantize_dynamic(str(ham), str(hedef), weight_type=QuantType.QInt8, per_channel=True)
        print(f"  ✓ {ad}: {_boyut(ham):.0f} MB → {_boyut(hedef):.0f} MB")

        if referans is not None:
            ayar = json.loads((CIKTI / "onisleme.json").read_text(encoding="utf-8"))
            boyut = ayar[boyut_anahtari]["boyut"]
            girdi = _ornek_girdi(boyut).numpy()
            oturum = ort.InferenceSession(str(hedef), providers=["CPUExecutionProvider"])
            (cikti,) = oturum.run(None, {"pixel_values": girdi})
            sapma = float(np.abs(cikti - referans[ad]).max())
            print(f"    int8 ↔ fp32 azami logit sapması: {sapma:.4f}")

        ham.unlink(missing_ok=True)
        ham.with_suffix(".onnx.data").unlink(missing_ok=True)

    (CIKTI / "_referans.npz").unlink(missing_ok=True)
    return 0


# ────────────────────────── model kartı ──────────────────────────


def _kart_yaz(paket: dict, yapilandirma, ucul_dizin: Path) -> None:
    """Ağırlığın künyesini karta geçirir.

    Kaynak ölçümler **bizim ölçümümüz değildir** ve kartta böyle işaretlenir.
    Kabul kapısının aradığı `capraz_auc` bilinçli olarak yazılmaz: onu
    `scripts/eval/m4_synthetic.py` üretir. Ölçülmeden ağırlık yüklenmez.
    """
    olcumler = paket.get("metrics", {})
    kaynak_kumesi = paket.get("dataset", "bilinmiyor")

    kart = ModelCard(
        name=MODEL_ADI,
        module="M4",
        title="Sentetik görüntü tespiti (ikili + üç sınıflı)",
        version="0.1",
        base_model="google/siglip2-base-patch16-512 · google/siglip2-base-patch16-224",
        purpose=(
            "Görüntüde yapay üretim izi arar ve bulduğunda türünü ayırır: tam sentetik "
            "üretim (SENTETİK_MEDYA) ile gerçek içerik üzerinde oynama (MANİPÜLE_MEDYA) "
            "farklı sınıflardır ve farklı müdahale tetikler. Modül olasılıksal çıkarım "
            "üretir; C2PA imzası varsa karar oradan gelir, bu detektörler onu geçersiz "
            "kılamaz."
        ),
        training_data=[
            f"İkili detektör: {kaynak_kumesi} · {paket.get('training_epochs', '?')} epok "
            "ince ayar (DeepReality, MIT)",
            "Üç sınıflı detektör: prithivMLmods/AI-vs-Deepfake-vs-Real-Siglip2 "
            "(Apache 2.0, harici hazır ağırlık)",
        ],
        training_procedure=(
            "Ağırlıklar DeepReality projesinden alındı; bu depoda eğitim yapılmadı. "
            "Görsel kule ve sınıflandırma başlığı ayrıştırılıp int8 ONNX'e aktarıldı; "
            "metin kulesi taşınmadı (375,8M → 93,7M parametre). İki detektör ayrı "
            "korpuslarda eğitildiği için hemfikirlikleri bağımsız doğrulama, "
            "çelişkileri ise çekinme sebebidir."
        ),
        hyperparameters={
            "ikili_giris": f"{yapilandirma.image_size}×{yapilandirma.image_size}",
            "ucul_giris": "224×224",
            "katman": yapilandirma.num_hidden_layers,
            "gizli_boyut": yapilandirma.hidden_size,
            "niceleme": "int8 dinamik, kanal başına",
        },
        split_strategy="Kaynak projelerin kendi tutulmuş test bölünmeleri",
        measurements=[
            Measurement(
                metric="alan_ici_auc",
                value=round(float(olcumler.get("test_roc_auc", 0.0)), 6),
                dataset=f"{kaynak_kumesi} (tutulmuş test)",
                n=3000,
                note="DeepReality tarafından fp32 ile ölçüldü — bu deponun ölçümü DEĞİLDİR",
            ),
            Measurement(
                metric="alan_ici_f1",
                value=round(float(olcumler.get("test_f1", 0.0)), 6),
                dataset=f"{kaynak_kumesi} (tutulmuş test)",
                n=3000,
                note="DeepReality tarafından fp32 ile ölçüldü — bu deponun ölçümü DEĞİLDİR",
            ),
        ],
        known_limits=[
            "Yalnızca görüntü. Video için kare çıkarımı (ffmpeg) gerekir ve kurulu değil; "
            "video içerikte modül çekinir.",
            "Hesaplamalı fotoğrafçılık yanlış pozitifi: çok kareli birleştirme ve gürültü "
            "bastırma uygulayan telefon kameralarının düşük gürültülü dokusu, üretim "
            "imzasına benziyor. DeepReality'de doğrudan gözlendi.",
            "Genelleme açığı üreticiye bağlıdır. Alan içi başarım ile görülmemiş üretici "
            "ailelerindeki başarım arasındaki fark ölçülmeli ve kartta ayrı satır olarak "
            "durmalıdır.",
            "Aşırı sıkıştırılmış ve düşük çözünürlüklü görüntülerde üretim izleri fiilen "
            "silinir; modül bu girdilerde skor üretmez.",
        ],
        ethical_notes=[
            "Skor bir suçlama değildir. Sentetik medya tespiti tek başına içerik "
            "kaldırma gerekçesi sayılmaz; sistemin böyle bir yetkisi zaten yoktur.",
            "Çekinme oranı ölçülür ve raporlanır: modelin neyi bilmediği, ne bildiği "
            "kadar önemlidir.",
        ],
        out_of_scope=[
            "Kimlik tespiti veya kişi eşleştirme.",
            "Adli delil üretimi — çıktı karar destek sinyalidir.",
            "Video ve ses içeriği.",
        ],
        license="MIT (DeepReality) · Apache 2.0 (üç sınıflı ağırlık)",
        git_commit=_git_commit(),
    )
    yol = kart.save(CIKTI)
    print(f"  ✓ model kartı: {yol.relative_to(REPO_ROOT)}")


# ────────────────────────── akış ──────────────────────────


def _alt_surec(bayrak: str, kaynak: Path) -> int:
    sonuc = subprocess.run(
        [sys.executable, __file__, bayrak, "--kaynak", str(kaynak)],
        capture_output=True,
        text=True,
    )
    if sonuc.stdout.strip():
        print(sonuc.stdout.rstrip())
    if sonuc.returncode != 0 and sonuc.stderr.strip():
        print(sonuc.stderr.strip()[-1500:])
    return sonuc.returncode


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument(
        "--kaynak",
        type=Path,
        default=VARSAYILAN_KAYNAK,
        help="DeepReality models/ dizini (ya da KK_DEEPREALITY_DIR)",
    )
    a.add_argument("--disa-aktar", action="store_true", help="yalnızca fp32 ONNX (torch)")
    a.add_argument("--nicele", action="store_true", help="yalnızca int8 niceleme")
    args = a.parse_args()

    if args.disa_aktar:
        return disa_aktar(args.kaynak)
    if args.nicele:
        return nicele()

    if not args.kaynak.exists():
        print(f"🔴 DeepReality ağırlık dizini yok: {args.kaynak}")
        print("   KK_DEEPREALITY_DIR ile yol verin ya da --kaynak kullanın.")
        return 1

    # Adımlar ayrı süreçlerde: macOS'ta torch ve onnxruntime aynı süreçte
    # OpenMP çalışma zamanını çakıştırıyor (M2 ve M5'te de yaşandı).
    for bayrak, baslik in (("--disa-aktar", "1/2 dışa aktarım"), ("--nicele", "2/2 niceleme")):
        print(f"\n═══ {baslik} ═══")
        if (kod := _alt_surec(bayrak, args.kaynak)) != 0:
            return kod

    print(f"\n✓ {CIKTI.relative_to(REPO_ROOT)}")
    print("  Kabul kapısı henüz açık değil: çapraz veri kümesi AUC'si ölçülmedi.")
    print("  Sıradaki: python scripts/eval/m4_synthetic.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
