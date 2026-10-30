"""Basit iki katmanli izgara yonlendirici (A*, 45/90 derece).

Her net, once guc netleri olmak uzere sirayla yonlendirilir. Bir net icin
diger netlerin bakiri (iz yari genisligi + bosluk) kadar sisirilip engel
yapilir; A* durumu (katman, y, x, yon) uzerinde calisir, donuslere ve
via'lara maliyet ekler. Sonuc KiCad DRC'si ile ayrica dogrulanir.
"""

import heapq
import math

import numpy as np
import pcbnew
from scipy import ndimage

import design

RES = 0.127                     # izgara (mm)
CLR_RULE = 0.2                  # bakir-bakir bosluk kurali (mm)
CLR = CLR_RULE + RES * 0.75
EDGE_CLR = 0.5 + RES * 0.75     # bakir-kart kenari (mm) + izgara payi
VIA_D, VIA_DRILL = 0.6, 0.3
VIA_COST = 2.5                  # mm esdegeri
BOTTOM_MULT = 1.6               # alt katmani GND duzlemine birakmak icin
TURN45, TURN90 = 0.15, 0.6      # mm esdegeri donus cezalari
H_WEIGHT = 1.6                  # agirlikli A*: hedefe yonelir
MAX_EXPANSIONS = 600_000         # tam kart aramasi; uzun, via'li dolambaclar icin

WIDTHS = design.WIDTHS
DEFAULT_W = 0.25
NECK_W = 0.3                    # ince pinlere girerken iz bu genislige iner
NECK_ZONE = 1.0                 # neck-down'a izin verilen ped cevresi (mm)
WAYPOINTS = []                  # uzun baglantilar icin koridor ara noktalari (route_pcb atar)

DIRS = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]
LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu]


def mm(v):
    return pcbnew.FromMM(float(v))


class Grid:
    def __init__(self, board, ox, oy, w, h, corner_r):
        self.board, self.ox, self.oy = board, ox, oy
        self.W = int(math.ceil(w / RES)) + 1
        self.H = int(math.ceil(h / RES)) + 1
        self.owner = np.zeros((2, self.H, self.W), dtype=np.int32)
        self.padowner = np.zeros((2, self.H, self.W), dtype=np.int32)
        self.netid, self.netname = {}, {}
        self.netinfo = {}
        for name, ni in board.GetNetsByName().items():
            name = str(name)
            if not name:
                continue
            k = len(self.netid) + 1
            self.netid[name] = k
            self.netname[k] = name
            self.netinfo[name] = ni
        yy, xx = np.mgrid[0:self.H, 0:self.W]
        self.X, self.Y = xx * RES, yy * RES
        outside = (self.X < 0) | (self.Y < 0) | (self.X > w) | (self.Y > h)
        for cx, cy in [(corner_r, corner_r), (w - corner_r, corner_r),
                       (corner_r, h - corner_r), (w - corner_r, h - corner_r)]:
            inx = (np.abs(self.X - cx) < corner_r + 1e-9) & ((self.X - cx) * (cx - w / 2) > 0)
            iny = (np.abs(self.Y - cy) < corner_r + 1e-9) & ((self.Y - cy) * (cy - h / 2) > 0)
            outside |= inx & iny & ((self.X - cx) ** 2 + (self.Y - cy) ** 2 > corner_r ** 2)
        edge = outside.copy()
        edge[0, :] = edge[-1, :] = True
        edge[:, 0] = edge[:, -1] = True
        self.edge = edge
        self.pads = {}
        self._raster_pads()

    def to_local(self, p):
        return pcbnew.ToMM(p.x) - self.ox, pcbnew.ToMM(p.y) - self.oy

    def cell(self, x, y):
        return int(round(y / RES)), int(round(x / RES))

    def to_vec(self, i, j):
        return pcbnew.VECTOR2I(mm(self.ox + j * RES), mm(self.oy + i * RES))

    def _win(self, x0, y0, x1, y1):
        i0 = max(int(math.floor(y0 / RES)) - 1, 0)
        i1 = min(int(math.ceil(y1 / RES)) + 2, self.H)
        j0 = max(int(math.floor(x0 / RES)) - 1, 0)
        j1 = min(int(math.ceil(x1 / RES)) + 2, self.W)
        return i0, i1, j0, j1

    def pad_mask(self, pad, shrink=0.0):
        bb = pad.GetBoundingBox()
        x0, y0 = self.to_local(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop()))
        x1, y1 = self.to_local(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
        i0, i1, j0, j1 = self._win(x0, y0, x1, y1)
        X, Y = self.X[i0:i1, j0:j1], self.Y[i0:i1, j0:j1]
        shape = pad.GetShape()
        if shape in (pcbnew.PAD_SHAPE_CIRCLE,) or pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            r = (x1 - x0) / 2 - shrink
            m = (X - cx) ** 2 + (Y - cy) ** 2 <= r * r
        elif shape == pcbnew.PAD_SHAPE_OVAL:
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            a, b = (x1 - x0) / 2 - shrink, (y1 - y0) / 2 - shrink
            rr = min(a, b)
            dx = np.maximum(np.abs(X - cx) - (a - rr), 0)
            dy = np.maximum(np.abs(Y - cy) - (b - rr), 0)
            m = dx * dx + dy * dy <= rr * rr
        else:
            m = ((X >= x0 + shrink) & (X <= x1 - shrink) &
                 (Y >= y0 + shrink) & (Y <= y1 - shrink))
        return (i0, i1, j0, j1), m

    def _raster_pads(self):
        for fp in self.board.GetFootprints():
            for pad in fp.Pads():
                net = pad.GetNetname()
                nid = self.netid.get(net, -2) if net else -2
                (i0, i1, j0, j1), m = self.pad_mask(pad)
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    (i0, i1, j0, j1), m = self.pad_mask(pad, shrink=-0.3)
                for li, L in enumerate(LAYERS):
                    if pad.IsOnLayer(L) or pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                        sub = self.owner[li, i0:i1, j0:j1]
                        sub[m] = nid
                        self.padowner[li, i0:i1, j0:j1][m] = nid
                if net:
                    (ti0, ti1, tj0, tj1), tm = self.pad_mask(pad, shrink=0.05)
                    layers = [li for li, L in enumerate(LAYERS) if pad.IsOnLayer(L)]
                    c = self.to_local(pad.GetPosition())
                    name = fp.GetReference() + '.' + pad.GetNumber()
                    lst = self.pads.setdefault(net, [])
                    # Ayni footprint'te ayni numarali pedler (SOT-89 tab'i, termal via'lar)
                    # fiziksel olarak tek bakirdir: tek hedef say, en buyuk pedi tut.
                    dup = next((k for k, p in enumerate(lst) if p[3] == name), None)
                    entry = (layers, (ti0, tj0, tm), c, name)
                    if dup is None:
                        lst.append(entry)
                    elif tm.sum() > lst[dup][1][2].sum():
                        lst[dup] = entry

    def mark_segment(self, li, x0, y0, x1, y1, hw, nid):
        i0, i1, j0, j1 = self._win(min(x0, x1) - hw, min(y0, y1) - hw,
                                   max(x0, x1) + hw, max(y0, y1) + hw)
        X, Y = self.X[i0:i1, j0:j1], self.Y[i0:i1, j0:j1]
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        if L2 == 0:
            d2 = (X - x0) ** 2 + (Y - y0) ** 2
        else:
            t = np.clip(((X - x0) * dx + (Y - y0) * dy) / L2, 0, 1)
            d2 = (X - x0 - t * dx) ** 2 + (Y - y0 - t * dy) ** 2
        sub = self.owner[li, i0:i1, j0:j1]
        sub[(d2 <= hw * hw) & (sub == 0)] = nid


def disk(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


class Router:
    def __init__(self, grid):
        self.g = grid
        self.tracks = []
        self.vias = []
        self.failed = []
        self.necked = []
        self._blk_cache = {}
        self._edge_cache = {}

    def _edge_dil(self, r):
        if r not in self._edge_cache:
            self._edge_cache[r] = ndimage.binary_dilation(self.g.edge, disk(r))
        return self._edge_cache[r]

    def blocked(self, nid, hw, win):
        i0, i1, j0, j1 = win
        key = (nid, round(hw, 4))
        if key not in self._blk_cache:
            rt = int(math.ceil((hw + CLR) / RES - 1e-6))
            re = int(math.ceil((hw + EDGE_CLR) / RES - 1e-6))
            rv = int(math.ceil((VIA_D / 2 + CLR) / RES - 1e-6))
            rve = int(math.ceil((VIA_D / 2 + EDGE_CLR) / RES - 1e-6))
            e_t = self._edge_dil(re)
            e_v = self._edge_dil(rve)
            bt, bv = [], []
            for li in range(2):
                o = self.g.owner[li]
                other = (o != 0) & (o != nid)
                bt.append(ndimage.binary_dilation(other, disk(rt)) | e_t)
                bv.append(ndimage.binary_dilation(other, disk(rv)) | e_v)
            via_ok = ~(bv[0] | bv[1])
            self._blk_cache[key] = (np.stack(bt), via_ok)
        bt_full, via_full = self._blk_cache[key]
        return bt_full[:, i0:i1, j0:j1], via_full[i0:i1, j0:j1]

    def route_net(self, net):
        self._blk_cache.clear()
        g = self.g
        pads = g.pads.get(net, [])
        if len(pads) < 2:
            return True
        nid = g.netid[net]
        w = WIDTHS.get(net, DEFAULT_W)
        hw = w / 2
        rest = pads[1:]
        tree_pts = [(l, pads[0][2]) for l in pads[0][0]]
        tree_cells = self._pad_cells(pads[0])
        if net == 'GND':
            for vx, vy, vnet in self.vias:
                if vnet == 'GND':
                    vi, vj = g.cell(vx, vy)
                    for li in (0, 1):
                        tree_pts.append((li, (vx, vy)))
                        tree_cells.add((li, vi, vj))
        ok = True
        connected = [pads[0]]
        while rest:
            tgt = min(rest, key=lambda p: min(math.dist(p[2], c) for _, c in tree_pts))
            rest.remove(tgt)
            near_pt = min((c for _, c in tree_pts), key=lambda c: math.dist(c, tgt[2]))
            path = self._astar(nid, hw, tree_cells, tgt, net, near_pt)
            cw = w
            if path is None and w > NECK_W:
                path = self._astar(nid, NECK_W / 2, tree_cells, tgt, net, near_pt)
                cw = NECK_W
                if path is not None:
                    self.necked.append((net, tgt[3], w))
            if path is None:
                path, cw = self._reverse(nid, w, tgt, connected, net)
            if path is None and self._via_waypoint(nid, w, tgt, tree_cells, net):
                connected.append(tgt)
                tree_cells |= self._pad_cells(tgt)
                tree_pts.extend((l, tgt[2]) for l in tgt[0])
                continue
            if path is None:
                self.failed.append((net, tgt[3]))
                ok = False
                tree_cells |= self._pad_cells(tgt)
                continue
            self._commit(path, nid, cw, net, tgt)
            for (li, i, j) in path:
                tree_cells.add((li, i, j))
            tree_cells |= self._pad_cells(tgt)
            connected.append(tgt)
            tree_pts.extend((l, tgt[2]) for l in tgt[0])
            tree_pts.extend((li, (j * RES, i * RES)) for li, i, j in path[::8])
        return ok

    def _waypoint_pad(self, x, y, r_cells=3):
        """Ara nokta icin iki katmanli kucuk disk seklinde sahte hedef."""
        i, j = self.g.cell(x, y)
        tm = disk(r_cells)
        return ([0, 1], (i - r_cells, j - r_cells, tm), (x, y), f'WP({x:.0f},{y:.0f})')

    def _via_waypoint(self, nid, w, tgt, tree_cells, net):
        """Uzun baglanti tek aramada bulunamazsa (Teensy pin siralari gibi uzun bir
        duvarin arkasinda kalinca genisleme siniri dolar) koridor ortasindaki bir
        ara nokta uzerinden iki parcada ara. Iki parca da bulunursa birlikte cizilir."""
        for (x, y) in WAYPOINTS:
            wp = self._waypoint_pad(x, y)
            for cw in ((w, NECK_W) if w > NECK_W else (w,)):
                self._blk_cache.clear()
                p2 = self._astar_win(nid, cw / 2, self._pad_cells(tgt), wp, net, full=True,
                                     near_pt=tgt[2])
                if p2 is None:
                    continue
                narrow2 = self._narrow
                p1 = self._astar_win(nid, cw / 2, tree_cells, wp, net, full=True,
                                     near_pt=(x, y))
                if p1 is None:
                    continue
                self._commit(p1, nid, cw, net, wp)
                self._narrow = narrow2
                p2.reverse()
                self._commit(p2, nid, cw, net, tgt)
                # Birlesim: p1 ara nokta merkezinde biter; p2'nin basini merkeze bagla,
                # katmanlar farkliysa merkeze via koy.
                g = self.g
                l2, i2, j2 = p2[0]
                self.tracks.append((l2, j2 * RES, i2 * RES, x, y, cw, net))
                g.mark_segment(l2, j2 * RES, i2 * RES, x, y, cw / 2, nid)
                if p1[-1][0] != l2:
                    self.vias.append((x, y, net))
                    for li in range(2):
                        g.mark_segment(li, x, y, x, y, VIA_D / 2, nid)
                if cw != w:
                    self.necked.append((net, tgt[3], w))
                return True
        return False

    def _reverse(self, nid, w, tgt, connected, net):
        """Agactan hedefe arama bulamazsa hedeften agactaki en yakin bagli pede ara.
        Ozel sekilli pedlerde (SOT-89 tab'i) pad merkezi dar bacakta kaldigi icin
        tek yonlu arama takilabiliyor; ters yonde yaklasim serbest taraftan olur."""
        for anchor in sorted(connected, key=lambda p: math.dist(p[2], tgt[2]))[:3]:
            for cw in ((w, NECK_W) if w > NECK_W else (w,)):
                self._blk_cache.clear()
                path = self._astar_win(nid, cw / 2, self._pad_cells(tgt), anchor, net,
                                       full=True, near_pt=tgt[2])
                if path is not None:
                    path.reverse()
                    if cw != w:
                        self.necked.append((net, tgt[3], w))
                    return path, cw
        return None, w

    def _pad_cells(self, pad):
        layers, (ti0, tj0, tm), _, _ = pad
        cells = set()
        ii, jj = np.nonzero(tm)
        for li in layers:
            for a, b in zip(ii, jj):
                cells.add((li, ti0 + a, tj0 + b))
        return cells

    def _astar(self, nid, hw, sources, tgt, net, near_pt=None):
        path = self._astar_win(nid, hw, sources, tgt, net, full=False, near_pt=near_pt)
        if path is None:
            path = self._astar_win(nid, hw, sources, tgt, net, full=True, near_pt=near_pt)
        return path

    def _astar_win(self, nid, hw, sources, tgt, net, full, near_pt=None):
        g = self.g
        tcells = self._pad_cells(tgt)
        if full:
            i0, i1, j0, j1 = 0, g.H, 0, g.W
        else:
            mi = 10.0 / RES
            tx, ty = tgt[2]
            nx, ny = near_pt if near_pt is not None else (tx, ty)
            i0 = max(int(min(ty, ny) / RES - mi), 0)
            i1 = min(int(max(ty, ny) / RES + mi) + 1, g.H)
            j0 = max(int(min(tx, nx) / RES - mi), 0)
            j1 = min(int(max(tx, nx) / RES + mi) + 1, g.W)
        bt, via_ok = self.blocked(nid, hw, (i0, i1, j0, j1))
        nhw = min(hw, NECK_W / 2)
        btn = bt if nhw == hw else self.blocked(nid, nhw, (i0, i1, j0, j1))[0]
        Hh, Ww = i1 - i0, j1 - j0
        own = [(g.owner[li, i0:i1, j0:j1] == nid) for li in range(2)]
        rz = int(math.ceil(NECK_ZONE / RES))
        zkey = ('zone', nid)
        if zkey not in self._blk_cache:
            self._blk_cache[zkey] = [
                ndimage.binary_dilation(g.padowner[li] == nid, disk(rz))
                for li in range(2)
            ]
        pzone = self._blk_cache[zkey]
        zone = [own[li] | pzone[li][i0:i1, j0:j1] for li in range(2)]
        free = np.stack([~bt[li] | (zone[li] & ~btn[li]) for li in range(2)])
        self._narrow = (i0, j0, np.stack([zone[li] & bt[li] for li in range(2)]))
        vol = np.stack([free[0], via_ok & free[0] & free[1], free[1]])
        lbl, _ = ndimage.label(vol)
        src_lbls = {int(lbl[li * 2, i - i0, j - j0]) for (li, i, j) in sources
                    if i0 <= i < i1 and j0 <= j < j1 and free[li, i - i0, j - j0]}
        src_lbls.discard(0)
        if not src_lbls:
            return None
        tset = {(li, i - i0, j - j0) for (li, i, j) in tcells
                if i0 <= i < i1 and j0 <= j < j1 and int(lbl[li * 2, i - i0, j - j0]) in src_lbls}
        if not tset:
            return None
        tx, ty = tgt[2]
        tci, tcj = ty / RES - i0, tx / RES - j0
        ND = 9
        N = 2 * Hh * Ww * ND
        gcost = np.full(N, np.inf, dtype=np.float64)
        parent = np.full(N, -1, dtype=np.int64)

        def idx(li, i, j, d):
            return ((li * Hh + i) * Ww + j) * ND + d

        def h(i, j):
            dy, dx = abs(i - tci), abs(j - tcj)
            return (max(dx, dy) + (math.sqrt(2) - 1) * min(dx, dy)) * RES * H_WEIGHT

        heap = []
        for (li, i, j) in sources:
            if not (i0 <= i < i1 and j0 <= j < j1):
                continue
            ii, jj = i - i0, j - j0
            if not free[li, ii, jj]:
                continue
            s = idx(li, ii, jj, 8)
            gcost[s] = 0
            heapq.heappush(heap, (h(ii, jj), 0.0, s))
        step = [RES * (math.sqrt(2) if d % 2 else 1) for d in range(8)]
        lm = [1.0, BOTTOM_MULT]
        found = None
        expansions = 0
        while heap:
            f, gc, s = heapq.heappop(heap)
            if gc > gcost[s]:
                continue
            d = s % ND
            rem = s // ND
            j = rem % Ww
            rem //= Ww
            i = rem % Hh
            li = rem // Hh
            if (li, i, j) in tset:
                found = s
                break
            expansions += 1
            if expansions > (MAX_EXPANSIONS if full else 60_000):
                break
            for nd, (di, dj) in enumerate(DIRS):
                if d != 8:
                    dd = min((nd - d) % 8, (d - nd) % 8)
                    if dd > 2:
                        continue
                    tc = 0 if dd == 0 else (TURN45 if dd == 1 else TURN90)
                else:
                    tc = 0
                ni, nj = i + di, j + dj
                if not (0 <= ni < Hh and 0 <= nj < Ww) or not free[li, ni, nj]:
                    continue
                if nd % 2 and not (free[li, i + di, j] and free[li, i, j + dj]):
                    continue
                ng = gc + step[nd] * lm[li] + tc
                t = idx(li, ni, nj, nd)
                if ng < gcost[t]:
                    gcost[t] = ng
                    parent[t] = s
                    heapq.heappush(heap, (ng + h(ni, nj), ng, t))
            if via_ok[i, j]:
                ol = 1 - li
                if free[ol, i, j]:
                    ng = gc + VIA_COST
                    t = idx(ol, i, j, 8)
                    if ng < gcost[t]:
                        gcost[t] = ng
                        parent[t] = s
                        heapq.heappush(heap, (ng + h(i, j), ng, t))
        if found is None:
            return None
        path = []
        s = found
        while s != -1:
            rem = s // ND
            j = rem % Ww
            rem //= Ww
            i = rem % Hh
            li = rem // Hh
            path.append((li, i + i0, j + j0))
            s = int(parent[s])
        path.reverse()
        return path

    def _commit(self, path, nid, w, net, tgt):
        g = self.g
        nw = min(w, NECK_W)
        ni0, nj0, narrow = self._narrow

        def is_narrow(c):
            li, i, j = c
            return bool(narrow[li, i - ni0, j - nj0])

        flags = [is_narrow(c) for c in path]
        pts = [0]
        for k in range(1, len(path) - 1):
            a, b, c = path[k - 1], path[k], path[k + 1]
            if b[0] != a[0] or c[0] != b[0] or flags[k] != flags[k + 1]:
                pts.append(k)
                continue
            if (b[1] - a[1], b[2] - a[2]) != (c[1] - b[1], c[2] - b[2]):
                pts.append(k)
        if len(path) > 1:
            pts.append(len(path) - 1)
        drawn = []
        for a_k, b_k in zip(pts, pts[1:]):
            a, b = path[a_k], path[b_k]
            if a[0] != b[0]:
                x, y = a[2] * RES, a[1] * RES
                self.vias.append((x, y, net))
                for li in range(2):
                    g.mark_segment(li, x, y, x, y, VIA_D / 2, nid)
                continue
            if (a[1], a[2]) == (b[1], b[2]):
                continue
            sw = nw if any(flags[a_k:b_k + 1]) else w
            drawn.append((a[0], a[2] * RES, a[1] * RES, b[2] * RES, b[1] * RES, sw))
        last = path[-1]
        tx, ty = tgt[2]
        if last[0] in tgt[0]:
            drawn.append((last[0], last[2] * RES, last[1] * RES, tx, ty, nw))
        for (li, x0, y0, x1, y1, sw) in drawn:
            self.tracks.append((li, x0, y0, x1, y1, sw, net))
            g.mark_segment(li, x0, y0, x1, y1, sw / 2, nid)
        return drawn

    def add_stitching(self, net='GND', pitch=4.0, keepout=None):
        self._blk_cache.clear()
        g = self.g
        nid = g.netid[net]
        _, via_ok = self.blocked(nid, VIA_D / 2, (0, g.H, 0, g.W))
        n = 0
        step = int(round(pitch / RES))
        for i in range(step // 2, g.H, step):
            for j in range(step // 2, g.W, step):
                if not via_ok[i, j]:
                    continue
                x, y = j * RES, i * RES
                if keepout and any(x0 <= x <= x1 and y0 <= y <= y1 for x0, y0, x1, y1 in keepout):
                    continue
                self.vias.append((x, y, net))
                for li in range(2):
                    g.mark_segment(li, x, y, x, y, VIA_D / 2, nid)
                n += 1
        return n

    def apply(self, board):
        g = self.g
        for (li, x0, y0, x1, y1, w, net) in self.tracks:
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(mm(g.ox + x0), mm(g.oy + y0)))
            t.SetEnd(pcbnew.VECTOR2I(mm(g.ox + x1), mm(g.oy + y1)))
            t.SetWidth(mm(w))
            t.SetLayer(LAYERS[li])
            t.SetNet(g.netinfo[net])
            board.Add(t)
        for (x, y, net) in self.vias:
            v = pcbnew.PCB_VIA(board)
            v.SetPosition(pcbnew.VECTOR2I(mm(g.ox + x), mm(g.oy + y)))
            v.SetWidth(mm(VIA_D))
            v.SetDrill(mm(VIA_DRILL))
            v.SetViaType(pcbnew.VIATYPE_THROUGH)
            v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
            v.SetNet(g.netinfo[net])
            board.Add(v)


def hpwl(grid, net):
    pts = [p[2] for p in grid.pads.get(net, [])]
    if len(pts) < 2:
        return 0
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (max(xs) - min(xs)) + (max(ys) - min(ys))


def net_order(grid, nets):
    power = [n for n in nets if n in WIDTHS and n != 'GND']
    early_sig = [n for n in ('T_ESC_EN', 'KILL_DIV', 'DEPTH_RAW', 'T_KILL_SENSE',
                             'T_PWM5', 'T_PWM4', 'T_PWM3', 'T_PWM2', 'T_PWM1', 'T_PWM0')
                 if n in nets]
    sig = [n for n in nets if n not in WIDTHS and n not in early_sig and n != 'GND']
    power.sort(key=lambda n: (-WIDTHS[n], hpwl(grid, n)))
    sig.sort(key=lambda n: hpwl(grid, n))
    tail = ['GND'] if 'GND' in nets else []
    return power + early_sig + sig + tail
