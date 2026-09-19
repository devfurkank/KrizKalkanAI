# M8 — Kriz Radar İddia Kümeleme `v0.1.0`

| | |
|---|---|
| Model adı | `m8_radar` |
| Temel model | intfloat/multilingual-e5-base (M5 kodlayıcısı) + HDBSCAN |
| Sürüm | 0.1.0 |
| Oluşturulma | 2026-09-12T11:21:59+00:00 |
| Git commit | `eab1f09` |
| Lisans | Model: MIT (e5) · BSD-3 (scikit-learn) |

## Amaç ve kapsam

Aynı iddianın farklı ifadelerini tek kümede toplar; panel yayılım hızını ve ivmesini bu kümeler üzerinden hesaplar.

## Eğitim verisi

- Eğitim verisi yok; kümeleme denetimsizdir

## Eğitim yordamı

Eğitim yok. Cümle gömmesi M5'in kodlayıcısıyla üretilir (ek ağırlık indirilmez), HDBSCAN ile kümelenir. Gürültü olarak işaretlenen iddialar tek üyeli kümelere dönüştürülür: bir kez görülmüş iddia da bir iddiadır, panelden düşürülmez.

### Hiperparametreler

| Parametre | Değer |
|---|---|
| min_cluster_size | 2 |
| metric | euclidean |

**Bölünme stratejisi:** Değerlendirme, gerçek DMM iddiaları ve elle yazılmış yeniden ifadeleri üzerinde yapılır

## Ölçümler

| Metrik | Değer | Değerlendirme kümesi | n | Not |
|---|---|---|---|---|
| ari_zor | 0.429 | elle yazılmış yeniden ifadeler | 56 | — |
| birlikte_zor | 0.5357 | elle yazılmış yeniden ifadeler | 56 | — |
| ari_kolay | 1 | gürültü varyantları | 120 | — |

## Bilinen sınırlar

- Zor kümede ARI 0.4290: aynı iddianın elle yeniden yazılmış hâllerinin yaklaşık yarısı ayrı kümelerde kalıyor. Panel bu durumda tek bir yalanı iki satır olarak gösterir — birleştirmeyi kaçırmak, yanlış birleştirmekten daha az zararlıdır ve eşik bu yönde seçilmiştir.
- Kümeleme denetimsizdir ve kriz alanına uyarlanmamıştır; gömme modeli genel amaçlıdır.
- Değerlendirme kümesi küçüktür (n=56 ve 120).

## Etik değerlendirme

- Panelin iki sayacı her koşulda görünür kalır: Kural 0 ile korunan yardım çağrısı sayısı ve kaldırılan içerik sayısı (her zaman sıfır).
- Kümeleme bir sıralama aracıdır, hüküm değil: küme büyüklüğü içeriğin yanlış olduğunu göstermez, yalnızca yayılımını gösterir.

## Kullanılmaması gereken durumlar

- Küme büyüklüğünden doğruluk hükmü çıkarmak
- Kural 0 ile korunmuş içerikleri kümelemek — panel onları hiç almaz

---

*Bu kart `scripts/eval/run_all.py` tarafından üretilmiştir; elle düzenlenmez.*
