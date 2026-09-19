# data/

Veri dizini. **Ham ve işlenmiş veri asla commit edilmez** (bkz. kök `.gitignore`).

```
data/
├── raw/          indirilen özgün veri setleri (dokunulmaz)
├── interim/      ara işleme çıktıları
├── processed/    eğitime hazır veri
├── external/     üçüncü taraf referans verisi
└── synthetic/    izole ortamda üretilmiş test verisi (dağıtılmaz)
```

Veri seti envanteri (kaynak, lisans, hacim, hedef modül) `docs/veri-envanteri.md` içinde tutulur.

## external/video_afet — M4 video kümesi

729 gerçek + 628 üretilmiş afet videosu (`real/`, `fake/`) ve `kaynak/` altında
dışa aktarımın okuduğu Keras ağırlığı. Bu videolar M4 video modelinin
**eğitim/doğrulama verisidir**; üzerlerinde ölçülen başarım genelleme ölçüsü
değildir (`docs/metrikler/m4-video.md`).

Manifest (sınıf, afet türü, çözünürlük, süre, SHA-256, bölme):
`scripts/data/kumeler/video_afet.json` · üretim: `make m4-video`.
