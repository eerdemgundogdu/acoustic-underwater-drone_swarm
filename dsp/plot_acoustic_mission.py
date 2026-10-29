"""Pelagos Akustik Sinyal Isleme (LOFAR/DEMON) ve Piezo Enerji Hasadi / Suru
Zaman Cizelgesi grafigini (docs/img/acoustic_demon_swarm.png) uretir.
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from acoustic_simulator import (  # noqa: E402
    analyze_lofar_demon,
    simulate_piezo_and_swarm_timeline,
    synthesize_hydrophone_signal,
)


def main():
    _, sig_hostile = synthesize_hydrophone_signal(
        duration_s=4.0, fs=2048.0, lofar_tonal_hz=145.0,
        shaft_hz=5.0, n_blades=5, sea_state_noise=0.35, seed=42
    )
    res_h = analyze_lofar_demon(sig_hostile, fs=2048.0)

    _, sig_friendly = synthesize_hydrophone_signal(
        duration_s=4.0, fs=2048.0, lofar_tonal_hz=380.0,
        shaft_hz=6.0, n_blades=3, sea_state_noise=0.30, seed=7
    )
    res_f = analyze_lofar_demon(sig_friendly, fs=2048.0)

    sim = simulate_piezo_and_swarm_timeline(hours=48.0, dt_min=5.0)

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.4), dpi=160)

    # Panel 1: LOFAR CFAR-Whitened Spectrum
    ax0 = axes[0]
    mask_l = (res_h.lofar_freqs_hz >= 10.0) & (res_h.lofar_freqs_hz <= 450.0)
    ax0.plot(res_h.lofar_freqs_hz[mask_l], res_h.lofar_snr_db[mask_l],
             color="#b91c1c", lw=1.2, label="Target track (145 Hz tonal + 290 Hz 2nd harm.)")
    ax0.plot(res_f.lofar_freqs_hz[mask_l], res_f.lofar_snr_db[mask_l],
             color="#1d4ed8", lw=1.1, alpha=0.85, label="Friendly UUV (380 Hz pilot beacon)")
    ax0.axhline(8.0, color="#4b5563", ls="--", lw=1.0, label="TPSW-CFAR threshold (8 dB)")
    ax0.set_title("1. LOFAR Narrowband Spectrum (TPSW-CFAR)", fontsize=10.5, fontweight="bold")
    ax0.set_xlabel("Frequency (Hz)")
    ax0.set_ylabel("CFAR-Whitened SNR (dB)")
    ax0.set_xlim(10, 450)
    ax0.grid(True, alpha=0.25)
    ax0.legend(loc="upper right", fontsize=8)

    # Panel 2: DEMON Propeller Cavitation Envelope Spectrum
    ax1 = axes[1]
    mask_d = (res_h.demon_freqs_hz >= 1.5) & (res_h.demon_freqs_hz <= 60.0)
    ax1.plot(res_h.demon_freqs_hz[mask_d], res_h.demon_snr_db[mask_d],
             color="#b91c1c", lw=1.35, label="Hostile 5-blade (f_shaft=5 Hz, f_blade=25 Hz)")
    ax1.plot(res_f.demon_freqs_hz[mask_d], res_f.demon_snr_db[mask_d],
             color="#047857", lw=1.2, alpha=0.85, label="Friendly 3-blade UUV (f_shaft=6 Hz, f_blade=18 Hz)")
    ax1.axvline(5.0, color="#b91c1c", ls=":", lw=1.0)
    ax1.axvline(25.0, color="#b91c1c", ls="--", lw=1.0)
    ax1.axvline(18.0, color="#047857", ls="--", lw=1.0)
    ax1.set_title("2. DEMON Cavitation Envelope (Propeller IFF)", fontsize=10.5, fontweight="bold")
    ax1.set_xlabel("Envelope Modulation Frequency (Hz)")
    ax1.set_ylabel("DEMON Envelope SNR (dB)")
    ax1.set_xlim(1.5, 60)
    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="upper right", fontsize=8)

    # Panel 3: Piezoelectric Wave Harvesting & Swarm Alert Timeline
    ax2 = axes[2]
    t_h = sim["t_hours"]
    v_b = sim["v_bus"]
    ax2.plot(t_h, v_b, color="#0f766e", lw=1.8, label="Harvested HV bus V_bus (V)")
    ax2.axhline(16.5, color="#d97706", ls="--", lw=1.0, label="Acoustic wake/TX ready threshold (16.5 V)")
    ax2.axvline(18.0, color="#1d4ed8", ls=":", lw=1.4, label="t=18h: Friendly UUV pass (IFF=FRIENDLY)")
    ax2.axvline(34.0, color="#b91c1c", ls="-.", lw=1.5, label="t=34h: Hostile pass -> 4-Node TDMA Swarm Alert")
    ax2.set_title("3. Piezo Wave Harvesting & Dormant Swarm Wake (48h)", fontsize=10.5, fontweight="bold")
    ax2.set_xlabel("Mission Time (hours)")
    ax2.set_ylabel("Capacitor / Buffer Bus Voltage (V)")
    ax2.set_xlim(0, 48)
    ax2.set_ylim(12.5, 25.5)
    ax2.grid(True, alpha=0.25)
    ax2.legend(loc="lower right", fontsize=7.8)

    plt.tight_layout()
    out_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "img")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.abspath(os.path.join(out_dir, "acoustic_demon_swarm.png"))
    fig.savefig(out_path, dpi=160)
    print(out_path)


if __name__ == "__main__":
    main()
