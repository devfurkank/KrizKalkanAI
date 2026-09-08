# M1 — Köken Motoru · Dayanıklılık Değerlendirmesi

*`scripts/eval/m1_robustness.py` tarafından üretildi · 08.09.2026 16:33 UTC · commit `ab2b653`*

| | |
|---|---|
| İndeks | 456 kayıt |
| Sorgu örneklemi | 80 görüntü |
| Eşleşme eşiği | Hamming ≤ 10 bit (64 bitte) |
| Karma | dHash + pHash, ikisinin iyisi |

## Dönüşüm altında Recall@1

Her satır, aynı görüntünün o dönüşümden geçirilip indekste aranmasıdır.
Doğru kayıt ilk sırada VE eşik içinde bulunduysa başarılı sayılır.

| Dönüşüm | Recall@1 | Ortalama Hamming mesafesi |
|---|---|---|
| temiz (kontrol) | 1.0000 | 0.00 |
| yeniden kodlama (JPEG q30) | 1.0000 | 0.04 |
| aşırı sıkıştırma (q10) | 1.0000 | 0.21 |
| ölçekleme (480p) | 1.0000 | 0.00 |
| kırpma %20 | 1.0000 | 0.14 |
| letterbox bant | 0.6125 | 9.86 |
| logo bindirme | 1.0000 | 1.60 |
| sosyal medya çerçevesi | 0.5000 | 10.80 |
| gürültü + renk kayması | 1.0000 | 0.07 |
| parlaklık %130 | 1.0000 | 1.35 |
| hafif bulanıklık | 1.0000 | 0.00 |
| ayna çevirme | 0.0125 | 17.96 |
| döndürme 5° | 0.5750 | 9.85 |

> Temiz kontrol: **1.0000** · rapor 3.2 hedefi ≥ 0,90

## Yanlış eşleşme oranı

İndekste bulunmayan görüntülerle sorgulandığında sistem kaç kez
"eşleşti" diyor? Bu sayı Recall'dan kritiktir: yanlış bir köken
eşleşmesi kullanıcıya "bu görüntü başka bir olaya ait" demek anlamına
gelir ve sistemin en görünür hatasıdır.

| | |
|---|---|
| Sorgu | 60 indeks dışı görüntü |
| Yanlış eşleşme oranı | **0.0167** |
| Ortalama en yakın mesafe | 18.10 bit |

> Rapor 3.2 hedefi < %1

## Eşik ödünleşimi

Eşleşme eşiği bir sayı değil bir karardır ve iki yönde de maliyetlidir:
gevşek eşik geometrik dönüşümlere dayanır ama alakasız görüntüleri
eşleştirir. Aşağıdaki tarama, ağır (geometrik) dönüşümlerdeki Recall@1 ile
yanlış eşleşme oranını aynı eksende gösterir.

| Hamming eşiği | Ağır dönüşüm Recall@1 | Yanlış eşleşme oranı |
|---|---|---|
| 4 | 0.2583 | 0.0167 |
| 6 | 0.3167 | 0.0167 |
| 8 | 0.5083 | 0.0167 |
| 10 | 0.6875 | 0.0167 |
| 12 | 0.8917 | 0.0167 |
| 14 | 0.9708 | 0.0333 |
| 16 | 0.9917 | 0.1833 |

Yürürlükteki eşik: **10 bit** (`provenance/hashing.py · MATCH_MAX_DISTANCE`).

## Yorum

Ayna çevirme algısal karmayı yapısal olarak kırar: dHash komşu piksel
farklarına, pHash DCT katsayılarına bakar ve çevirme her ikisinin de
uzamsal düzenini bozar. Bu bir kusur değil, karma tabanlı aramanın
bilinen sınırıdır ve görsel-dil gömmesi tabanlı ikinci bir arama
katmanıyla kapatılır (rapor 3.1 · M1 · gömme indeksi).
