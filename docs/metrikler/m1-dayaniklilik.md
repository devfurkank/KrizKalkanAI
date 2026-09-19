# M1 — Köken Motoru · Dayanıklılık Değerlendirmesi

*`scripts/eval/m1_robustness.py` tarafından üretildi · 12.09.2026 11:21 UTC · commit `eab1f09`*

| | |
|---|---|
| İndeks | 1,758 kayıt |
| Sorgu örneklemi | 200 görüntü |
| Eşleşme eşiği | Hamming ≤ 10 bit (64 bitte) |
| Karma | dHash + pHash, ikisinin iyisi |

## Dönüşüm altında Recall@1

Her satır, aynı görüntünün o dönüşümden geçirilip indekste aranmasıdır.
Doğru kayıt ilk sırada VE eşik içinde bulunduysa başarılı sayılır.

| Dönüşüm | Recall@1 | Ortalama Hamming mesafesi |
|---|---|---|
| temiz (kontrol) | 0.9950 | 0.00 |
| yeniden kodlama (JPEG q30) | 0.9950 | 0.06 |
| aşırı sıkıştırma (q10) | 0.9950 | 0.35 |
| ölçekleme (480p) | 0.9950 | 0.00 |
| kırpma %20 | 1.0000 | 0.12 |
| letterbox bant | 0.6150 | 9.63 |
| logo bindirme | 0.9950 | 1.73 |
| sosyal medya çerçevesi | 0.4750 | 10.70 |
| gürültü + renk kayması | 1.0000 | 0.09 |
| parlaklık %130 | 0.9900 | 1.44 |
| hafif bulanıklık | 0.9950 | 0.00 |
| ayna çevirme | 0.0150 | 16.28 |
| döndürme 5° | 0.6050 | 9.82 |

> Temiz kontrol: **0.9950** · rapor 3.2 hedefi ≥ 0,90

## Eşleşme hataları — zararına göre ayrılmış

Ham "eşleşti/eşleşmedi" sayımı bu korpusta yanıltıcıdır: Wikimedia Commons
aynı çekimden ardışık kareler barındırır (IDF 157 ↔ IDF 158, Arslantepe
16 ↔ 17). Böyle bir eşleşme hata DEĞİLDİR — sistem "bu görüntü 2023
depremlerine ait, şu tarihte yayımlandı" der ve bu doğrudur.

Zararlı olan, içeriğin BAŞKA BİR OLAYA bağlanmasıdır: kullanıcıya
"görüntünüz farklı bir olaya ait" demek, yanlış olduğunda sistemin en
görünür hatasıdır. İki oran bu yüzden ayrı raporlanır.

| | |
|---|---|
| Sorgu | 200 indeks dışı görüntü |
| **Olay dışı eşleşme (zararlı)** | **0.0100** |
| Yakın kopya eşleşmesi (doğru davranış) | 0.0700 |
| Ham eşleşme oranı | 0.0800 |
| Ortalama en yakın mesafe | 15.49 bit |

> Rapor 3.2 hedefi < %1 · ölçülen **0.0100** (2 / 200 görüntü). Örneklem küçük olduğu için çözünürlük 0.0050; sayı bu hassasiyetle okunmalıdır.

## Eşik ödünleşimi

Eşleşme eşiği bir sayı değil bir karardır ve iki yönde de maliyetlidir:
gevşek eşik geometrik dönüşümlere dayanır ama alakasız görüntüleri
eşleştirir. Aşağıdaki tarama, ağır (geometrik) dönüşümlerdeki Recall@1 ile
olay dışı eşleşme oranını aynı eksende gösterir.

| Hamming eşiği | Ağır dönüşüm Recall@1 | Olay dışı eşleşme |
|---|---|---|
| 4 | 0.2583 | 0.0000 |
| 6 | 0.3125 | 0.0000 |
| 8 | 0.4167 | 0.0000 |
| 10 | 0.6458 | 0.0100 |
| 12 | 0.8500 | 0.0250 |
| 14 | 0.9417 | 0.0700 |
| 16 | 0.9708 | 0.1900 |

Yürürlükteki eşik: **10 bit** (`provenance/hashing.py · MATCH_MAX_DISTANCE`).

## Yorum

Ayna çevirme algısal karmayı yapısal olarak kırar: dHash komşu piksel
farklarına, pHash DCT katsayılarına bakar ve çevirme her ikisinin de
uzamsal düzenini bozar. Bu bir kusur değil, karma tabanlı aramanın
bilinen sınırıdır ve görsel-dil gömmesi tabanlı ikinci bir arama
katmanıyla kapatılır (rapor 3.1 · M1 · gömme indeksi).
