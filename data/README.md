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
