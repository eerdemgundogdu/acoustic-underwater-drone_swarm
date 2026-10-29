# Donanım Tasarım Kararları ve Hesaplamalar (`DESIGN.md`)

Bu belge, `acoustic-swarm-node` (Rev A) kartındaki güç yönetimi, piezoelektrik enerji hasadı tamponlaması, hidrofon analog ön-ucu (AFE) anti-aliasing filtrelemesi ve donanımsal manyetik kurma/emniyet zinciri hesaplarını özetler.

---

## 1. Piezoelektrik Dalga / VIV Enerji Hasadı ve Tampon Bara (`J1`, `D1`, `D2`, `C1`, `U1`)

Deniz tabanında uzun süreli (dormant) bekleme modunda düğüm, dip akıntılarının ve yüzey dalgalarının oluşturduğu girdap kaynaklı titreşimleri (Vortex-Induced Vibration — VIV) PVDF/PZT piezoelektrik kirişlerle elektrik enerjisine dönüştürür:

1. **Doğrultma ve Darbe Koruması:** Piezo hasat katından veya tampon batarya paketinden gelen hat `F1` (`1 A` sıfırlanabilir PTC), `D1` (`SS16`, $V_F \approx 0.42\text{ V}$) ve `D2` (`SMBJ30CA`, $V_{RWM} = 30\text{ V}$, $600\text{ W}$) üzerinden `C1` ($47\ \mu\text{F}$, $63\text{ V}$) depolama kapasitörüne bağlanır.
2. **Depolanan Enerji:**
   $$E_{\text{bank}} = \frac{1}{2} C_1 \left(V_{\text{high}}^2 - V_{\text{low}}^2\right)$$
   Hasat gerilimi $24\text{ V}$'tan $12\text{ V}$'a boşalırken tek darbede $\sim 10.1\text{ mJ}$ enerji aktarılır; bu enerji kısa süreli LOFAR/DEMON FFT sınıflandırma ve BFSK akustik paket gönderimi için tampon sağlar.
3. **5 V Buck (`LMR16006X`) ve 3.3 V AFE LDO (`AP2112K-3.3`):**
   - `R2 = 54.9 kΩ`, `R3 = 10 kΩ` ile:
     $$V_{\text{out}} = 0.765\text{ V} \times \left(1 + \frac{54.9}{10}\right) = 4.965\text{ V}$$
   - `U2` (`AP2112K-3.3`), anahtarlamalı regülatörün $700\text{ kHz}$ anahtarlama gürültüsünü $>60\text{ dB}$ PSRR ile bastırarak hidrofon AFE ve ADC referansına temiz $+3.3\text{ V}$ sağlar.

---

## 2. Hidrofon Analog Ön-Ucu (AFE) ve Anti-Aliasing Filtre (`J2`, `R21`, `R22`, `C11`, `D6`)

Piezoseramik hidrofon ön-yükselteç çıkışı (`J2`, $0.5\text{ V} - 4.5\text{ V}$ dinamik aralıklı, $2.5\text{ V}$ merkez öngerilimli akustik sinyal) MCU'nun $3.3\text{ V}$ toleranslı SAR ADC girişine (`Pin 16 / A2`) uygulanmadan önce ölçeklenir ve filtrelenir:

- **Gerilim Bölücü Kazancı:**
  $$G_{\text{div}} = \frac{R_{22}}{R_{21} + R_{22}} = \frac{10\text{ k}\Omega}{10\text{ k}\Omega + 10\text{ k}\Omega} = 0.500 \quad (-6.02\text{ dB})$$
- **Thevenin Eşdeğer Direnci ve Kesim Frekansı:**
  $$R_{\text{th}} = R_{21} \parallel R_{22} = 5\text{ k}\Omega, \qquad f_c = \frac{1}{2\pi R_{\text{th}} C_{11}} = \frac{1}{2\pi \cdot 5\text{ k}\Omega \cdot 100\text{ nF}} \approx 318.3\text{ Hz}$$
  Bu kesim frekansı, su altı araçlarının ve su üstü platformlarının **LOFAR** (dar bant makine/şaft harmonikleri: $5\text{ Hz} - 250\text{ Hz}$) ve **DEMON** (zarfı alınmış pervane kanat geçiş frekansları: $1\text{ Hz} - 120\text{ Hz}$) bantlarını zayıflatmadan geçirirken yüksek frekanslı örtüşme (aliasing) bileşenlerini bastırır.
- **Aşırı Basınç / Yakın Patlama Klempi (`D6` `BAT54S`):** Yakın mesafe akustik şok dalgalarında ADC girişini $[-0.3\text{ V},\ +3.6\text{ V}]$ aralığında sınırlar.

---

## 3. Donanımsal Manyetik Kurma / Emniyet Kilidi (`J11`, `J12`, `Q2`)

Su altı düğümlerinde güverte/laboratuvar güvenliği kritik önem taşır:
- `J11` (su geçirmez NC manyetik reed anahtar) ile `J12` (eyleyici / yüksek güçlü akustik verici kontaktör bobini) **seri** bağlıdır.
- Güvenlik mıknatısı takılıyken (veya kurma pimi çekilmemişken) hat fiziksel olarak açıktır; MCU yazılımı (`T_ESC_EN`) ne yaparsa yapsın yüksek güçlü çıkış enerjilenemez.
- MCU, `R32/R33` (`47k/10k`) bölücüsü üzerinden `T_KILL_SENSE` (`Pin 36`) piniyle donanımsal emniyet durumunu gerçek zamanlı izler.
