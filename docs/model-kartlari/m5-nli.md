# M5 — Türkçe Çıkarım Modeli (NLI-TR) `v0.1.0`

| | |
|---|---|
| Model adı | `m5_nli` |
| Temel model | FacebookAI/xlm-roberta-base |
| Sürüm | 0.1.0 |
| Oluşturulma | 2026-09-08T18:08:09+00:00 |
| Git commit | `51f6ad8` |
| Lisans | Model: MIT · Veri: SNLI türevi (araştırma) |

## Amaç ve kapsam

Kullanıcının iddiası ile havuzdaki kaydın AYNI iddia olup olmadığına karar verir. Geri getirme aday üretir, karar bu modelindir.

## Eğitim verisi

- SNLI-TR (NLI-TR) — 150,000 satır, sınıf dengeli altörnekleme

## Eğitim yordamı

XLM-R base üzerine 3 sınıflı dizi-çifti sınıflandırma başlığı; erken durdurma. Altın etiketi olmayan (-1) satırlar elendi.

### Hiperparametreler

| Parametre | Değer |
|---|---|
| epok | 2 |
| yigin | 32 |
| ogrenme_orani | 2e-05 |
| maks_uzunluk | 128 |
| ornek | 150000 |

**Bölünme stratejisi:** SNLI-TR'nin kendi eğitim/doğrulama bölünmesi

## Ölçümler

| Metrik | Değer | Değerlendirme kümesi | n | Not |
|---|---|---|---|---|
| dogruluk | 0.8181 | SNLI-TR doğrulama | 9842 | — |
| makro_f1 | 0.8178 | SNLI-TR doğrulama | 9842 | — |
| alan_ici_dogru_eslesme | 0.0714 | kriz iddiası → DMM kaydı | 28 | SNLI doğruluğu bu sayıyı TEMSİL ETMEZ |
| alan_ici_zararli_eslesme | 0.1786 | kriz iddiası → DMM kaydı | 28 | yanlış kayıt gösterilerek 'resmî kaynak seni yalanlıyor' denmesi |

## Bilinen sınırlar

- 🔴 MODEL DEVREDE DEĞİLDİR. Kriz alanında ölçüldü ve reddedildi: 28 sorguda 2 doğru, 5 ZARARLI eşleşme üretti. Aynı kümede sözlük yolu daha iyi sonuç veriyor.
- Sebep görev uyumsuzluğu, eğitim başarısızlığı değil: SNLI'ın "öncül varsayımı ima ediyor mu?" sorusu, "bu iki metin aynı iddiayı mı öne sürüyor?" sorusu değildir. Öncül/varsayım yönü ters çevrilerek de denendi; iki yönde de başarısız.
- SNLI-TR makine çevirisiyle üretilmiştir; kısa, genel cümlelerden oluşur. Kriz iddiaları ve DMM kayıtları uzun ve kurumsal dildedir.
- Gerçek bir iddia eşleştirme kümesiyle eğitilmiş model geldiğinde karar ölçümle yeniden ele alınmalıdır; kod yolu (`engine._cikarim_yolu`) ve testleri korunmaktadır.

## Etik değerlendirme

- Yanlış 'aynı iddia' kararı, kullanıcıya resmî kaynağın onu yalanladığını söylemek demektir; eşik (0,75) bu yüzden kesinlik lehine ayarlıdır.

## Kullanılmaması gereken durumlar

- Doğruluk hükmü vermek
- Havuzda karşılığı olmayan iddiaları yanlış saymak

---

*Bu kart `scripts/eval/run_all.py` tarafından üretilmiştir; elle düzenlenmez.*
