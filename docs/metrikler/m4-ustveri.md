# M4 — Üretici üstverisi

*Üretim: 2026-09-12 08:48 UTC · commit `96194aa`*

Üretici araçlar dosyaya kendi parametrelerini yazar: Stable Diffusion ve
ComfyUI PNG `tEXt` bloklarına `parameters`, `prompt`, `workflow` alanlarını
gömer. Bu bir tahmin değil **beyandır** — bulunduğunda kullanıcıya gömülü
istemin kendisi gösterilebilir.

## 1. Yakalama ve kesinlik

Küme: `ComplexDataLab/OpenFake` · `core/test-00000-of-00013.parquet`

| Metrik | Değer |
|---|---|
| Üretilmiş · üretici imzası bulunan | 91 / 1011 (**9.0%** yakalama) |
| Gerçek · üretici imzası bulunan | 0 / 989 (**0.0%** yanlış pozitif) |
| **Kesinlik** | **1.0000** |
| Gerçek · kamera telemetrisi bulunan | 41 / 989 (4.1%) |
| Üretilmiş · kamera telemetrisi bulunan | 0 / 1011 (0.0%) |
| Çekinme (üstveri yok) | 93.4% |

> Yakalama düşüktür ve bu kusur değildir. Sinyalin değeri kesinliğinde:
> imza bulunduğunda yanılma payı yok denecek kadar azdır. Sinir ağı
> detektörü (`docs/metrikler/m4.md`) ters ödünleşimde durur ve alan
> içinde kullanılamaz durumdadır.

### 1.1. Üretici ailesi başına

Üstveri bırakma alışkanlığı araca göre değişiyor. Tablo, sinyalin hangi
üreticilerde çalıştığını ve hangilerinde sessiz kaldığını gösterir.

| Üretici | İmza bulunan | n | Oran |
|---|---|---|---|
| `ernie-image` | 7 | 9 | 77.8% |
| `z-image-turbo` | 53 | 280 | 18.9% |
| `illustrious` | 24 | 135 | 17.8% |
| `ernie-image-turbo` | 2 | 15 | 13.3% |
| `flux.2-klein-9b` | 4 | 204 | 2.0% |
| `gpt-image-1.5` | 1 | 118 | 0.8% |
| `imagenet` | 0 | 648 | 0.0% |
| `docci` | 0 | 341 | 0.0% |
| `midjourney-7` | 0 | 74 | 0.0% |
| `veo-3` | 0 | 48 | 0.0% |
| `wan-video-2.5` | 0 | 27 | 0.0% |
| `recraft-v3` | 0 | 19 | 0.0% |
| `sora-2` | 0 | 15 | 0.0% |
| `gpt-image-2` | 0 | 10 | 0.0% |
| `seedream-v5.0` | 0 | 9 | 0.0% |
| `halfmoon-4-4-25` | 0 | 8 | 0.0% |
| `ideogram-2.0` | 0 | 7 | 0.0% |
| `nano-banana-pro` | 0 | 7 | 0.0% |
| `recraft-v2` | 0 | 7 | 0.0% |
| `lumina-17-2-25` | 0 | 7 | 0.0% |
| `frames-23-1-25` | 0 | 6 | 0.0% |
| `aurora-20-1-25` | 0 | 6 | 0.0% |

### 1.2. Bulunan kanıt örnekleri

Kanıt panelinde kullanıcıya gösterilecek olan metin budur:

- `z-image-turbo` — parameters → Tuarichit art style. Cinematic overhead shot: A young woman stands defiantly at the center of an abandoned con
- `illustrious` — prompt → {"278": {"inputs": {"action": "append", "tidy_tags": "yes", "text_a": "embedding:IllusP0s, axolotl costume, ri
- `z-image-turbo` — prompt → {"6": {"inputs": {"text": "stylized image\n[SUBJECT & COMPOSITION]\nThe image presents a surreal, ultra-detail
- `z-image-turbo` — prompt → {"3": {"inputs": {"seed": 466322965998853, "steps": 12, "cfg": 1.0, "sampler_name": "euler_ancestral", "schedu
- `z-image-turbo` — parameters → macro photography of a human blue eye, extreme detail, iris texture, reflection of a window in the pupil, skin

## 2. Afet alanı — yanlış pozitif

Wikimedia Commons Türkiye afet korpusu. **Tamamı gerçektir.**

| Durum | Adet | Oran |
|---|---|---|
| Üretici imzası (yanlış pozitif) | 0 | **0.00%** |
| Kamera telemetrisi | 0 | 0.0% |
| Üstveri yok (çekinme) | 786 | 100.0% |
| Toplam | 786 | |

> Çekinme oranının yüksekliği beklenen sonuçtur: Wikimedia küçük boy
> görüntüleri yeniden kodlarken üstveriyi siler, sosyal platformlar da
> aynısını yapar. Sinyal bu içerikte **susuyor**, yanlış konuşmuyor.

## 3. Bilinen sınırlar

- **Üstveri silinebilir ve siliniyor.** Sosyal platformların çoğu yüklemede
  siler; sahadaki yakalama bu tablodakinden düşük olacaktır.
- **Üstveri elle yazılabilir.** Ama tehdit modeli asimetriktir: kimse kendi
  gerçek fotoğrafına "bunu Stable Diffusion üretti" yazmaz. Silme sessizliğe
  yol açar, yanlış suçlamaya değil.
- **Üretici kapsamı eksiktir.** Midjourney, GPT-Image ve Sora örneklerinde
  imza bulunamadı; bu araçlar üstveri bırakmıyor ya da platform siliyor.
- Sinyal yalnızca gerçek dosyalarda çalışır; demo parmak izlerinde değil.

---

*`scripts/eval/m4_ustveri.py` tarafından üretildi; elle düzenlenmez.*
