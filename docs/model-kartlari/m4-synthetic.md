# M4 — Sentetik görüntü tespiti (temiz lisans) `v0.2-temiz`

| | |
|---|---|
| Model adı | `m4_synthetic` |
| Temel model | google/siglip2-base-patch16-224 |
| Sürüm | 0.2-temiz |
| Oluşturulma | 2026-09-14T14:32:24+00:00 |
| Git commit | `547d1c4` |
| Lisans | MIT (GenImage) · CC BY-SA 4.0 (Wikimedia afet korpusu) |

## Amaç ve kapsam

Görüntüde yapay üretim izi arar. Gövde donuk, yalnızca LayerNorm ve sınıflandırma başlığı eğitildi; önceki sürümün doygunluk sorunu bu kısıtla giderildi. Çıktı olasılıksaldır; C2PA imzası varsa karar oradan gelir.

## Eğitim verisi

- jhutter2/281_Genimage (MIT) · ADM, SD 1.5, wukong + ImageNet gerçekleri
- Wikimedia Commons Türkiye afet korpusu · 628 görüntü negatif sınıfta

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
| niceleme | int8 dinamik, kanal başına |
| kalibrasyon_sicakligi | 5.0 |

**Bölünme stratejisi:** Üretici bazlı ayrım; değerlendirme kümesi (OpenFake core/test) eğitime hiç girmedi

## Ölçümler

| Metrik | Değer | Değerlendirme kümesi | n | Not |
|---|---|---|---|---|
| dogrulama_auc | 0.9888 | kendi doğrulama bölmesi | 737 | — |
| capraz_auc | 0.785 | ComplexDataLab/OpenFake · core/test-00000-of-00013.parquet | 773 | Detektörlerin eğitiminde kullanılmayan korpus; çekinilenler hariç |
| capraz_eer | 0.2781 | ComplexDataLab/OpenFake · core/test-00000-of-00013.parquet | 773 | eşik 0.203 |
| capraz_yanlis_pozitif | 0.0989 | ComplexDataLab/OpenFake · core/test-00000-of-00013.parquet | 374 | karar eşiği 0.5 |
| afet_ozgulluk | 0.9885 | Wikimedia Commons Türkiye afet korpusu (tamamı gerçek) | 784 | karar eşiği 0.5 · kabul kapısının ölçütü · bu deponun kendi ölçümü |
| afet_yanlis_pozitif | 0.0115 | Wikimedia Commons Türkiye afet korpusu (tamamı gerçek) | 784 | karar eşiği 0.5 · bu deponun kendi ölçümü |

## Bilinen sınırlar

- Yalnızca görüntü. Video için kare çıkarımı gerekir ve kurulu değil.
- Eğitim üreticileri 2023 kuşağı (ADM, SD 1.5, wukong); 2026 üreticilerinde başarım çapraz veri kümesi ölçümünden okunmalıdır.
- Üstveri ve C2PA sinyalleri belgeseldir ve bu modelden önce gelir.
- Afet alanında kullanılamaz durumda: gerçek Türk afet fotoğraflarının %1.15'i 0,50 eşiğinde 'üretilmiş' çıkıyor (n=784). Kabul kapısı bu yüzden kapalıdır ve modül kural yolunda çalışır.
- Skor dağılımı dar bir banda sıkışıyor; model sıralıyor ama mutlak eşik taşımıyor. AUC'ye bakarak devreye almak hatalı olur — eşik taraması: docs/metrikler/m4.md
- Genelleme açığı ölçüldü: alan içi AUC 1,0000 (kaynak projenin ölçümü) → çapraz veri kümesinde 0.7850. Düşüş beklenendir ve raporun ≥ 0,72 hedefini karşılar; kullanılabilirliği belirleyen ise AUC değil, alan içindeki çalışma noktasıdır.
- Dönüşüm dayanıklılığı: skorlar dönüşümler altında kaymıyor, ancak `jpeg_q35` dönüşümü çekinme oranını 0.0000 → 0.2200 seviyesine çıkarıyor: ağır sıkıştırmada modül karar vermeyi reddediyor. Ayrıntı: docs/metrikler/m4.md

## Etik değerlendirme

- Skor bir suçlama değildir; tek başına içerik kaldırma gerekçesi sayılmaz.
- Afet alanı yanlış pozitifi kabul kapısının ölçütüdür: gerçek bir afet fotoğrafını işaretlemek, sentetik bir görüntüyü kaçırmaktan daha zararlıdır.

## Kullanılmaması gereken durumlar

- Kimlik tespiti
- Adli delil üretimi
- Video ve ses içeriği

---

*Bu kart `scripts/eval/run_all.py` tarafından üretilmiştir; elle düzenlenmez.*
