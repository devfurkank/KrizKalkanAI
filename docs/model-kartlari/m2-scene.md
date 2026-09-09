# M2 — Sahne–İddia Uyumu `v0.1.0`

| | |
|---|---|
| Model adı | `m2_scene` |
| Temel model | openai/clip-vit-base-patch32 + clip-ViT-B-32-multilingual-v1 (int8 ONNX) |
| Sürüm | 0.1.0 |
| Oluşturulma | 2026-09-09T09:16:25+00:00 |
| Git commit | `dcb32a8` |
| Lisans | Model: MIT (CLIP) · Apache-2.0 (çok dilli kule) |

## Amaç ve kapsam

Metindeki iddianın görüntüdekiyle uyuşup uyuşmadığını ölçer. Karar vermez; çelişki sinyali üretir.

## Eğitim verisi

- İnce ayar yok; hazır çok dilli CLIP sıfır-atışlı kullanılır

## Eğitim yordamı

Eğitim yok. İki kule int8 ONNX'e aktarıldı; karşıt istemler inşa sırasında gömüldü.

**Bölünme stratejisi:** Eşli karşılaştırma — sınıf dengesizliğinden bağımsız

## Ölçümler

| Metrik | Değer | Değerlendirme kümesi | n | Not |
|---|---|---|---|---|
| esli_dogruluk | 0.795 | M1 korpusu · doğru tür vs yanlış tür | 600 | — |
| ilk_sirada_orani | 0.725 | M1 korpusu | 200 | — |

## Bilinen sınırlar

- Korpus olay türleri arasında ağır dengesizdir; yangın ve sel sınıflarında örneklem azdır ve o satırlar geniş güven aralığı taşır.
- Sıfır-atışlı kullanım: model kriz görüntüleri üzerinde ince ayar görmemiştir. Türkçe iddia metinleri çok dilli metin kulesiyle işlenir ve o kule de kriz alanına uyarlanmamıştır.
- Sinyal karar vermez, çelişki bildirir. Sahne uyuşmazlığı tek başına içeriğin yanlış olduğu anlamına gelmez: aynı olayın farklı bir aşamasını gösteren bir görüntü de düşük skor alabilir.
- Yalnızca üç olay türü ve bir 'diğer' sınıfı tanımlıdır; bu kümenin dışındaki afetler için sinyal anlamsızdır.

## Etik değerlendirme

- Sahne uyuşmazlığı, kullanıcıya içeriğinin sahte olduğunu söylemek için yeterli değildir; füzyon katmanı bu sinyali tek başına karar verdirmeyecek biçimde kullanır.

## Kullanılmaması gereken durumlar

- Görüntüden olay türü hükmü vermek
- Tanımlı dört tür dışındaki içerikleri değerlendirmek

---

*Bu kart `scripts/eval/run_all.py` tarafından üretilmiştir; elle düzenlenmez.*
