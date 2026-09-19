# Veri Envanteri

*Bu dosya `scripts/data/fetch_text.py` tarafından üretilmiştir. Son güncelleme: 08.09.2026 11:02 UTC*

Her kümenin **dağıtım biçimi** kullanılabilirliği belirleyen alandır: yalnızca
tweet kimliği dağıtan kümeler X API hidrasyonu gerektirir ve pratikte
kullanılamaz (ücretli erişim + silinmiş içerik kaybı).

## Özet

| Kod | Küme | Lisans | Biçim | Satır | Durum | Modül |
|---|---|---|---|---|---|---|
| **D1** | DMM Dezenformasyon Bültenleri | CC BY 4.0 | tam metin | 2,810 | ✅ kullanılıyor | M5, M3 |
| **D2** | MiDe22 (Türkçe yanlış bilgi) | MIT | tam metin | 5,066 | ✅ kullanılıyor | M3, M8 |
| **D10** | HumAID (İngilizce kriz tweetleri) | CC BY-NC-SA 4.0 (araştırma) | tam metin | 53,531 | ✅ kullanılıyor | M3 |
| **D5** | Turkish Disaster News GeoNLP | CC BY-NC 4.0 | tam metin | 472 | ⚠️ yalnızca değerlendirme | M3 |
| **D3** | deprem-ml / Açık Yazılım Ağı — niyet | belirtilmemiş | görsel bağlantısı | — | 🔴 kullanılamaz | M3 |
| **D3b** | ctoraman/deprem-tweet-dataset | CC | yalnızca kimlik (hidrasyon gerekir) | — | 🔴 kullanılamaz | M3 |
| **D8** | NLI-TR · SNLI-TR (eğitim) | araştırma (SNLI türevi) | tam metin | 550,152 | ✅ kullanılıyor | M5 |
| **D8b** | NLI-TR · SNLI-TR (doğrulama) | araştırma (SNLI türevi) | tam metin | 10,000 | ✅ kullanılıyor | M5 |

## Ayrıntılar

### D1 — DMM Dezenformasyon Bültenleri

- **Kaynak:** `iletisim/dezenformasyon-bultenleri`
- **Dosya:** `data/train-00000-of-00001.parquet`
- **Lisans:** CC BY 4.0
- **Dağıtım biçimi:** tam metin
- **Hedef modül:** M5, M3
- **Doğrulama:** ✅ 2,810 satır · sütunlar: `id`, `bulletin_number`, `date_published`, `claim`, `fact_check`, `rating_value`, `rating_label`, `claim_url`, `source_url`, `author`

Bilgi havuzunun çekirdeği. Resmî kurum kaynağı, ticari kullanıma açık.

**Uyarılar:**

- rating_label TEK DEĞER içerir ('Yanlış') — DMM yalnızca tekzip yayımlar. DESTEKLİYOR sınıfı için AFAD/valilik duyuruları ayrıca gerekir.
- date_published yalnızca 5 benzersiz değer taşır; bunlar bülten tarihi değil derleme tarihidir. Gerçek zaman sinyali bulletin_number alanıdır (6–1020).
- Metinler PDF çıkarımı kaynaklı satır sonları içerir; normalizasyon zorunlu.

### D2 — MiDe22 (Türkçe yanlış bilgi)

- **Kaynak:** `ogozcelik/turkish-fake-news-detection`
- **Dosya:** `mide22_all_tr.tsv`
- **Lisans:** MIT
- **Dağıtım biçimi:** tam metin
- **Hedef modül:** M3, M8
- **Doğrulama:** ✅ 5,066 satır · sütunlar: `tweet`, `label`

Yol haritasında hidrasyon riski taşıdığı varsayılmıştı; bu ayna TAM METİN içerir ve riski ortadan kaldırır. LREC-COLING 2024 kıyası bu küme üzerinden.

**Uyarılar:**

- Konular Rusya-Ukrayna, COVID-19, mülteciler — afet alanı DEĞİL. İki aşamalı ince ayarın yalnızca 1. aşamasında kullanılır.
- Sınıf dengesizliği: Other 2663 / False 1732 / True 669.

### D10 — HumAID (İngilizce kriz tweetleri)

- **Kaynak:** `QCRI/HumAID-all`
- **Lisans:** CC BY-NC-SA 4.0 (araştırma)
- **Dağıtım biçimi:** tam metin
- **Hedef modül:** M3
- **Doğrulama:** ✅ 53,531 satır · sütunlar: `tweet_text`, `class_label`

Görev A (iddia tipi) ve Görev B2 (yardım_çağrısı) için çapraz dilli taşıyıcı küme. Etiket şeması ClaimType ile neredeyse birebir eşleşir; Türkçe etiketli yardım çağrısı verisi bulunmadığı için kritik hâle geldi.

**Uyarılar:**

- İngilizce — yalnızca çok dilli omurga (XLM-R) ile kullanılabilir.
- CC BY-NC-SA: araştırma/değerlendirme amaçlıdır, ticari modele girmez. Bu ayrım raporda beyan edilir.

### D5 — Turkish Disaster News GeoNLP

- **Kaynak:** `FatmaElik/turkish-disaster-news-geonlp`
- **Dosya:** `train.csv`
- **Lisans:** CC BY-NC 4.0
- **Dağıtım biçimi:** tam metin
- **Hedef modül:** M3
- **Doğrulama:** ✅ 472 satır · sütunlar: `id`, `title`, `text_excerpt`, `url`, `source`, `publish_date`, `year`, `language`, `city`, `district`, `latitude`, `longitude`, `geocode_confidence`, `admin_level`, `hazard_source`, `impact_type`, `damage_level`, `urgency`, `relevance_score`, `humanitarian_categories`, `deaths_reported`, `injured_reported`, `collapsed_buildings`, `data_quality_flags`, `is_core`, `is_extended`, `provenance`

Konum/hasar/aciliyet etiketleri — Görev A değerlendirmesi için.

**Uyarılar:**

- 🔴 CC BY-NC 4.0: TİCARİ KULLANIM YASAK. Üretim modeline SOKULMAZ, yalnızca değerlendirme kümesi olarak kullanılır.

### D3 — deprem-ml / Açık Yazılım Ağı — niyet

- **Kaynak:** `deprem-private/intent_train_v13_anonymized`
- **Dosya:** `data/train-00000-of-00001-9ed7e0e7781e4925.parquet`
- **Lisans:** belirtilmemiş
- **Dağıtım biçimi:** görsel bağlantısı
- **Hedef modül:** M3
- **Doğrulama:** 🔴 kullanılamaz olarak işaretli — atlandı

Yol haritasında yardım_çağrısı kaynağı olarak planlanmıştı.

**Uyarılar:**

- 🔴 İçerik METİN DEĞİL: alanlar image_url + görsel etiketi (ör. 'Enkaz Kaldırma'). Metin niyet/NER verisi erişilebilir değil.
- Sonuç: yardım_çağrısı sınıfı HumAID çapraz dilli aktarımı + elle etiketlenmiş altın küme ile öğrenilecek.

### D3b — ctoraman/deprem-tweet-dataset

- **Kaynak:** `ctoraman/deprem-tweet-dataset`
- **Dosya:** `deprem-tweet-dataset.tsv`
- **Lisans:** CC
- **Dağıtım biçimi:** yalnızca kimlik (hidrasyon gerekir)
- **Hedef modül:** M3
- **Doğrulama:** 🔴 kullanılamaz olarak işaretli — atlandı

Adres/kişi/şehir NER aralıkları içerir — metin olsaydı ideal olurdu.

**Uyarılar:**

- 🔴 Yalnızca tweet_id: metin için X API hidrasyonu gerekir (ücretli, silinmiş içerik geri gelmez). Kullanılmıyor.

### D8 — NLI-TR · SNLI-TR (eğitim)

- **Kaynak:** `boun-tabi/nli_tr`
- **Dosya:** `snli_tr/train/0000.parquet`
- **Lisans:** araştırma (SNLI türevi)
- **Dağıtım biçimi:** tam metin
- **Hedef modül:** M5
- **Doğrulama:** ✅ 550,152 satır · sütunlar: `idx`, `premise`, `hypothesis`, `label`

M5'in DESTEKLİYOR/ÇELİŞİYOR/İLGİSİZ çıkarımını eğitir. Rapor atıfı [15] ile aynı özgün kümedir.

**Uyarılar:**

- Küme betik tabanlı dağıtılır ve datasets>=4 betikleri desteklemez; HF'in otomatik ürettiği `refs/convert/parquet` dalı kullanılır.
- Eğitimde tamamı değil, dengeli altörnekleme (~120k) kullanılacak — Kaggle kotası bütünüyle eğitmeye yetmez.

### D8b — NLI-TR · SNLI-TR (doğrulama)

- **Kaynak:** `boun-tabi/nli_tr`
- **Dosya:** `snli_tr/validation/0000.parquet`
- **Lisans:** araştırma (SNLI türevi)
- **Dağıtım biçimi:** tam metin
- **Hedef modül:** M5
- **Doğrulama:** ✅ 10,000 satır · sütunlar: `idx`, `premise`, `hypothesis`, `label`

NLI 3 sınıf doğruluğu bu küme üzerinde raporlanır (rapor hedefi ≥ 0,80).
