"""Acoustic Swarm DSP (LOFAR / DEMON / TPSW-CFAR) ve Piezo Hasat / Suru Benzetim Testleri."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from acoustic_simulator import (  # noqa: E402
    analyze_lofar_demon,
    simulate_piezo_and_swarm_timeline,
    synthesize_hydrophone_signal,
)


def test_hostile_5blade_demon_classification():
    _, sig = synthesize_hydrophone_signal(
        duration_s=4.0,
        fs=2048.0,
        lofar_tonal_hz=145.0,
        shaft_hz=5.0,
        n_blades=5,
        sea_state_noise=0.35,
        seed=42,
    )
    res = analyze_lofar_demon(sig, fs=2048.0, friendly_beacon_hz=380.0)
    assert abs(res.lofar_peak_hz - 145.0) <= 1.0
    assert res.lofar_peak_snr_db > 15.0
    assert abs(res.shaft_rate_hz - 5.0) <= 0.5
    assert res.estimated_blades == 5
    assert abs(res.blade_rate_hz - 25.0) <= 1.0
    assert res.iff_label == "HOSTILE_VESSEL"


def test_friendly_3blade_uuv_classification():
    _, sig = synthesize_hydrophone_signal(
        duration_s=4.0,
        fs=2048.0,
        lofar_tonal_hz=380.0,
        shaft_hz=6.0,
        n_blades=3,
        sea_state_noise=0.30,
        seed=7,
    )
    res = analyze_lofar_demon(sig, fs=2048.0, friendly_beacon_hz=380.0)
    assert abs(res.lofar_peak_hz - 380.0) <= 1.0
    assert res.estimated_blades == 3
    assert res.iff_label == "FRIENDLY_UUV"


def test_piezo_harvest_and_swarm_wake_timeline():
    sim = simulate_piezo_and_swarm_timeline(hours=48.0, dt_min=5.0)
    assert float(sim["v_bus"][-1]) > float(sim["v_bus"][0])
    assert 1 in sim["swarm_state"]
    assert 2 in sim["swarm_state"]


if __name__ == "__main__":
    test_hostile_5blade_demon_classification()
    test_friendly_3blade_uuv_classification()
    test_piezo_harvest_and_swarm_wake_timeline()
    print("OK")
