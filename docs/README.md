# docs/

Proje dokümantasyonu.

| Doküman | İçerik | Üretimi |
| --- | --- | --- |
| `mimari.md` | Sistem mimarisi, füzyon sırası, ölçümle verilen kararlar | elle |
| `veri-envanteri.md` | Veri setleri: kaynak, lisans, hacim, **dağıtım biçimi**, hedef modül | `scripts/data/fetch_text.py` |
| `metrikler/` | Modül başına ölçüm raporları | `scripts/eval/*.py` |
| `model-kartlari/` | Her model için kart (amaç, veri, ölçüm, **bilinen sınırlar**) | `scripts/eval/*.py` |
| `etik-protokol.md` | KVKK taahhüt/uygulama karşılaştırması, adalet, sentetik veri, kötüye kullanım, **açık yükümlülükler** | elle |

Metrik raporları ve model kartları **elle yazılmaz**: her biri üstünde üreten
betiği, tarihi ve git commit'ini taşır. Ölçümü tekrarlamak için `mimari.md`
bölüm 6'ya bakın.

Yarışma yol haritası bir üst dizindeki `KrizKalkan-YolHaritasi.md` dosyasındadır.
