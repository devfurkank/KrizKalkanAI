# Sistem — Gecikme ve Verim

*`scripts/eval/system_latency.py` tarafından üretildi · 12.09.2026 11:23 UTC · commit `eab1f09`*

| | |
|---|---|
| Çalışma zamanı | onnx · mps |
| Yüklü model | 5/6 · m1_provenance, m2_scene, m3_text, m5_nli, m5_retriever |
| Vaka sayısı | 120 |

## Soğuk hat (önbellek kapalı)

| Metrik | Ölçülen | Hedef | |
|---|---|---|---|
| p50 | 0.04 sn | ≤ 8 sn | ✓ |
| p95 | 0.10 sn | ≤ 20 sn | ✓ |
| p99 | 0.60 sn | — | |
| Verim | 952 içerik/dk | ≥ 400 | ✓ |

## Sıcak hat (algısal karma önbelleği açık)

Rapor 4.1'deki maliyet verimliliği tezinin ölçümü: aynı içerik yeniden
yüklendiğinde boru hattı baştan çalıştırılmaz.

| Metrik | Ölçülen |
|---|---|
| p50 | 0.000 sn |
| Verim | 5281334 içerik/dk |
| Hızlanma | 43500× |

## İçerik türüne göre

| Tür | n | p50 | p95 | Verim |
|---|---|---|---|---|
| yalnızca metin | 60 | 0.062 sn | 0.106 sn | 954/dk |
| görsel + metin | 60 | 0.043 sn | 0.102 sn | 1119/dk |

## Bileşen dökümü

Toplam gecikmenin nereden geldiği görülmeden optimizasyon kararı
verilemez.

| Bileşen | Süre |
|---|---|
| M3 · ONNX ileri geçiş | 27.79 ms |
| M3 · örtme tabanlı kanıt | 135.83 ms |
| M5 · gömme kodlama + arama | 5.29 ms |
| M1 · görüntü karması | 4.12 ms |

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
