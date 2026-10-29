#ifndef ACOUSTIC_NODE_ACOUSTIC_DSP_H
#define ACOUSTIC_NODE_ACOUSTIC_DSP_H

#include <stddef.h>
#include <stdint.h>

namespace acoustic_node {

constexpr size_t kFftSize = 1024;
constexpr size_t kDemonFftSize = 256;

enum TargetIFF : uint8_t {
    IFF_AMBIENT_NOISE = 0,
    IFF_FRIENDLY_UUV  = 1,
    IFF_HOSTILE_TRACK = 2,
    IFF_UNKNOWN_TONAL = 3
};

struct AcousticSignature {
    float lofar_peak_hz;       // Dominant dar-bant makine tonali (Hz)
    float lofar_snr_db;        // CFAR beyazlatma sonrasi tepe SNR (dB)
    float shaft_rate_hz;       // DEMON saft devir frekansi f_shaft (Hz)
    float blade_rate_hz;       // DEMON kanat gecis frekansi f_blade (Hz)
    uint8_t estimated_blades;  // Kestirilen pervane kanat sayisi (N = f_blade / f_shaft)
    TargetIFF iff_class;       // Dost / Dusman / Ortam siniflandirmasi
    float confidence;          // [0.0 .. 1.0] siniflandirma guveni
};

// Radix-2 Cooley-Tukey yerinde (in-place) kompleks FFT (n = 2^k)
void fft_radix2(float* re, float* im, size_t n);

// Hanning penceresi uygula ve DC bileseni cikar
void apply_hanning_zero_dc(const float* input, float* output, size_t n);

// Two-Pass Split-Window (TPSW) CFAR spektral beyazlatma (ortam 1/f gurultusunu bastirir)
void cfar_tpsw_whiten(const float* mag_sq, float* snr_linear, size_t n_bins,
                      size_t window_half = 12, size_t gap_half = 2);

// Tam LOFAR + DEMON analizi ve akustik IFF siniflandirmasi
AcousticSignature analyze_hydrophone_frame(
    const float* samples,
    size_t n_samples,
    float sample_rate_hz,
    float friendly_beacon_hz = 380.0f);

}  // namespace acoustic_node

#endif  // ACOUSTIC_NODE_ACOUSTIC_DSP_H
