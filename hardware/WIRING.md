# Kablolama — Akustik sürü düğümü Rev A

Sızdırmaz basınç gövdesi içindeki her konnektörün pin pin nereye gittiği. Pin 1, kart üzerinde kare pedli olan pindir. JST XH konnektörler kilitlidir, ters takılamaz.

> **Rev A henüz üretilmedi ve test edilmedi.** İlk enerji vermeden önce [DESIGN.md](DESIGN.md) bölüm 12'deki devreye alma adımlarını uygulayın.

## Güç ve güvenlik

### J1 — 4S Li-ion pil girişi (vidalı klemens, 5.08 mm)

| Pin | Net | Bağlantı |
|----|-----|----------|
| 1 | `VBAT_IN` | Pil paketi + (paket BMS çıkışı) |
| 2 | `GND` | Pil paketi − |

### J2 — Kurma (arming) reed anahtarı (JST XH 2p)

| Pin | Net | Bağlantı |
|----|-----|----------|
| 1 | `VBAT_F` | Gövde dışına yakın monte edilmiş **NC** reed anahtar, uç 1 |
| 2 | `ARM_RET` | NC reed anahtar, uç 2 |

Taşıma mıknatısı gövdenin üstüne takılıyken kontak açıktır ve kart pilden tamamen ayrıktır. Denize indirmeden hemen önce mıknatıs çıkarılır; kart uyku moduna girer (~7 µA).

## Akustik

### J4 — Hidrofon (JST XH 3p)

| Pin | Net | Bağlantı |
|----|-----|----------|
| 1 | `HYD_SIG` | Pasif piezo hidrofon sıcak ucu (−200 dB re 1 V/µPa sınıfı) |
| 2 | `GND` | Hidrofon soğuk ucu |
| 3 | `GND` | Kablo ekranı (yalnızca kart tarafında bağlanır) |

Aynı sinyal hem uyanma yükseltecine (`C13`) hem ana AFE'ye (`C28`) gider; iki yolun da DC bias'ı ayrıdır.

### J5 — Modem transdüseri (JST XH 2p)

| Pin | Net | Bağlantı |
|----|-----|----------|
| 1 | `TX_P` | Eşleştirme trafosu primeri, uç 1 (`C40` DC blok sonrası) |
| 2 | `TX_OUT2` | Eşleştirme trafosu primeri, uç 2 |

Trafo (1:5) ve ~25 kHz rezonanslı projektör kart dışında, kablo ucundaki kılıf içindedir. Tezgâh testinde transdüser yerine 10 Ω / 5 W direnç bağlanır.

### J3 — Piezo hasat elemanı (JST XH 2p)

| Pin | Net | Bağlantı |
|----|-----|----------|
| 1 | `PZ1` | PVDF/PZT şerit, uç 1 |
| 2 | `PZ2` | PVDF/PZT şerit, uç 2 |

Polarite önemsiz; `D14`/`D15` tam dalga köprüdür.

## Gövde

### J6 — Su sızıntı probu (JST XH 2p)

| Pin | Net | Bağlantı |
|----|-----|----------|
| 1 | `LEAK_P` | Elektrot 1 (`+3V3A`'dan 10 kΩ ile beslenir) |
| 2 | `LEAK_NODE` | Elektrot 2 (47 kΩ ile `GND`'ye, 1 kΩ ile Pin 14 / A0) |

## Teensy 4.1 pin eşlemesi

| Pin | Net | Yön | İşlev |
|-----|-----|-----|-------|
| 6 | `T_TX_IN1` | Çıkış | `DRV8871 IN1`, FlexPWM2.2A, 24/28 kHz BFSK taşıyıcı |
| 9 | `T_TX_IN2` | Çıkış | `DRV8871 IN2`, FlexPWM2.2B, yarım köprü modunda LOW |
| 12 | `T_HARV_PG` | Giriş | Piezo hasat çıkışı var (`V_HARV` 10 kΩ üzerinden) |
| 13 | `T_LED` | Çıkış | `D13` durum LED'i (Teensy dahili LED ile paralel) |
| 14 / A0 | `T_LEAK_ADC` | Analog | Sızıntı probu |
| 15 / A1 | `T_BATT_ADC` | Analog | Pil gerilimi, 100k/15k (yalnızca `BATT_EN` HIGH iken) |
| 16 / A2 | `T_ADC_LO` | Analog | AFE 20 dB çıkışı (ADC1, DMA) |
| 17 / A3 | `T_ADC_HI` | Analog | AFE 40 dB çıkışı (ADC0, DMA) |
| 21 | `T_WAKE` | Giriş | Uyanma karşılaştırıcısı çıkışı (10 kΩ üzerinden) |
| 22 | `T_BATT_EN` | Çıkış | `Q2`/`Q1` pil bölücü anahtarı |
| 23 | `T_PWR_HOLD` | Çıkış | `D6` üzerinden `BUCK_EN`; açılışta ilk iş HIGH yapılır |
| VIN | `TEENSY_VIN` | Güç | `+5V`, `D9` (B5819W) üzerinden |

Teensy'nin 3.3 V pinleri kullanılmaz. USB takılıyken kart 5 V'u ile USB 5 V'u `D9` sayesinde birbirini geri beslemez; tezgâhta USB ile çalışırken `bench` firmware'i kullanılır.
