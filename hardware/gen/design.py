"""Stingray ROV tasiyici karti (Rev A) — tek kaynak netlist.

Sematik (make_sch.py) ve PCB (make_pcb.py) bu dosyadan uretilir; bu yuzden
ikisi her zaman ayni baglantilari tasir. Bir baglantiyi degistirmek icin
sadece burayi duzenleyip `python3 hardware/gen/build.py` calistirin.

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
LED0603 = 'LED_SMD:LED_0603_1608Metric'


def R(ref, value, a, b, block, mpn=''):
    add(ref, 'Device:R', value, R0603, {'1': a, '2': b},
        mpn or f'0603 {value} 1%', block=block)


def C(ref, value, a, b, block, fp=C0603, mpn=''):
    add(ref, 'Device:C', value, fp, {'1': a, '2': b}, mpn, block=block)


# =============================================================================
# 1. Guc girisi ve koruma (6S Li-Po 22.2 V nominal / 25.2 V dolu -> +24V)
# =============================================================================
B = 'power'
add('J1', 'Connector:Screw_Terminal_01x02', 'PIEZO/HV',
    'TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal',
    {'1': 'VBAT_IN', '2': 'GND'}, 'Phoenix 1715721',
    '6S Li-Po girisi (ana sigortadan sonra, ESC kontaktorunden once)', B)
add('F1', 'Device:Fuse', '1A 63V', 'Fuse:Fuse_1206_3216Metric',
    {'1': 'VBAT_IN', '2': 'VBAT_F'}, 'Littelfuse 0466001.NRHF',
    'Lojik + kontaktor bobini sigortasi', B)
add('D1', 'Device:D_Schottky', 'SS16', 'Diode_SMD:D_SMA',
    {'1': '+24V', '2': 'VBAT_F'}, 'SS16 (60V 1A)', 'Ters kutup korumasi', B)
add('D2', 'Device:D_TVS', 'SMBJ30CA', 'Diode_SMD:D_SMB',
    {'1': '+24V', '2': 'GND'}, 'Littelfuse SMBJ30CA',
    'Vrwm 30V; 6x ESC rejeneratif/enduktif sicrama kiskaci', B)
add('C1', 'Device:C_Polarized', '47uF 63V', 'Capacitor_SMD:CP_Elec_8x10',
    {'1': '+24V', '2': 'GND'}, 'Panasonic EEE-FK1J470P',
    'Toplu giris kondansatoru (tether/aku kablosu rezonans sonumleme)', B)
C('C2', '2.2uF 100V', '+24V', 'GND', B, C1210, 'X7R 1210 100V')
C('C3', '2.2uF 100V', '+24V', 'GND', B, C1210, 'X7R 1210 100V')

# =============================================================================
# 2. 6S (+24V) -> 5 V buck (LMR16006X, 700 kHz, 0.6 A)
# =============================================================================
B = 'buck'
R('R1', '100k', '+24V', 'BUCK_SHDN', B)
add('U1', 'Regulator_Switching:LMR16006YQ', 'LMR16006XDDCR',
    'Package_TO_SOT_SMD:SOT-23-6',
    {'1': 'BUCK_CB', '2': 'GND', '3': 'BUCK_FB', '4': 'BUCK_SHDN',
     '5': '+24V', '6': 'BUCK_SW'},
    'TI LMR16006XDDCR', 'X versiyonu (700 kHz); sembol Y ile pin uyumlu', B)
C('C4', '100nF 25V', 'BUCK_CB', 'BUCK_SW', B, mpn='X7R 0603 25V')
add('D3', 'Device:D_Schottky', 'SS16', 'Diode_SMD:D_SMA',
    {'1': 'BUCK_SW', '2': 'GND'}, 'SS16 (60V 1A)', 'Buck serbest gecis (catch) diyodu', B)
add('L1', 'Device:L', '22uH', 'Inductor_SMD:L_Bourns_SRN6045TA',
    {'1': 'BUCK_SW', '2': '+5V'}, 'Bourns SRN6045TA-220M', 'Isat >= 1 A gerekli', B)
R('R2', '54.9k', '+5V', 'BUCK_FB', B)
R('R3', '10k', 'BUCK_FB', 'GND', B)
C('C5', '22uF 10V', '+5V', 'GND', B, C1206, 'X7R 1206 10V')
C('C6', '22uF 10V', '+5V', 'GND', B, C1206, 'X7R 1206 10V')
R('R4', '2.2k', '+5V', 'LED_PWR_A', B)
add('D5', 'Device:LED', 'YESIL', LED0603, {'1': 'GND', '2': 'LED_PWR_A'},
    '0603 yesil LED', '+5V var', B)

# =============================================================================
# 3. 5 V -> 3.3 V LDO (AFE-I2C IMU + sizinti probu; Teensy VIN D4 uzerinden)
# =============================================================================
B = 'ldo'
add('U2', 'Regulator_Linear:AP2112K-3.3', 'AP2112K-3.3', 'Package_TO_SOT_SMD:SOT-23-5',
    {'1': '+5V', '2': 'GND', '3': '+5V', '4': '', '5': '+3V3'},
    'Diodes AP2112K-3.3TRG1', '600 mA; IMU + sizinti algilama hatti', B)
C('C7', '1uF', '+5V', 'GND', B, mpn='X7R 0603 16V')
C('C8', '1uF', '+3V3', 'GND', B, mpn='X7R 0603 16V')
C('C9', '10uF', '+3V3', 'GND', B, C0805, 'X5R 0805 10V')
add('D4', 'Device:D_Schottky', 'B5819W', 'Diode_SMD:D_SOD-123',
    {'1': 'TEENSY_VIN', '2': '+5V'}, 'B5819W (40V 1A)',
    'Jetson USB 5V ile kart 5V birbirini geri beslemesin', B)

# =============================================================================
# 4. Teensy 4.1 (soket)
# =============================================================================
TEENSY_NETS = {
    'VIN': 'TEENSY_VIN', 'GND': 'GND',
    '2': 'T_PWM0', '3': 'T_PWM1', '4': 'T_PWM2',
    '5': 'T_PWM3', '6': 'T_PWM4', '7': 'T_PWM5',
    '11': 'T_LED',
    '14': 'T_LEAK_ADC', '15': 'T_BATT_ADC', '16': 'T_DEPTH_ADC',
    '18': 'T_SDA0', '19': 'T_SCL0',
    '36': 'T_KILL_SENSE', '37': 'T_BUZZER', '38': 'T_ESC_EN',
}
teensy_pins = {}
for i, name in enumerate(TEENSY_LEFT + TEENSY_RIGHT):
    teensy_pins[str(i + 1)] = TEENSY_NETS.get(name, '')
add('U3', 'stingray:Teensy4.1', 'Teensy 4.1', 'stingray:Teensy4.1_Socket', teensy_pins,
    'PJRC Teensy 4.1 + 2x 1x24 disi header', 'Tum 3.3V pinleri bos; VIN D4 uzerinden', 'mcu')

# =============================================================================
# 5. 6x Itici ESC PWM cikislari (M0..M5; BEC 5V pini bilerek bos, 220R + 100k)
# =============================================================================
B = 'esc'
ESC_CHANNELS = [
    (0, 'J5',  'R5',  'R11', 'AKUSTIK CH0 TX'),
    (1, 'J6',  'R6',  'R12', 'AKUSTIK CH1 TX'),
    (2, 'J7',  'R7',  'R13', 'AKUSTIK CH2 TX'),
    (3, 'J8',  'R8',  'R14', 'AKUSTIK CH3 TX'),
    (4, 'J9',  'R9',  'R15', 'SWARM BFSK TX0'),
    (5, 'J10', 'R10', 'R16', 'SWARM BFSK TX1'),
]
for idx, jref, rser, rpd, label in ESC_CHANNELS:
    tnet = f'T_PWM{idx}'
    enet = f'ESC_PWM{idx}'
    add(jref, 'Connector_Generic:Conn_01x03', label,
        'Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical',
        {'1': 'GND', '2': '', '3': enet}, 'JST B3B-XH-A',
        'Pin 2 (ESC BEC 5V) bilerek bagli degil', B)
    R(rser, '220', tnet, enet, B)
    R(rpd, '100k', enet, 'GND', B)

# =============================================================================
# 6. IMU (AFE-I2C, I2C0 400 kHz: 4.7k pull-up + 33R seri sonumleme)
# =============================================================================
B = 'imu'
add('J3', 'Connector_Generic:Conn_01x04', 'AKUSTIK I2C',
    'Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical',
    {'1': '+3V3', '2': 'GND', '3': 'IMU_SCL', '4': 'IMU_SDA'},
    'JST B4B-XH-A', 'Pin 18 SDA0, Pin 19 SCL0 @ 400 kHz', B)
R('R17', '4.7k', '+3V3', 'T_SCL0', B)
R('R18', '4.7k', '+3V3', 'T_SDA0', B)
R('R19', '33', 'T_SCL0', 'IMU_SCL', B)
R('R20', '33', 'T_SDA0', 'IMU_SDA', B)
C('C10', '100nF', '+3V3', 'GND', B, mpn='X7R 0603 16V')

# =============================================================================
# 7. Hidrostatik basinc / derinlik sensoru (SEN0257 5V -> 10k/10k + BAT54S)
# =============================================================================
B = 'depth'
add('J2', 'Connector_Generic:Conn_01x03', 'HIDROFON AFE',
    'Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical',
    {'1': '+5V', '2': 'GND', '3': 'DEPTH_RAW'}, 'JST B3B-XH-A',
    'DFRobot SEN0257 (0.5-4.5V ratiometric, 1.6 MPa)', B)
R('R21', '10k', 'DEPTH_RAW', 'T_DEPTH_ADC', B)
R('R22', '10k', 'T_DEPTH_ADC', 'GND', B)
C('C11', '100nF', 'T_DEPTH_ADC', 'GND', B, mpn='X7R 0603 16V')
add('D6', 'Diode:BAT54S', 'BAT54S', SOT23,
    {'1': 'GND', '2': '+3V3', '3': 'T_DEPTH_ADC'}, 'BAT54S',
    'Pin 16 (A2) asiri gerilim kiskaci', B)
C('C12', '100nF', '+5V', 'GND', B, mpn='X7R 0603 16V')

# =============================================================================
# 8. Su sizinti probu (Pin 14 / A0) ve 6S batarya voltaj olcumu (Pin 15 / A1)
# =============================================================================
B = 'analog'
add('J4', 'Connector_Generic:Conn_01x02', 'SIZINTI PROBU',
    'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical',
    {'1': 'LEAK_P', '2': 'LEAK_NODE'}, 'JST B2B-XH-A',
    'Tup ici iletken su sizinti elektrotlari', B)
R('R23', '10k', '+3V3', 'LEAK_P', B)
R('R24', '47k', 'LEAK_NODE', 'GND', B)
C('C13', '100nF', 'LEAK_NODE', 'GND', B, mpn='X7R 0603 16V')
R('R25', '1k', 'LEAK_NODE', 'T_LEAK_ADC', B)

R('R26', '68k', '+24V', 'BATT_DIV', B)
R('R27', '10k', 'BATT_DIV', 'GND', B)
C('C14', '100nF', 'BATT_DIV', 'GND', B, mpn='X7R 0603 16V')
add('D7', 'Device:D_Zener', 'BZT52C3V3', 'Diode_SMD:D_SOD-123',
    {'1': 'BATT_DIV', '2': 'GND'}, 'BZT52C3V3', 'Batarya ADC 3.3 V kiskaci', B)
R('R28', '1k', 'BATT_DIV', 'T_BATT_ADC', B)

# =============================================================================
# 9. Tup ici akustik buzzer ve durum LED'i
# =============================================================================
B = 'ui'
add('BZ1', 'Device:Buzzer', '5V aktif', 'Buzzer_Beeper:Buzzer_12x9.5RM7.6',
    {'1': '+5V', '2': 'BUZ_N'}, '12 mm 5V aktif buzzer',
    'Tup ici arming / sizinti / dusuk pil sesli uyari', B)
add('Q1', 'Transistor_FET:AO3400A', 'AO3400A', SOT23,
    {'1': 'Q1_G', '2': 'GND', '3': 'BUZ_N'}, 'AOS AO3400A', '', B)
R('R35', '100', 'T_BUZZER', 'Q1_G', B)
R('R36', '100k', 'Q1_G', 'GND', B)
add('D8', 'Device:D', '1N4148W', 'Diode_SMD:D_SOD-323',
    {'1': '+5V', '2': 'BUZ_N'}, '1N4148WS', 'Buzzer serbest gecis', B)
R('R37', '330', 'T_LED', 'LED_STAT_A', B)
add('D9', 'Device:LED', 'MAVI', LED0603, {'1': 'GND', '2': 'LED_STAT_A'},
    '0603 mavi LED', 'Durum LED (pin 11)', B)

# =============================================================================
# 10. Manyetik kill-switch (NC) + ana itici gucu kontaktoru (ESC_EN)
#   +24V -> [Manyetik Kill-Switch NC] -> KILL_RET -> [Kontaktor bobini] -> COIL_N -> Q2 -> GND
#   Disaridan manyetik pim cekilince bobin yazilimdan bagimsiz olarak duser.
#   Teensy T_ESC_EN (pin 8) ile sizinti / haberlesme kaybi / kritik pil durumunda
#   kontaktoru ayrica birakabilir; resetteyken Q2 kapalidir.
# =============================================================================
B = 'killswitch'
add('J11', 'Connector_Generic:Conn_01x02', 'ARM-SW (NC)',
    'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical',
    {'1': '+24V', '2': 'KILL_RET'}, 'JST B2B-XH-A',
    'Su gecirmez manyetik acil durdurma anahtari (normalde kapali)', B)
add('J12', 'Connector_Generic:Conn_01x02', 'MODEM KONTAKTOR',
    'Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical',
    {'1': 'KILL_RET', '2': 'COIL_N'}, 'JST B2B-XH-A', '24V bobin, <= 0.4 A', B)
add('Q2', 'Transistor_BJT:BCP56', 'BCP56-16', 'Package_TO_SOT_SMD:SOT-223-3_TabPin2',
    {'1': 'Q2_B', '2': 'COIL_N', '3': 'GND', '4': 'COIL_N'},
    'Nexperia BCP56-16', '80V 1A; hFE 100-250', B)
R('R29', '470', 'T_ESC_EN', 'Q2_B', B)
R('R30', '10k', 'Q2_B', 'GND', B)
add('D10', 'Device:D_Schottky', 'SS16', 'Diode_SMD:D_SMA',
    {'1': 'KILL_RET', '2': 'COIL_N'}, 'SS16 (60V 1A)', 'Bobin serbest gecis diyodu', B)
R('R31', '10k', 'KILL_RET', 'LED_ESC_A', B)
add('D11', 'Device:LED', 'KIRMIZI', LED0603, {'1': 'COIL_N', '2': 'LED_ESC_A'},
    '0603 kirmizi LED', 'Itici ESC gucu acik', B)
R('R32', '47k', 'KILL_RET', 'KILL_DIV', B)
R('R33', '10k', 'KILL_DIV', 'GND', B)
add('D12', 'Device:D_Zener', 'BZT52C3V3', 'Diode_SMD:D_SOD-123',
    {'1': 'KILL_DIV', '2': 'GND'}, 'BZT52C3V3', '3.3 V kiskac', B)
R('R34', '1k', 'KILL_DIV', 'T_KILL_SENSE', B)

# =============================================================================
# 11. Test noktalari, montaj delikleri, ERC guc bayraklari
# =============================================================================
B = 'misc'
for tp, net in [('TP1', '+24V'), ('TP2', '+5V'), ('TP3', '+3V3'), ('TP4', 'GND')]:
    add(tp, 'Connector:TestPoint', net, 'TestPoint:TestPoint_Pad_D1.5mm',
        {'1': net}, '', '', B)
for h in ['H1', 'H2', 'H3', 'H4']:
    add(h, 'Mechanical:MountingHole', 'CH3', 'MountingHole:MountingHole_3.2mm_M3',
        {}, '', '', B)

# PWR_FLAG: sadece sematikte (ERC icin), PCB'de yok
PWR_FLAGS = ['+24V', 'GND', '+5V', 'TEENSY_VIN']


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
