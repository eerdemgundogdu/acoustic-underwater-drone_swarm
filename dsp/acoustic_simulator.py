"""Pelagos Deniz Tabani Akustik Sinyal Isleme (LOFAR / DEMON / TPSW-CFAR),
Piezoelektrik Dalga Enerji Hasadi ve Akustik Suru (Swarm) Benzetim Cekirdegi.

Not: Saha hidrofon kalibrasyon katsayilari ve gercek hedef akustik imza
kutuphaneleri acik kaynak surumunden cikarilmis; sentetik pervane/saft
harmonik modelleri kullanilmistir.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np


@dataclass
class DemonAnalysisResult:
    lofar_freqs_hz: np.ndarray
    lofar_snr_db: np.ndarray
    lofar_peak_hz: float
    lofar_peak_snr_db: float
    demon_freqs_hz: np.ndarray
    demon_snr_db: np.ndarray
    shaft_rate_hz: float
    blade_rate_hz: float
    estimated_blades: int
    iff_label: str


def tpsw_cfar(power_spec: np.ndarray, win_half: int = 14, gap_half: int = 2,
              clip_factor: float = 2.5) -> np.ndarray:
    """Two-Pass Split-Window (TPSW) CFAR spektral beyazlatma."""
    n = len(power_spec)
    snr_lin = np.ones(n, dtype=float)
    for i in range(n):
        idx = [k for k in range(max(0, i - win_half), min(n, i + win_half + 1))
               if abs(k - i) > gap_half]
        if not idx:
            continue
        neighbors = power_spec[idx]
        mean1 = float(np.mean(neighbors))
        clipped = np.where(neighbors > clip_factor * mean1, mean1, neighbors)
        noise_floor = max(float(np.mean(clipped)), 1e-12)
        snr_lin[i] = power_spec[i] / noise_floor
    return snr_lin


def synthesize_hydrophone_signal(
    duration_s: float = 4.0,
    fs: float = 2048.0,
    lofar_tonal_hz: float = 145.0,
    shaft_hz: float = 5.0,
    n_blades: int = 5,
    sea_state_noise: float = 0.35,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """Knudsen deniz durumu (1/f) gurultusu icinde LOFAR makine tonali ve
    pervane kavitasyon zarf modülasyonlu (DEMON) hidrofon sinyali uretir.
    """
    rng = np.random.default_rng(seed)
    n = int(duration_s * fs)
    t = np.arange(n, dtype=float) / fs

    # Pembe / 1/f ortam deniz gurultusu
    white = rng.standard_normal(n)
    w_fft = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    pink_filter = 1.0 / np.sqrt(np.maximum(freqs, 5.0) / 50.0)
    ambient = np.fft.irfft(w_fft * pink_filter, n=n)
    ambient = sea_state_noise * ambient / (np.std(ambient) + 1e-9)

    # Dar-bant makine / redüktör tonali (LOFAR)
    tonal = 1.15 * np.sin(2.0 * np.pi * lofar_tonal_hz * t) + \
            0.40 * np.sin(2.0 * np.pi * (2.0 * lofar_tonal_hz) * t)

    # Pervane kavitasyon zarfi (saft devri + N kanat gecis harmonikleri)
    blade_hz = shaft_hz * n_blades
    envelope = (
        1.0
        + 0.48 * np.sin(2.0 * np.pi * shaft_hz * t)
        + 0.92 * np.sin(2.0 * np.pi * blade_hz * t)
        + 0.30 * np.sin(2.0 * np.pi * 2.0 * blade_hz * t)
    )
    # Genis-bant kavitasyon tasiyicisi (450..850 Hz bandinda)
    carrier = (
        np.sin(2.0 * np.pi * 620.0 * t + 0.3)
        + 0.7 * np.sin(2.0 * np.pi * 740.0 * t - 0.8)
    )
    signal = tonal + 1.25 * envelope * carrier + ambient
    return t, signal


def analyze_lofar_demon(
    signal: np.ndarray,
    fs: float = 2048.0,
    friendly_beacon_hz: float = 380.0,
) -> DemonAnalysisResult:
    """LOFAR + TPSW-CFAR ve DEMON kavitasyon zarf spektrumu uzerinden
    saft devri, kanat sayisi ve IFF siniflandirmasi yapar.
    """
    n = len(signal)
    win = np.hanning(n)
    sig_zero = (signal - np.mean(signal)) * win

    # 1. LOFAR spektrumu
    spec = np.abs(np.fft.rfft(sig_zero)) ** 2
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    snr_lin = tpsw_cfar(spec, win_half=18, gap_half=3)
    snr_db = 10.0 * np.log10(np.maximum(snr_lin, 1e-3))

    valid_mask = (freqs >= 20.0) & (freqs <= 450.0)
    valid_indices = np.where(valid_mask)[0]
    best_idx = valid_indices[int(np.argmax(snr_db[valid_indices]))]
    lofar_peak_hz = float(freqs[best_idx])
    lofar_peak_snr_db = float(snr_db[best_idx])

    # 2. DEMON: Yuksek frekans kavitasyon bandi (> 450 Hz) + tam dalga dogrultma + desimasyon
    fft_sig = np.fft.rfft(signal)
    bp_mask = (freqs >= 480.0) & (freqs <= 900.0)
    cav_band = np.fft.irfft(fft_sig * bp_mask, n=n)
    rectified = np.abs(cav_band)

    decim = 8
    env_dec = rectified[::decim]
    fs_env = fs / decim
    env_zero = (env_dec - np.mean(env_dec)) * np.hanning(len(env_dec))
    demon_spec = np.abs(np.fft.rfft(env_zero)) ** 2
    demon_freqs = np.fft.rfftfreq(len(env_dec), d=1.0 / fs_env)
    demon_snr_lin = tpsw_cfar(demon_spec, win_half=10, gap_half=2)
    demon_snr_db = 10.0 * np.log10(np.maximum(demon_snr_lin, 1e-3))

    # Saft devri arama [2.5 .. 10.0 Hz]
    shaft_mask = (demon_freqs >= 2.5) & (demon_freqs <= 10.0)
    shaft_indices = np.where(shaft_mask)[0]
    shaft_idx = shaft_indices[int(np.argmax(demon_spec[shaft_indices]))]
    shaft_hz = float(demon_freqs[shaft_idx])

    # Kanat sayisi N = 3..7 harmonik eslestirme
    best_blades = 3
    best_score = -1.0
    best_blade_hz = shaft_hz * 3
    for n_b in range(3, 8):
        target_f = shaft_hz * n_b
        b_idx = int(np.argmin(np.abs(demon_freqs - target_f)))
        score = float(demon_spec[b_idx])
        if score > best_score:
            best_score = score
            best_blades = n_b
            best_blade_hz = float(demon_freqs[b_idx])

    if lofar_peak_snr_db < 8.0:
        iff = "AMBIENT_NOISE"
    elif abs(lofar_peak_hz - friendly_beacon_hz) <= 3.0 and best_blades == 3:
        iff = "FRIENDLY_UUV"
    elif best_blades >= 5:
        iff = "HOSTILE_VESSEL"
    else:
        iff = "UNKNOWN_CONTACT"

    return DemonAnalysisResult(
        lofar_freqs_hz=freqs,
        lofar_snr_db=snr_db,
        lofar_peak_hz=lofar_peak_hz,
        lofar_peak_snr_db=lofar_peak_snr_db,
        demon_freqs_hz=demon_freqs,
        demon_snr_db=demon_snr_db,
        shaft_rate_hz=shaft_hz,
        blade_rate_hz=best_blade_hz,
        estimated_blades=best_blades,
        iff_label=iff,
    )


def simulate_piezo_and_swarm_timeline(
    hours: float = 48.0,
    dt_min: float = 5.0,
) -> Dict[str, np.ndarray]:
    """48 saatlik deniz tabani gorevinde piezoelektrik dalga/akinti enerji
    hasadi, pasif akustik uyandirma ve 4 dugumlu akustik suru (swarm) yayilimini
    modelleyerek zaman serilerini dondurur.
    """
    n_steps = int((hours * 60.0) / dt_min)
    t_hours = np.arange(n_steps, dtype=float) * (dt_min / 60.0)
    dt_sec = dt_min * 60.0

    # Esdeger enerji depolama kapasitesi (hibrit supercap + tampon: C_eq = 2.5 F)
    c_eq = 2.5
    v_bus = np.zeros(n_steps, dtype=float)
    p_harvest_mw = np.zeros(n_steps, dtype=float)
    swarm_state = np.zeros(n_steps, dtype=int)

    v = 13.8
    for k, h in enumerate(t_hours):
        # Gelgit ve yuzey dalga periyoduna bagli piezo VIV gucu (8..45 mW)
        wave_mw = 18.0 + 14.0 * np.sin(2.0 * np.pi * h / 12.4) + \
                  6.0 * np.cos(2.0 * np.pi * h / 3.1)
        p_harvest_mw[k] = max(wave_mw, 3.0)

        # 18. saatte dost UUV gecisi (pasif siniflandirma, alarm yok)
        # 34. saatte dusman 5-kanatli hedef gecisi (akustik suru TDMA alarmi)
        if abs(h - 18.0) <= 0.25 and v >= 16.5:
            swarm_state[k] = 1  # DSP_CLASSIFY (Dost UUV)
            load_mw = 95.0
        elif abs(h - 34.0) <= 0.35 and v >= 16.5:
            swarm_state[k] = 2  # SWARM_TX_ALERT (4 dugum cok-atlamali alarm)
            load_mw = 260.0
        else:
            swarm_state[k] = 0  # DEEP_SLEEP_HARVEST (< 0.15 mW)
            load_mw = 0.15

        e_curr = 0.5 * c_eq * (v ** 2)
        e_next = max(0.0, e_curr + (p_harvest_mw[k] - load_mw) * 1e-3 * dt_sec)
        v = min(24.8, float(np.sqrt(2.0 * e_next / c_eq)))
        v_bus[k] = v

    return {
        "t_hours": t_hours,
        "v_bus": v_bus,
        "p_harvest_mw": p_harvest_mw,
        "swarm_state": swarm_state,
    }
