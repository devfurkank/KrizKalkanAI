# Sistem — Gecikme ve Verim

*`scripts/eval/system_latency.py` tarafından üretildi · 09.09.2026 08:47 UTC · commit `668ac44`*

| | |
|---|---|
| Çalışma zamanı | onnx · mps |
| Yüklü model | 4/4 · m1_provenance, m3_text, m5_nli, m5_retriever |
| Vaka sayısı | 120 |

## Soğuk hat (önbellek kapalı)

| Metrik | Ölçülen | Hedef | |
|---|---|---|---|
| p50 | 0.02 sn | ≤ 8 sn | ✓ |
| p95 | 0.03 sn | ≤ 20 sn | ✓ |
| p99 | 0.05 sn | — | |
| Verim | 2455 içerik/dk | ≥ 400 | ✓ |

## Sıcak hat (algısal karma önbelleği açık)

Rapor 4.1'deki maliyet verimliliği tezinin ölçümü: aynı içerik yeniden
yüklendiğinde boru hattı baştan çalıştırılmaz.

| Metrik | Ölçülen |
|---|---|
| p50 | 0.000 sn |
| Verim | 6702350 içerik/dk |
| Hızlanma | 19000× |

## İçerik türüne göre

| Tür | n | p50 | p95 | Verim |
|---|---|---|---|---|
| yalnızca metin | 60 | 0.023 sn | 0.026 sn | 2910/dk |
| görsel + metin | 60 | 0.018 sn | 0.022 sn | 3160/dk |

## Bileşen dökümü

Toplam gecikmenin nereden geldiği görülmeden optimizasyon kararı
verilemez.

| Bileşen | Süre |
|---|---|
| M3 · ONNX ileri geçiş | 14.19 ms |
| M3 · örtme tabanlı kanıt | 66.14 ms |
| M5 · gömme kodlama + arama | 3.25 ms |
| M1 · görüntü karması | 2.81 ms |

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
