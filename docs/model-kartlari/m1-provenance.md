# M1 — Köken Referans İndeksi `v0.1.0`

| | |
|---|---|
| Model adı | `m1_provenance` |
| Temel model | dHash + pHash (8×8, 64 bit) |
| Sürüm | 0.1.0 |
| Oluşturulma | 2026-09-08T16:49:07+00:00 |
| Git commit | `77df8a4` |
| Lisans | Veri: Wikimedia Commons (kayıt başına lisans indekste tutulur) |

## Amaç ve kapsam

Bir görüntünün daha önce, başka bir tarih veya olayda yayımlanıp yayımlanmadığını tespit eder. Yanlış bağlam sınıfının kanıt kaynağıdır.

## Eğitim verisi

- Wikimedia Commons açık lisanslı Türkiye afet görüntüleri — 1,758 kayıt
- Her kayıt olay ve il düzeyinde konum etiketi taşır

## Eğitim yordamı

Eğitim yok; algısal karma hesabı ve tam tarama indeksi.

### Hiperparametreler

| Parametre | Değer |
|---|---|
| karma_boyutu | 8×8 (64 bit) |
| esik | 10 |

**Bölünme stratejisi:** Yanlış eşleşme ölçümü indeks dışı görüntülerle yapılır

## Ölçümler

| Metrik | Değer | Değerlendirme kümesi | n | Not |
|---|---|---|---|---|
| recall1_temiz | 0.995 | dönüşümsüz sorgu | 200 | — |
| recall1_agir_donusum | 0.6737 | kırpma/çerçeve/letterbox/döndürme ortalaması | 200 | — |
| olay_disi_eslesme_orani | 0.01 | indeks dışı görüntüler | 200 | — |

## Bilinen sınırlar

- Ayna çevirme algısal karmayı yapısal olarak kırar; bu saldırı ancak görsel-dil gömmesi tabanlı ikinci arama katmanıyla yakalanabilir ve o katman henüz kurulmadı.
- İndeks 1,758 kayıtla sınırlıdır ve yalnızca Wikimedia Commons kaynaklıdır; haber ajansı arşivleri ve DMM'de yalanlanan görseller henüz eklenmedi.
- Video desteği ffmpeg gerektirir; kurulu değilse video yolu devre dışı kalır ve modül çekinir.

## Etik değerlendirme

- Yanlış köken eşleşmesi, kullanıcıya içeriğinin başka bir olaya ait olduğunu söylemek demektir; eşik bu yüzden duyarlılık değil kesinlik lehine ayarlanmıştır.

## Kullanılmaması gereken durumlar

- Eşleşme bulunmamasını 'içerik sahte' olarak yorumlamak
- İndeks kapsamı dışındaki olaylar hakkında köken hükmü vermek

---

*Bu kart `scripts/eval/run_all.py` tarafından üretilmiştir; elle düzenlenmez.*
