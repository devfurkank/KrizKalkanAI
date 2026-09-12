# Sistem Mimarisi

Bu belge sistemin **fiilen inşa edilmiş** hâlini anlatır. Her tasarım kararının
gerekçesi bir ölçümdür ve ölçümün nerede olduğu belirtilir; sayılar burada
tekrarlanmaz, üreten dosyaya işaret edilir (`docs/metrikler/`).

---

## 1. Katmanlar

```
apps/web        Next.js · akış, analiz kartı, moderatör paneli, kriz radar
apps/api        FastAPI · alım, analiz uçları, moderasyon
apps/worker     Celery · ağır medya analizi (kuyruk)
libs/krizkalkan-core
  ├── models/       ağırlık yükleme, kabul kapısı, model kartları
  ├── provenance/   M1  köken ve yeniden bağlam
  ├── multimodal/   M2  çok modlu çelişki
  ├── text/         M3  Türkçe kriz metni
  ├── synthetic/    M4  sentetik medya sinyalleri
  ├── knowledge/    M5  doğrulanmış kriz bilgi havuzu
  ├── fusion/       M6  kalibrasyon ve kanıt füzyonu
  ├── policy/       M7  kademeli müdahale
  └── radar/        M8  kriz radar kümeleme
```

Modüller birbirini doğrudan çağırmaz; `schemas.py` üzerinden `Signal` ve
`Evidence` alışverişi yapar. Bir modülün iç yöntemi değiştiğinde çağıran
katmanlar değişmez — bu, sözlük tabanlı motorların yerine modellerin
konabilmesini mümkün kılan tek yapısal özelliktir.

---

## 2. Model katmanı — iki yollu tasarım

Her analiz modülünün **iki yolu** vardır:

| | |
|---|---|
| **model yolu** | eğitilmiş ağırlıkla çalışır |
| **kural yolu** | sözlük, desen ve karma ile çalışır |

`models/registry.py` ikisi arasında seçim yapar ve şu güvenceyi verir:
`registry.get()` **hiçbir koşulda istisna fırlatmaz.** Ağırlık yoksa, çalışma
zamanı kurulu değilse veya yükleyici hata verirse `None` döner ve modül kural
yoluna düşer.

Bu bir kolaylık değil, sunum sigortasıdır: ağırlık dizini boş bir makinede
sistem eksiksiz çalışmaya devam eder. `KK_MODELS=off` ile tüm model katmanı
tek anahtarla kapatılabilir. Testler her iki modda da koşar.

### Kabul kapısı

Ağırlık yüklenmeden önce **model kartındaki ölçüm** okunur. Kart yoksa, istenen
metrik ölçülmemişse veya eşiğin altındaysa ağırlık yüklenmez.

Gerekçe ölçülerek bulundu: 256 örnekle eğitilmiş bir deneme modelini ağırlık
dizinine koyduğumda demo senaryoları **sessizce** bozuldu — hata mesajı yok,
log yok, yalnızca yanlış cevaplar. Yarım eğitilmiş bir ağırlık, hiç ağırlık
olmamasından kötüdür. Kapı bunu yapısal olarak engeller: ölçülmemiş model
üretime giremez.

Eşikler "hedef başarım" değil, "model gerçekten çalışıyor mu" seviyesindedir.

### Ölçüm → kart → kapı döngüsü

```
scripts/eval/*.py  →  docs/metrikler/*.md   (rapor tabloları)
                   →  models/*/kart.json    (kabul kapısı bunu okur)
                   →  docs/model-kartlari/  (belge)
```

Metrik üreten her şey betiktir. Elle yazılmış tablo yoktur; her rapor üstünde
üreten betiği, tarihi ve git commit'ini taşır.

---

## 3. Modüller ve durumları

| Kod | Modül | Model yolu | Ölçüm |
|---|---|---|---|
| M1 | Köken ve yeniden bağlam | dHash + pHash, çoklu görünüm indeksi | `m1-dayaniklilik.md` |
| M2 | Sahne–iddia uyumu | çok dilli CLIP, int8 ONNX | `m2.md` |
| M2 | AV senkron, konuşmacı–yüz | ⏳ kurulmadı | — |
| M3 | Türkçe kriz metni | XLM-R çok görevli, int8 ONNX | `m3.md` |
| M4 | C2PA köken üstverisi | kriptografik doğrulama · **manifest zinciri taranıyor** | testlerle |
| M4 | Üretici üstverisi | ✅ **kural tabanlı · devrede** | `m4-ustveri.md` |
| M4 | Sentetik görüntü | ⛔ kuruldu ve ölçüldü, **devreye alınmadı** | `m4.md` |
| M4 | Hata seviyesi analizi | ⛔ kuruldu ve ölçüldü, **devreye alınmadı** | `m4-ela.md` |
| M4 | Video, ses | ⏳ kare çıkarımı yok / ASVspoof | — |
| M5 | Bilgi havuzu geri getirme | e5 gömme + indeks | `m5.md` |
| M5 | Çıkarım (NLI) | ⛔ eğitildi, **devreye alınmadı** | `m5.md` |
| M6 | Kalibrasyon ve füzyon | ölçülmüş isotonic | `m6.md` |
| M7 | Kademeli müdahale | kural tabanlı (model gerekmez) | — |
| M8 | Kriz radar kümeleme | gömme + HDBSCAN | `m8.md` |

---

## 4. Analiz akışı

```
içerik
  │
  ├─ M3  metin  ──────────────► iddia yapısı, manipülatif söylem, yardım çağrısı
  │
  ├─ M1  köken  ──────────────► eşleşme + BAĞLAM ÇELİŞKİSİ
  │        │
  │        └─ kesin sonuç ise M2 ve M4 hiç çalıştırılmaz (kademeli işlem)
  │
  ├─ M5  bilgi havuzu ────────► sözlük adayı + geri getirme vetosu
  │
  ├─ M2/M4 (gerekiyorsa) ─────► sahne çelişkisi, C2PA, sentetik izler
  │
  ├─ M6  kalibrasyon + füzyon ► sınıf + güven + katkı veren sinyaller
  │
  └─ M7  politika ────────────► müdahale seviyesi (Kural 0 önceliklidir)
```

### Füzyon sırası

Sıra tesadüf değil; **kanıtın gücüne** göredir:

1. **Köken çelişkisi** — kesin kanıt. Kayıt, görüntünün başka bir olaya ait
   olduğunu tarih ve kaynakla gösterir.
2. **Sentetik medya** — içerik üretilmiş.
3. **Manipüle medya** — gerçek kayıt üzerinde oynanmış.
4. **Sahne çelişkisi** — medya gerçek, gösterdiği olay iddiadan başka.
5. **Doğrulanmamış iddia** — resmî kaynakla çelişiyor veya kaynak sessiz.
6. **Provokatif çerçeveleme** — içerik doğru olabilir, sunum manipülatif.
7. **Çekinme / temiz**.

Sıralama ölçümle düzeltildi: sahne çelişkisi başlangıçta ikinci sıradaydı ve
sentetik medya senaryosunu yanlış sınıflandırıyordu. "İçerik üretilmiş" bulgusu
"sahne uyuşmuyor"dan güçlüdür.

**Köken önceliği kuralı:** köken kaydı bağlamı *doğruladıysa* sahne çelişkisi
dalı çalışmaz. Kesin kanıt, olasılıksal sinyal tarafından geçersiz kılınamaz.

---

## 5. Ölçümle verilen kararlar

Bu bölüm, sistemin şu anki hâlini belirleyen kararları ve gerekçelerini
toplar. Hepsinde ortak bir örüntü var: **ilk tasarım ölçüldüğünde yanlış çıktı.**

### Kural 0 modele bağlanmadı (M3)

Modelin yardım çağrısı başlığı Kural 0'ı beslemiyor; karar sözlükte kaldı.
İki ölçüm bunu gerektirdi. Birincisi, başlığın duyarlılığı yalnızca İngilizce
üzerinde ölçüldü — doğrulama kümesindeki pozitiflerin tamamı HumAID'den geliyor
ve Türkçe kaynaklarda bu etiket yok. İkincisi, Türkçe'de model seferberlik
söylemini yardım çağrısından ayıramıyor: "hepimiz sokağa dökülelim" metni
sınanan tüm çalışma noktalarında korumaya alınıyordu. Kural 0 tetiklendiğinde
sistem hiçbir müdahale uygulamadığı için bu, provokatif içeriğin etiketsiz
geçmesi demekti. Aynı metinlerde sözlük kusursuz ayırıyor.

Ayrıntı: `docs/model-kartlari/m3-text.md`

### NLI çıkarım katmanı devreye alınmadı (M5)

Model rapor hedefini tutturdu (SNLI-TR doğruluğu ≥ 0,80) ama kriz alanında
sözlük yolundan **hem daha az doğru hem çok daha zararlı** sonuç verdi. Sebep
görev uyumsuzluğu: SNLI'ın "öncül varsayımı ima ediyor mu?" sorusu, bizim "bu
iki metin aynı iddiayı mı öne sürüyor?" sorumuz değil.

Yerine geçen tasarım da ölçümle bulundu: sözlük aday üretir, **geri getirme
vetolar**. Geri getirmenin değeri sıralayıcı olmasında değil, uzak adayları
reddetmesindeydi — zararlı eşleşme geri getiricinin ilk yirmisinde bile yoktu,
doğru eşleşmelerin tamamı ilk üçteydi. Veto sayesinde sözlük eşiği güvenle
düşürüldü.

Ayrıntı: `docs/metrikler/m5.md` · `docs/model-kartlari/m5-nli.md`

### Köken eşleşmesi tek başına suçlama değildir (M1/M6)

Füzyon başlangıçta `matched` olmasını koşulsuz "yanlış bağlam" sayıyordu; bu,
doğru bağlamda paylaşılan her arşiv görüntüsünü suçlamak demekti. Sınıf artık
ancak kaydın konumu/olayı metindeki iddiayla **çeliştiğinde** kurulur.

### Eşleşme hatası zararına göre ayrıldı (M1)

Ham yanlış eşleşme oranı %8 çıkmıştı. Eşleşmelere tek tek bakıldığında
neredeyse hepsinin aynı çekimden ardışık kareler olduğu görüldü — bunlar hata
değil, doğru davranış. Zararlı olan, içeriğin **başka bir olaya** bağlanması.
İki oran ayrı raporlanıyor ve rapor hedefi zararlı olana uygulanıyor.

### Ağız normalizasyonu (M3 · adalet)

Alt grup denetimi, ölçünlü Türkçe dışında yazan kullanıcıların provokatif
içerikte **yarı oranda** korunduğunu gösterdi. Sorun kökte değil çekimdeydi.
Ünlü uyumuna duyarlı bir normalizasyon katmanı farkı sıfıra indirdi; zararsız
metinlerde yanlış pozitif artışı ölçülmedi.

Ayrıntı: `docs/metrikler/adalet.md`

### Karşılaştırmalı karar, mutlak eşik değil (M2, M5, M4)

Üç modülde de aynı ders çıktı: skorlar dar bir bantta sıkışıyor ve mutlak eşik
seçmek anlamsız. M5'te en yüksek skorlu alakasız sorgu bir resmî duyuruydu;
M2'de afet dışı istemler enkaz sahnelerini geçiyordu. M4'te sentetik görüntü
skorları 0,93–0,97 bandına sıkıştı. M2 ve M5'te karşılaştıracak bir şey vardı
(karşıt istem, aday kayıt) ve karar **karşılaştırmayla** verildi. M4'te yok:
tek bir görüntünün doğal bir karşılaştırma eşi bulunmuyor. Sonuç, modülün
devreye alınmaması oldu.

### M4'te belgesel sinyal, olasılıksal sinyali geçti

| | |
|---|---|
| **Beklenti** | Sinir ağı detektörü M4'ün omurgası olacaktı |
| **Ölçüm 1** | Detektör afet alanında kullanılamaz çıktı (aşağıda) |
| **Ölçüm 2** | Dosyaya gömülü üretici üstverisi: %9,0 yakalama, **1.678 gerçek görüntüde 0 yanlış pozitif** (`m4-ustveri.md`) |
| **Ölçüm 3** | Hata seviyesi analizi: ayrım gücü AUC 0,5805 — rastgeleden farksız (`m4-ela.md`) |
| **Karar** | M4'ün çalışan iki yolu **belgesel**: C2PA imzası ve üretici üstverisi. Olasılıksal iki yol (sinir ağı, ELA) ölçüldü ve devreye alınmadı |

Bu, raporun köken önceliği tezinin M4 içinde de doğrulanması demek: belgesel
kanıt, olasılıksal çıkarımdan önce gelir ve bu tercih artık ölçülmüş bir
gerekçeye dayanıyor.

### M4 sentetik görüntü modeli devreye alınmadı

| | |
|---|---|
| **Plan** | DeepReality detektörleri int8 ONNX'e taşınıp `synthetic.video` sinyalini besleyecekti |
| **Ölçüm 1** | Çapraz veri kümesinde (OpenFake, 22 üretici ailesi) AUC **0,7818** — raporun ≥ 0,72 hedefini karşılıyor |
| **Ölçüm 2** | Gerçek Türk afet fotoğraflarının **%99,71'i** 0,50 eşiğinde "üretilmiş" çıkıyor (n=686) |
| **Ölçüm 3** | Yanlış pozitifi %5'e indiren eşikte duyarlılık 0,25'e düşüyor; %1'de 0,10 |
| **Ölçüm 4** | Üç sınıflı detektör, tamamı gerçek olan kümelerde "gerçek" sınıfına ortalama 0,001–0,004 olasılık veriyor |
| **Doğrulama** | Kapı zorla açıldığında gerçek bir Kahramanmaraş deprem fotoğrafı **SENTETİK_MEDYA (güven 0,835)** olarak sınıflandı; kapalıyken TEMİZ |
| **Karar** | Ağırlık yüklenmiyor, M4 kural yolunda kalıyor. Kabul kapısı AUC'ye değil **afet alanı özgüllüğüne** bağlandı |

İki ölçüm çelişmiyor: AUC bir sıralama ölçüsüdür ve model gerçekten sıralıyor.
Kullanılabilirliği belirleyen ise çalışma noktasıdır. Kapıyı yetenek metriğine
bağlamak, geçen bir AUC'nin gerçek afet fotoğraflarını sentetik ilan eden bir
modeli sisteme sokmasına izin verirdi — bu yüzden kapı **zarar metriğine**
bağlıdır.

---

## 6. Yeniden üretim

```bash
make setup            # bağımlılıklar
make setup-models     # çıkarım katmanı (ONNX, FAISS, sklearn)
make veri             # metin kümeleri: indir → doğrula → uyumlaştır → böl
make m5-index         # DMM havuzu + geri getirme indeksi
make m4-model         # sentetik görüntü detektörleri (DeepReality → int8 ONNX)
make depo-denetimi    # kaynak dosyalar depoda mı?
make test             # KK_MODELS=off ve on
```

Ağırlıklar depoda tutulmaz. Eğitim Kaggle defterleriyle yapılır
(`notebooks/`), çıktı `models/` altına indirilir. Kart olmadan ağırlık
yüklenmez.

### Ölçümü tekrarlamak

```bash
KK_MODELS=on python scripts/eval/m1_robustness.py    # köken dayanıklılığı
KK_MODELS=on python scripts/eval/m2_scene.py         # sahne–iddia
KK_MODELS=on python scripts/eval/m3_text.py --onnx --kontrol-noktasi models/m3_text
KK_MODELS=on python scripts/eval/m3_fairness.py      # adalet denetimi
KK_MODELS=on python scripts/eval/m4_synthetic.py     # sentetik görüntü (çapraz veri kümesi)
python scripts/eval/m4_ustveri.py                    # üretici üstverisi (ağırlık gerekmez)
python scripts/eval/m4_ela.py                        # hata seviyesi analizi (ağırlık gerekmez)
KK_MODELS=on python scripts/eval/m5_knowledge.py     # havuz + karar
KK_MODELS=on python scripts/eval/m6_fusion.py        # kalibrasyon + füzyon
KK_MODELS=on python scripts/eval/m8_radar.py         # kümeleme
KK_MODELS=on python scripts/eval/system_latency.py   # gecikme + verim
```

---

## 7. Bilinen boşluklar

- **M2 · AV senkron ve konuşmacı–yüz** kurulmadı. Ses–görüntü veri kümeleri
  EULA gerektiriyor.
- **M4 · sentetik görüntü** kuruldu, ölçüldü ve **devreye alınmadı**: alan
  içindeki çalışma noktası kabul edilebilir değil (`docs/metrikler/m4.md`).
  Dışa aktarım, motor, değerlendirme ve testler yerinde; daha iyi bir ağırlık
  tek komutla devreye girer.
- **M4 · hata seviyesi analizi** kuruldu, ölçüldü ve **devreye alınmadı**:
  ayrım gücü AUC 0,5805 ile rastgeleden farksız; yöntem yapıştırmayı değil
  görüntünün doğal doku değişimini ölçüyor (`docs/metrikler/m4-ela.md`).
- **M4 · video ve ses** kurulmadı. Video için kare çıkarımı (ffmpeg) yok; ses
  için ASVspoof üzerinde eğitim planlı.
- **SENTETİK_MEDYA ve MANİPÜLE_MEDYA** sınıfları uçtan uca değerlendirme
  kümesinde yok — o sınıflar M2/M4'ü gerektiriyor. Makro-F1 bu nedenle rapor
  3.2'deki altı sınıflı hedefle doğrudan karşılaştırılamaz.
- **`synthetic.video` kalibrasyonu** hiç ölçülmemişti; M4 çalışması ilk ölçümü
  üretti (ECE 0,2990 → 0,0755). Noktalar `docs/metrikler/m4.md` içinde duruyor
  ama **devreye alınmadı**: kalibrasyon M6'nın veri ürünüdür ve benimseme,
  uçtan uca kümeye SENTETİK_MEDYA vakaları eklendikten sonra yapılmalıdır.
- **8 etiketli manipülatif söylem başlığı** eğitilmedi; sistem sözlük yolunu
  kullanıyor. Provokatif çerçeveleme sınıfının düşük başarımının sebebi budur.
- **Video hattı** ffmpeg gerektiriyor ve gecikme ölçümü yalnızca görsel/metin
  içeriğini kapsıyor.
- **Ölçümler çalışma zamanı sürümüne duyarlı.** İki makinede aynı ağırlıklar,
  aynı veri ve aynı tohumla koşulduğunda ONNX kullanmayan M1 birebir aynı
  sayıları verdi (Recall@1 0,9950 · zararlı eşleşme 0,0100), ONNX kullanan
  modüller ise marjinal kararlarda kaydı: M5 Recall@1 0,8929 → 0,8571,
  M8 zor küme ARI 0,5742 → 0,4290. Recall@5 (0,964) ve M8 kolay küme (1,0000)
  değişmedi — yani sıralama değil, yalnızca sınırdaki kararlar oynuyor.
  `pyproject.toml` `onnxruntime>=1.20` diyor ve üst sınır yok. Sunumda
  raporlanan sayılar, demoyu çalıştıracak makinede yeniden üretilmeli.
- **Taşınabilirlik tuzağı: konumsal dosya adları.** `fetch_provenance.py`
  görüntüleri indirme sırasına göre numaralandırıyor; Commons kategorileri
  değiştiği için aynı ad iki koşuda farklı görüntüye denk gelebiliyor. Köken
  indeksi ve uçtan uca küme bu adlara bağlı olduğundan, veri ile ağırlık ayrı
  kanallardan taşındığında ölçümler sessizce bozuluyor. `ProvenanceIndex` artık
  bunu yüklenirken tespit edip hata basıyor; kalıcı çözüm, adların içerikten
  türetilmesi olurdu.
- **Türkçe etiketli yardım çağrısı kümesi** yok. Kural 0'ın Türkçe duyarlılığı
  ölçülmemiş durumda; bu, sistemin en kritik ölçülmemiş büyüklüğü.
