# M4 — Hata seviyesi analizi (yerel oynama)

*Üretim: 2026-09-12 11:24 UTC · commit `eab1f09` · aykırılık katı 4.0*

Yöntem, yeniden kaydetmede bölgelerin farklı bozulmasına dayanır: bir
bölge sonradan yapıştırılmışsa sıkıştırma geçmişi çevresinden ayrışır.
Aranan şey sentetik üretim değil **yerel oynama** — MANİPÜLE_MEDYA'yı
besleyebilecek tek görüntü sinyali budur.

## 1. Yakalama — üretilmiş yapıştırma örnekleri

Etiketli oynanmış görüntü kümesi olmadığı için pozitifler üretildi:
nötr bir fotoğrafın %25% kenar oranındaki bölgesine başka bir
fotoğraftan parça yapıştırılıp dosya yeniden kaydedildi.

> **Afet görüntüleri bu üretimde kullanılmadı.** Etik protokol §6 kural 4,
> gerçek afet mağdurlarının görüntüleri üzerine sahte anlatı kurulmasını
> yasaklıyor. Kaynaklar afet dışı nötr fotoğraflardır.

| Sonuç | Adet | Oran |
|---|---|---|
| **Yerel aykırılık (yakalama)** | 116 | **60.4%** |
| Aykırılık yok (kaçırma) | 76 | 39.6% |
| Uygulanamaz (çekinme) | 0 | 0.0% |
| Toplam | 192 | |

## 2. Kontrol — yalnızca yeniden kaydedilmiş, oynanmamış

Aynı fotoğraflar yapıştırma UYGULANMADAN yeniden kaydedildi. Bu grup,
sinyalin yeniden kaydetmeden değil gerçekten yapıştırmadan geldiğini
ayırır.

| Sonuç | Adet | Oran |
|---|---|---|
| **Yerel aykırılık (yanlış pozitif)** | 92 | **46.0%** |
| Aykırılık yok | 108 | 54.0% |
| Uygulanamaz | 0 | 0.0% |
| Toplam | 200 | |

## 3. Afet alanı — yanlış pozitif

Wikimedia Commons Türkiye afet korpusu, **dokunulmadan**. Tamamı
gerçektir; ölçülen şey sistemin sahada kaç gerçek afet fotoğrafını
oynanmış sanacağıdır.

| Sonuç | Adet | Oran |
|---|---|---|
| **Yerel aykırılık (yanlış pozitif)** | 231 | **29.39%** |
| Aykırılık yok | 523 | 66.5% |
| Uygulanamaz (çekinme) | 32 | 4.1% |
| Toplam | 786 | |

## 4. Ayrım gücü — belirleyici ölçüm

Yakalama ve yanlış pozitif oranları eşiğe bağlıdır; eşik oynatılarak
istenen görüntü verdirilebilir. **Ayrım gücü eşikten bağımsızdır.**

Karşılaştırma eşlidir: aynı taban fotoğrafın yapıştırılmış ve
oynanmamış hâli kıyaslanır, böylece fotoğraflar arası doku farkı
ölçümün dışında kalır.

| Metrik | Değer |
|---|---|
| **AUC (yapıştırılmış vs oynanmamış)** | **0.5805** |
| Eşli örnek sayısı | 193 |
| Sapma medyanı · yapıştırılmış | 4.706 |
| Sapma medyanı · oynanmamış | 3.987 |

> 0,50 hiç ayrım olmadığı anlamına gelir. Ölçülen değer buna çok
> yakındır: yöntem, yapıştırılmış bölgeyi değil görüntünün doğal doku
> değişimini ölçüyor. Düz bir gökyüzü ile detaylı bir enkaz alanı
> yeniden kaydetmede farklı bozuluyor ve bu fark, yapıştırmanın
> ürettiğinden büyük.

## 5. Karar

**Sinyal füzyona BAĞLANMADI; bilgi olarak raporlanıyor.**

Kabul için aranan üç koşul ve ölçülen değerler:

| Koşul | Gereken | Ölçülen | |
|---|---|---|---|
| **Ayrım gücü (AUC)** | ≥ 0,75 | **0.5805** | ✗ |
| Yakalama (üretilmiş yapıştırma) | bilgi | 60.4% | |
| Yanlış pozitif (afet, gerçek) | ≤ 5% | 29.39% | ✗ |
| Yanlış pozitif (kontrol, yeniden kayıt) | ≤ 10% | 46.0% | ✗ |

## 6. Bilinen sınırlar

- **Kayıpsız biçimlerde uygulanamaz.** PNG ve kayıpsız WebP'de sıkıştırma
  geçmişi yoktur; modül bu dosyalarda çekinir.
- **Yeniden kodlama izi siler.** Sosyal platformlar yüklemede yeniden
  kodlar ve yapıştırma izi ile çevresi aynı geçmişe kavuşur.
- **Yerel oynamayı bulur, kimin yaptığını değil.** Kırpma, renk düzeltme
  ve yasal düzenlemeler de aykırılık üretebilir; sinyal tek başına
  suçlama değildir.
- Pozitifler bu depoda üretildi; yayımlanmış bir kıyas kümesi değildir.

---

*`scripts/eval/m4_ela.py` tarafından üretildi; elle düzenlenmez.*
