"""KiCad kurulum yollari. Linux paketinde varsayilanlar dogrudur; Windows/macOS
icin KICAD_SHARE (ornegin C:/Program Files/KiCad/9.0/share/kicad) ve KICAD_CLI
ortam degiskenleri verilir."""

import os

SHARE = os.environ.get('KICAD_SHARE', '/usr/share/kicad')
SYMDIR = os.path.join(SHARE, 'symbols')
FPDIR = os.path.join(SHARE, 'footprints')
CLI = os.environ.get('KICAD_CLI', 'kicad-cli')

for v in ('7', '8', '9'):
    os.environ.setdefault(f'KICAD{v}_FOOTPRINT_DIR', FPDIR)
    os.environ.setdefault(f'KICAD{v}_SYMBOL_DIR', SYMDIR)
