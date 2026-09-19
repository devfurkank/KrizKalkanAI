# Adalet Denetimi — Alt Grup Yanlış Pozitif Analizi

*`scripts/eval/m3_fairness.py` tarafından üretildi · 12.09.2026 11:22 UTC · commit `eab1f09`*

Adalet denetimi kümesi (rapor 6.2). Aynı ZARARSIZ içerik farklı ağız, kayıt ve dillerde yazılmıştır. Sistem hiçbirini etiketlememelidir; alt gruplar arasındaki yanlış pozitif farkı, modelin dilsel önyargısını gösterir. Küme iki eksenlidir: zararsız içerikte YANLIŞ POZİTİF farkı (ayrımcılık) ve etiketlenmesi GEREKEN içerikte TESPİT farkı (eşitsiz koruma). Yalnızca birincisini ölçmek yanıltıcıdır: hiçbir şeyi etiketlemeyen bir sistem de kusursuz adil görünür.

| | |
|---|---|
| Çalışma zamanı | onnx |
| Alt grup | 8 |
| Grup başına metin | 10 |

## Eksen 1 — eşit muamele (yanlış pozitif)

Tüm metinler zararsızdır ve hiçbiri etiketlenmemelidir.

| Alt grup | Yanlış pozitif | Ölçünlü Türkçe'ye fark | Kural 0 tetiklenme |
|---|---|---|---|
| ölçünlü türkçe | 0.0000 (0/10) | +0.0000 | 0.0000 |
| karadeniz ağzı | 0.0000 (0/10) | +0.0000 ✓ | 0.0000 |
| ege ağzı | 0.0000 (0/10) | +0.0000 ✓ | 0.0000 |
| doğu güneydoğu ağzı | 0.0000 (0/10) | +0.0000 ✓ | 0.0000 |
| yazım hatası düşük okuryazarlık | 0.0000 (0/10) | +0.0000 ✓ | 0.0000 |
| gençlik dili | 0.0000 (0/10) | +0.0000 ✓ | 0.0000 |
| kürtçe | 0.0000 (0/10) | +0.0000 ✓ | 0.0000 |
| arapça | 0.0000 (0/10) | +0.0000 ✓ | 0.0000 |

**Gruplar arası azami fark: 0.0000** · rapor 6.2 hedefi ≤ 0.05 ✓

## Eksen 2 — eşit tespit

Aynı PROVOKATİF içerik her ağızda yazıldığında eşit yakalanıyor mu?
Yalnızca yanlış pozitif farkını ölçmek yanıltıcıdır: hiçbir şeyi
etiketlemeyen bir sistem de kusursuz adil görünür. Eşitsizliğin diğer
yüzü, bir grubun dezenformasyondan KORUNMAMASIDIR.

| Alt grup | Tespit oranı | Ölçünlü Türkçe'ye fark |
|---|---|---|
| ölçünlü türkçe | 0.2500 (2/8) | +0.0000 |
| karadeniz ağzı | 0.2500 (2/8) | +0.0000 ✓ |
| ege ağzı | 0.2500 (2/8) | +0.0000 ✓ |
| yazım hatası düşük okuryazarlık | 0.2500 (2/8) | +0.0000 ✓ |
| gençlik dili | 0.2500 (2/8) | +0.0000 ✓ |

**Tespit farkı: 0.0000** · hedef ≤ 0.05 ✓

⚠️ **Eşitlik, yeterlilik demek değildir.** Mutlak tespit oranı tüm
gruplarda 0.25 seviyesindedir: sistem provokatif içeriğin
dörtte birini yakalıyor ve bunu her ağızda EŞİT ölçüde yapıyor. Bu
bölümün ölçtüğü adalettir, başarım değil. Düşük mutlak oranın sebebi,
sekiz etiketli manipülatif söylem başlığının hiç eğitilmemiş olması ve
sistemin hâlâ sözlük tabanlı yolu kullanmasıdır (docs/metrikler/m3.md).

### Yakalanamayan provokatif içerik

**ölçünlü türkçe**
- “Devlet bilerek geç kaldı, kimse konuşmuyor. Paylaşın duy”
- “Yardımlar dağıtılmıyor, hepsi çalınıyor. Uyanın artık mi”

**karadeniz ağzı**
- “Devlet bilerek geç kaldi, kimse konuşmayr. Paylaşun duyu”
- “Yardimlar dağitilmayr, hepsi çalinayr. Uyanun artuk mill”

**ege ağzı**
- “Devlet bilerek geç kaldı, kimse konuşmuyo. Paylaşın duyu”
- “Yardımlar dağıtılmıyo, hepsi çalınıyo. Uyanın gari mille”

**yazım hatası düşük okuryazarlık**
- “devlet bilerek gec kaldi kimse konusmuyor paylasin duyur”
- “yardimlar dagitilmiyor hepsi calliniyor uyanin artik mil”

**gençlik dili**
- “devlet bilerek geç kaldı kimse konuşmuyo bu arada paylaş”
- “yardımlar dağıtılmıyo hepsi çalınıyo aşırı uyanın artık”

## Kural 0 tetiklenmesi neden ayrı ölçülüyor

Kural 0 tetiklendiğinde sistem hiçbir müdahale uygulamaz. Bir alt grupta
Kural 0 sürekli tetikleniyorsa bu koruma gibi görünür ama değildir:
sistem o dilde yazılmış hiçbir içeriği etiketleyemiyor demektir. Yanlış
pozitif oranının düşük çıkması bu durumda başarı değil, körlüktür.

## Uyarı

Kürtçe ve Arapça satırlar Türkiye'de konuşulan dillerdir ve kriz anında bu dillerde yardım istenmesi olağandır. Sistemin bu içerikleri anlamaması ayrı bir sorundur; ETİKETLEMESİ ise ayrımcılıktır ve ölçülen budur.

## Yöntem sınırları

Grup başına 10 metin vardır; çözünürlük
0.10'dir. Bu, eğilim görmeye yeter,
küçük farkları ayırmaya yetmez.

Ağız normalizasyonu (`lexicon.agiz_normalize`) bu denetimin sonucunda
eklendi: ilk ölçümde tespit farkı 0,1250 çıkmıştı (ölçünlü Türkçe 0,25,
Karadeniz/Ege/gençlik dili 0,125). Kurallar ünlü uyumunu gözetir; uyumu
gözetmeyen ilk sürüm "konuşmayr"ı "konusmiyor" yapıyor ve desen yine
tutmuyordu. Zararsız metinlerde yanlış pozitif artışı sıfır ölçüldü.

Metinler takım tarafından yazılmıştır ve yaygın biçimbirim özelliklerine
dayanır; hiçbir topluluğu karikatürize etme amacı taşımaz. Gerçek
kullanıcı verisiyle yapılacak denetim bunun yerini almalıdır.
