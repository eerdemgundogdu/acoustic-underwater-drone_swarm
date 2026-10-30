# Tezgâh Testi

Düğümü suya indirmeden önce sistemi tezgâhta (kuru ortamda) test etmek için adımlar. Kart yokken firmware'in büyük bölümü, Teensy 4.1'e elle bağlanmış bir hidrofon ön yükselteci ve sinyal jeneratörüyle denenebilir.

## 1. Host testleri (donanımsız)

```bash
cmake -S firmware/test -B build/test && cmake --build build/test && ctest --test-dir build/test --output-on-failure
python3 dsp/test_node_model.py
```

Beklenen: `test_dsp`, `test_bfsk_modem`, `test_swarm_mesh`, `test_power_manager` ve 15 model testi geçer. `test_dsp` çıktısında sentetik 5 kanatlı pervane için `shaft ~6 Hz, N=5`, 3 kanatlı için `N=3` görülür.

## 2. Teensy'yi kart olmadan çalıştırma

1. `pio run -e bench -t upload` (USB beslemede, dinleme penceresi bitince kapanmaz).
2. Sinyal jeneratörünü 1.65 V DC ofset ve en fazla 100 mVpp genlikle Pin 17'ye (A3, `AFE_HI`) ve Pin 16'ya (A2, `AFE_LO`) bağla.
3. Seri port (115200): her ~2.7 s'de bir `LOFAR ... | DEMON ... | IFF ...` satırı gelir.
   - 145 Hz sinüs → `LOFAR ~145 Hz`, SNR > 15 dB.
   - 20 kHz taşıyıcı, 6 Hz ve 30 Hz ile AM modüle edilmiş gürültü → `DEMON 6 Hz N=5`, `IFF 2`.

## 3. Modem döngü testi (iki Teensy)

1. Birini `-D NODE_ID=1`, diğerini `-D NODE_ID=2` ile derle (aynı `SWARM_KEY_BYTES`).
2. Pin 6 çıkışını 10 kΩ + 1 nF ile diğer Teensy'nin Pin 17'sine bağla (1.65 V ofsetli). Ortak GND.
3. Birinci düğümde hedef imzası verildiğinde ikinci düğümün seri portunda `RX dugum 1 sira N hop 0 IFF 2` görülür.

## 4. Kart ile (Rev A üretildikten sonra)

[hardware/DESIGN.md](../hardware/DESIGN.md) bölüm 12'deki devreye alma sırası uygulanır: önce Teensy'siz uyku akımı (< 10 µA), sonra mandal, Vref, en son firmware.
