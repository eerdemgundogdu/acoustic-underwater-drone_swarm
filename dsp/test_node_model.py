"""Donanim degerleri <-> firmware sabitleri <-> tasarim hedefleri tutarlilik testleri.

    python3 dsp/test_node_model.py
"""

import math
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import node_model as nm  # noqa: E402


def node_config_value(name):
    path = os.path.join(HERE, '..', 'firmware', 'teensy_node', 'node_config.h')
    text = open(path, encoding='utf-8').read()
    m = re.search(rf'{name}\s*=\s*([^;]+);', text)
    return eval(m.group(1).replace('f', ''), {'__builtins__': {}})  # noqa: S307


class AfeTest(unittest.TestCase):
    def setUp(self):
        self.a = nm.afe_model()

    def test_gains_match_firmware(self):
        self.assertAlmostEqual(self.a.gain_lo, nm.firmware_constant('kGainLo'), places=3)
        self.assertAlmostEqual(self.a.gain_hi, nm.firmware_constant('kGainHi'), places=2)

    def test_sallen_key_butterworth_like(self):
        self.assertTrue(38e3 < self.a.sk_fc_hz < 42e3, self.a.sk_fc_hz)
        self.assertTrue(0.68 < self.a.sk_q < 0.80, self.a.sk_q)

    def test_bfsk_tones_flat(self):
        # 24/28 kHz BFSK tonlari: 1.5 dB'den az zayiflama, aralarindaki egim < 1 dB
        h24 = 20 * math.log10(abs(self.a.response(24e3)) / self.a.gain_hi)
        h28 = 20 * math.log10(abs(self.a.response(28e3)) / self.a.gain_hi)
        self.assertGreater(h28, -1.5)
        self.assertLess(abs(h24 - h28), 1.0)

    def test_demon_band(self):
        # DEMON 4..30 kHz zarf bandi: 2. derece filtrenin kenarinda 2 dB'ye kadar dusme kabul
        for f in (4e3, 10e3, 20e3, 30e3):
            h = abs(self.a.response(f)) / self.a.gain_hi
            self.assertGreater(20 * math.log10(h), -2.0, f)

    def test_alias_band_attenuated(self):
        # fs = 192 kHz: 152 kHz -> 40 kHz'e katlanir. Analog zincir bunu bastirmali.
        h = abs(self.a.response(152e3)) / self.a.gain_hi
        self.assertLess(20 * math.log10(h), -25.0)

    def test_input_coupling_below_lofar_band(self):
        self.assertLess(self.a.bias_hp_hz, 5.0)
        self.assertLess(self.a.hp1_hz, 20.0)

    def test_adc_rc_settles_within_sample(self):
        # Yuk kovasi RC'si bir ornek periyodunda 12 bit'e yerlesmeli: ln(2^13) ~ 9 tau
        tau = 1 / (2 * math.pi * self.a.adc_rc_hz)
        self.assertLess(9 * tau, 1 / 192e3)
        # Harici C, ADC ornekleme kapasitesinin (~4 pF) en az 500 kati
        self.assertGreater(nm.val('C36'), 500 * 4e-12)


class WakeTest(unittest.TestCase):
    def test_gain_and_band(self):
        w = nm.wake_model()
        self.assertTrue(55 < w['gain_db'] < 62, w['gain_db'])
        self.assertTrue(300 < w['bw_hz'] < 600, w['bw_hz'])
        self.assertLess(w['hp_hz'], 10)

    def test_threshold_above_reference(self):
        w = nm.wake_model()
        self.assertGreater(w['v_th'], w['v_ref'])
        self.assertLess(w['v_th'] - w['v_ref'], 0.2)

    def test_latch_outlasts_teensy_boot(self):
        # Teensy 4.1 acilisi ~0.4 s; RC mandal PWR_HOLD gelene kadar buck'i tutmali
        self.assertGreater(nm.wake_model()['latch_tau_s'], 0.8)


class PowerTest(unittest.TestCase):
    def test_always_on_current(self):
        total, _ = nm.aon_budget()
        self.assertLess(total, 8e-6, total)

    def test_battery_life(self):
        self.assertGreater(nm.battery_life_days(), 365)

    def test_batt_divider_matches_firmware_and_adc_range(self):
        ratio = nm.batt_divider()
        self.assertAlmostEqual(ratio, node_config_value('kBattDivRatio'), places=4)
        self.assertLess(16.8 / ratio, 3.3)


class LinkTest(unittest.TestCase):
    def test_thorp_at_26khz(self):
        self.assertAlmostEqual(nm.thorp_db_per_km(26.0), 6.53, delta=0.1)

    def test_range_estimate(self):
        r = nm.LinkBudget().max_range_m()
        self.assertTrue(1000 < r < 5000, r)


if __name__ == '__main__':
    unittest.main(verbosity=2)
