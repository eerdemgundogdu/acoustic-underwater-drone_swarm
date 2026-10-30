"""Yerlesimi kurar, tum netleri yonlendirir ve kaydeder.

    python3 route_pcb.py
"""

import os
import time

import kicad_env  # noqa: F401
import pcbnew  # noqa: E402

import make_pcb  # noqa: E402
import router  # noqa: E402


def get_keepout(board):
    keepout = []
    for fp in board.GetFootprints():
        bb = fp.GetBoundingBox(False, False)
        keepout.append((pcbnew.ToMM(bb.GetLeft()) - make_pcb.ORIGIN_X - 0.5,
                        pcbnew.ToMM(bb.GetTop()) - make_pcb.ORIGIN_Y - 0.5,
                        pcbnew.ToMM(bb.GetRight()) - make_pcb.ORIGIN_X + 0.5,
                        pcbnew.ToMM(bb.GetBottom()) - make_pcb.ORIGIN_Y + 0.5))
    return keepout


def attempt(priority, verbose):
    router.WAYPOINTS = make_pcb.WAYPOINTS
    board = make_pcb.build()
    grid = router.Grid(board, make_pcb.ORIGIN_X, make_pcb.ORIGIN_Y,
                       make_pcb.BOARD_W, make_pcb.BOARD_H, make_pcb.CORNER_R)
    r = router.Router(grid)
    nets = sorted(grid.pads.keys())
    order = router.net_order(grid, nets)
    pwr = [n for n in order if n in router.WIDTHS and n != 'GND']
    prio = [n for n in priority if n in order and n not in pwr and n != 'GND']
    rest = [n for n in order if n not in pwr and n not in prio and n != 'GND']
    # GND en son: dikis via'lari sinyallerden kalan bos alana yerlesir, dar
    # koridorlari (Teensy yani gibi) tikamaz. GND'nin asil baglantisi iki katman dokumdur.
    order = pwr + prio + rest + ['GND']
    for n in order:
        if n == 'GND':
            r.stitch_count = r.add_stitching('GND', 4.0, get_keepout(board))
        t = time.time()
        ok = r.route_net(n)
        dt = time.time() - t
        if verbose and (not ok or dt > 0.5):
            print(f'  {"OK  " if ok else "HATA"} {n:16s} {dt:5.1f}s', flush=True)
    return board, r


def run(save_name='routed.kicad_pcb', verbose=True, max_attempts=4):
    t0 = time.time()
    priority, best = [], None
    for k in range(max_attempts):
        board, r = attempt(priority, verbose)
        print(f'deneme {k + 1}: {len(r.failed)} basarisiz', flush=True)
        if best is None or len(r.failed) < len(best[1].failed):
            best = (board, r)
        if not r.failed:
            break
        for net, _ in r.failed:
            if net not in priority:
                priority.insert(0, net)
    board, r = best
    print(f'{r.stitch_count} GND dikis via', flush=True)
    r.apply(board)
    out = make_pcb.save(board, save_name)
    print(f'{len(r.tracks)} iz, {len(r.vias)} via, {len(r.failed)} basarisiz baglanti, '
          f'{time.time() - t0:.0f}s')
    for f in r.failed:
        print('  BASARISIZ', f)
    for n in r.necked:
        print('  INCELTILDI', n)
    return out, r


if __name__ == '__main__':
    run()
