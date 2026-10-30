#ifndef ACOUSTIC_NODE_ACOUSTIC_DSP_H
#define ACOUSTIC_NODE_ACOUSTIC_DSP_H

#include <stddef.h>
#include <stdint.h>

#include "dsp_filter.h"

namespace acoustic_node {

// Hidrofon ADC ornekleme hizi (Teensy 4.1 ADC0 + ADC1, zamanlayici tetikli DMA)
constexpr float kAdcSampleRateHz = 192000.0f;

// LOFAR: 192 kHz -> (LP 2 kHz, /16) -> 12 kHz -> (LP 700 Hz, /6) -> 2 kHz
constexpr size_t kLofarFftSize   = 1024;     // 2 kHz'de 1.95 Hz cozunurluk, 0.512 s pencere
constexpr size_t kLofarAverages  = 4;        // 4 spektrum ortalamasi (2.05 s)
constexpr float kLofarMinHz      = 20.0f;
constexpr float kLofarMaxHz      = 700.0f;

// DEMON: BP 4..30 kHz -> kare-yasasi zarf -> (ortalama /64) 3 kHz -> (LP 150 Hz, /8) 375 Hz
constexpr size_t kDemonFftSize   = 1024;     // 375 Hz'de 0.366 Hz cozunurluk, 2.73 s pencere
constexpr float kDemonBandLoHz   = 4000.0f;
constexpr float kDemonBandHiHz   = 30000.0f;
constexpr float kShaftMinHz      = 2.5f;
constexpr float kShaftMaxHz      = 11.5f;

enum TargetIFF : uint8_t {
    IFF_AMBIENT_NOISE = 0,
    IFF_FRIENDLY_UUV  = 1,
    IFF_HOSTILE_TRACK = 2,
    IFF_UNKNOWN_TONAL = 3
};

struct LofarResult {
    float peak_hz = 0.0f;        // En guclu dar-bant makine tonali (Hz)
    float peak_snr_db = 0.0f;    // TPSW-CFAR beyazlatma sonrasi SNR (dB)
};

struct DemonResult {
    float shaft_hz = 0.0f;       // Saft devir frekansi f_shaft (Hz)
    float blade_hz = 0.0f;       // Kanat gecis frekansi f_blade = N * f_shaft (Hz)
    uint8_t blades = 0;          // Kestirilen kanat sayisi N (0 = bulunamadi)
    float shaft_snr_db = 0.0f;
    float blade_snr_db = 0.0f;
};

struct AcousticSignature {
    LofarResult lofar;
    DemonResult demon;
    TargetIFF iff_class = IFF_AMBIENT_NOISE;
    float confidence = 0.0f;     // [0.0 .. 1.0]
};

// Radix-2 Cooley-Tukey yerinde (in-place) kompleks FFT (n = 2^k)
void fft_radix2(float* re, float* im, size_t n);

// Hanning penceresi uygula ve DC bileseni cikar
void apply_hanning_zero_dc(const float* input, float* output, size_t n);

// Two-Pass Split-Window (TPSW) CFAR spektral beyazlatma (ortam gurultusu tabanina gore SNR)
void cfar_tpsw_whiten(const float* mag_sq, float* snr_linear, size_t n_bins,
                      size_t window_half = 12, size_t gap_half = 2);

// Dar-bant (LOFAR) islemcisi: 192 kHz ornek alir, ~2 s'de bir sonuc uretir
class LofarProcessor {
public:
    LofarProcessor();
    void reset();
    bool push(float x);                 // Yeni sonuc hazirsa true
    const LofarResult& result() const { return result_; }
    float fs_out() const { return dec2_.fs_out(); }

private:
    void analyze();

    Decimator dec1_, dec2_;
    float frame_[kLofarFftSize];
    float acc_[kLofarFftSize / 2];
    size_t fill_ = 0;
    size_t n_avg_ = 0;
    LofarResult result_;
};

// Zarf (DEMON) islemcisi: kavitasyon bandinin zarfindan saft/kanat frekanslarini cikarir
class DemonProcessor {
public:
    DemonProcessor();
    void reset();
    bool push(float x);
    const DemonResult& result() const { return result_; }
    float fs_out() const { return dec_.fs_out(); }

private:
    void analyze();

    Butterworth4 hp_, lp_;
    BoxcarDecimator box_;
    Decimator dec_;
    float frame_[kDemonFftSize];
    size_t fill_ = 0;
    DemonResult result_;
};

// LOFAR + DEMON sonuclarindan akustik IFF karari.
// Demo kural seti: dost UUV = pilot tonu + 3 kanat, hedef = 5+ kanat kavitasyon modulasyonu.
AcousticSignature classify_signature(const LofarResult& lofar, const DemonResult& demon,
                                     float friendly_beacon_hz = 380.0f);

// Cift kazancli AFE kanal secici. Iki ADC ayni anda LO (20 dB) ve HI (40 dB) cikislarini
// ornekler; HI kirpilmiyorsa onu, kirpiliyorsa LO'yu kullanir ve hidrofon girisine
// indirgenmis gerilime (V) cevirir.
class DualGainSelector {
public:
    static constexpr float kVref = 3.3f;
    static constexpr float kGainLo = 10.1f;         // U5A: 1 + 9.1k / 1k
    static constexpr float kGainHi = 10.1f * 10.1f; // U5A x U6A
    static constexpr uint16_t kClipMargin = 96;     // 12-bit raydan uzaklik esigi
    static constexpr uint16_t kHoldSamples = 256;   // Kirpilma sonrasi LO'da kalma suresi

    float convert(uint16_t lo_counts, uint16_t hi_counts);
    bool using_low_gain() const { return hold_ > 0; }

private:
    uint16_t hold_ = 0;
};

}  // namespace acoustic_node

#endif  // ACOUSTIC_NODE_ACOUSTIC_DSP_H
