"""Teensy 4.1 icin proje sembolu ve footprint'i uretir.

KiCad'in standart kutuphanelerinde Teensy 4.1 yok. Footprint, kartin iki dis
pin sirasini (2x24, 2.54 mm aralik, siralar arasi 15.24 mm = 0.6") 1x24 disi
header'larla tasir; alttaki ic pedler kullanilmaz.
"""

import os

from design import TEENSY_LEFT, TEENSY_RIGHT

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.join(HERE, '..', 'acoustic-swarm-node')

PITCH = 2.54
ROW_GAP = 15.24
FONT = '(effects (font (size 1.27 1.27)))'


def pin_type(name):
    if name in ('GND', 'VIN'):
        return 'power_in'
    if name == '3V3':
        return 'power_out'
    return 'bidirectional'


def pin_label(name):
    special = {'0': '0/RX1', '1': '1/TX1', '18': '18/SDA0', '19': '19/SCL0'}
    if name in special:
        return special[name]
    if name.isdigit() and 14 <= int(name) <= 21:
        return f'{name}/A{int(name) - 14}'
    return name


def pin(kind, x, y, angle, name, number):
    return f'''      (pin {kind} line (at {x} {y:.2f} {angle}) (length 5.08)
        (name "{name}" {FONT})
        (number "{number}" {FONT}))'''


def teensy_symbol():
    pins = []
    for i, name in enumerate(TEENSY_LEFT):
        pins.append(pin(pin_type(name), -17.78, 29.21 - i * PITCH, 0, pin_label(name), i + 1))
    for i, name in enumerate(TEENSY_RIGHT):
        pins.append(pin(pin_type(name), 17.78, 29.21 - i * PITCH, 180, pin_label(name), i + 25))
    body = '\n'.join(pins)
    return f'''  (symbol "Teensy4.1" (in_bom yes) (on_board yes)
    (property "Reference" "U" (at 0 34.29 0) {FONT})
    (property "Value" "Teensy4.1" (at 0 -34.29 0) {FONT})
    (property "Footprint" "acoustic:Teensy4.1_Socket" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (property "Datasheet" "https://www.pjrc.com/store/teensy41.html" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (property "ki_description" "PJRC Teensy 4.1, dis iki pin sirasi (ust gorunus, USB yukarida)" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))
    (symbol "Teensy4.1_0_1"
      (rectangle (start -12.7 31.75) (end 12.7 -31.75) (stroke (width 0.254) (type default)) (fill (type background)))
      (text "USB" (at 0 29.21 0) {FONT})
    )
    (symbol "Teensy4.1_1_1"
{body}
    )
  )'''


def symbol_lib():
    return f'''(kicad_symbol_lib (version 20220914) (generator acoustic_make_lib)
{teensy_symbol()}
)
'''


def footprint():
    pads = []
    for i in range(24):
        y = i * PITCH
        shape = 'rect' if i == 0 else 'circle'
        pads.append(f'  (pad "{i + 1}" thru_hole {shape} (at 0 {y:.2f}) (size 1.6 1.6) (drill 1.0) (layers "*.Cu" "*.Mask"))')
        pads.append(f'  (pad "{i + 25}" thru_hole circle (at {ROW_GAP:.2f} {y:.2f}) (size 1.6 1.6) (drill 1.0) (layers "*.Cu" "*.Mask"))')
    x0, x1 = -1.27, ROW_GAP + 1.27
    y0, y1 = -1.27, 23 * PITCH + 1.27
    silk = [
        f'  (fp_line (start {x0} {y0}) (end {x1} {y0}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))',
        f'  (fp_line (start {x1} {y0}) (end {x1} {y1}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))',
        f'  (fp_line (start {x1} {y1}) (end {x0} {y1}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))',
        f'  (fp_line (start {x0} {y1}) (end {x0} {y0}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))',
        f'  (fp_rect (start {ROW_GAP / 2 - 3.8:.2f} {y0 - 1.5}) (end {ROW_GAP / 2 + 3.8:.2f} {y0 + 3.5}) (stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS"))',
        f'  (fp_text user "USB" (at {ROW_GAP / 2:.2f} {y0 + 1.0}) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
        f'  (fp_rect (start {x0 - 0.25} {y0 - 1.75}) (end {x1 + 0.25} {y1 + 0.25}) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))',
        f'  (fp_rect (start {x0} {y0}) (end {x1} {y1}) (stroke (width 0.1) (type solid)) (fill none) (layer "F.Fab"))',
    ]
    return f'''(footprint "Teensy4.1_Socket" (version 20221018) (generator acoustic_make_lib)
  (layer "F.Cu")
  (descr "PJRC Teensy 4.1 icin 2x 1x24 disi header (0.6 inch siralar arasi). Pad 1 = sol ust GND, USB ust kenarda.")
  (tags "Teensy 4.1 socket")
  (attr through_hole)
  (fp_text reference "REF**" (at {ROW_GAP / 2:.2f} {y1 + 2}) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))
  (fp_text value "Teensy4.1_Socket" (at {ROW_GAP / 2:.2f} {y1 + 4}) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
{chr(10).join(silk)}
{chr(10).join(pads)}
)
'''


def main():
    os.makedirs(os.path.join(PROJ, 'acoustic.pretty'), exist_ok=True)
    with open(os.path.join(PROJ, 'acoustic.kicad_sym'), 'w') as f:
        f.write(symbol_lib())
    with open(os.path.join(PROJ, 'acoustic.pretty', 'Teensy4.1_Socket.kicad_mod'), 'w') as f:
        f.write(footprint())
    with open(os.path.join(PROJ, 'sym-lib-table'), 'w') as f:
        f.write('(sym_lib_table\n  (lib (name "acoustic")(type "KiCad")(uri "${KIPRJMOD}/acoustic.kicad_sym")(options "")(descr "Akustik suru dugumu proje sembolleri"))\n)\n')
    with open(os.path.join(PROJ, 'fp-lib-table'), 'w') as f:
        f.write('(fp_lib_table\n  (lib (name "acoustic")(type "KiCad")(uri "${KIPRJMOD}/acoustic.pretty")(options "")(descr "Akustik suru dugumu proje footprintleri"))\n)\n')


if __name__ == '__main__':
    main()
    print('ok')
