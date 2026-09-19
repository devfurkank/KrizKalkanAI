# M3 — Türkçe Kriz Metin Motoru `v0.1.0`

| | |
|---|---|
| Model adı | `m3_text` |
| Temel model | FacebookAI/xlm-roberta-base |
| Sürüm | 0.1.0 |
| Oluşturulma | 2026-09-08T16:15:50+00:00 |
| Git commit | `51f6ad8` |
| Lisans | Model: MIT · Veri: karışık (bkz. docs/veri-envanteri.md) |

## Amaç ve kapsam

Metinden iddia yapısı çıkarır, yanlış bilgi ve manipülatif söylem sınıflandırır, Kural 0'ı besleyen yardım çağrısı sınıfını üretir.

## Eğitim verisi

- HumAID (CC BY-NC-SA, araştırma) — kriz alanı, İngilizce, 19 olay
- MiDe22 (MIT) — Türkçe yanlış bilgi
- DMM Dezenformasyon Bültenleri (CC BY 4.0) — iddia ve tekzip metinleri

## Eğitim yordamı

İki aşamalı ince ayar: kriz alanı (İngilizce) → Türkçe uyarlama. 2. aşamada 1. aşamadan örneklem karıştırılır (replay) — unutmayı hem engeller hem ölçülebilir kılar. Maskelenmiş çok görevli kayıp: etiketi olmayan başlık kayba katkı vermez.

**Bölünme stratejisi:** Olay bazlı bölünme, kaynak içi katmanlı

## Ölçümler

| Metrik | Değer | Değerlendirme kümesi | n | Not |
|---|---|---|---|---|
| claim_makro_f1 | 0.8475 | karışık val | 4030 | — |
| yanlis_makro_f1 | 0.7162 | karışık val | 4030 | — |
| yardim_duyarlilik | 0.9231 | HumAID İngilizce alt kümesi · FPR ≤ 0.2 | 78 | Türkçe ölçüm YOK — Kural 0 bu başlığa bağlı değildir |
| yardim_yanlis_pozitif_orani | 0.1988 | karışık val | 4030 | — |
| yardim_esik | 0.000317 | karışık val | 4030 | Kural 0 karar eşiği — çıkarım katmanı bu değeri kullanır |

## Bilinen sınırlar

- Kural 0 rapor hedefi (0.98) TUTMUYOR: yanlış pozitif sınırı içinde ulaşılabilen en yüksek duyarlılık 0.9231. Hedef duyarlılık ancak sistemin etiketleme kapsamı yok edilerek elde edilebiliyor; bu bilinçli olarak yapılmadı.
- 🔴 Modelin yardım çağrısı başlığı KURAL 0'A BAĞLI DEĞİLDİR. Kural 0 kararı sözlük tabanlı yolda kalır. Gerekçe ölçüldü: model Türkçe'de seferberlik söylemini yardım çağrısından ayıramıyor — “hepimiz sokağa dökülelim” metni sınanan tüm çalışma noktalarında (duyarlılık 0,80–0,95) korumaya alınıyor. Aynı metinlerde sözlük kusursuz ayırıyor.
- Yardım çağrısı duyarlılığı (0.9231) yalnızca İNGİLİZCE üzerinde ölçülmüştür — yardım pozitifleri: en=78 (toplam 78). Türkçe kaynaklarda bu etiket yoktur (docs/veri-envanteri.md · D3). Sayı çapraz dilli aktarımı ölçer, ürünün çalışacağı dildeki başarımı DEĞİL.
- Türkçe yardım çağrısı başarımını ölçmek için elle etiketlenmiş bir Türkçe test kümesi gerekir; bu küme henüz yoktur.
- 8 sınıflı manipülatif söylem başlığı (Görev B1) eğitilmemiştir; sistemde hâlâ sözlük tabanlı yol kullanılır.
- Bölgesel ağız ve Türkçe dışı diller için alt grup analizi yapılmamıştır.

## Etik değerlendirme

- Kural 0'da yanlış pozitif, içeriğin korumaya alınıp etiketlenmemesi demektir; sistemin kapsamını doğrudan azaltır. Bu yüzden duyarlılık yanlış pozitif sınırıyla birlikte seçilir.
- Yanlış negatif ise gerçek bir yardım çağrısının etiketlenmesi demektir ve etik maliyeti daha ağırdır; eşik bu asimetriyi gözetir.

## Kullanılmaması gereken durumlar

- Tek başına doğruluk hükmü vermek
- Kural 0'ı model tabanlı çalıştırmak — çalışma noktası kabul edilebilir değilse sözlük yolu kullanılmalıdır

---

*Bu kart `scripts/eval/run_all.py` tarafından üretilmiştir; elle düzenlenmez.*
