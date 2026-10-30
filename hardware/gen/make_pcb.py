"""design.py netlist'inden PCB'yi kurar: footprint'ler, netler, yerlesim,
kart kenari. Yol cizimi router.py, bakir dokum ve DRC finish_pcb.py'dedir.

Koordinatlar mm; (0,0) kartin sol ust kosesi. KiCad sayfasinda kart
(ORIGIN_X, ORIGIN_Y) noktasina tasinir.

Yerlesim mantigi:
  sag ust  : pil girisi, koruma, 5 V buck + uyanma mandali, anahtarli pil olcumu
  sag orta : hidrofon AFE (Teensy ADC pinleri 16/17'ye kisa yol), J4 sag kenarda
  sag alt  : pasif uyanma yukselteci + karsilastirici (J4'e yakin, yuksek empedansli giris kisa)
  sol ust  : piezo hasadi (kopru + depolama + HT7533), sol ortada hep acik LDO + diyot-VEYA
  sol alt  : DRV8871 modem H-koprusu (anahtarlamali akim AFE'den en uzak kosede)
  alt 10 mm ve Teensy sag sirasi yaninda 10 mm: kart boyu yonlendirme koridorlari
"""

import os
import xml.etree.ElementTree as ET

import kicad_env  # noqa: F401  (KICADx_FOOTPRINT_DIR ayari pcbnew'den once)
import pcbnew  # noqa: E402

import design  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.join(HERE, '..', 'acoustic-swarm-node')
FPDIR = kicad_env.FPDIR

ORIGIN_X, ORIGIN_Y = 50.0, 50.0
BOARD_W, BOARD_H = 120.0, 95.0
CORNER_R = 3.0

# ref: (x, y, aci_derece)
TX, TY = 30.48, 12.7            # Teensy pad 1 (sol ust GND)

PLACE = {
    # --- MCU ---
    'U7': (TX, TY, 0),

    # --- Pil girisi ve koruma (sag ust) ---
    'J1': (113.0, 9.0, 90),
    'F1': (104.5, 4.0, 0),
    'J2': (94.5, 4.0, 0),
    'D1': (102.5, 10.5, 0),
    'D2': (102.0, 21.5, 0),
    'C1': (111.5, 21.5, 90),
    'C2': (95.0, 15.0, 90),
    'C3': (99.0, 15.0, 90),
    'TP1': (106.0, 15.5, 0),

    # --- 5 V buck (ust orta) ---
    'U5': (85.0, 11.0, 0),
    'C21': (85.0, 7.0, 0),
    'D7': (89.0, 17.5, 90),
    'L1': (78.0, 7.0, 0),
    'R21': (80.0, 14.0, 90),
    'R22': (82.5, 15.0, 90),
    'C22': (70.0, 4.0, 0),
    'C23': (70.0, 8.0, 0),
    'R23': (65.0, 16.0, 0),
    'D8': (69.0, 16.0, 180),
    'D9': (61.5, 8.0, 90),
    'TP2': (65.0, 4.0, 0),


    # --- Anahtarli pil olcumu ---
    'Q1': (106.5, 29.5, 0),
    'R1': (102.0, 27.0, 0),
    'R2': (102.0, 30.0, 0),
    'Q2': (97.0, 29.5, 0),
    'R3': (92.0, 28.0, 0),
    'R4': (92.0, 31.0, 0),
    'R5': (87.0, 28.0, 0),
    'R6': (87.0, 31.0, 0),
    'C4': (82.5, 28.0, 0),
    'D3': (82.5, 31.5, 0),
    'R7': (59.0, 41.0, 90),


    # --- Analog LDO ---
    'U6': (65.0, 26.0, 0),
    'C24': (65.0, 22.0, 0),
    'C25': (69.5, 26.0, 90),
    'TP3': (70.5, 30.5, 0),

    # --- Hidrofon AFE (sag orta; akis sagdan sola: J4 -> U8 -> U9 -> ADC) ---
    'J4': (116.0, 46.0, 90),
    'C28': (106.5, 44.0, 90),
    'R27': (102.5, 43.0, 0),
    'R28': (102.5, 46.0, 0),
    'D10': (98.0, 40.5, 0),
    'U8': (94.0, 47.5, 0),
    'R29': (96.5, 53.0, 0),
    'R30': (93.0, 53.0, 0),
    'R31': (89.5, 53.0, 0),
    'R32': (86.0, 53.0, 0),
    'C29': (96.5, 56.5, 0),
    'C30': (92.5, 56.5, 0),
    'C31': (89.0, 59.5, 0),
    'C32': (94.0, 42.0, 0),
    'U9': (80.0, 47.5, 0),
    'R33': (73.5, 46.0, 90),
    'C33': (71.5, 46.0, 90),
    'R34': (73.5, 50.5, 90),
    'C34': (71.5, 51.0, 90),
    'C35': (80.0, 42.0, 0),
    'R24': (76.0, 60.0, 0),
    'R25': (79.5, 60.0, 0),
    'C26': (83.5, 60.0, 0),
    'R26': (74.5, 56.5, 0),
    'C27': (78.0, 56.5, 0),
    'TP6': (70.5, 57.0, 0),
    'R35': (64.0, 36.0, 0),
    'C36': (67.5, 36.0, 0),
    'D11': (65.0, 32.0, 0),
    'R36': (64.0, 39.0, 0),
    'C37': (67.5, 39.0, 0),
    'D12': (65.0, 43.0, 0),

    # --- Teensy sag sirasi: seri direncler (pin 13, 14, 15, 40, 41) ---
    'R42': (61.0, 44.0, 90),
    'R43': (59.0, 47.0, 90),
    'D13': (61.0, 48.5, 90),

    # --- Uyanma mandali (buck EN yaninda; PWR_HOLD = pin 23, WAKE = pin 21) ---
    'D6': (76.0, 19.5, 0),
    'R20': (81.0, 19.0, 90),
    'C20': (83.5, 19.5, 90),
    'R19': (72.5, 22.5, 90),

    # --- Su sizinti probu (J6 alt kenarda) ---
    'R40': (65.0, 48.0, 0),
    'R41': (65.0, 51.0, 0),
    'C41': (65.0, 54.0, 0),
    'J6': (44.0, 91.0, 0),

    # --- Pasif akustik uyanma (sag alt) ---
    'C13': (106.5, 52.0, 90),
    'U3': (101.0, 66.0, 0),
    'R12': (95.0, 63.5, 0),
    'R13': (95.0, 66.5, 0),
    'C14': (95.0, 69.5, 0),
    'R14': (106.5, 71.0, 0),
    'R15': (103.0, 71.0, 0),
    'C15': (99.5, 71.0, 0),
    'C16': (101.0, 61.5, 0),
    'R9': (106.5, 74.5, 0),
    'R10': (103.0, 74.5, 0),
    'C12': (99.5, 74.5, 0),
    'R11': (106.5, 59.0, 0),
    'D5': (91.0, 66.0, 0),
    'C17': (91.0, 69.5, 0),
    'R16': (91.0, 72.5, 0),
    'U4': (85.5, 67.0, 0),
    'R17': (85.5, 71.5, 0),
    'R18': (85.5, 74.5, 0),
    'C18': (81.5, 71.5, 0),
    'C19': (85.5, 63.3, 180),

    # --- Piezo hasadi (sol ust) ---
    'J3': (3.5, 14.0, 270),
    'D14': (10.5, 11.5, 0),
    'D15': (10.5, 16.5, 0),
    'C7': (16.0, 14.0, 90),
    'C8': (19.5, 14.0, 90),
    'D16': (15.0, 20.0, 0),
    'U2': (23.5, 14.0, 0),
    'C9': (23.0, 20.0, 0),
    'R44': (23.0, 23.0, 0),

    # --- Hep acik besleme (sol orta): HT7533 + diyot-VEYA, hasat durumu pin 12 ---
    'U1': (12.0, 40.0, 0),
    'C5': (6.5, 40.0, 90),
    'C6': (17.5, 40.0, 90),
    'D4': (12.0, 46.0, 0),
    'C11': (17.5, 46.0, 90),
    'TP5': (6.5, 46.5, 0),
    'R8': (25.0, 45.72, 0),

    # --- Teensy sol sirasi: modem PWM seri direncleri (pin 6, 9) ---
    'R37': (25.0, 30.48, 0),
    'R38': (25.0, 38.1, 0),

    # --- Modem H-koprusu (sol alt) ---
    'U10': (16.0, 70.0, 180),
    'R39': (21.5, 66.0, 90),
    'C38': (16.0, 79.0, 0),
    'C39': (14.0, 64.5, 0),
    'C40': (9.5, 77.0, 90),
    'J5': (3.5, 69.0, 270),
    'TP4': (30.0, 89.0, 0),

    # --- Montaj delikleri (koseler) ---
    'H1': (4.0, 4.0, 0),
    'H2': (116.0, 31.0, 0),
    'H3': (4.0, 91.0, 0),
    'H4': (116.0, 91.0, 0),
}

# Teensy'nin iki pin sirasi kalin/uzun izler icin bir duvardir; kart boyu baglantilar
# yonlendiricide once dogrudan, olmazsa bu koridor ortalarindan gecirilerek aranir.
WAYPOINTS = [(38.0, 82.0), (38.0, 4.5), (52.0, 40.0)]

SILK_REFS = {'U7'}


def load_fp(fpid):
    lib, name = fpid.split(':')
    path = (os.path.join(PROJ, 'acoustic.pretty') if lib == 'acoustic'
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
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(mm(0.2))
    nc.SetTrackWidth(mm(0.25))
    nc.SetViaDiameter(mm(0.6))
    nc.SetViaDrill(mm(0.3))


def unconnected_nets():
    """Sematikte bos birakilan pinler icin KiCad'in verdigi 'unconnected-(...)' net
    adlari. PCB pedleri ayni adi tasimazsa DRC paritesi net_conflict uyarisi verir."""
    path = os.path.join(HERE, '..', 'output', 'netlist.xml')
    if not os.path.exists(path):
        return {}
    out = {}
    for net in ET.parse(path).getroot().iter('net'):
        name = net.get('name')
        if name.startswith('unconnected-'):
            for n in net.iter('node'):
                # KiCad net adlarinda '/' (Teensy '0/RX1' pin adi) {slash} olarak kacislanir
                out[(n.get('ref'), n.get('pin'))] = name.replace('/', '{slash}')
    return out


def build():
    board = pcbnew.BOARD()
    setup_rules(board)

    netcodes = {}
    for i, name in enumerate(sorted(design.nets().keys())):
        ni = pcbnew.NETINFO_ITEM(board, name, i + 1)
        board.Add(ni)
        netcodes[name] = ni
    nc_nets = unconnected_nets()
    for name in sorted(set(nc_nets.values())):
        ni = pcbnew.NETINFO_ITEM(board, name, len(netcodes) + 1)
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
            net = p.pins.get(pad.GetNumber(), '') or nc_nets.get((p.ref, pad.GetNumber()), '')
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


def save(board, name='acoustic-swarm-node.kicad_pcb'):
    out = os.path.join(PROJ, name)
    board.Save(out)
    return out


if __name__ == '__main__':
    b = build()
    print(save(b, 'placement.kicad_pcb'))
