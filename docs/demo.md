# Demo Kılavuzu

Sunum sırasında izlenecek akış ve sistemin çalışma biçimi.

## Başlatma

```bash
make demo
```

Tek komut iki süreç başlatır:

| Servis | Adres |
| --- | --- |
| Analiz API'si | http://localhost:8000 (dokümantasyon: `/docs`) |
| Arayüz | http://localhost:3000 |

**PostgreSQL, Redis, MinIO ve Celery gerekmez.** Depo bellek içi, analiz istek
içinde çalışır (`KK_INLINE_ANALYSIS=true`). Bu, sunum ortamında hata yüzeyini
altı süreçten ikiye indirir. Altyapıyı gerçekten ayağa kaldırmak isterseniz
`make up` ile Docker servisleri başlatılabilir; kod yolu aynıdır.

## Bu sürümde neyin mock olduğu

Analiz zincirinin **yapısı, sözleşmesi ve kararları gerçektir**; yerine model
konduğunda çağıran katmanlar değişmez. Mock olan, sinyal üreten alt katmandır.

| Modül | Gerçek olan | Mock olan |
| --- | --- | --- |
| M1 Köken | Algısal karma, Hamming mesafesi, eşik, benzerlik hesabı | Referans korpusu tohumlanmış; kareler ffmpeg ile çıkarılmıyor |
| M2 Çok modlu | Sinyal ayrıştırması, ölçülü dil kuralı | Skorlar parmak izinden türetiliyor |
| M3 Metin | Sözlük, desen eşleştirme, iddia çıkarımı, etiketleme — **tamamı gerçek çalışıyor** | Eğitilmiş dönüştürücü yerine kural tabanlı |
| M4 Sentetik | Çekinme (OOD) mantığı, C2PA kontrolü | Skorlar parmak izinden türetiliyor |
| M5 Bilgi havuzu | Çapa terimli eşleştirme, dört durumlu karar | Havuz tohumlanmış; canlı AFAD akışı yok |
| M6 Füzyon | Kalibrasyon, sınıflandırma, kanıt grafı — **tamamı gerçek** | Kalibrasyon noktaları elle konmuş |
| M7 Politika | Kural 0, müdahale merdiveni — **tamamı gerçek** | — |
| M8 Radar | Kümeleme, yayılım hesabı — **tamamı gerçek** | — |

Aynı girdi her zaman aynı çıktıyı verir; demo tekrarlanabilir.

## Sunum akışı (4 dakika)

### 1 · Yanlış bağlam (60 sn)

Ana sayfada **“Yanlış bağlam”** senaryosuna tıkla → **Gönder**.

Gösterilecek: analiz kartı `YANLIŞ_BAĞLAM`, güven %97. **“Neden?”** ile kanıt
panelini aç — “Bu görüntü ilk kez 08.02.2023 tarihinde yayımlanmış”, eşleşen
kare, özgün olay ve “metindeki konum ile kaydın konumu uyuşmuyor”.

Vurgulanacak: klasik bir deepfake dedektörü bu içeriği “gerçek” der ve hiçbir
uyarı üretmez. Kanıt panelinin altında **“Atlanan: M2 · M4”** yazar — köken
kesin sonuç ürettiği için pahalı modüller hiç çalıştırılmadı.

### 2 · Kurum taklidi (45 sn)

**“Kurum taklidi”** senaryosu → **Gönder**.

`DOĞRULANMAMIŞ_İDDİA`, Seviye 1 alt bilgi. Kanıt panelinde DMM kaydı:
“AFAD, deprem tahmininin bilimsel olarak mümkün olmadığını duyurmuştur.”

### 3 · Yardım çağrısı — Kural 0 (45 sn)

**“Yardım çağrısı”** senaryosu → **Gönder**.

Metin panik dili taşır; sınıflandırıcı bunu yüzeysel olarak “panik yayma”ya
yakın bulur. Ancak **hiçbir etiket, hiçbir sürtünme uygulanmaz.** Yeşil kart:
“Kural 0 gereği … denetim kaydına `koruma_kuralı_uygulandı` yazıldı.”

Bu 45 saniye sunumun en akılda kalıcı anıdır.

### 4 · Sentetik medya — sürtünme (45 sn)

**“Sentetik medya”** senaryosu → **Gönder** → sürtünme ekranı açılır.

Ekranda “Yine de paylaş” düğmesi **etkin ve görsel olarak bastırılmamış**.
Altında: “Bu ekran paylaşımı engellemez.” Paylaş → gönderi akışa düşer.

### 5 · Kriz Radar (45 sn)

Sol menüden **Kriz Radar**. İki kalıcı sayaç: korunan yardım çağrısı sayısı ve
**“0 içerik kaldırıldı”**. Altında kümelenmiş iddialar, yayılım hızları ve
resmî kaynak durumları.

### 6 · Moderatör paneli (30 sn)

**Moderatör** sekmesi. Kuyruk yayılım hızına göre sıralı. Bir satıra tıkla →
kanıt grafı → “Etiketi onayla / Bağlam ekle / Yetkili mercie bildir”.
Kaldırma seçeneği **yoktur**. Denetim kaydı en altta.

## Jüri kendi metnini yazmak isterse

Composer'a herhangi bir metin yazılabilir; analiz gerçek motordan geçer.
Denemeye değer ifadeler:

| Yazılan | Beklenen |
| --- | --- |
| “enkaz altında kaldık, yardım edin” | Kural 0 · müdahale yok |
| “baraj yıkıldı” | Doğrulanmamış iddia · DMM tekzibi |
| “hemen paylaşın, medya gizliyor” | Provokatif çerçeveleme |
| “bugün hava güzel” | Temiz · müdahale yok |
| “baraj yıkıldı iddiası asılsızdır” | Temiz — yalanlama çerçevesi tanınır |

Son satır özellikle önemli: tekzip metinlerinin dezenformasyon sanılması
bilinen bir hata modudur ve sistem bunu yapısal olarak engeller.

## Demoyu sıfırlama

```bash
curl -X POST http://localhost:8000/api/demo/reset
```

Akışı tohum durumuna döndürür. Art arda sunum yaparken kullanışlıdır.

## Sorun giderme

**Arayüz “Analiz servisine ulaşılamıyor” diyorsa:** API çalışmıyor demektir.
`make dev-api` ile ayrı başlatın. Arayüz bu durumda boş ekran göstermez,
yeniden deneme düğmesi sunar.

**Port çakışması:** API `--port` ile, arayüz `PORT=3001 pnpm dev` ile
değiştirilebilir; arayüzün API adresi `apps/web/.env.local` içindeki
`NEXT_PUBLIC_API_URL` ile ayarlanır.
