# M5 — Kriz Bilgi Havuzu Geri Getirici `v0.1.0`

| | |
|---|---|
| Model adı | `m5_retriever` |
| Temel model | intfloat/multilingual-e5-base (int8 ONNX) |
| Sürüm | 0.1.0 |
| Oluşturulma | 2026-09-12T11:21:48+00:00 |
| Git commit | `eab1f09` |
| Lisans | Model: MIT (e5) · Veri: CC BY 4.0 (DMM) |

## Amaç ve kapsam

Kullanıcı metninden çıkarılan iddiaya en yakın resmî kayıtları bulur. Karar vermez; aday üretir. Kararı M5 çıkarım katmanı verir.

## Eğitim verisi

- DMM Dezenformasyon Bültenleri (CC BY 4.0) — 2,519 kayıt indekslendi
- Model ince ayar görmedi; hazır çok dilli gömme modeli kullanıldı

## Eğitim yordamı

İnce ayar yok. Kodlayıcı int8 dinamik nicelemeyle (per_channel) ONNX'e aktarıldı; indeks ve sorgu aynı kodlayıcıyla gömülür.

### Hiperparametreler

| Parametre | Değer |
|---|---|
| maks_uzunluk | 192 |
| onek | query:/passage: |
| niceleme | int8 |

**Bölünme stratejisi:** Değerlendirme kümesi elle yazılmış yeniden ifadelerden oluşur

## Ölçümler

| Metrik | Değer | Değerlendirme kümesi | n | Not |
|---|---|---|---|---|
| recall1 | 0.8571 | elle yazılmış yeniden ifadeler | 28 | — |
| recall5 | 0.9643 | elle yazılmış yeniden ifadeler | 28 | — |
| mrr | 0.9107 | elle yazılmış yeniden ifadeler | 28 | — |

## Bilinen sınırlar

- Benzerlik skoru tek başına 'aynı iddia' ile 'benzer konu'yu AYIRAMAZ; ölçüldü ve raporlandı (docs/metrikler/m5.md · ayrım analizi). Karar katmanı olmadan kullanılmamalıdır.
- Değerlendirme kümesi küçüktür (n=28); güven aralığı geniştir.
- Havuz yalnızca tekzip kayıtları içerir (DMM); DESTEKLİYOR sınıfı için AFAD/valilik duyuruları ayrıca gereklidir.
- Türkçe dışı ve bölgesel ağız başarımı ölçülmedi.

## Etik değerlendirme

- Yanlış eşleşme, kullanıcıya 'resmî kaynak seni yalanlıyor' demek anlamına gelir; bu nedenle karar eşiği duyarlılık değil kesinlik lehine ayarlanır.

## Kullanılmaması gereken durumlar

- Tek başına doğruluk hükmü vermek
- Havuzda karşılığı olmayan iddiaları yanlış saymak

---

*Bu kart `scripts/eval/run_all.py` tarafından üretilmiştir; elle düzenlenmez.*
