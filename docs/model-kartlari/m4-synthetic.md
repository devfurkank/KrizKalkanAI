# M4 — Sentetik görüntü tespiti (temiz lisans) `v0.2-temiz`

| | |
|---|---|
| Model adı | `m4_synthetic` |
| Temel model | google/siglip2-base-patch16-224 |
| Sürüm | 0.2-temiz |
| Oluşturulma | 2026-09-17T00:59:05+00:00 |
| Git commit | `12f4c29` |
| Lisans | CC BY-NC-SA 4.0 (GenImage) · CC BY-SA 4.0 (Wikimedia afet korpusu) · Apache-2.0 + OpenRAIL++-M (üretilmiş afet korpusu) — TİCARİ KULLANIMA KAPALI |

## Amaç ve kapsam

Görüntüde yapay üretim izi arar. Gövde donuk, yalnızca LayerNorm ve sınıflandırma başlığı eğitildi; önceki sürümün doygunluk sorunu bu kısıtla giderildi. Çıktı olasılıksaldır; C2PA imzası varsa karar oradan gelir.

## Eğitim verisi

- jhutter2/281_Genimage (CC BY-NC-SA 4.0 — ayna 'MIT' diyor, özgün GenImage lisansı NC-SA) · ADM, SD 1.5, wukong + ImageNet gerçekleri
- Üretilmiş afet korpusu · 1700 görsel pozitif sınıfta (SANA 1.6B Apache-2.0 · SDXL OpenRAIL++-M · hizalı VAE/img2img)
- Wikimedia Commons Türkiye afet korpusu · 656 görüntü negatif sınıfta (130 tutulan olay eğitime girmedi)

## Eğitim yordamı

Donuk SigLIP2 gövdesi + LayerNorm ayarı · 6 epok · OneCycle lr=0.0003 · her iki sınıfa sosyal medya artırması (JPEG yeniden kodlama 35-95, ölçekleme 0,35-1,0, kırpma, ayna). Artırma bilinçlidir: sıkıştırma izinin sınıf ipucu olarak öğrenilmesini engeller.

### Hiperparametreler

| Parametre | Değer |
|---|---|
| giris | 224x224 |
| yigin | 64 |
| epok | 6 |
| ogrenme_orani | 0.0003 |
| egitilebilir_parametre | 0.24M |
| niceleme | yok — int8 kararı bozuyor, fp32 dağıtılıyor |
| kalibrasyon_sicakligi | 1.05 |

**Bölünme stratejisi:** ÇİFT ayrım: (1) afet fotoğrafları OLAY bazında — tutulan olaylar eğitime girmedi, özgüllük yalnızca orada ölçüldü; (2) üretilmiş afet görselleri ÜRETİCİ bazında — PixArt-Σ ve z_image eğitime girmedi, duyarlılık yalnızca orada ölçüldü. OpenFake core/test de eğitime girmedi.

## Ölçümler

| Metrik | Değer | Değerlendirme kümesi | n | Not |
|---|---|---|---|---|
| dogrulama_auc | 0.9679 | kendi doğrulama bölmesi | 848 | — |
| capraz_auc | 0.866 | ComplexDataLab/OpenFake · core/test-00000-of-00013.parquet | 968 | Detektörlerin eğitiminde kullanılmayan korpus; çekinilenler hariç |
| capraz_eer | 0.2066 | ComplexDataLab/OpenFake · core/test-00000-of-00013.parquet | 968 | eşik 0.254 |
| capraz_yanlis_pozitif | 0.0341 | ComplexDataLab/OpenFake · core/test-00000-of-00013.parquet | 469 | karar eşiği 0.7 |
| afet_ozgulluk | 0.9615 | Wikimedia Commons Türkiye afet korpusu (tamamı gerçek) | 130 | karar eşiği 0.7 · kabul kapısının ölçütü · bu deponun kendi ölçümü |
| afet_yanlis_pozitif | 0.0385 | Wikimedia Commons Türkiye afet korpusu (tamamı gerçek) | 130 | karar eşiği 0.7 · bu deponun kendi ölçümü |
| afet_duyarlilik | 0.9193 | Üretilmiş afet görselleri korpusu (tamamı sahte) | 285 | karar eşiği 0.7 · kabul kapısına DAHİL DEĞİL |

## Bilinen sınırlar

- Yalnızca görüntü. Video için kare çıkarımı gerekir ve kurulu değil.
- Eğitim üreticileri 2023 kuşağı (ADM, SD 1.5, wukong); 2026 üreticilerinde başarım çapraz veri kümesi ölçümünden okunmalıdır.
- Üstveri ve C2PA sinyalleri belgeseldir ve bu modelden önce gelir.
- Afet alanında kullanılamaz durumda: gerçek Türk afet fotoğraflarının %3.85'i 0,50 eşiğinde 'üretilmiş' çıkıyor (n=130). Kabul kapısı bu yüzden kapalıdır ve modül kural yolunda çalışır.
- ALAN KÖR NOKTASI — üretilmiş afet görsellerinin yalnızca %91.9'i yakalanıyor (n=285, eşik 0,50). Model genel yapay görüntüde çalışıyor (çapraz AUC ölçüldü) ama KRİZ ALANINDA çalışmıyor. Muhtemel sebep: eğitimde afet korpusu negatif sınıfa kondu, pozitif sınıfta hiç afet içeriği yoktu; model 'afet sahnesi → gerçek' kısayolunu öğrenmiş olabilir. Kabul kapısı bu metriği OKUMAZ.
- Skor dağılımı dar bir banda sıkışıyor; model sıralıyor ama mutlak eşik taşımıyor. AUC'ye bakarak devreye almak hatalı olur — eşik taraması: docs/metrikler/m4.md
- Genelleme açığı ölçüldü: alan içi AUC 1,0000 (kaynak projenin ölçümü) → çapraz veri kümesinde 0.8660. Düşüş beklenendir ve raporun ≥ 0,72 hedefini karşılar; kullanılabilirliği belirleyen ise AUC değil, alan içindeki çalışma noktasıdır.
- Dönüşüm dayanıklılığı: skorlar dönüşümler altında kaymıyor, ancak `jpeg_q35` dönüşümü çekinme oranını 0.0000 → 0.2500 seviyesine çıkarıyor: ağır sıkıştırmada modül karar vermeyi reddediyor. Ayrıntı: docs/metrikler/m4.md

## Etik değerlendirme

- Skor bir suçlama değildir; tek başına içerik kaldırma gerekçesi sayılmaz.
- Afet alanı yanlış pozitifi kabul kapısının ölçütüdür: gerçek bir afet fotoğrafını işaretlemek, sentetik bir görüntüyü kaçırmaktan daha zararlıdır.

## Kullanılmaması gereken durumlar

- Kimlik tespiti
- Adli delil üretimi
- Video ve ses içeriği

---

*Bu kart `scripts/eval/run_all.py` tarafından üretilmiştir; elle düzenlenmez.*
