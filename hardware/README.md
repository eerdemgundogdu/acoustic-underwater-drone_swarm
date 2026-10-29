# Akustik Suru Dugum Karti (Rev A)

2 katmanli (110x85 mm, FR-4, 1.6 mm, 1 oz bakir) tasiyici ve analog on-uc (AFE) PCB tasarimi.

Kart uzerindeki alt devreler:

- Piezo hasat / HV tampon girisi (`J1`): 1 A PTC sigorta (`F1`), ters polarite ve geri akim onleyici Schottky (`D1` SS16), cift yonlu TVS (`D2` SMBJ30CA) ve 47 uF depolama kondansatoru (`C1`).
- Regülator katlari (`U1`, `U2`): `LMR16006X` (700 kHz, 5 V step-down) ve `AP2112K-3.3` (3.3 V dusuk gurultulu analog/sensor LDO). USB ile kart beslemesi arasinda `D4` (B5819W) izolasyonu bulunur.
- Hidrofon analog girisi (`J2`): 10k/10k gerilim bolucu (`R21`, `R22`), 100 nF anti-aliasing RC filtre (`C11`, kesim frekansi ~318 Hz) ve `BAT54S` ciftli Schottky ADC koruma klempi (`D6`, Pin 16 / A2).
- I2C sensor hatti (`J3`): 4.7k pull-up (`R17`, `R18`) ve 33 ohm seri hat direncleri (`R19`, `R20`, Pin 18/19).
- 6 kanal transduser / eyleyici / BFSK modem cikisi (`J5..J10`): 220 ohm seri direnc ve uyku modunda kacak akimi onleyen 100k pull-down.
- Su sizinti probu (`J4`) ve batarya/hasat gerilim bolucusu (`R26` 68k, `R27` 10k, `D7` BZT52C3V3, Pin 14 ve Pin 15).
- Manyetik kurma/emniyet anahtari (`J11`) ve kontaktor surucusu (`J12`, `Q2` BCP56-16, `D10` SS16): NC manyetik reed anahtar bobinle seri baglidir; miknatis cekilmeden veya kurma halkasi acikken kontaktor yazilimdan bagimsiz olarak enerjilenemez (`T_KILL_SENSE` Pin 36).

## Dosyalar

- `DESIGN.md`: Devre hesaplari, filtre kesim frekanslari ve parca secim notlari.
- `WIRING.md`: Konnektor ve Teensy 4.1 pin baglantilari.
- `acoustic-swarm-node/`: KiCad 7/9 proje, sematik (`.kicad_sch`) ve PCB (`.kicad_pcb`) dosyalari.
- `output/`: Gerber + delik arsivi, BOM, dizgi (CPL) CSV, sematik PDF ve DRC raporu.
- `gen/`: Tek kaynak netlist (`design.py`) uzerinden sematik ve PCB'yi ureten betikler.

Yeniden uretmek icin:

```bash
cd hardware/gen
python3 build.py
```
