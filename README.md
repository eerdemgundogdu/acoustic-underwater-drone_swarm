# acoustic-underwater-drone_swarm

Gomulu yazilim, pasif akustik sinyal isleme (LOFAR / DEMON) ve 2 katmanli AFE / enerji hasadi tasiyici kart tasarimi.

Su altinda bekleme modunda (dormant) duran dugumlerin dip akintisi ve dalga hareketlerinden piezoelektrik (PVDF/PZT) enerji hasadi yapmasi, hidrofondan alinan akustik sinyali FFT tabanli dar-bant ve zarf analizinden gecirerek su araclarinin pervane/saft imzasina gore dost-dusman siniflandirmasi yapmasi ve ultrasonik BFSK/TDMA paketleriyle diger dugumlerle haberlesmesi icin yazilmis cekirdek modullerdir.

Saha hidrofon kalibrasyon katsayilari, gercek araclarin akustik imza tablolari ve gorev tetikleme mantigi bu depoda yer almaz. Testlerde sentetik 3-kanatli ve 5-kanatli pervane harmonik modelleri kullanilmistir.

## Yapi

- `firmware/src/acoustic_dsp.cpp`: 1024-nokta Radix-2 Cooley-Tukey FFT, Hanning pencereleme, ortam deniz gurultusunu bastirmak icin Two-Pass Split-Window (TPSW) CFAR beyazlatma, LOFAR tepe izleme ve yuksek frekans kavitasyon bandinin zarfini cozerek saft devri ile kanat gecis frekansini cikaran DEMON (Detection of Envelope Modulation on Noise) modulu.
- `firmware/src/piezo_harvester.cpp`: Dusuk akimli derin uyku (`STATE_DEEP_SLEEP_HARVEST`), pasif akustik esik asiminda uyanma (`STATE_PASSIVE_LISTEN`), FFT siniflandirma (`STATE_DSP_CLASSIFY`) ve komsu dugumlere alarm yayini (`STATE_SWARM_TX_ALERT`) durum makinesi. Kapasitor/tampon bara gerilimini, govde su sizinti probunu ve manyetik emniyet anahtarini denetler.
- `firmware/src/swarm_mesh.cpp`: Su alti akustik kanali icin 16 baytlik ikili paketleme (`0xA5 0x5A` baslik, kaynak dugum ID, sira numarasi, hop/TTL, IFF sinifi, kestirilen kanat sayisi, LOFAR frekansi, SNR, batarya yuzdesi, 16-bit anahtarli FNV-1a dogrulama etiketi ve CRC-16-CCITT). Coklu-yol yankilarinda ayni paketin tekrar yayinlanmasini engelleyen halka tampon ve dugum ID tabanli TDMA gecikmesi icerir.
- `firmware/teensy_node/main.cpp`: Teensy 4.1 (Cortex-M7) uzerinde `IntervalTimer` ile 1024 Hz cift tamponlu (ping-pong) ADC ornekleme ve 24/28 kHz BFSK cikis surucusu.
- `dsp/`: Sinyal isleme ve 48 saatlik enerji hasadi / suru uyanma dongusunun Python dogrulama betikleri (`acoustic_simulator.py`, `test_acoustic_pipeline.py`).
- `hardware/`: KiCad 2 katmanli tasiyici ve analog on-uc (AFE) karti (Rev A, 110x85 mm). Detaylar ve uretim dosyalari `hardware/README.md` ve `hardware/DESIGN.md` icindedir.

## Derleme ve Test

Donanim olmadan C++ ve Python birim testlerini calistirmak icin:

```bash
cmake -S firmware/test -B build/test
cmake --build build/test
ctest --test-dir build/test --output-on-failure

python3 dsp/test_acoustic_pipeline.py
```

Teensy 4.1 hedef derlemesi (PlatformIO):

```bash
pio run -d firmware -e teensy41_acoustic_node
```
