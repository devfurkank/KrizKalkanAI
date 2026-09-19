# M4 — Sentetik video tespiti `v1.0`

| | |
|---|---|
| Model adı | `m4_video` |
| Temel model | ResNet50 (ImageNet) kare kodlayıcı + 2×BiLSTM + çok başlı dikkat |
| Sürüm | 1.0 |
| Oluşturulma | 2026-09-19T11:38:15+00:00 |
| Git commit | `—` |
| Lisans | Proje içi kullanım |

## Amaç ve kapsam

Afet videolarında yapay zekâ ile üretilmiş içerik izi arar. Çıktı olasılıksaldır; C2PA imzası ya da üretici üstverisi varsa karar oradan gelir.

## Eğitim verisi

- Afet video kümesi · 729 gerçek afet videosu (çığ, deprem, kasırga, heyelan, yanardağ, sel, orman yangını) + 628 üretilmiş afet videosu
- Eğitim/doğrulama ayrımının dosya listesi depoda kayıtlı değil; hangi videonun hangi bölmede olduğu BİLİNMİYOR.

## Eğitim yordamı

Keras 2.10 (TensorFlow) ile eğitildi. Kayıp: BinaryFocalCrossentropy (α=0,25, γ=2). ResNet50'nin yalnızca conv5 bloğu eğitilebilir. Ayrıntılı eğitim kodu depoda değil.

### Hiperparametreler

| Parametre | Değer |
|---|---|
| giris | 32 kare × 224×224 |
| kare_secimi | 16 eşit aralık + 16 en hareketli (Farneback, 112×112) |
| parametre | 27.8M |
| esik_p_gercek | 0.45 |
| niceleme | yok — fp32 |
| onnx_aktarim_farki | 6.0e-08 |

**Bölünme stratejisi:** BİLİNMİYOR. Eğitimde bir eğitim/doğrulama ayrımı kullanıldı ancak ayrımın dosya listesi depoda kayıtlı değil. Bu kümede ölçülen her sayı alan içidir ve modelin gördüğü videoları içerir.

## Ölçümler

| Metrik | Değer | Değerlendirme kümesi | n | Not |
|---|---|---|---|---|
| alan_ici_ozgulluk | 1 | Afet video kümesi (modelin eğitim/doğrulama verisi · ayrım bilinmiyor) | 100 | kabul kapısı · çalışırlık kontrolü · eşik P(üretilmiş) > 0.55 · eğitim/doğrulama verisi · genelleme ölçüsü DEĞİL |
| alan_ici_duyarlilik | 1 | Afet video kümesi (modelin eğitim/doğrulama verisi · ayrım bilinmiyor) | 100 | eğitim/doğrulama verisi · genelleme ölçüsü DEĞİL |
| alan_ici_auc | 1 | Afet video kümesi (modelin eğitim/doğrulama verisi · ayrım bilinmiyor) | 200 | eğitim/doğrulama verisi · genelleme ölçüsü DEĞİL |
| alan_ici_ozgulluk_dogal_dikey | 1 | Afet video kümesi (modelin eğitim/doğrulama verisi · ayrım bilinmiyor) | 8 | eğitim/doğrulama verisi · genelleme ölçüsü DEĞİL |
| dayaniklilik_ozgulluk_dikey_kirpma | 0.76 | Afet video kümesi (modelin eğitim/doğrulama verisi · ayrım bilinmiyor) · yatay video ortadan 9:16 kırpılır (Reels/TikTok) | 25 | kırılganlık ölçüsü · içerik eğitimde görüldü |
| dayaniklilik_ozgulluk_dikey_bant | 0.84 | Afet video kümesi (modelin eğitim/doğrulama verisi · ayrım bilinmiyor) · yatay video siyah bantla 9:16 çerçeveye konur | 25 | kırılganlık ölçüsü · içerik eğitimde görüldü |
| dayaniklilik_ozgulluk_sikistirma | 1 | Afet video kümesi (modelin eğitim/doğrulama verisi · ayrım bilinmiyor) · 360p + JPEG kalite 35 (platform sıkıştırması) | 25 | kırılganlık ölçüsü · içerik eğitimde görüldü |
| dayaniklilik_duyarlilik_yatay_kirpma | 0.48 | Afet video kümesi (modelin eğitim/doğrulama verisi · ayrım bilinmiyor) · dikey video ortadan 16:9 kırpılır | 25 | kırılganlık ölçüsü · içerik eğitimde görüldü |
| gecikme_medyan_ms | 686.6 | Afet video kümesi (modelin eğitim/doğrulama verisi · ayrım bilinmiyor) | 200 | CPU · uçtan uca |

## Bilinen sınırlar

- Genelleme ÖLÇÜLMEDİ. Tüm ölçümler modelin eğitim/doğrulama verisinde yapıldı; görülmemiş videoda başarım bilinmiyor.
- Yatay gerçek bir video sonradan dikeye kırpıldığında ya da bantlandığında "üretilmiş" sanılma oranı belirgin biçimde artıyor (özgüllük %76,0 kırpma · %84,0 bant). Sosyal medyada yaygın bir dönüşümdür.
- Kareler en-boy oranı korunmadan 224×224'e ezilir; bu, eğitimdeki ön işlemedir ve değiştirilemez (model yeniden eğitilmeden).
- Ses kanalı incelenmez; model yalnızca görüntüye bakar.
- 180 sn'den uzun videolarda çekinilir (hareket analizi her kareyi çözer).
- Eğitim kümesindeki üretici araçları bilinmiyor; kümede olmayan bir üreticinin videolarında duyarlılık bilinmiyor.

## Kullanılmaması gereken durumlar

- Tek başına kanıt olarak kullanılamaz; çıktı olasılıksaldır ve füzyonda diğer sinyallerle birlikte değerlendirilir.
- Yüz değiştirme (face-swap) deepfake'leri için eğitilmedi; afet sahnesi üretimine yöneliktir.

---

*Bu kart `scripts/eval/run_all.py` tarafından üretilmiştir; elle düzenlenmez.*
