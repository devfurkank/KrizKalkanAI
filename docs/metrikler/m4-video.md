# M4 video — ölçüm raporu

*`scripts/eval/m4_video.py` tarafından üretildi · 2026-09-19 19:24 UTC · tohum 13. Elle düzenlenmez.*

> **Bu rapordaki sayıların hiçbiri genelleme ölçüsü değildir.** Ölçüm kümesi modelin **eğitim/doğrulama verisidir**; hangi videonun hangi bölmede olduğu depoda kayıtlı değil. Model bu videoların hepsini ya da çoğunu eğitimde gördü. Aşağıdaki başarım, modelin görmediği bir videoda beklenecek başarım olarak **sunulamaz**.

Karar eşiği: P(üretilmiş) > 0,55 (dağıtım yapılandırmasındaki P(gerçek) ≥ 0,45 eşiğinin karşılığı).

## 1. Çalışırlık — kurulum özgün modeli doğru yeniden üretiyor mu?

Kabul kapısı bu bölümdeki **özgüllüğü** okur. Kapının sorduğu soru dardır: ONNX aktarımı ve depodaki kare seçimi doğru mu? Hatalı bir ön işleme (BGR/RGB karışması, çift normalizasyon, farklı kare seçimi) gerçek videoları kendi eğitim kümesinde bile "üretilmiş" gösterir ve bu kapıdan geçemez.

| Metrik | Değer | n |
|---|---|---|
| Özgüllük (gerçek → gerçek) | %100,0 | 100 |
| Duyarlılık (üretilmiş → üretilmiş) | %100,0 | 100 |
| AUC | 1,0000 | 200 |
| Çekinme | 0 | 200 |
| Özgüllük · doğal dikey gerçek videolar | %100,0 | 8 |

## 2. Dayanıklılık — sosyal medya dönüşümleri

Aynı videolar dönüştürülüp yeniden ölçüldü. İçerik modelin eğitimde gördüğü içeriktir; bu tablo genelleme değil **kırılganlık** gösterir. Kontrol satırı yalnızca yeniden kodlamanın etkisini ayırır.

| Dönüşüm | Açıklama | Gerçek → gerçek | Üretilmiş → üretilmiş |
|---|---|---|---|
| `yeniden_kodlama` | kontrol · aynı kareler mp4v ile yeniden yazılır | %100,0 (n=25) | %100,0 (n=25) |
| `dikey_kirpma` | yatay video ortadan 9:16 kırpılır (Reels/TikTok) | %76,0 (n=25) | — |
| `dikey_bant` | yatay video siyah bantla 9:16 çerçeveye konur | %84,0 (n=25) | — |
| `sikistirma` | 360p + JPEG kalite 35 (platform sıkıştırması) | %100,0 (n=25) | %100,0 (n=25) |
| `yatay_kirpma` | dikey video ortadan 16:9 kırpılır | — | %48,0 (n=25) |

**Okuma.** Eğitim kümesindeki *doğal* dikey gerçek videolarda model doğru çalışıyor (bölüm 1). Kırılganlık dikeyliğin kendisinden değil, yatay bir videonun **sonradan** yeniden çerçevelenmesinden geliyor. Model kareleri en-boy oranını korumadan 224×224'e ezer; kırpma ve bant, karelerin geometrisini eğitimde görülmemiş biçimde değiştirir. Sosyal medyada gerçek afet görüntüleri bu dönüşümle sık dolaşır: bu satırlar, gerçek bir videoya "üretilmiş" denmesinin en olası yolunu gösterir.

## Gecikme

Video başına uçtan uca (kare seçimi + ONNX çıkarımı, CPU): medyan 687 ms · p95 1321 ms. Hareket analizi videonun her karesini çözdüğü için süre video uzunluğuyla doğrusal artar.

## Eksik ölçüm — genelleme

Modelin görmediği videolarda ölçüm **yapılmadı**, çünkü böyle bir küme henüz yok. Yapılması gereken:

1. Eğitim/doğrulama ayrımının dosya listesini depoya eklemek (`scripts/data/build_video_afet.py --dogrulama-listesi`). Bu, eğitimde kullanılmamış videolarda ilk dürüst sayıyı verir.
2. Eğitim kümesiyle hiç örtüşmeyen bir test kümesi kurmak: farklı kaynaktan gerçek afet videoları (ör. Wikimedia Commons, kamu kurumu arşivleri) ve kümede olmayan üreticilerle üretilmiş afet videoları. M4 görüntü modelindeki gibi **üretici bazında** ayrım yapılmalı: görülmemiş üreticide duyarlılık, literatürdeki asıl açıktır.
