# Sistem — Gecikme ve Verim

*`scripts/eval/system_latency.py` tarafından üretildi · 14.09.2026 17:11 UTC · commit `547d1c4`*

| | |
|---|---|
| Çalışma zamanı | onnx · mps |
| Yüklü model | 6/6 · m1_provenance, m2_scene, m3_text, m4_synthetic, m5_nli, m5_retriever |
| Vaka sayısı | 120 |

## Soğuk hat (önbellek kapalı)

| Metrik | Ölçülen | Hedef | |
|---|---|---|---|
| p50 | 0.04 sn | ≤ 8 sn | ✓ |
| p95 | 0.20 sn | ≤ 20 sn | ✓ |
| p99 | 0.98 sn | — | |
| Verim | 775 içerik/dk | ≥ 400 | ✓ |

## Sıcak hat (algısal karma önbelleği açık)

Rapor 4.1'deki maliyet verimliliği tezinin ölçümü: aynı içerik yeniden
yüklendiğinde boru hattı baştan çalıştırılmaz.

| Metrik | Ölçülen |
|---|---|
| p50 | 0.000 sn |
| Verim | 6589635 içerik/dk |
| Hızlanma | 39400× |

## İçerik türüne göre

| Tür | n | p50 | p95 | Verim |
|---|---|---|---|---|
| yalnızca metin | 60 | 0.045 sn | 0.052 sn | 1412/dk |
| görsel + metin | 60 | 0.037 sn | 0.207 sn | 800/dk |

## Bileşen dökümü

Toplam gecikmenin nereden geldiği görülmeden optimizasyon kararı
verilemez.

| Bileşen | Süre |
|---|---|
| M3 · ONNX ileri geçiş | 29.19 ms |
| M3 · örtme tabanlı kanıt | 137.90 ms |
| M5 · gömme kodlama + arama | 5.39 ms |
| M1 · görüntü karması | 3.85 ms |

Örtme tabanlı kanıt yalnızca yardım çağrısı olasılığı eşiği aştığında
çalışır; tipik içerikte bu maliyet ödenmez.

## Ölçümün sınırları

Rapor hedefi **60 saniyelik video** ve **tek GPU** içindir. Bu ölçüm
görsel ve metin içeriğini **CPU üzerinde** koşturur:

- Video hattı ffmpeg gerektirir ve M2/M4-video kurulmadı; "60 sn video"
  senaryosu henüz koşturulamıyor.
- Ölçüm üretimde çalışacak yapılandırmadadır (int8 ONNX, CPU). GPU'da
  daha hızlı olması beklenir, ama bu ölçülmedi ve tahmin raporlanmaz.

Bu nedenle tablodaki sayılar rapor hedefiyle **doğrudan**
karşılaştırılamaz; aynı eksende olan tek şey verim.
