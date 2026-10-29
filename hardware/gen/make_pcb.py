"""design.py netlist'inden PCB'yi kurar: footprint'ler, netler, yerlesim,
kart kenari. Yol cizimi router.py, bakir dokum ve DRC finish_pcb.py'dedir.

Koordinatlar mm; (0,0) kartin sol ust kosesi. KiCad sayfasinda kart
(ORIGIN_X, ORIGIN_Y) noktasina tasinir.
"""

import os

os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
os.environ.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")
import pcbnew  # noqa: E402

import design  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.join(HERE, '..', 'pelagos-node-carrier')
FPDIR = '/usr/share/kicad/footprints'

ORIGIN_X, ORIGIN_Y = 50.0, 50.0
BOARD_W, BOARD_H = 110.0, 85.0
CORNER_R = 3.0

# ref: (x, y, aci_derece)
# Konnektorler kenarlara, Teensy ortaya (USB ust kenara bakar).
TX, TY = 30.48, 12.7            # Teensy pad 1 (sol ust GND)
RX = TX + 15.24                 # Teensy sag sira x


PLACE = {
    # --- MCU ---
    'U3': (TX, TY, 0),

    # --- Guc girisi (sag ust) ---
    'J1': (103.0, 9.0, 90),
    'F1': (93.5, 6.5, 0),
    'D1': (87.0, 6.5, 0),
    'D2': (88.0, 22.5, 0),
    'C1': (88.0, 15.0, 0),
    'C2': (77.0, 11.0, 90),
    'C3': (80.5, 11.0, 90),
    'TP1': (102.0, 18.5, 0),

    # --- Buck (ust orta) ---
    'U1': (72.0, 10.0, 0),
    'R1': (74.0, 14.5, 90),
    'C4': (72.0, 7.4, 0),
    'D3': (77.0, 4.5, 0),
    'L1': (65.0, 8.5, 180),
    'R2': (67.0, 14.0, 90),
    'R3': (70.0, 14.0, 90),
    'C5': (60.0, 6.0, 90),
    'C6': (60.0, 11.0, 90),
    'R4': (56.0, 18.0, 0),
    'D5': (60.0, 18.0, 180),
    'TP2': (56.0, 4.0, 0),

    # --- LDO ve Teensy VIN ---
    'U2': (52.0, 23.5, 270),
    'C7': (55.5, 21.8, 90),
    'C8': (55.5, 26.5, 90),
    'C9': (51.5, 28.5, 0),
    'D4': (50.5, 8.5, 90),
    'TP3': (58.5, 28.0, 0),

    # --- 6x ESC PWM cikislari (sol kenar, yukaridan asagi M0..M5) ---
    'J5':  (3.5, 12.0, 270),
    'R5':  (14.0, 12.0, 180),
    'R11': (14.0, 15.0, 0),

    'J6':  (3.5, 23.5, 270),
    'R6':  (14.0, 23.5, 180),
    'R12': (14.0, 26.5, 0),

    'J7':  (3.5, 35.0, 270),
    'R7':  (14.0, 35.0, 180),
    'R13': (14.0, 38.0, 0),

    'J8':  (3.5, 46.5, 270),
    'R8':  (14.0, 46.5, 180),
    'R14': (14.0, 49.5, 0),

    'J9':  (3.5, 58.0, 270),
    'R9':  (14.0, 58.0, 180),
    'R15': (14.0, 61.0, 0),

    'J10': (3.5, 69.5, 270),
    'R10': (14.0, 69.5, 180),
    'R16': (14.0, 72.5, 0),

    # --- IMU AKUSTIK I2C (orta sag) ---
    'J3':  (66.0, 34.0, 0),
    'R17': (56.0, 32.5, 0),
    'R18': (56.0, 35.5, 0),
    'R19': (61.0, 32.5, 0),
    'R20': (61.0, 35.5, 0),
    'C10': (66.0, 29.0, 0),

    # --- Basinc sensoru 5V -> 3.3V ADC (Pin 16 / A2 hizasinda + alt konnektor) ---
    'J2':  (66.0, 81.0, 0),
    'R21': (60.0, 41.5, 90),
    'R22': (63.5, 41.5, 90),
    'C11': (67.0, 41.5, 90),
    'D6':  (55.0, 40.5, 0),
    'C12': (73.0, 75.0, 90),

    # --- Su sizinti probu + 6S batarya ADC (alt orta) ---
    'J4':  (42.0, 81.0, 0),
    'R23': (34.5, 76.5, 0),
    'R24': (44.0, 74.0, 0),
    'C13': (49.5, 74.0, 0),
    'R25': (49.5, 70.5, 0),

    'R26': (66.0, 47.0, 0),
    'R27': (66.0, 50.0, 0),
    'C14': (66.0, 53.0, 0),
    'D7':  (60.5, 51.0, 90),
    'R28': (55.0, 49.0, 180),

    # --- Buzzer ve durum LED ---
    'BZ1': (88.0, 72.0, 0),
    'Q1':  (80.5, 64.0, 90),
    'R35': (74.0, 60.26, 0),
    'R36': (80.5, 60.0, 0),
    'D8':  (86.0, 63.0, 0),
    'R37': (23.0, 76.0, 180),
    'D9':  (23.0, 79.0, 0),

    # --- Manyetik Kill-Switch ve ESC Kontaktor (sag kenar) ---
    'J11': (106.5, 35.0, 90),
    'J12': (106.5, 47.0, 90),
    'Q2':  (93.0, 46.0, 0),
    'R29': (79.0, 52.0, 0),
    'R30': (85.5, 52.0, 0),
    'D10': (100.0, 53.5, 90),
    'R31': (99.0, 40.0, 90),
    'D11': (99.0, 44.5, 270),
    'R32': (88.0, 37.0, 0),
    'R33': (83.0, 40.0, 90),
    'D12': (86.5, 41.5, 90),
    'R34': (72.0, 56.0, 180),
    'TP4': (102.0, 22.5, 0),

    # --- Montaj delikleri (koseler) ---
    'H1': (4.0, 4.0, 0),
    'H2': (106.0, 26.0, 0),
    'H3': (4.0, 81.0, 0),
    'H4': (106.0, 81.0, 0),
}


SILK_REFS = {'U3'}


def load_fp(fpid):
    lib, name = fpid.split(':')
    path = (os.path.join(PROJ, 'stingray.pretty') if lib == 'stingray'
            else os.path.join(FPDIR, f'{lib}.pretty'))
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise RuntimeError(f'footprint yok: {fpid}')
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(ORIGIN_X + x), mm(ORIGIN_Y + y))


def add_outline(board):
    w, h, r = BOARD_W, BOARD_H, CORNER_R

    def seg(x1, y1, x2, y2):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pt(x1, y1))
        s.SetEnd(pt(x2, y2))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        board.Add(s)

    def arc(cx, cy, sx, sy, ex, ey):
        a = pcbnew.PCB_SHAPE(board)
        a.SetShape(pcbnew.SHAPE_T_ARC)
        mx = cx + (sx - cx + ex - cx) * 0.7071 / 1.0
        my = cy + (sy - cy + ey - cy) * 0.7071 / 1.0
        a.SetArcGeometry(pt(sx, sy), pt(mx, my), pt(ex, ey))
        a.SetLayer(pcbnew.Edge_Cuts)
        a.SetWidth(mm(0.1))
        board.Add(a)

    seg(r, 0, w - r, 0)
    seg(w, r, w, h - r)
    seg(w - r, h, r, h)
    seg(0, h - r, 0, r)
    arc(w - r, r, w - r, 0, w, r)
    arc(w - r, h - r, w, h - r, w - r, h)
    arc(r, h - r, r, h, 0, h - r)
    arc(r, r, 0, r, r, 0)


def setup_rules(board):
    ds = board.GetDesignSettings()
    ds.m_MinClearance = mm(0.2)
    ds.m_TrackMinWidth = mm(0.2)
    ds.m_ViasMinSize = mm(0.6)
    ds.m_MinThroughDrill = mm(0.3)
    ds.m_CopperEdgeClearance = mm(0.5)
    ds.m_HoleClearance = mm(0.25)
    ds.SetCopperLayerCount(2)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(mm(0.2))
    nc.SetTrackWidth(mm(0.25))
    nc.SetViaDiameter(mm(0.6))
    nc.SetViaDrill(mm(0.3))


def build():
    board = pcbnew.BOARD()
    setup_rules(board)

    netcodes = {}
    for i, name in enumerate(sorted(design.nets().keys())):
        ni = pcbnew.NETINFO_ITEM(board, name, i + 1)
        board.Add(ni)
        netcodes[name] = ni

    missing = []
    for p in design.PARTS:
        fp = load_fp(p.fp)
        fp.SetReference(p.ref)
        fp.SetValue(p.value)
        if p.ref not in PLACE:
            missing.append(p.ref)
            x, y, rot = 0, 0, 0
        else:
            x, y, rot = PLACE[p.ref]
        board.Add(fp)
        fp.SetPosition(pt(x, y))
        fp.SetOrientationDegrees(rot)
        for pad in fp.Pads():
            net = p.pins.get(pad.GetNumber(), '')
            if net:
                pad.SetNet(netcodes[net])
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        fp.Reference().SetTextThickness(mm(0.12))
        fp.Value().SetVisible(False)
        if p.ref not in SILK_REFS:
            fp.Reference().SetLayer(pcbnew.F_Fab)
            fp.Reference().SetPosition(fp.GetPosition())
    if missing:
        raise RuntimeError(f'yerlesimi olmayan parcalar: {missing}')
    keep_inside(board)

    add_outline(board)
    return board


EDGE_KEEP = 0.4


def keep_inside(board):
    """Kenardaki konnektorleri, butun cizimleri kartin icinde kalacak kadar
    iceri kaydirir (silkscreen'in kenarda kesilmemesi icin)."""
    for fp in board.GetFootprints():
        if not fp.GetReference().startswith('J'):
            continue
        bb = fp.GetBoundingBox(False, False)
        x0 = pcbnew.ToMM(bb.GetLeft()) - ORIGIN_X
        y0 = pcbnew.ToMM(bb.GetTop()) - ORIGIN_Y
        x1 = pcbnew.ToMM(bb.GetRight()) - ORIGIN_X
        y1 = pcbnew.ToMM(bb.GetBottom()) - ORIGIN_Y
        dx = max(EDGE_KEEP - x0, 0) - max(x1 - (BOARD_W - EDGE_KEEP), 0)
        dy = max(EDGE_KEEP - y0, 0) - max(y1 - (BOARD_H - EDGE_KEEP), 0)
        if dx or dy:
            p = fp.GetPosition()
            fp.SetPosition(pcbnew.VECTOR2I(p.x + mm(dx), p.y + mm(dy)))


def save(board, name='pelagos-node-carrier.kicad_pcb'):
    out = os.path.join(PROJ, name)
    board.Save(out)
    return out


if __name__ == '__main__':
    b = build()
    print(save(b, 'placement.kicad_pcb'))
