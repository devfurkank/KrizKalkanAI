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
| M4 | Sentetik görüntü | ⚠️ sıfırdan eğitildi · devrede · **kriz alanında kör** | `m4.md` |
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

### M4 sentetik görüntü modeli: devralınan ağırlık elendi, yenisi eğitildi

**Birinci tur — devralınan ağırlık (DeepReality) reddedildi.**

| | |
|---|---|
| **Ölçüm 1** | Çapraz veri kümesinde AUC **0,7818** — raporun ≥ 0,72 hedefini karşılıyor |
| **Ölçüm 2** | Gerçek Türk afet fotoğraflarının **%99,49'u** 0,50 eşiğinde "üretilmiş" çıkıyor |
| **Ölçüm 3** | Skorlar 0,92–0,97 bandına sıkışmış; üretilmiş/gerçek medyan farkı **0,0167** |
| **Teşhis** | Alan karışıklığı değil **doygunluk**: model her girdiye yüksek güvenle "üretilmiş" diyor, AUC o mikroskobik sıralamadan geliyor |
| **Doğrulama** | Kapı zorla açıldığında gerçek bir Kahramanmaraş deprem fotoğrafı SENTETİK_MEDYA (0,835) sınıflandı |
| **Karar** | Devreye alınmadı. Kapı, yetenek metriğine (AUC) değil **zarar metriğine** (afet alanı özgüllüğü) bağlandı |

**İkinci tur — sıfırdan eğitim.** Teşhis tarifi belirledi: gövde donduruldu
(93M yerine 0,8M eğitilebilir parametre), her iki sınıfa sosyal medya artırması
uygulandı (JPEG yeniden kodlama, ölçekleme, kırpma) ve afet korpusu negatif
sınıfa katıldı. Eğitim `notebooks/m4_colab.ipynb`, dışa aktarım
`scripts/train/m4_disa_aktar.py`.

| Metrik | Devralınan | **Yeni (devrede)** |
|---|---|---|
| Afet özgüllüğü (kabul kapısı ≥ 0,95) | 0,0051 ✗ | **0,9885** ✓ |
| Afet yanlış pozitif | 0,9949 | **0,0115** |
| Çapraz veri kümesi AUC | 0,7818 | **0,7850** |
| Üretilmiş/gerçek medyan farkı | 0,0167 | **0,9265** |

786 gerçek afet fotoğrafında yanlış alarm **782'den 9'a** düştü.

Daha yüksek başarımlı ikinci bir ağırlık da eğitildi (`models/m4_synthetic_genis`,
çapraz AUC 0,9159). **Devreye alınmadı:** OpenFake'in eğitim bölümüyle eğitilip
test bölümüyle ölçüldüğü için genelleme gücü ölçülemiyor, ve CC BY-NC lisansı
ticari kullanıma kapalı.

### Yol boyunca yakalanan üç sessiz hata

Üçünü de **kabul kapısı** yakaladı; hiçbiri çökmüyordu, yalnızca yanlış sayı
üretiyordu.

1. **int8 niceleme kararı bozuyordu.** Azami logit sapması 2,4152; gerçek afet
   fotoğraflarında P(üretilmiş) medyanı 0,0197'den 0,2552'ye kaydı. Devralınan
   ağırlık buna dayanıyordu çünkü çıktıları zaten doygundu — kaydırılacak bir
   karar yoktu. Yeni model fp32 dağıtılıyor (355 MB).
2. **Eğitim ortamında torch ölçülüp ONNX dağıtılıyordu.** Raporlanan sayı ile
   dağıtılan dosya farklı şeylerdi. Defter artık ONNX ile yeniden ölçüyor.
3. **Çelişki tabanlı çekinme, yetkin olmayan bir detektöre veto hakkı
   veriyordu.** Üç sınıflı detektör her şeye "sentetik" dediği için, ikili
   detektör gerçek bir fotoğrafa doğru şekilde "gerçek" dediğinde kural bunu
   çelişki sayıp susuyordu: afet korpusunda çekinme oranı **%96,18**. Kural
   kaldırıldı, üç sınıflı detektör isteğe bağlı hâle getirildi.

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

**Çıkarım yığınının sürümleri sabittir** (`libs/krizkalkan-core/pyproject.toml`
· `models` grubu). Alt sınırla bırakıldığında iki makine farklı sürüm kurup
farklı sayı üretiyordu: aynı ağırlık, aynı veri ve aynı tohumla M5 Recall@1
0,8929 yerine 0,8571, M8 zor küme ARI 0,5742 yerine 0,4290 ölçüldü. ONNX
kullanmayan M1 ise birebir aynı kaldı (0,9950 · 0,6737 · 0,0100) — fark int8
çıkarımın sınırdaki kararlarından geliyor. Bu belgedeki ve
`docs/metrikler/` altındaki bütün sayılar sabitlenmiş sürümlerle üretildi;
sürüm değişirse ölçümlerin tamamı yeniden koşturulmalıdır.

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

### M4'ün ölçülmemiş yarısı: kapı bir yanı ödüllendiriyordu

| | |
|---|---|
| **Beklenti** | `afet_ozgulluk ≥ 0,95` kabul kapısı M4'ün afet alanındaki yetkinliğini güvence altına alıyordu |
| **Ölçüm** | Kapı yalnızca **yanlış pozitifi** ölçüyor. Doğru pozitif hiç ölçülmemişti — üretilmiş afet görselinden oluşan bir küme yoktu |
| **Bulgu** | Küme kuruldu (n=35). Model **0/35** yakalıyor; P(üretilmiş) medyanı 0,0259 |
| **Karar** | Ölçüm kalıcı hâle getirildi (`afet_duyarlilik`), model kartına ve rapora yazıldı. Kapı **değiştirilmedi** — değiştirmek M4'ü yarışma öncesi devreden çıkarırdı; karar takımındır |

Kapının tek yanlı olması yapısal bir kusurdur: **her görüntüye "gerçek" diyen
bozuk bir model `afet_ozgulluk` metriğinden 1,0000 alır.** Mevcut model tam da
o yöne kaymış durumda ve kapı bunu göremiyordu.

Muhtemel sebep eğitim kümesinin kuruluşunda: afet korpusu **negatif** sınıfa
kondu, pozitif sınıfta hiç afet içeriği yoktu. Model büyük olasılıkla
"afet sahnesi → gerçek" kısayolunu öğrendi. Yanlış alarmların 782/786'dan
9/786'ya düşmesi ile bu kör nokta **aynı madalyonun iki yüzü**.

İki model de aynı kör noktayı taşıyor: `temiz` 0/35, `genis` 2/35. Ortak
sebep ikisinde de aynı: afet korpusu negatif sınıfta.

Düzeltme yolu ölçüldü ama uygulanmadı: pozitif sınıfa üretilmiş afet görseli
konmalı. Elimizde 35 tane var; eğitim için birkaç yüz gerekir.

### Kalibrasyon bir sinyali sessizce kesebilir

M6 kümesine SENTETİK_MEDYA eklendikten sonra `synthetic.video` ilk kez
kalibre edilebildi. Öğrenilen eşleme ham **1,0000**'i **0,3294**'e gönderiyordu:
kümede model gerçekten ayrıştırmadığı için isotonic doğru öğrenmişti. Ama o
sonuç alanla sınırlıydı ve küresel eşleme olarak yazılsaydı — karar eşiği 0,62
olduğundan — **M4 sinyali bir daha hiç ateşleyemezdi.**

Hata vermeden. Tam olarak köken kalibrasyonunda yaşanan sorunun aynısı.

`scripts/eval/m6_fusion.py` artık eşlemenin tavanını karar eşiğiyle
karşılaştırıyor ve ulaşamıyorsa **yazmayı reddediyor**. Üretimdeki eşlemenin
ateşleyebildiği ayrıca testle kilitli
(`test_fusion_kalibrasyon_kilidi.py`).

---

## 7. Bilinen boşluklar

- **M2 · AV senkron ve konuşmacı–yüz** kurulmadı. Ses–görüntü veri kümeleri
  EULA gerektiriyor.
- **M4 · tür ayrımı** (SENTETİK_MEDYA ↔ MANİPÜLE_MEDYA) yapılamıyor. Üç sınıflı
  detektör ölçüldü ve kullanılamaz bulundu; kaldırıldı. Ayrımı yapacak yeni bir
  model eğitilmedi.
- **M4 · hata seviyesi analizi** kuruldu, ölçüldü ve **devreye alınmadı**:
  ayrım gücü AUC 0,5805 ile rastgeleden farksız; yöntem yapıştırmayı değil
  görüntünün doğal doku değişimini ölçüyor (`docs/metrikler/m4-ela.md`).
- **M4 · video ve ses** kurulmadı. Video için kare çıkarımı (ffmpeg) yok; ses
  için ASVspoof üzerinde eğitim planlı.
- **M4 · ALAN KÖR NOKTASI (en ciddi açık).** Model üretilmiş afet
  görsellerinin **%0,0'ını** yakalıyor (n=35, eşik 0,50). Genel yapay
  görüntüde çalışıyor (çapraz AUC 0,7871; OpenFake sahtelerinde medyan skor
  0,5152), kriz alanında çalışmıyor. Ayrıntı: *M4'ün ölçülmemiş yarısı* bölümü.
- **MANİPÜLE_MEDYA** sınıfı uçtan uca değerlendirme kümesinde yok — M2'yi
  gerektiriyor. Makro-F1 bu nedenle rapor 3.2'deki altı sınıflı hedefle
  doğrudan karşılaştırılamaz. SENTETİK_MEDYA sınıfı **eklendi** (n=35).
- **`synthetic.video` kalibrasyonu** hâlâ elle yazılmış noktalarla çalışıyor.
  Ölçüm yapıldı ama **yazılmadı**: M6 kümesinden öğrenilen eşleme ham 1,0000'i
  0,3294'e gönderiyordu ve karar eşiği 0,62 olduğu için sinyali ateşleyemez
  hâle getiriyordu. `m6_fusion.py` artık böyle bir eşlemeyi reddediyor.
- **8 etiketli manipülatif söylem başlığı** eğitilmedi; sistem sözlük yolunu
  kullanıyor. Provokatif çerçeveleme sınıfının düşük başarımının sebebi budur.
- **Video hattı** ffmpeg gerektiriyor ve gecikme ölçümü yalnızca görsel/metin
  içeriğini kapsıyor.
- **M8 zor küme ARI'si küçük örneklemde kırılgan.** n=56, ~28 gerçek grup ve
  `min_cluster_size=2` ile tek bir gömmenin kıl payı kayması kümeyi bölüp
  ARI'yi büyük oynatıyor. Ölçülen 0,4290 değeri bu kırılganlıkla birlikte
  okunmalı; kolay kümede (n=120) aynı yöntem 1,0000 veriyor. Kümenin
  büyütülmesi bu sayıyı anlamlı kılacak tek yoldur.
- **Taşınabilirlik tuzağı: konumsal dosya adları.** `fetch_provenance.py`
  görüntüleri indirme sırasına göre numaralandırıyor; Commons kategorileri
  değiştiği için aynı ad iki koşuda farklı görüntüye denk gelebiliyor. Köken
  indeksi ve uçtan uca küme bu adlara bağlı olduğundan, veri ile ağırlık ayrı
  kanallardan taşındığında ölçümler sessizce bozuluyor. `ProvenanceIndex` artık
  bunu yüklenirken tespit edip hata basıyor; kalıcı çözüm, adların içerikten
  türetilmesi olurdu.
- **Türkçe etiketli yardım çağrısı kümesi** yok. Kural 0'ın Türkçe duyarlılığı
  ölçülmemiş durumda; bu, sistemin en kritik ölçülmemiş büyüklüğü.
