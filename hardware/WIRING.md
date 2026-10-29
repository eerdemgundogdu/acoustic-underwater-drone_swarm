# Konnektör ve Kablolama Kılavuzu (`WIRING.md`)

## Konnektör Özeti

| Ref | Etiket | Tip | Pin 1 | Pin 2 | Pin 3 | Pin 4 |
|---|---|---|---|---|---|---|
| `J1` | `PIEZO/HV` | Phoenix MKDS 5.08 mm 2P | `VBAT_IN` (+12..26 V) | `GND` | — | — |
| `J2` | `HIDROFON AFE` | JST-XH 3P | `+5V` (Preamp Besleme) | `GND` | `DEPTH_RAW` (Akustik Çıkış) | — |
| `J3` | `AKUSTIK I2C` | JST-XH 4P | `+3V3` | `GND` | `SCL` (Pin 19) | `SDA` (Pin 18) |
| `J4` | `SIZINTI PROBU` | JST-XH 2P | `LEAK_P` (+3.3 V, 10k üzerinden) | `LEAK_NODE` (Pin 14 / A0) | — | — |
| `J5..J8` | `AKUSTIK CH0..CH3` | JST-XH 3P | `GND` | `NC` (İzole) | `PWM0..PWM3` (Pin 2..5) | — |
| `J9..J10` | `SWARM BFSK TX0..1` | JST-XH 3P | `GND` | `NC` (İzole) | `PWM4..PWM5` (Pin 6..7) | — |
| `J11` | `ARM-SW (NC)` | JST-XH 2P | `+24V` | `KILL_RET` | — | — |
| `J12` | `MODEM KONTAKTOR` | JST-XH 2P | `KILL_RET` | `COIL_N` (`Q2` Collector) | — | — |

## MCU (`U3` — Teensy 4.1 / Cortex-M7 DSP) Pin Eşlemesi

| Teensy Pin | Sinyal Adı | İşlev |
|---|---|---|
| `Pin 2..5` | `T_PWM0..T_PWM3` | 4-kanal akustik faz dizisi / yerel eyleyici PWM çıkışları |
| `Pin 6..7` | `T_PWM4..T_PWM5` | Ultrasonik BFSK sürü (swarm) akustik modem taşıyıcı çıkışları (`24 kHz / 28 kHz`) |
| `Pin 11` | `T_LED` | Akustik IFF kilit / durum LED'i (`D9`, mavi) |
| `Pin 14 (A0)` | `T_LEAK_ADC` | Basınç tüpü su sızıntı probu ADC girişi |
| `Pin 15 (A1)` | `T_BATT_ADC` | Piezo enerji hasadı / tampon batarya gerilim ölçümü (`68k/10k` bölücü) |
| `Pin 16 (A2)` | `T_DEPTH_ADC` | Hidrofon AFE analog girişi (DMA zamanlayıcı tetiklemeli örnekleme) |
| `Pin 18 / 19` | `T_SDA0 / T_SCL0` | 400 kHz I2C akustik/ataletsel yönelim sensörü |
| `Pin 36` | `T_KILL_SENSE` | Manyetik kurma/emniyet anahtarı (`J11`) durum algılama |
| `Pin 37` | `T_BUZZER` | Akustik işaret / hata ping vericisi (`BZ1`) |
| `Pin 38` | `T_ESC_EN` | Kontaktör bobin sürücüsü (`Q2` `BCP56-16`) |
