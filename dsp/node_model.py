"""Akustik suru dugumu: donanim degerlerinden analitik model.

Bilesen degerleri dogrudan hardware/gen/design.py'den okunur; boylece
sematik ile firmware sabitleri (AFE kazanclari, bolucu oranlari) ayrisirsa
dsp/test_node_model.py kirilir.

Icerik:
  - AFE: on yukseltec, Sallen-Key anti-aliasing, ikinci kademe, toplam yanit
  - Pasif uyanma yolu: kazanc, bant, esik
  - Hep acik alan akim butcesi ve pil omru
  - Akustik BFSK baglanti butcesi (sonar denklemi, Thorp sogurmasi)

    python3 dsp/node_model.py
"""

import math
import os
import re
import sys
from dataclasses import dataclass

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'hardware', 'gen'))
import design  # noqa: E402

SUFFIX = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'k': 1e3, 'M': 1e6, '': 1.0}


def parse_value(text):
    """'9.1k' -> 9100, '2.2nF' -> 2.2e-9, '22uF 25V' -> 22e-6, '49.9' -> 49.9"""
    m = re.match(r'^\s*([0-9.]+)\s*([pnumkM]?)', text)
    if not m:
        raise ValueError(text)
    return float(m.group(1)) * SUFFIX[m.group(2)]


PARTS = {p.ref: p for p in design.PARTS}


def val(ref):
    return parse_value(PARTS[ref].value)


# -----------------------------------------------------------------------------
# AFE
# -----------------------------------------------------------------------------
@dataclass
class AfeModel:
    gain1: float          # U8A on yukseltec
    hp1_hz: float         # R30/C29 (kazanc bacagi) yuksek geciren kutup
    sk_fc_hz: float       # Sallen-Key dogal frekans
    sk_q: float
    gain2: float          # U9A
    lp2_hz: float         # R33 || C33 kutbu
    adc_rc_hz: float      # R35/C36 yuk kovasi
    bias_hp_hz: float     # C28 / R28 giris kuplaji

    @property
    def gain_lo(self):
        return self.gain1

    @property
    def gain_hi(self):
        return self.gain1 * self.gain2

    def response(self, f):
        """AFE_HI kompleks yaniti (ADC pininde, giris volt basina)."""
        s = 2j * np.pi * np.asarray(f, dtype=float)
        w0 = 2 * np.pi * self.sk_fc_hz
        h_sk = w0 ** 2 / (s ** 2 + s * w0 / self.sk_q + w0 ** 2)
        wh1 = 2 * np.pi * self.hp1_hz
        h1 = 1 + (self.gain1 - 1) * s / (s + wh1)
        wh2 = 2 * np.pi * self.hp1_hz
        w2 = 2 * np.pi * self.lp2_hz
        h2 = 1 + (self.gain2 - 1) * (s / (s + wh2)) / (1 + s / w2)
        wb = 2 * np.pi * self.bias_hp_hz
        h_in = s / (s + wb)
        h_rc = 1 / (1 + s / (2 * np.pi * self.adc_rc_hz))
        return h_in * h1 * h_sk * h2 * h_rc


def afe_model():
    r31, r32, c30, c31 = val('R31'), val('R32'), val('C30'), val('C31')
    # Birim kazancli Sallen-Key LP: w0 = 1/sqrt(R1 R2 C1 C2), Q = sqrt(R1 R2 C1 C2)/(C2 (R1 + R2))
    w0 = 1 / math.sqrt(r31 * r32 * c30 * c31)
    q = math.sqrt(r31 * r32 * c30 * c31) / (c31 * (r31 + r32))
    return AfeModel(
        gain1=1 + val('R29') / val('R30'),
        hp1_hz=1 / (2 * math.pi * val('R30') * val('C29')),
        sk_fc_hz=w0 / (2 * math.pi),
        sk_q=q,
        gain2=1 + val('R33') / val('R34'),
        lp2_hz=1 / (2 * math.pi * val('R33') * val('C33')),
        adc_rc_hz=1 / (2 * math.pi * val('R35') * val('C36')),
        bias_hp_hz=1 / (2 * math.pi * val('R28') * val('C28')),
    )


def firmware_constant(name):
    """firmware/include/acoustic_dsp.h icindeki 'name = <ifade>f' sabitini hesaplar."""
    path = os.path.join(HERE, '..', 'firmware', 'include', 'acoustic_dsp.h')
    text = open(path, encoding='utf-8').read()
    m = re.search(rf'{name}\s*=\s*([^;]+);', text)
    expr = m.group(1).replace('f', '')
    expr = re.sub(r'kGainLo', str(firmware_constant('kGainLo')) if name != 'kGainLo' else '0', expr)
    return float(eval(expr, {'__builtins__': {}}))  # noqa: S307 (sadece sayisal sabit)


# -----------------------------------------------------------------------------
# Pasif uyanma yolu (MCP6042, GBW 14 kHz)
# -----------------------------------------------------------------------------
MCP6042_GBW_HZ = 14e3
MCP6042_IQ_A = 0.6e-6          # amplifikator basina
TLV7031_IQ_A = 0.335e-6
HT7533_IQ_A = 2.5e-6
AON_RAIL_V = 3.3


def wake_model():
    g1 = 1 + val('R12') / val('R13')
    g2 = 1 + val('R14') / val('R15')
    bw = MCP6042_GBW_HZ / max(g1, g2)
    hp = 1 / (2 * math.pi * val('R13') * val('C14'))
    v_ref = AON_RAIL_V * val('R10') / (val('R9') + val('R10'))
    v_th = AON_RAIL_V * val('R18') / (val('R17') + val('R18'))
    return {
        'gain': g1 * g2,
        'gain_db': 20 * math.log10(g1 * g2),
        'bw_hz': bw,
        'hp_hz': hp,
        'v_ref': v_ref,
        'v_th': v_th,
        'env_tau_s': val('R16') * val('C17'),
        'latch_tau_s': val('R20') * val('C20'),
    }


def aon_budget():
    """Uykudaki toplam pil akimi (A) ve kalemleri."""
    items = {
        'HT7533 (U1) Iq': HT7533_IQ_A,
        'MCP6042 (U3) 2 kanal': 2 * MCP6042_IQ_A,
        'TLV7031 (U4)': TLV7031_IQ_A,
        'Vref bolucu R9+R10': AON_RAIL_V / (val('R9') + val('R10')),
        'Esik bolucu R17+R18': AON_RAIL_V / (val('R17') + val('R18')),
        'Zarf bosaltma R16 (dinlenmede ~1.4 V)': 1.4 / val('R16'),
        'Mandal R20 (BUCK_EN = 0 V)': 0.0,
        'LMR16006 kapali (EN dusuk)': 1e-6,
        'DRV8871 uyku': 1e-6,
    }
    return sum(items.values()), items


def battery_life_days(capacity_ah=3.4, awake_s_per_day=600.0, awake_power_w=0.55,
                      vbat_nom=14.8, buck_eff=0.85):
    """Yillik dongu: uykuda AON akimi + gunde awake_s_per_day saniye uyanik."""
    i_sleep, _ = aon_budget()
    i_awake = awake_power_w / (vbat_nom * buck_eff)
    ah_per_day = (i_sleep * 86400 + i_awake * awake_s_per_day) / 3600
    return capacity_ah / ah_per_day


# -----------------------------------------------------------------------------
# Pil olcumu
# -----------------------------------------------------------------------------
def batt_divider():
    r5, r6 = val('R5'), val('R6')
    return (r5 + r6) / r6


# -----------------------------------------------------------------------------
# Akustik baglanti butcesi (tahmini; varsayimlar DESIGN.md'de)
# -----------------------------------------------------------------------------
def thorp_db_per_km(f_khz):
    f2 = f_khz ** 2
    return 0.11 * f2 / (1 + f2) + 44 * f2 / (4100 + f2) + 2.75e-4 * f2 + 0.003


@dataclass
class LinkBudget:
    tvr_db: float = 130.0          # Projektor TVR (dB re 1 uPa/V @ 1 m), 25 kHz rezonans
    drive_vrms: float = 50.0       # DRV8871 14.8 V kare dalga, 1:5 eslesme trafosu
    noise_psd_db: float = 40.0     # Deniz durumu 2, 26 kHz (dB re 1 uPa^2/Hz, Wenz)
    rx_bw_hz: float = 1000.0       # 192 noktalik Goertzel kutu genisligi
    required_snr_db: float = 10.0
    f_khz: float = 26.0

    @property
    def source_level_db(self):
        return self.tvr_db + 20 * math.log10(self.drive_vrms)

    @property
    def noise_level_db(self):
        return self.noise_psd_db + 10 * math.log10(self.rx_bw_hz)

    def snr_db(self, r_m):
        tl = 20 * math.log10(r_m) + thorp_db_per_km(self.f_khz) * r_m / 1000.0
        return self.source_level_db - tl - self.noise_level_db

    def max_range_m(self):
        lo, hi = 1.0, 50000.0
        for _ in range(60):
            mid = math.sqrt(lo * hi)
            if self.snr_db(mid) >= self.required_snr_db:
                lo = mid
            else:
                hi = mid
        return lo


def main():
    a = afe_model()
    print('AFE')
    print(f'  1. kademe kazanc {a.gain1:.2f} ({20 * math.log10(a.gain1):.1f} dB), HP {a.hp1_hz:.1f} Hz')
    print(f'  Sallen-Key fc {a.sk_fc_hz / 1e3:.2f} kHz, Q {a.sk_q:.3f}')
    print(f'  2. kademe kazanc {a.gain2:.2f}, kutup {a.lp2_hz / 1e3:.1f} kHz')
    print(f'  LO {a.gain_lo:.1f} ({20 * math.log10(a.gain_lo):.1f} dB), HI {a.gain_hi:.1f} '
          f'({20 * math.log10(a.gain_hi):.1f} dB)')
    for f in (1e3, 24e3, 28e3, 40e3, 96e3, 152e3):
        h = abs(a.response(f)) / a.gain_hi
        print(f'  |H({f / 1e3:5.0f} kHz)| = {20 * math.log10(h):6.1f} dB')

    w = wake_model()
    print('Uyanma')
    print(f'  kazanc {w["gain_db"]:.1f} dB, bant {w["hp_hz"]:.1f} .. {w["bw_hz"]:.0f} Hz, '
          f'Vref {w["v_ref"]:.3f} V, esik {w["v_th"]:.3f} V')
    total, items = aon_budget()
    print(f'Hep acik akim: {total * 1e6:.2f} uA')
    for k, v in items.items():
        print(f'  {k:42s} {v * 1e6:6.3f} uA')
    print(f'Pil omru (3.4 Ah, gunde 10 dk uyanik): {battery_life_days():.0f} gun')
    lb = LinkBudget()
    print(f'Akustik baglanti: SL {lb.source_level_db:.0f} dB, NL {lb.noise_level_db:.0f} dB, '
          f'alfa {thorp_db_per_km(lb.f_khz):.2f} dB/km, menzil ~{lb.max_range_m() / 1000:.2f} km')


if __name__ == '__main__':
    main()
