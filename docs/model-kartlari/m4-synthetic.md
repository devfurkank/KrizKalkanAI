# M4 — Sentetik görüntü tespiti (ikili + üç sınıflı) `v0.1`

| | |
|---|---|
| Model adı | `m4_synthetic` |
| Temel model | google/siglip2-base-patch16-512 · google/siglip2-base-patch16-224 |
| Sürüm | 0.1 |
| Oluşturulma | 2026-09-11T09:47:06+00:00 |
| Git commit | `2c36ae4` |
| Lisans | MIT (DeepReality) · Apache 2.0 (üç sınıflı ağırlık) |

## Amaç ve kapsam

Görüntüde yapay üretim izi arar ve bulduğunda türünü ayırır: tam sentetik üretim (SENTETİK_MEDYA) ile gerçek içerik üzerinde oynama (MANİPÜLE_MEDYA) farklı sınıflardır ve farklı müdahale tetikler. Modül olasılıksal çıkarım üretir; C2PA imzası varsa karar oradan gelir, bu detektörler onu geçersiz kılamaz.

## Eğitim verisi

- İkili detektör: prithivMLmods/OpenDeepfake-Preview · 8 epok ince ayar (DeepReality, MIT)
- Üç sınıflı detektör: prithivMLmods/AI-vs-Deepfake-vs-Real-Siglip2 (Apache 2.0, harici hazır ağırlık)

## Eğitim yordamı

Ağırlıklar DeepReality projesinden alındı; bu depoda eğitim yapılmadı. Görsel kule ve sınıflandırma başlığı ayrıştırılıp int8 ONNX'e aktarıldı; metin kulesi taşınmadı (375,8M → 93,7M parametre). İki detektör ayrı korpuslarda eğitildiği için hemfikirlikleri bağımsız doğrulama, çelişkileri ise çekinme sebebidir.

### Hiperparametreler

| Parametre | Değer |
|---|---|
| ikili_giris | 512×512 |
| ucul_giris | 224×224 |
| katman | 12 |
| gizli_boyut | 768 |
| niceleme | int8 dinamik, kanal başına |

**Bölünme stratejisi:** Kaynak projelerin kendi tutulmuş test bölünmeleri

## Ölçümler

| Metrik | Değer | Değerlendirme kümesi | n | Not |
|---|---|---|---|---|
| alan_ici_auc | 1 | prithivMLmods/OpenDeepfake-Preview (tutulmuş test) | 3000 | DeepReality tarafından fp32 ile ölçüldü — bu deponun ölçümü DEĞİLDİR |
| alan_ici_f1 | 0.9997 | prithivMLmods/OpenDeepfake-Preview (tutulmuş test) | 3000 | DeepReality tarafından fp32 ile ölçüldü — bu deponun ölçümü DEĞİLDİR |
| capraz_auc | 0.7818 | ComplexDataLab/OpenFake · core/test-00000-of-00013.parquet | 959 | Detektörlerin eğitiminde kullanılmayan korpus; çekinilenler hariç |
| capraz_eer | 0.2899 | ComplexDataLab/OpenFake · core/test-00000-of-00013.parquet | 959 | eşik 0.952 |
| capraz_yanlis_pozitif | 0.9914 | ComplexDataLab/OpenFake · core/test-00000-of-00013.parquet | 463 | karar eşiği 0.5 |
| afet_ozgulluk | 0.0029 | Wikimedia Commons Türkiye afet korpusu (tamamı gerçek) | 686 | karar eşiği 0.5 · kabul kapısının ölçütü · bu deponun kendi ölçümü |
| afet_yanlis_pozitif | 0.9971 | Wikimedia Commons Türkiye afet korpusu (tamamı gerçek) | 686 | karar eşiği 0.5 · bu deponun kendi ölçümü |

## Bilinen sınırlar

- Yalnızca görüntü. Video için kare çıkarımı (ffmpeg) gerekir ve kurulu değil; video içerikte modül çekinir.
- Hesaplamalı fotoğrafçılık yanlış pozitifi: çok kareli birleştirme ve gürültü bastırma uygulayan telefon kameralarının düşük gürültülü dokusu, üretim imzasına benziyor. DeepReality'de doğrudan gözlendi.
- Aşırı sıkıştırılmış ve düşük çözünürlüklü görüntülerde üretim izleri fiilen silinir; modül bu girdilerde skor üretmez.
- Afet alanında kullanılamaz durumda: gerçek Türk afet fotoğraflarının %99.71'i 0,50 eşiğinde 'üretilmiş' çıkıyor (n=686). Kabul kapısı bu yüzden kapalıdır ve modül kural yolunda çalışır.
- Skor dağılımı dar bir banda sıkışıyor; model sıralıyor ama mutlak eşik taşımıyor. AUC'ye bakarak devreye almak hatalı olur — eşik taraması: docs/metrikler/m4.md
- Genelleme açığı ölçüldü: alan içi AUC 1,0000 (kaynak projenin ölçümü) → çapraz veri kümesinde 0.7818. Düşüş beklenendir ve raporun ≥ 0,72 hedefini karşılar; kullanılabilirliği belirleyen ise AUC değil, alan içindeki çalışma noktasıdır.
- Dönüşüm dayanıklılığı: skorlar dönüşümler altında kaymıyor, ancak `jpeg_q35` dönüşümü çekinme oranını 0.0125 → 0.2750 seviyesine çıkarıyor: ağır sıkıştırmada modül karar vermeyi reddediyor. Ayrıntı: docs/metrikler/m4.md

## Etik değerlendirme

- Skor bir suçlama değildir. Sentetik medya tespiti tek başına içerik kaldırma gerekçesi sayılmaz; sistemin böyle bir yetkisi zaten yoktur.
- Çekinme oranı ölçülür ve raporlanır: modelin neyi bilmediği, ne bildiği kadar önemlidir.

## Kullanılmaması gereken durumlar

- Kimlik tespiti veya kişi eşleştirme.
- Adli delil üretimi — çıktı karar destek sinyalidir.
- Video ve ses içeriği.

---

*Bu kart `scripts/eval/run_all.py` tarafından üretilmiştir; elle düzenlenmez.*
