# Akustik Suru Dugumu (acoustic-underwater-drone_swarm)

Deniz tabanina birakilan, aylarca pille bekleyen pasif akustik dinleme dugumu: gemi/arac gurultusuyle uyanir, pervane imzasini LOFAR ve DEMON ile cikarir, sonucu 24/28 kHz BFSK akustik modemle komsu dugumlere cok atlamali (multi-hop) olarak yayar. Uyku akimini piezo dalga/akinti hasadi destekler.

![Akustik suru dugum karti (KiCad 3B render)](hardware/images/node-iso.png)

Sistem uc katmandan olusur:

- Donanim (`hardware/`): Teensy 4.1 tasiyici + hidrofon AFE + uyanma devresi + piezo hasadi + modem H-koprusu (2 katman, 120x95 mm, KiCad 9).
- Firmware (`firmware/`): 192 kHz cift ADC DMA ornekleme, akisli LOFAR/DEMON islemcileri, Goertzel tabanli BFSK alici, SipHash etiketli mesh protokolu ve guc durum makinesi.
- Model (`dsp/`): Bilesen degerlerinden AFE yaniti, uyku akim butcesi ve akustik baglanti butcesi; sematik ile firmware sabitlerinin tutarliligini test eder.

> **Durum:** Kart Rev A tasarim asamasindadir; uretilmedi ve donanimda test edilmedi. DSP ve modem zinciri sentetik sinyallerle (192 kHz) host testlerinde dogrulandi; firmware Teensy 4.1 icin derlenir. IFF kural seti bir demodur, saha imza kutuphanesi degildir.

## Calisma Dongusu

1. Uykuda yalnizca hep acik alan (~7 uA) calisir: `MCP6042` iki kademe ~60 dB (5..450 Hz) + tepe dedektoru + `TLV7031` karsilastirici.
2. Esik asilinca karsilastirici `LMR16006X` buck'i acar; RC mandal Teensy acilisina (~0.4 s) kadar gucu tutar, Teensy `PWR_HOLD` (pin 23) ile devralir.
3. Teensy, AFE'nin 20 dB ve 40 dB cikislarini ADC0/ADC1'de ayni anda 192 kHz'te DMA ile ornekler; `DualGainSelector` kirpilmayan kanali secer.
4. LOFAR (~2 s) ve DEMON (~2.7 s) sonucu `classify_signature` ile siniflandirilir. Hedef bulunursa dugum kendi TDMA yuvasinda alarm yayinlar.
5. Komsu dugumlerden gelen cerceveler dogrulanir (CRC-16 + SipHash-2-4), TTL > 0 ise tekrar yayinlanir.
6. Son aktiviteden 30 s sonra `PWR_HOLD` birakilir; buck kapanir, kart uykuya doner.

## Firmware (`firmware/`)

- `acoustic_dsp.cpp`: Radix-2 FFT, Hanning, Two-Pass Split-Window CFAR beyazlatma.
  - `LofarProcessor`: 192 kHz -> (4. derece Butterworth, /16) -> (/6) 2 kHz, 1024 noktalik FFT, 4 spektrum ortalamasi, 20..700 Hz tepe arama.
  - `DemonProcessor`: 4..30 kHz bant geciren -> kare-yasasi zarf -> /64 ortalama -> (LP 150 Hz, /8) 375 Hz -> 1024 noktalik FFT. Saft (2.5..11.5 Hz) ve N = 3..7 kanat harmonigi; yanlis alarm olasiligi ~7e-4 olacak sekilde 10 dB esik.
  - `DualGainSelector`: 20/40 dB AFE kanal secimi, kirpilma sonrasi 256 ornek histerezis.
- `dsp_filter.cpp`: RBJ biquad, 4. derece Butterworth, desimatorler.
- `bfsk_modem.cpp`: Verici bit plani (16 bit preamble + cerceve). Alicida 192 noktalik Goertzel (24/28 kHz tonlar + 20/32 kHz bant disi gurultu referansi), ceyrek sembol adimli 4 zamanlama seridi, `0xA55A` senkron kelimesi, verici sirasinda alici susturma.
- `swarm_mesh.cpp`: 20 baytlik cerceve, SipHash-2-4 (128 bit anahtar, 32 bit etiket) + CRC-16-CCITT, (kaynak, sira) halka tamponuyla tekrar eleme, TTL ile cok atlamali aktarim, dugum kimligine gore 250 ms TDMA yuvasi.
- `power_manager.cpp`: `BOOT / LISTEN / SHUTDOWN / FAULT_LEAK / LOW_BATT` durum makinesi; dinleme penceresi, alarm hiz siniri, sizintida periyodik alarm, dusuk pilde kapanma.
- `teensy_node/main.cpp`: Teensy entegrasyonu (`ADC` + `AnalogBufferDMA`, `IntervalTimer` ile sembol sembol BFSK yayini).

## Donanim (`hardware/`)

- 4S Li-ion girisi: 2 A sigorta, seri NC reed kurma anahtari, SS26 ters kutup, SMBJ20CA TVS.
- Hep acik alan: `HT7533-1` (30 V giris, 2.5 uA) ve piezo hasadi (BAT54S kopru + 22 uF + 18 V kiskac + ikinci `HT7533-1`), `BAT54C` diyot-VEYA.
- Uyanma mandali: `WAKE_CMP` VEYA `PWR_HOLD` -> 1 s RC -> `LMR16006X` `EN`.
- Hidrofon AFE: `MCP6022` x2, 20 dB + Sallen-Key 39.7 kHz (Q 0.74) + 20 dB, 100 ohm / 2.2 nF ADC surme ve BAT54S kiskaclari; `LP5907` dusuk gurultulu analog besleme.
- Modem vericisi: `DRV8871`, FlexPWM 24/28 kHz, 62k ILIM (~1 A), DC blok kondansatoru; eslesme trafosu ve projektor kart disi.
- Uykuda sifir akimli pil olcumu (`AO3401A` + `2N7002` yuksek taraf anahtari).

Tasarim hesaplari `hardware/DESIGN.md`, konnektor tablolari `hardware/WIRING.md`, uretim dosyalari (Gerber, BOM, CPL, sematik PDF, DRC raporu) `hardware/output/` altindadir.

## Derleme ve Testler

Donanim olmadan calisan C++ ve Python testleri:

```bash
cmake -S firmware/test -B build/test && cmake --build build/test && ctest --test-dir build/test --output-on-failure

python3 dsp/test_node_model.py
python3 dsp/node_model.py          # AFE yaniti, akim butcesi, baglanti butcesi ozeti
```

Teensy 4.1 derlemesi:

```bash
cd firmware
pio run -e node      # Rev A kart: uyanma/uyku dongusu
pio run -e bench     # Tezgah: USB beslemede surekli uyanik
```

Saha icin suru anahtari uretme:

```bash
python3 scripts/gen_swarm_key.py      # build_flags satirini yazar
```

Tezgah testi adimlari: `docs/tezgah_testi.md`.
