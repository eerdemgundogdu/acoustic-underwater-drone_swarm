"""Akustik suru dugumu (acoustic-swarm-node Rev A) — tek kaynak netlist.

Sematik (make_sch.py) ve PCB (make_pcb.py) bu dosyadan uretilir; bu yuzden
ikisi her zaman ayni baglantilari tasir. Bir baglantiyi degistirmek icin
sadece burayi duzenleyip `python3 hardware/gen/build.py` calistirin.

Guc alanlari:
  VSYS      : 4S Li-ion (12.0 - 16.8 V), sigorta + manyetik kurma anahtari sonrasi
  +3V3_AON  : Hep acik alan (HT7533-1 LDO || piezo hasat LDO'su, diyot-VEYA)
              Uyanma yukselteci + karsilastirici. Uykuda toplam ~7 uA.
  +5V       : LMR16006X buck; EN pini uyanma mandali (BUCK_EN) ile surulur.
              Uykuda kapali -> Teensy, AFE ve modem enerjisiz.
  +3V3A     : LP5907 dusuk gurultulu LDO, sadece hidrofon AFE icin.

Tasarim kararlari ve hesaplar: hardware/DESIGN.md
"""

from dataclasses import dataclass
from typing import Dict

# --- Teensy 4.1: fiziksel pin sirasi (ust gorunus, USB yukarida) -------------
# Sol sira yukaridan asagi = footprint pad 1..24, sag sira = pad 25..48.
TEENSY_LEFT = ['GND', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
               '11', '12', '3V3', '24', '25', '26', '27', '28', '29', '30',
               '31', '32']
TEENSY_RIGHT = ['VIN', 'GND', '3V3', '23', '22', '21', '20', '19', '18', '17',
                '16', '15', '14', '13', 'GND', '41', '40', '39', '38', '37',
                '36', '35', '34', '33']


def teensy_pad(name: str, occurrence: int = 0) -> str:
    """Teensy pin adindan footprint pad numarasini bulur."""
    hits = [str(i + 1) for i, n in enumerate(TEENSY_LEFT) if n == name]
    hits += [str(i + 25) for i, n in enumerate(TEENSY_RIGHT) if n == name]
    return hits[occurrence]


@dataclass
class Part:
    ref: str
    sym: str                 # KiCad sembol (Lib:Name)
    value: str
    fp: str                  # KiCad footprint (Lib:Name)
    pins: Dict[str, str]     # sembol pin numarasi -> net
    mpn: str = ''
    note: str = ''
    block: str = ''
    dnp: bool = False


PARTS = []


def add(ref, sym, value, fp, pins, mpn='', note='', block=''):
    PARTS.append(Part(ref, sym, value, fp, pins, mpn, note, block))


R0603 = 'Resistor_SMD:R_0603_1608Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'
C1210 = 'Capacitor_SMD:C_1210_3225Metric'
SOT23 = 'Package_TO_SOT_SMD:SOT-23'
SOT235 = 'Package_TO_SOT_SMD:SOT-23-5'
SOIC8 = 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'
LED0603 = 'LED_SMD:LED_0603_1608Metric'
SOD123 = 'Diode_SMD:D_SOD-123'
SOD323 = 'Diode_SMD:D_SOD-323'
JST2 = 'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical'
JST3 = 'Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical'


def R(ref, value, a, b, block, mpn=''):
    add(ref, 'Device:R', value, R0603, {'1': a, '2': b},
        mpn or f'0603 {value} 1%', block=block)


def C(ref, value, a, b, block, fp=C0603, mpn=''):
    add(ref, 'Device:C', value, fp, {'1': a, '2': b}, mpn, block=block)


def opamp_dual(ref, value, fp, mpn, a, b, vpos, block, note=''):
    """Cift op-amp, standart SOIC-8 pin dizilimi (MCP6022 sembolu; MCP6042 ayni pinler).
    a/b = (cikis, eksi, arti) uclari, unit 3 = besleme."""
    add(ref, 'Amplifier_Operational:MCP6022',
        value, fp,
        {'1': a[0], '2': a[1], '3': a[2], '5': b[2], '6': b[1], '7': b[0],
         '4': 'GND', '8': vpos}, mpn, note, block)


# =============================================================================
# 1. Pil girisi, sigorta, manyetik kurma (arming) anahtari ve koruma
#   J1 (4S Li-ion) -> F1 -> J2 (NC reed: miknatis takiliyken kart tamamen kapali)
#   -> D1 ters kutup -> VSYS. D2 TVS, C1..C3 toplu kapasite.
# =============================================================================
B = 'power'
add('J1', 'Connector:Screw_Terminal_01x02', '4S LI-ION',
    'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal',
    {'1': 'VBAT_IN', '2': 'GND'}, 'Phoenix 1715721',
    '4S Li-ion paket (BMS dahili), 12.0 - 16.8 V', B)
add('F1', 'Device:Fuse', '2A 63V', 'Fuse:Fuse_1206_3216Metric',
    {'1': 'VBAT_IN', '2': 'VBAT_F'}, 'Littelfuse 0466002.NRHF',
    'Modem H-koprusu tepe akimi (ILIM 1 A) + lojik', B)
add('J2', 'Connector_Generic:Conn_01x02', 'ARM-SW (NC)', JST2,
    {'1': 'VBAT_F', '2': 'ARM_RET'}, 'JST B2B-XH-A',
    'Su gecirmez NC reed: tasima miknatisi takiliyken pil tamamen ayrik', B)
add('D1', 'Device:D_Schottky', 'SS26', 'Diode_SMD:D_SMA',
    {'1': 'VSYS', '2': 'ARM_RET'}, 'SS26 (60V 2A)', 'Ters kutup korumasi', B)
add('D2', 'Device:D_TVS', 'SMBJ20CA', 'Diode_SMD:D_SMB',
    {'1': 'VSYS', '2': 'GND'}, 'Littelfuse SMBJ20CA',
    'Vrwm 20V > 16.8V tam dolu; transdusor geri tepme kiskaci', B)
add('C1', 'Device:C_Polarized', '47uF 35V', 'Capacitor_SMD:CP_Elec_6.3x7.7',
    {'1': 'VSYS', '2': 'GND'}, 'Panasonic EEE-FK1V470P', 'Toplu giris kondansatoru', B)
C('C2', '2.2uF 50V', 'VSYS', 'GND', B, C1210, 'X7R 1210 50V')
C('C3', '2.2uF 50V', 'VSYS', 'GND', B, C1210, 'X7R 1210 50V')

# =============================================================================
# 2. Anahtarli pil gerilim olcumu (uykuda sifir akim)
#   Q2 (2N7002) iletimde -> Q1 (AO3401A) gate'i 100k/100k ile Vgs = -VSYS/2 (max -8.4 V,
#   +-12 V sinirinin altinda) -> BATT_SW -> 100k/15k bolucu -> ADC (16.8 V -> 2.19 V).
# =============================================================================
B = 'battsense'
add('Q1', 'Transistor_FET:AO3401A', 'AO3401A', SOT23,
    {'1': 'BS_G', '2': 'VSYS', '3': 'BATT_SW'}, 'AOS AO3401A', 'Vds -30V, Vgs +-12V', B)
R('R1', '100k', 'VSYS', 'BS_G', B)
R('R2', '100k', 'BS_G', 'BS_D', B)
add('Q2', 'Transistor_FET:2N7002', '2N7002', SOT23,
    {'1': 'BS_EN_G', '2': 'GND', '3': 'BS_D'}, 'Nexperia 2N7002', '', B)
R('R3', '100', 'T_BATT_EN', 'BS_EN_G', B)
R('R4', '100k', 'BS_EN_G', 'GND', B)
R('R5', '100k', 'BATT_SW', 'BATT_DIV', B)
R('R6', '15k', 'BATT_DIV', 'GND', B)
C('C4', '100nF', 'BATT_DIV', 'GND', B, mpn='X7R 0603 16V')
add('D3', 'Device:D_Zener', 'BZT52C3V3', SOD123,
    {'1': 'BATT_DIV', '2': 'GND'}, 'BZT52C3V3', 'ADC 3.3 V kiskaci', B)
R('R7', '1k', 'BATT_DIV', 'T_BATT_ADC', B)

# =============================================================================
# 3. Hep acik (AON) besleme: HT7533-1 (pilden) || piezo hasadi, BAT54C diyot-VEYA
#   Piezo -> D14/D15 (BAT54S tam dalga kopru) -> C7 22 uF depolama, D16 18 V kiskac
#   -> U2 HT7533-1 -> V_HARV. Hasat varken AON alani piezodan beslenir; pil sadece
#   U1'in 2.5 uA sukunet akimini oder. Hasat yalnizca ~15 uW'lik AON yukunu tasidigi
#   icin dogrusal regulator yeterli (bkz. DESIGN.md, Rev B: LTC3588-1 buck).
# =============================================================================
B = 'aon'
add('U1', 'Regulator_Linear:HT75xx-1-SOT89', 'HT7533-1', 'Package_TO_SOT_SMD:SOT-89-3',
    {'1': 'GND', '2': 'VSYS', '3': '+3V3_LDO'}, 'Holtek HT7533-1',
    'Vin max 30 V, Iq 2.5 uA, 100 mA', B)
C('C5', '1uF 50V', 'VSYS', 'GND', B, C1206, 'X7R 1206 50V')
C('C6', '4.7uF', '+3V3_LDO', 'GND', B, C0805, 'X5R 0805 10V')

add('J3', 'Connector_Generic:Conn_01x02', 'PIEZO', JST2,
    {'1': 'PZ1', '2': 'PZ2'}, 'JST B2B-XH-A',
    'PVDF/PZT dalga-akinti hasat elemani (AC)', B)
add('D14', 'Diode:BAT54S', 'BAT54S', SOT23,
    {'1': 'GND', '2': 'HV_STORE', '3': 'PZ1'}, 'BAT54S', 'Tam dalga kopru, 1. kol', B)
add('D15', 'Diode:BAT54S', 'BAT54S', SOT23,
    {'1': 'GND', '2': 'HV_STORE', '3': 'PZ2'}, 'BAT54S', 'Tam dalga kopru, 2. kol', B)
C('C7', '22uF 25V', 'HV_STORE', 'GND', B, C1210, 'X5R 1210 25V')
C('C8', '100nF 50V', 'HV_STORE', 'GND', B, mpn='X7R 0603 50V')
add('D16', 'Device:D_Zener', 'BZT52C18', SOD123,
    {'1': 'HV_STORE', '2': 'GND'}, 'BZT52C18',
    'Depolama kiskaci: C7 25 V ve BAT54 30 V sinirlarinin altinda', B)
add('U2', 'Regulator_Linear:HT75xx-1-SOT89', 'HT7533-1', 'Package_TO_SOT_SMD:SOT-89-3',
    {'1': 'GND', '2': 'HV_STORE', '3': 'V_HARV'}, 'Holtek HT7533-1',
    'Hasat LDO: Iq 2.5 uA, depolama > ~3.5 V iken regule', B)
C('C9', '4.7uF', 'V_HARV', 'GND', B, C0805, 'X5R 0805 10V')
R('R44', '1M', 'V_HARV', 'GND', B)
add('D4', 'Diode:BAT54C', 'BAT54C', SOT23,
    {'1': '+3V3_LDO', '2': 'V_HARV', '3': '+3V3_AON'}, 'BAT54C',
    'Diyot-VEYA: yuksek olan kaynak AON alanini besler', B)
C('C11', '10uF', '+3V3_AON', 'GND', B, C0805, 'X5R 0805 10V')
R('R8', '10k', 'V_HARV', 'T_HARV_PG', B)

# =============================================================================
# 4. Pasif akustik uyanma: MCP6042 (2 x 600 nA) 2 kademe ~60 dB, 5..450 Hz bandi
#   -> Schottky tepe dedektoru -> TLV7031 (335 nA) karsilastirici -> WAKE_CMP
# =============================================================================
B = 'wake'
R('R9', '10M', '+3V3_AON', 'VREF_W', B)
R('R10', '10M', 'VREF_W', 'GND', B)
C('C12', '100nF', 'VREF_W', 'GND', B, mpn='X7R 0603 16V')
C('C13', '100nF', 'HYD_SIG', 'W_IN', B, C1206, 'C0G/NP0 1206 50V')
R('R11', '10M', 'W_IN', 'VREF_W', B)
opamp_dual('U3', 'MCP6042', SOIC8, 'Microchip MCP6042-I/SN',
           ('W_A', 'W_FB1', 'W_IN'), ('W_B', 'W_FB2', 'W_A'), '+3V3_AON', B,
           'GBW 14 kHz; kademe kazanci 31.3 -> BW ~450 Hz')
R('R12', '1M', 'W_A', 'W_FB1', B)
R('R13', '33k', 'W_FB1', 'W_G1', B)
C('C14', '1uF', 'W_G1', 'VREF_W', B, mpn='X7R 0603 16V')
R('R14', '1M', 'W_B', 'W_FB2', B)
R('R15', '33k', 'W_FB2', 'W_G2', B)
C('C15', '1uF', 'W_G2', 'VREF_W', B, mpn='X7R 0603 16V')
C('C16', '100nF', '+3V3_AON', 'GND', B, mpn='X7R 0603 16V')
add('D5', 'Device:D_Schottky', 'BAT54WS', SOD323,
    {'1': 'W_ENV', '2': 'W_B'}, 'Diodes BAT54WS', 'Tepe (zarf) dedektoru', B)
C('C17', '470nF', 'W_ENV', 'GND', B, mpn='X7R 0603 16V')
R('R16', '4.7M', 'W_ENV', 'GND', B)
R('R17', '4.7M', '+3V3_AON', 'W_TH', B)
R('R18', '5.1M', 'W_TH', 'GND', B)
C('C18', '100nF', 'W_TH', 'GND', B, mpn='X7R 0603 16V')
add('U4', 'Comparator:TLV7031DBV', 'TLV7031', SOT235,
    {'1': 'WAKE_CMP', '2': 'GND', '3': 'W_ENV', '4': 'W_TH', '5': '+3V3_AON'},
    'TI TLV7031DBVR', 'Push-pull, 335 nA', B)
C('C19', '100nF', '+3V3_AON', 'GND', B, mpn='X7R 0603 16V')
R('R19', '10k', 'WAKE_CMP', 'T_WAKE', B)

# =============================================================================
# 5. Uyanma mandali: WAKE_CMP VEYA Teensy PWR_HOLD -> BUCK_EN
#   R20/C20 (1 s) karsilastirici darbesini Teensy acilisina (~0.4 s) kadar uzatir.
#   Teensy PWR_HOLD'u dusurunce buck kapanir ve kart uyku moduna doner.
# =============================================================================
B = 'latch'
add('D6', 'Diode:BAT54C', 'BAT54C', SOT23,
    {'1': 'WAKE_CMP', '2': 'T_PWR_HOLD', '3': 'BUCK_EN'}, 'BAT54C', '', B)
R('R20', '1M', 'BUCK_EN', 'GND', B)
C('C20', '1uF', 'BUCK_EN', 'GND', B, mpn='X7R 0603 16V')

# =============================================================================
# 6. VSYS -> 5 V buck (LMR16006X, 700 kHz, 0.6 A), EN = BUCK_EN
# =============================================================================
B = 'buck'
add('U5', 'Regulator_Switching:LMR16006YQ', 'LMR16006XDDCR',
    'Package_TO_SOT_SMD:SOT-23-6',
    {'1': 'BUCK_CB', '2': 'GND', '3': 'BUCK_FB', '4': 'BUCK_EN',
     '5': 'VSYS', '6': 'BUCK_SW'},
    'TI LMR16006XDDCR', 'X versiyonu (700 kHz); sembol Y ile pin uyumlu', B)
C('C21', '100nF 25V', 'BUCK_CB', 'BUCK_SW', B, mpn='X7R 0603 25V')
add('D7', 'Device:D_Schottky', 'SS16', 'Diode_SMD:D_SMA',
    {'1': 'BUCK_SW', '2': 'GND'}, 'SS16 (60V 1A)', 'Buck serbest gecis (catch) diyodu', B)
add('L1', 'Device:L', '22uH', 'Inductor_SMD:L_Bourns_SRN6045TA',
    {'1': 'BUCK_SW', '2': '+5V'}, 'Bourns SRN6045TA-220M', 'Isat >= 1 A', B)
R('R21', '54.9k', '+5V', 'BUCK_FB', B)
R('R22', '10k', 'BUCK_FB', 'GND', B)
C('C22', '22uF 10V', '+5V', 'GND', B, C1206, 'X7R 1206 10V')
C('C23', '22uF 10V', '+5V', 'GND', B, C1206, 'X7R 1206 10V')
R('R23', '2.2k', '+5V', 'LED_PWR_A', B)
add('D8', 'Device:LED', 'YESIL', LED0603, {'1': 'GND', '2': 'LED_PWR_A'},
    '0603 yesil LED', '+5V var (dugum uyanik)', B)
add('D9', 'Device:D_Schottky', 'B5819W', SOD123,
    {'1': 'TEENSY_VIN', '2': '+5V'}, 'B5819W (40V 1A)',
    'USB 5V ile kart 5V birbirini geri beslemesin', B)

# =============================================================================
# 7. Analog besleme: LP5907 (6.5 uVrms) +5V -> +3V3A, sadece AFE
# =============================================================================
B = 'ldo'
add('U6', 'Regulator_Linear:LP5907MFX-3.3', 'LP5907MFX-3.3', SOT235,
    {'1': '+5V', '2': 'GND', '3': '+5V', '5': '+3V3A'}, 'TI LP5907MFX-3.3',
    'Dusuk gurultulu analog LDO', B)
C('C24', '1uF', '+5V', 'GND', B, mpn='X7R 0603 16V')
C('C25', '1uF', '+3V3A', 'GND', B, mpn='X7R 0603 16V')

# =============================================================================
# 8. Teensy 4.1 (soket)
# =============================================================================
# Her islev, kartta yerlestigi taraftaki Teensy sirasina atanir; Teensy'nin iki
# sirasi arasindan iz gecirmek gerekmez. Sol sira: modem PWM ve hasat durumu.
TEENSY_NETS = {
    'VIN': 'TEENSY_VIN', 'GND': 'GND',
    '6': 'T_TX_IN1', '9': 'T_TX_IN2',          # FlexPWM2.2 A/B (modem sol altta)
    '12': 'T_HARV_PG',                         # hasat + hep acik LDO sol ortada
    '23': 'T_PWR_HOLD', '21': 'T_WAKE',        # uyanma mandali buck'in yaninda
    '22': 'T_BATT_EN',
    '17': 'T_ADC_HI', '16': 'T_ADC_LO',        # A3 / A2: ADC1 ve ADC2'de ortak
    '15': 'T_BATT_ADC', '14': 'T_LEAK_ADC',
    '13': 'T_LED',
}
teensy_pins = {}
for i, name in enumerate(TEENSY_LEFT + TEENSY_RIGHT):
    teensy_pins[str(i + 1)] = TEENSY_NETS.get(name, '')
add('U7', 'acoustic:Teensy4.1', 'Teensy 4.1', 'acoustic:Teensy4.1_Socket', teensy_pins,
    'PJRC Teensy 4.1 + 2x 1x24 disi header', 'Tum 3.3V pinleri bos; VIN D9 uzerinden', 'mcu')

# =============================================================================
# 9. Hidrofon analog on-ucu (AFE), +3V3A, Vref = 1.65 V
#   Giris: 100 nF C0G kuplaj, 10M bias, 1k + BAT54S koruma
#   U8A : evirmeyen on yukseltec, G = 1 + 9.1k/1k = 10.1 (20 dB), HP 16 Hz
#   U8B : Sallen-Key 2. derece LP, 2.7k/2.7k, 2.2n/1n -> fc 39.7 kHz, Q 0.74 -> AFE_LO
#   U9A : G = 10.1 (toplam 40 dB), 270 pF ile 65 kHz kutup -> AFE_HI
#   U9B : Vref tamponu
#   ADC surme: 100R + 2.2 nF C0G (ornekleme kapasitesine yuk kovasi) + BAT54S kiskac
# =============================================================================
B = 'afe'
add('J4', 'Connector_Generic:Conn_01x03', 'HIDROFON', JST3,
    {'1': 'HYD_SIG', '2': 'GND', '3': 'GND'}, 'JST B3B-XH-A',
    'Pasif piezo hidrofon (-200 dB re 1V/uPa sinifi); pin 3 kablo ekrani', B)
R('R24', '10k', '+3V3A', 'VREF_DIV', B)
R('R25', '10k', 'VREF_DIV', 'GND', B)
C('C26', '10uF', 'VREF_DIV', 'GND', B, C0805, 'X5R 0805 10V')
R('R26', '49.9', 'VREF_BUF', 'VREF_A', B)
C('C27', '10uF', 'VREF_A', 'GND', B, C0805, 'X5R 0805 10V')

C('C28', '100nF', 'HYD_SIG', 'A_IN', B, C1206, 'C0G/NP0 1206 50V')
R('R27', '1k', 'A_IN', 'A_INP', B)
R('R28', '10M', 'A_INP', 'VREF_A', B)
add('D10', 'Diode:BAT54S', 'BAT54S', SOT23,
    {'1': 'GND', '2': '+3V3A', '3': 'A_INP'}, 'BAT54S', 'Giris asiri gerilim kiskaci', B)

opamp_dual('U8', 'MCP6022', SOIC8, 'Microchip MCP6022-I/SN',
           ('A_S1', 'A_FB1', 'A_INP'), ('AFE_LO', 'AFE_LO', 'A_SK2'), '+3V3A', B,
           'GBW 10 MHz, 8.7 nV/rtHz, RRIO')
R('R29', '9.1k', 'A_S1', 'A_FB1', B)
R('R30', '1k', 'A_FB1', 'A_G1', B)
C('C29', '10uF', 'A_G1', 'VREF_A', B, C0805, 'X5R 0805 10V')
R('R31', '2.7k', 'A_S1', 'A_SK1', B)
R('R32', '2.7k', 'A_SK1', 'A_SK2', B)
C('C30', '2.2nF', 'A_SK1', 'AFE_LO', B, mpn='C0G 0603 50V')
C('C31', '1nF', 'A_SK2', 'GND', B, mpn='C0G 0603 50V')
C('C32', '100nF', '+3V3A', 'GND', B, mpn='X7R 0603 16V')

opamp_dual('U9', 'MCP6022', SOIC8, 'Microchip MCP6022-I/SN',
           ('AFE_HI', 'A_FB2', 'AFE_LO'), ('VREF_BUF', 'VREF_BUF', 'VREF_DIV'), '+3V3A', B,
           'B kanali Vref tamponu')
R('R33', '9.1k', 'AFE_HI', 'A_FB2', B)
C('C33', '270pF', 'AFE_HI', 'A_FB2', B, mpn='C0G 0603 50V')
R('R34', '1k', 'A_FB2', 'A_G2', B)
C('C34', '10uF', 'A_G2', 'VREF_A', B, C0805, 'X5R 0805 10V')
C('C35', '100nF', '+3V3A', 'GND', B, mpn='X7R 0603 16V')

R('R35', '100', 'AFE_LO', 'T_ADC_LO', B)
C('C36', '2.2nF', 'T_ADC_LO', 'GND', B, mpn='C0G 0603 50V')
add('D11', 'Diode:BAT54S', 'BAT54S', SOT23,
    {'1': 'GND', '2': '+3V3A', '3': 'T_ADC_LO'}, 'BAT54S', 'Pin 16 (A2) kiskaci', B)
R('R36', '100', 'AFE_HI', 'T_ADC_HI', B)
C('C37', '2.2nF', 'T_ADC_HI', 'GND', B, mpn='C0G 0603 50V')
add('D12', 'Diode:BAT54S', 'BAT54S', SOT23,
    {'1': 'GND', '2': '+3V3A', '3': 'T_ADC_HI'}, 'BAT54S', 'Pin 17 (A3) kiskaci', B)

# =============================================================================
# 10. Akustik modem vericisi: DRV8871 H-koprusu, 24/28 kHz BFSK
#   IN1 = FlexPWM2.2A (pin 6) %50 kare dalga, IN2 = pin 9 (normalde LOW).
#   OUT1 -> C40 DC blok -> J5 -> harici eslesme trafosu / transdusor.
#   ILIM = 62k -> ~1.0 A tepe akim siniri (64 / R[kOhm]).
# =============================================================================
B = 'tx'
add('U10', 'Driver_Motor:DRV8871DDA', 'DRV8871',
    'Package_SO:Texas_HTSOP-8-1EP_3.9x4.9mm_P1.27mm_EP2.95x4.9mm_Mask2.4x3.1mm_ThermalVias',
    {'1': 'GND', '2': 'TX_IN2', '3': 'TX_IN1', '4': 'TX_ILIM', '5': 'VSYS',
     '6': 'TX_OUT1', '7': 'GND', '8': 'TX_OUT2', '9': 'GND'},
    'TI DRV8871DDAR', 'PWM <= 200 kHz; IN1=IN2=0 iken ~1 ms sonra uyku (<1 uA)', B)
R('R37', '100', 'T_TX_IN1', 'TX_IN1', B)
R('R38', '100', 'T_TX_IN2', 'TX_IN2', B)
R('R39', '62k', 'TX_ILIM', 'GND', B)
add('C38', 'Device:C_Polarized', '47uF 35V', 'Capacitor_SMD:CP_Elec_6.3x7.7',
    {'1': 'VSYS', '2': 'GND'}, 'Panasonic EEE-FK1V470P', 'H-koprusu VM toplu kapasite', B)
C('C39', '100nF 50V', 'VSYS', 'GND', B, mpn='X7R 0603 50V')
C('C40', '2.2uF 50V', 'TX_OUT1', 'TX_P', B, C1210, 'X7R 1210 50V')
add('J5', 'Connector_Generic:Conn_01x02', 'TRANSDUSOR', JST2,
    {'1': 'TX_P', '2': 'TX_OUT2'}, 'JST B2B-XH-A',
    'Eslesme trafosu + 25 kHz rezonansli projektor (kart disi)', B)

# =============================================================================
# 11. Govde su sizinti probu (Pin 14 / A0) ve durum LED'i
# =============================================================================
B = 'io'
add('J6', 'Connector_Generic:Conn_01x02', 'SIZINTI PROBU', JST2,
    {'1': 'LEAK_P', '2': 'LEAK_NODE'}, 'JST B2B-XH-A',
    'Tup ici iletken su sizinti elektrotlari', B)
R('R40', '10k', '+3V3A', 'LEAK_P', B)
R('R41', '47k', 'LEAK_NODE', 'GND', B)
C('C41', '100nF', 'LEAK_NODE', 'GND', B, mpn='X7R 0603 16V')
R('R42', '1k', 'LEAK_NODE', 'T_LEAK_ADC', B)
R('R43', '330', 'T_LED', 'LED_STAT_A', B)
add('D13', 'Device:LED', 'MAVI', LED0603, {'1': 'GND', '2': 'LED_STAT_A'},
    '0603 mavi LED', 'Durum LED (pin 13, Teensy dahili LED ile paralel)', B)

# =============================================================================
# 12. Test noktalari, montaj delikleri, ERC guc bayraklari
# =============================================================================
B = 'misc'
for tp, net in [('TP1', 'VSYS'), ('TP2', '+5V'), ('TP3', '+3V3A'), ('TP4', 'GND'),
                ('TP5', '+3V3_AON'), ('TP6', 'VREF_A')]:
    add(tp, 'Connector:TestPoint', net, 'TestPoint:TestPoint_Pad_D1.5mm',
        {'1': net}, '', '', B)
for h in ['H1', 'H2', 'H3', 'H4']:
    add(h, 'Mechanical:MountingHole', 'M3', 'MountingHole:MountingHole_3.2mm_M3',
        {}, '', '', B)

# PWR_FLAG: sadece sematikte (ERC icin), PCB'de yok
PWR_FLAGS = ['VSYS', 'GND', '+5V', 'TEENSY_VIN', '+3V3_AON', 'HV_STORE']

# Yonlendirici iz genislikleri (mm); listede olmayan netler 0.25 mm
WIDTHS = {
    'VBAT_IN': 0.8, 'VBAT_F': 0.8, 'ARM_RET': 0.8, 'VSYS': 0.8,
    'TX_OUT1': 0.6, 'TX_OUT2': 0.6, 'TX_P': 0.6, 'BUCK_SW': 0.6,
    '+5V': 0.5, 'TEENSY_VIN': 0.5, 'GND': 0.3, '+3V3A': 0.3, '+3V3_AON': 0.3,
}


def nets():
    out = {}
    for p in PARTS:
        for pin, n in p.pins.items():
            if n:
                out.setdefault(n, []).append((p.ref, pin))
    return out


if __name__ == '__main__':
    ns = nets()
    print(f'{len(PARTS)} parca, {len(ns)} net')
    for n, conns in sorted(ns.items()):
        if len(conns) < 2:
            print('  TEK BAGLANTILI NET:', n, conns)
