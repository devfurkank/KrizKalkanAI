# Etik Protokol

KVKK uyumu, sentetik veri üretimi, adalet ve kötüye kullanıma karşı önlemler

| | |
|---|---|
| Sürüm | 0.1 |
| Kapsam | `libs/krizkalkan-core` analiz modülleri, `apps/api`, `apps/web` |
| Durum | **Taslak.** Hukuki değerlendirmeden geçmedi |

> **Bu belge hukuki görüş değildir.** KVKK ve 5651 sayılı Kanun yükümlülükleri
> için hukuk danışmanı incelemesi gerekir. Belge, sistemin nasıl tasarlandığını
> ve **şu an ne yaptığını** anlatır. Bu ikisinin ayrıştığı yerler bölüm 3'te
> açıkça işaretlidir.

---

## 1. Neden bu belge

Kriz dönemlerinde içerik moderasyonu iki yönde de zarar verebilir. Bir yandan
dezenformasyon can kaybına yol açabilir. Öbür yandan hatalı bir moderasyon
sistemi yardım çağrılarını bastırabilir, muhalif sesleri susturabilir ya da
belirli dil gruplarını orantısız biçimde işaretleyebilir.

KrizKalkan bu riski yapısal kısıtlarla sınırlamaya çalışır. Kısıtlar
politikaya bırakılmaz, doğrudan koda yazılır. Bu belge o kısıtları, uygulanma
durumlarını ve henüz karşılanmayan yükümlülükleri kaydeder.

---

## 2. Değişmez ilkeler

Aşağıdaki dört ilke sistem mimarisine gömülüdür. Bir yapılandırma değişikliğiyle
kapatılamazlar.

### 2.1. Sistem içerik silmez

Sistemin içerik silme ya da erişimi engelleme yetkisi yoktur. Uygulayabileceği
en ağır otomatik eylem, paylaşım öncesinde gösterilen bir sürtünme ekranıdır.
Kullanıcı bu ekranı görse bile içeriğini paylaşabilir.

| Uygulama | Konum |
|---|---|
| Müdahale merdiveninde "silme" seviyesi bilinçli olarak tanımsız | `taxonomy.py · InterventionLevel` |
| `content_removed` alanı hiçbir kod yolunda `True` olmaz | `policy/engine.py` |
| Radar paneli "kaldırılan içerik: 0" sayacını her zaman gösterir | `radar/engine.py` |
| Paylaşım uç noktası analiz sonucundan bağımsız olarak 201 döner | `apps/api/routers/posts.py` |

**Durum:** ✅ Uygulanmış ve testle kilitlenmiş (`test_gonderi_olusturma_engellenmez`).

### 2.2. Kural 0: yardım çağrısı her şeyin önüne geçer

Yardım çağrısı olarak sınıflanan bir içeriğe hiçbir etiket, sürtünme ya da
yavaşlatma uygulanmaz. Bu kural diğer bütün sinyalleri geçersiz kılar.

Eşik bilinçli olarak düşük tutulmuştur. Birkaç dezenformasyon içeriğinin
etiketsiz geçmesi, tek bir yardım çağrısının engellenmesinden daha kabul
edilebilir bir sonuçtur.

**Durum:** ✅ Uygulanmış. Karar şu an **sözlük tabanlı** yoldan veriliyor.
Modelin yardım çağrısı başlığı Kural 0'a bağlanmadı. Gerekçesi ölçüldü (bkz.
`docs/model-kartlari/m3-text.md`): model, Türkçe seferberlik söylemini yardım
çağrısından ayırt edemiyor. "Hepimiz sokağa dökülelim" gibi bir metin sınanan
tüm çalışma noktalarında korumaya alınıyordu. Bu da provokatif içeriğin
etiketsiz kalması anlamına geliyordu.

> ⚠️ **Açık yükümlülük:** Kural 0'ın Türkçe duyarlılığı **ölçülmedi.** Elde
> Türkçe etiketli bir yardım çağrısı kümesi yok. Modelin 0,92 duyarlılığı
> yalnızca İngilizce veride ölçüldü. Sistemin en kritik ölçülmemiş büyüklüğü bu.

### 2.3. Karar insanındır

Otomatik müdahale bağlam kartı ve sürtünme ekranıyla sınırlıdır. Yüksek
yayılım gösteren içerik insan moderatöre yönlendirilir. Bu bir kısıtlama
değildir, yalnızca inceleme kuyruğunda öncelik verir. Moderatör kararları
denetim kaydına yazılır.

**Durum:** ⚠️ Kısmen uygulanmış. Moderatör kuyruğu ve itiraz akışı mevcut.
Denetim kaydı ise **süreç belleğinde** tutuluyor, kalıcı değil (bkz. bölüm 3).

### 2.4. Sistem "bilmiyorum" diyebilir

Kanıt yetersizse sistem sınıf üretmez, çekinir. Çekinen modüller kanıt
panelinde görünür: sistemin neyi bilmediği, neyi bildiği kadar önemlidir.

| Çekinme durumu | Modül |
|---|---|
| Medyada C2PA imzası yok. İmzanın yokluğu içeriğin sahte olduğunu göstermez | M4 |
| Metinden afet türü çıkarılamadı, sahne neyle karşılaştırılacağı belirsiz | M2 |
| Metin sınıflandırma için çok kısa | M3 |
| Ağırlık yok, model kabul eşiğinin altında ya da çalışma zamanı eksik | Tümü |

**Durum:** ✅ Uygulanmış.

---

## 3. KVKK: taahhüt ve uygulama

Teknik raporda (bölüm 4.3) verilen taahhütler ve kodun şu an yaptıkları
aşağıda yan yana gösteriliyor. Bu tablo, jüri ya da denetçi sormadan önce
takımın bilmesi gereken boşlukları gösterir.

| Taahhüt (rapor) | Şu anki durum | |
|---|---|---|
| Ham medya analiz sonrası saklanmaz | Analiz hattı ham medyayı diske yazmıyor | ✅ |
| Yalnızca geri döndürülemez gömmeler ve karmalar tutulur | Analiz önbelleği `AnalysisResult` nesnelerini tutuyor. Bu nesneler **iddia metninden alıntılar** ve kanıt etiketlerinde **kullanıcı metninden parçalar** içeriyor | ❌ |
| Varsayılan saklama 24 saat, sonra imha | Önbellekte süre sınırı yok, süreç yaşadığı sürece büyüyor | ❌ |
| Veri silme talebi akışı arayüzde | Silme uç noktası yok | ❌ |
| Yurt içi işleme | Çıkarım yerel ve CPU üzerinde. Harici API çağrısı yok | ✅ |
| Aydınlatma: kullanıcıya analiz yapıldığı bildirilir | Analiz kartı her gönderide görünüyor | ✅ |
| Tüm kararlar denetim kaydına yazılır | Denetim kaydı var, süreç belleğinde. Yeniden başlatmada kayboluyor | ⚠️ |

### 3.1. Kapatılması gereken boşluklar

Bu üç eksik, bir kişisel veri denetiminde ilk sorulacak konular:

1. **Önbelleğe süre sınırı.** `pipeline.py` içindeki `_cache` sözlüğü ya TTL'li
   bir yapıya çevrilmeli ya da yalnızca karma ile sınıf etiketini tutacak
   biçimde küçültülmeli. Önbelleğin amacı tekrarlanan içeriği yeniden analiz
   etmemektir (rapor 4.1). Bunun için sonucun tamamını değil, sınıfı ve
   güveni saklamak yeter.

2. **Önbellekteki metin alıntıları.** `ExtractedClaim.text` ve kanıt
   etiketleri kullanıcının metninden birebir alıntı içeriyor. Önbellekte
   saklandıklarında bu alıntılar kişisel veri kapsamına girebilir. Ya
   önbellekten çıkarılmalı ya da saklama süresi sınırlanmalı.

3. **Silme uç noktası.** Kullanıcının kendi içeriğine ait analiz sonucunu ve
   denetim kaydını silme talebinde bulunabileceği bir akış gerekiyor. Denetim
   kaydının kendisi de silinmeli mi? Bu, denetlenebilirlik ile silme hakkı
   arasında bir gerilim yaratır ve hukuki görüş gerektirir.

### 3.2. Özel nitelikli kişisel veri

Yüz ve ses verisi, 6698 sayılı Kanun'un 6. maddesi uyarınca özel nitelikli
kişisel veridir. Bugünkü sistemde durum şöyle:

- Konuşmacı–yüz uyumu modülü (M2) **kurulmadı.** Yüz ya da ses gömmesi
  hesaplanmıyor.
- Sahne–iddia modülü (M2) görüntünün **tamamını** gömer. Yüz tespiti yapmaz ve
  kimlik çıkarımına yönelik değildir.
- Köken indeksi (M1) yalnızca açık lisanslı referans görüntülerinin 64 bitlik
  algısal karmasını tutar. Bu karmalardan görüntü geri üretilemez.

> **Gömmelerin tersine çevrilebilirliği:** Rapor, gömmelerin "tersine
> çevrilemez" olduğunu belirtiyor. Bu ifade **algısal karmalar için
> doğrudur**, çünkü 64 bitten görüntü geri üretilemez. **Metin gömmeleri
> için bu kadar kesin konuşulamaz.** Akademik çalışmalar metin gömmelerinden
> kaynak metnin kısmen geri üretilebildiğini göstermiştir. Sistem şu an
> kullanıcı metninin gömmesini **saklamıyor**, sorgu anında hesaplayıp
> atıyor. Bu yüzden risk bugün pratikte yok. Gömmeler ileride saklanacaksa bu
> ifade düzeltilmelidir.

---

## 4. Hukuki konum

- **5651 sayılı Kanun:** İçerik sağlayıcı yükümlülükleri platformdadır, bu
  sisteme ait değildir.
- **TCK 217/A:** Halkı yanıltıcı bilgiyi alenen yayma suçudur. Sistemin
  "doğrulanmamış iddia" ya da "yanlış bağlam" sınıfları bu suçun tespiti
  **değildir**. Hiçbir çıktı hukuki bir niteleme olarak kullanılamaz.

**KrizKalkan bir karar destek ve şeffaflık aracıdır. Hukuki hüküm vermez.**
Erişimi engelleme ya da içerik kaldırma yetkisi yalnızca yetkili mercide ve
insan moderatördedir.

Arayüzdeki dil bu konumu yansıtır. Sistem "bu içerik yanlış" demez. Bunun
yerine "resmî kaynaklarda bu iddia teyit edilmiyor" ya da "bu görüntü gerçek
ama güncel olaya ait değil" gibi, kanıtla desteklenen ve doğrulanabilir
ifadeler kullanır.

---

## 5. Adalet ve ayrımcılık

Rapor 6.2, alt gruplar arasındaki yanlış pozitif farkının 5 puanı aşmamasını
taahhüt ediyor. Bu taahhüt ölçüldü. Ayrıntılar `docs/metrikler/adalet.md`
dosyasında.

### 5.1. İki eksenli ölçüm

Yalnızca yanlış pozitif farkını ölçmek yanıltıcı olur, çünkü **hiçbir şeyi
etiketlemeyen bir sistem de kusursuz adil görünür.** Denetim bu yüzden iki
ekseni birlikte ölçer:

| Eksen | Soru | Sonuç |
|---|---|---|
| Eşit muamele | Zararsız içerik bazı gruplarda daha çok mu etiketleniyor? | 8 alt grupta fark **0,0000** |
| Eşit tespit | Dezenformasyon bazı gruplarda daha az mı yakalanıyor? | 5 alt grupta fark **0,0000** |

Denetlenen alt gruplar şunlar: ölçünlü Türkçe, Karadeniz, Ege ve
Doğu/Güneydoğu ağızları, yazım hatalı metin, gençlik dili, Kürtçe ve Arapça.

### 5.2. Denetimin bulduğu ve düzelttiği sorun

İlk ölçümde tespit farkı **0,1250** çıktı, yani hedefin 2,5 katı. Ölçünlü
Türkçe'de provokatif içeriğin 0,25'i yakalanırken Karadeniz, Ege ve gençlik
dilinde bu oran 0,125'e düşüyordu. Kısacası ağız konuşanlar dezenformasyona
karşı **yarı oranda** korunuyordu.

Sorunun kaynağı kök sözcükler değil, çekim ekleriydi. Eğitilmiş model bir
çözüm sunmadı, durumu daha da kötüleştirdi. Model yalnızca ölçünlü Türkçe
veriyle eğitildiği için Karadeniz ağzında 0,000 sonuç verdi. Sorun, ünlü
uyumunu gözeten bir normalizasyon katmanıyla giderildi.

### 5.3. Eşitlik yeterlilik demek değildir

Mutlak tespit oranı bütün gruplarda **0,25** düzeyinde. Sistem provokatif
içeriğin dörtte birini yakalıyor ve bunu her ağızda eşit oranda yapıyor. Bu
bölüm adaleti ölçer, başarımı değil.

### 5.4. Sınırlar

- Grup başına 8 ile 10 metin var, çözünürlük 0,1. Eğilimleri görmeye yeter
  ama küçük farkları ayırmaya yetmez.
- Metinler takım tarafından yazıldı. Gerçek kullanıcı verisiyle yapılacak bir
  denetim bunun yerini almalı.
- Kürtçe ve Arapça içerik **anlaşılmıyor**. Bu dillerde yanlış pozitif sıfır
  çıkıyor, çünkü sistem bu dillerdeki hiçbir içeriği etiketleyemiyor.
  Görünürde koruma var ama gerçekte bu bir körlük. Eşit tespit ekseninde bu
  diller ölçülmedi.

---

## 6. Sentetik veri üretim protokolü

Çok modlu çelişki senaryoları ve demo içeriği için sentetik medya gerekebilir.
Bu kurallar pazarlığa açık değildir:

1. **İzole ortam.** Üretim yalnızca ağa kapalı bir ortamda yapılır ve hiçbir
   çıktı internete yüklenmez.
2. **Zorunlu işaretleme.** Her sentetik dosya dört işaret taşır: (a) görünür
   "SENTETİK — TEST VERİSİ" filigranı, (b) ses damgası, (c) C2PA meta
   verisinde "AI-generated" kaydı, (d) `SYNTH_` dosya adı öneki.
3. **Gerçek kişi yasağı.** Kamu görevlisi, siyasetçi ya da tanınabilir
   herhangi bir gerçek kişinin yüzü veya sesi klonlanmaz. Yalnızca izin
   vermiş takım üyelerinin verisi ya da lisanslı sentetik kimlikler
   kullanılır.
4. **Mağdur görüntüsü yasağı.** Gerçek afet mağdurlarının görüntüleri
   üzerine sahte anlatı kurulmaz.
5. **Dağıtım yasağı.** Sentetik küme kaynak koda ya da herkese açık depoya
   konmaz.
6. **Kayıt.** Üretilen her örnek için amaç, üretici model, üretim tarihi ve
   imha planı kayda geçirilir.
7. **Danışman onayı.** Takım danışmanı bu protokolü yazılı olarak onaylar.

### 6.1. Bugüne kadar üretilen sentetik içerik

Sistemde tek bir sentetik içerik var: **C2PA test dosyası.** `test_c2pa.py`
bu dosyayı çalışma anında üretir. Üretim şöyle işler: düz renkli bir JPEG
oluşturulur ve geçici bir sertifika zinciriyle "yapay zekâ üretimi" olarak
imzalanır.

| Kural | Durum |
|---|---|
| İzole ortam | ✅ Dosya pytest'in geçici dizininde üretilir ve test bitince silinir |
| İşaretleme | ✅ C2PA meta verisinde `trainedAlgorithmicMedia` kaydı var. Görünür filigran gerekmiyor çünkü görüntü düz renk ve içerik taşımıyor |
| Gerçek kişi yasağı | ✅ Görüntüde kişi yok |
| Mağdur görüntüsü yasağı | ✅ Görüntü tek renk bir yüzey |
| Dağıtım yasağı | ✅ Hiçbir ikili dosya depoya girmiyor |
| Kayıt | ✅ Test kaynağının kendisi kayıt işlevi görüyor |
| Danışman onayı | ⏳ Alınmadı |

Uçtan uca değerlendirme kümesi (`scripts/data/build_m6_set.py`) sentetik
medya **içermiyor**. Görüntü tabanlı vakalarda gerçek, açık lisanslı
Wikimedia Commons görüntüleri kullanılıyor. Görüntüler olduğu gibi kalıyor,
yalnızca yanlarına **şablondan üretilen metin** ekleniyor.

---

## 7. Kötüye kullanım senaryoları

| Senaryo | Karşı önlem | Durum |
|---|---|---|
| Sistemin muhalif sesleri susturmak için kullanılması | Silme yetkisi yok. Kararlar denetim kaydına yazılıyor. İtiraz akışı mevcut | ✅ Silme yok · ⚠️ Kayıt kalıcı değil |
| Bir saldırganın gerçek içeriği sistem aracılığıyla "sahte" işaretletmesi | Çekinme mekanizması, dayanıklılık testi ve insan onayı katmanı var | ✅ M1'in 13 dönüşüm altında dayanıklılığı ölçüldü |
| Yardım çağrılarının bastırılması | Kural 0 ve ayrı bir denetim sayacı var | ✅ · ⚠️ Türkçe duyarlılık ölçülmedi |
| Belirli dil gruplarının orantısız biçimde işaretlenmesi | İki eksenli adalet denetimi yapıldı ve ağız normalizasyonu eklendi | ✅ Ölçüldü, fark 0 |
| Resmî duyuruların "yalan" olarak etiketlenmesi | Bilgi havuzunda "resmî kaynak sessiz" ile "yalan" ayrımı yapılıyor. Geri getirmede veto var | ✅ Ölçüldü (bkz. `m5.md`) |
| Tekzip paylaşan kullanıcının dezenformasyon yayıyor sayılması | Yalanlama çerçevesi tespiti yapılıyor | ✅ Testle kilitli |
| Doğru bağlamda paylaşılan arşiv görüntüsünün suçlanması | Köken eşleşmesi tek başına sınıf kurmuyor, bağlam çelişkisi şartı aranıyor | ✅ Testle kilitli |
| Yarım eğitilmiş bir modelin sistemi sessizce bozması | Kabul kapısı var: ölçüm kartı olmayan ağırlık yüklenmiyor | ✅ |
| Modelden kişisel veri sızması | Ham medya saklanmıyor, kullanıcı metninin gömmesi saklanmıyor | ✅ · ❌ Önbellekte metin alıntısı var |

### 7.1. Ölçülen hataların ürüne yansıması

Sistemin yanılma oranları gizlenmez. Bu oranlar metrik raporlarında ve model
kartlarının "bilinen sınırlar" bölümünde yer alır. Özellikle şu üç konu kamuya
açık biçimde beyan edilmelidir:

- Bilgi havuzu iddiaların yalnızca bir kısmını eşleştirebiliyor. Geri kalanlar
  "resmî kaynak sessiz" olarak raporlanıyor. Bu **yalan anlamına gelmez.**
- Provokatif söylem tespiti düşük (0,25). Sekiz etiketli başlık hiç
  eğitilmedi.
- Çıkarım modeli (NLI) eğitildi ama kriz alanında zararlı eşleşme ürettiği
  için **devreye alınmadı.**

---

## 8. Şeffaflık

| Belge | Kapsam | Durum |
|---|---|---|
| Model kartları | Amaç, veri, yöntem, ölçüm ve **bilinen sınırlar** | ✅ M1, M2, M3, M5, M8 (`docs/model-kartlari/`) |
| Veri envanteri | Kaynak, lisans, dağıtım biçimi, uyarılar | ✅ `docs/veri-envanteri.md` |
| Hata beyanı | Modül başına ölçülen yanılma oranları | ✅ `docs/metrikler/` |
| Mimari | Füzyon sırası ve ölçümle alınan kararlar | ✅ `docs/mimari.md` |

Metrik raporları ve model kartları **elle yazılmaz.** Her biri kendisini üreten
betiğin adını, üretim tarihini ve git commit'ini taşır. Böylece bir sayının
nereden geldiği her zaman izlenebilir.

### 8.1. Lisans uyumu

Üç veri kümesi ticari kullanıma kapalı:

| Küme | Lisans | Kullanım |
|---|---|---|
| Turkish Disaster News GeoNLP | CC BY-NC 4.0 | Yalnızca değerlendirmede kullanılıyor, üretim modeline girmedi |
| HumAID | CC BY-NC-SA 4.0 | M3 eğitiminde **kullanıldı** |
| ComplexDataLab/OpenFake | CC BY-NC 4.0 | Yalnızca M4 değerlendirmesinde kullanılıyor, hiçbir ağırlık bu kümeyle eğitilmedi |

> ⚠️ **HumAID ile eğitilen M3 ağırlığı ticari kullanımda sorun
> yaratabilir.** Bu durum raporun iş modeli bölümüyle çelişebilir. Ticari
> dağıtımdan önce ya HumAID'siz yeniden eğitim yapılmalı ya da lisans sahibinden
> izin alınmalı. Konu hukuki görüş gerektirir.
>
> HumAID'in lisansı iki yerde farklı yazılmış: kart üst verisinde
> `cc-by-nc-sa-4.0`, README'nin lisans bölümünde `cc-by-nc-4.0`. İkisi de
> ticari kullanımı yasaklıyor, dolayısıyla sonuç değişmiyor.

**M4 görüntü ağırlıkları ticari kullanıma açıktır.** M3'teki durumun
aksine, sentetik görüntü detektörlerinin zincirinde ticari kısıt yoktur:

| Bileşen | Lisans | Not |
|---|---|---|
| İkili detektör (DeepReality PIN-B2) | MIT | Takım üyesinin kendi projesi; kaynak ve ağırlık aynı elden |
| İkili detektörün eğitim kümesi (OpenDeepfake-Preview) | Apache 2.0 | Ticari kullanıma açık |
| Üç sınıflı detektör (AI-vs-Deepfake-vs-Real-Siglip2) | Apache 2.0 | Harici hazır ağırlık, atıf yeterli |

> Değerlendirme kümesinin (OpenFake, CC BY-NC) lisansı ağırlığa **bulaşmaz**:
> o küme yalnızca ölçüm için okunur, hiçbir parametre ondan öğrenilmez. Ayrım
> önemlidir ve ticari dağıtımda savunulabilir olması için burada yazılıdır.

**MiDe22 lisansı doğrulanmalı.** Veri, `ogozcelik/turkish-fake-news-detection`
adlı bir **aynadan** alındı ve bu ayna MIT lisanslı olarak etiketlenmiş. Özgün
küme METU NLP'ye aittir (`metunlp/MiDe22`, LREC-COLING 2024). Bir aynanın
lisans etiketi, özgün sahibin lisansını geçersiz kılmaz. Özgün lisans
doğrulanmadan MIT kabul edilmemelidir.

---

## 9. Açık yükümlülükler

Bunlar, sistem gerçek kullanıcıyla buluşmadan önce kapatılması gereken
maddeler. Önem sırasına göre:

| # | Yükümlülük | Neden kritik |
|---|---|---|
| 1 | Türkçe etiketli yardım çağrısı kümesi hazırlanıp Kural 0'ın duyarlılığı ölçülmeli | Etik tezin merkezinde yer alıyor ve hiç ölçülmedi |
| 2 | Önbelleğe süre sınırı getirilmeli ve metin alıntıları önbellekten çıkarılmalı | Raporda verilen KVKK taahhüdüyle çelişiyor |
| 3 | Veri silme uç noktası eklenmeli | Raporda verilen KVKK taahhüdüyle çelişiyor |
| 4 | Denetim kaydı kalıcı hâle getirilmeli | "Tüm kararlar denetim kaydında" önleminin dayanağı bu |
| 5 | HumAID lisans sorunu çözülmeli, MiDe22'nin özgün lisansı doğrulanmalı | Ticari dağıtım önünde engel |
| 6 | Kürtçe ve Arapça için eşit tespit ölçülmeli | Bu dillerde sistem şu an kör |
| 7 | Sentetik veri protokolü için danışman onayı alınmalı | Protokolün 7. kuralı |
| 8 | Hukuki inceleme yapılmalı | Bu belge hukuki görüş değildir |

---

*Belge sistemin şu anki durumunu anlatır. Bölüm 3 ve 9'daki boşluklar
kapatıldıkça güncellenmelidir.*
