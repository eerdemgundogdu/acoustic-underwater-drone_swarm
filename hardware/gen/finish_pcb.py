"""Yonlendirilmis karta GND dokumu ve yazilar ekler, KiCad DRC'sini calistirir.

    python3 finish_pcb.py [girdi.kicad_pcb]
"""

import os
import re
import sys

os.environ.setdefault("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
os.environ.setdefault("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")
import pcbnew  # noqa: E402

import make_pcb  # noqa: E402

PROJ = make_pcb.PROJ


def mm(v):
    return pcbnew.FromMM(float(v))


def add_gnd_zones(board):
    gnd = board.FindNet('GND')
    inset = 0.3
    w, h = make_pcb.BOARD_W, make_pcb.BOARD_H
    # Teensy soket GND pinleri: iki sira arasindaki ust katman dokumu kucuk adalara
    # bolunuyor; termal kollar bu adalara dusunce KiCad 9 "starved_thermal" verir.
    # Bu pinlerde dokume tam (solid) baglanti kullan.
    for pad in board.FindFootprintByReference('U3').Pads():
        if pad.GetNetname() == 'GND':
            pad.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNetCode(gnd.GetNetCode())
        o = z.Outline()
        o.NewOutline()
        for x, y in [(inset, inset), (w - inset, inset), (w - inset, h - inset), (inset, h - inset)]:
            o.Append(mm(make_pcb.ORIGIN_X + x), mm(make_pcb.ORIGIN_Y + y))
        z.SetLocalClearance(mm(0.3))
        z.SetMinThickness(mm(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(mm(0.3))
        z.SetThermalReliefSpokeWidth(mm(0.4))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetAssignedPriority(0)
        z.SetZoneName(f'GND_{"F" if layer == pcbnew.F_Cu else "B"}')
        board.Add(z)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def _box(fp_or_item):
    bb = fp_or_item.GetBoundingBox(False, False) if hasattr(fp_or_item, 'Pads') \
        else fp_or_item.GetBoundingBox()
    return (pcbnew.ToMM(bb.GetLeft()) - make_pcb.ORIGIN_X, pcbnew.ToMM(bb.GetTop()) - make_pcb.ORIGIN_Y,
            pcbnew.ToMM(bb.GetRight()) - make_pcb.ORIGIN_X, pcbnew.ToMM(bb.GetBottom()) - make_pcb.ORIGIN_Y)


def _hit(a, b, m=0.3):
    return a[0] - m < b[2] and b[0] - m < a[2] and a[1] - m < b[3] and b[1] - m < a[3]


class Labeler:
    """Silkscreen etiketlerini parca govdelerine, pedlere ve birbirine
    degmeyen ilk bos yere koyar."""

    def __init__(self, board):
        self.board = board
        self.obst = [_box(fp) for fp in board.GetFootprints()]
        self.w, self.h = make_pcb.BOARD_W, make_pcb.BOARD_H

    def _make(self, text, size, layer, bold):
        t = pcbnew.PCB_TEXT(self.board)
        t.SetText(text)
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(size * 0.15))
        t.SetBold(bold)
        if layer == pcbnew.B_SilkS:
            t.SetMirrored(True)
        return t

    def place(self, text, candidates, size=0.9, layer=pcbnew.F_SilkS, bold=False, quiet=False,
              angle=0):
        t = self._make(text, size, layer, bold)
        if angle:
            t.SetTextAngle(pcbnew.EDA_ANGLE(angle, pcbnew.DEGREES_T))
        for (x, y) in candidates:
            t.SetPosition(make_pcb.pt(x, y))
            b = _box(t)
            if b[0] < 0.6 or b[1] < 0.6 or b[2] > self.w - 0.6 or b[3] > self.h - 0.6:
                continue
            if any(_hit(b, o) for o in self.obst):
                continue
            self.board.Add(t)
            self.obst.append(b)
            return (x, y)
        if not quiet:
            print('  etiket icin yer bulunamadi:', text)
        return None

    def near(self, text, ref, **kw):
        fp = self.board.FindFootprintByReference(ref)
        x0, y0, x1, y1 = _box(fp)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        cands = []
        for d in [1.2 + 0.5 * k for k in range(14)]:
            cands += [(x1 + d + 3, cy), (cx, y0 - d), (cx, y1 + d), (x0 - d - 3, cy),
                      (x1 + d + 3, y0), (x1 + d + 3, y1)]
        hit = self.place(text, cands, quiet=True, **kw)
        if hit is None:
            r = 14.0
            hit = self.scan(text, max(x0 - r, 1), max(y0 - r, 1),
                            min(x1 + r, self.w - 1), min(y1 + r, self.h - 1), step=0.5, **kw)
        return hit

    def beside(self, text, ref, **kw):
        """Konnektorun hemen soluna dikey etiket."""
        fp = self.board.FindFootprintByReference(ref)
        x0, y0, x1, y1 = _box(fp)
        cy = (y0 + y1) / 2
        cands = [(x0 - d, cy + dy) for d in [0.9 + 0.25 * k for k in range(12)]
                 for dy in (0, -0.5, 0.5, -1.0, 1.0)]
        return self.place(text, cands, angle=90, **kw)

    def scan(self, text, x0, y0, x1, y1, step=1.0, **kw):
        cands = [(x0 + i * step, y0 + j * step)
                 for j in range(int((y1 - y0) / step) + 1)
                 for i in range(int((x1 - x0) / step) + 1)]
        return self.place(text, cands, **kw)


def add_labels(board):
    L = Labeler(board)
    for text, ref in [('ARM-SW', 'J11'), ('KONTAKTOR', 'J12')]:
        if L.beside(text, ref, size=0.8, quiet=True) is None:
            L.near(text, ref, size=0.8)
    for text, ref in [('PIEZO/HV', 'J1'), ('HIDROFON', 'J2'), ('AFE-I2C', 'J3'), ('SIZINTI', 'J4'),
                      ('CH0', 'J5'), ('CH1', 'J6'), ('CH2', 'J7'), ('CH3', 'J8'),
                      ('CH4', 'J9'), ('CH5', 'J10'),
                      ('+24V', 'TP1'), ('+5V', 'TP2'),
                      ('+3V3', 'TP3'), ('GND', 'TP4')]:
        L.near(text, ref, size=0.8 if ref.startswith('TP') else 0.9)
    L.scan('PELAGOS AKUSTIK DUGUM KARTI REV A', 55, 25, 100, 80, size=1.2, bold=True)
    L.scan('PASIF AKUSTIK VE ENERJI HASADI 2026', 55, 25, 100, 80, size=1.0)
    L.scan('Rev A: uretilmedi / test edilmedi', 20, 30, 95, 80, size=0.8,
           layer=pcbnew.B_SilkS)


def run_drc(board, path):
    pcbnew.WriteDRCReport(board, path, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(path).read()
    counts = {
        'violations': int(re.search(r'\*\* Found (\d+) DRC violations', txt).group(1)),
        'unconnected': int(re.search(r'\*\* Found (\d+) unconnected pads', txt).group(1)),
    }
    kinds = {}
    for m in re.finditer(r'^\[(\w+)\]', txt, re.M):
        kinds[m.group(1)] = kinds.get(m.group(1), 0) + 1
    return counts, kinds


def main(src=None):
    src = src or os.path.join(PROJ, 'routed.kicad_pcb')
    board = pcbnew.LoadBoard(src)
    add_gnd_zones(board)
    add_labels(board)
    out = os.path.join(PROJ, 'pelagos-node-carrier.kicad_pcb')
    board.Save(out)
    board = pcbnew.LoadBoard(out)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(out)
    rep = os.path.join(PROJ, '..', 'output', 'drc_report.txt')
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    counts, kinds = run_drc(board, rep)
    with open(rep) as f:
        txt = f.read().replace(out, 'pelagos-node-carrier.kicad_pcb')
    txt = txt.replace(os.path.normpath(out), 'pelagos-node-carrier.kicad_pcb')
    with open(rep, 'w') as f:
        f.write(txt)
    print(out)
    print('DRC:', counts, kinds)
    return counts, kinds


if __name__ == '__main__':
    main(*sys.argv[1:])
