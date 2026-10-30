#include "acoustic_dsp.h"

#include <math.h>
#include <string.h>

namespace acoustic_node {

namespace {
constexpr float kPi = 3.14159265358979323846f;

// Iki FFT islemcisi tek is parcaciginda calistigi icin ortak calisma alani yeterli
float g_re[kLofarFftSize > kDemonFftSize ? kLofarFftSize : kDemonFftSize];
float g_im[kLofarFftSize > kDemonFftSize ? kLofarFftSize : kDemonFftSize];
float g_snr[(kLofarFftSize > kDemonFftSize ? kLofarFftSize : kDemonFftSize) / 2];
float g_mag[(kLofarFftSize > kDemonFftSize ? kLofarFftSize : kDemonFftSize) / 2];

float to_db(float lin) { return 10.0f * log10f(lin > 1e-6f ? lin : 1e-6f); }

// Ucuncu dereceden tepe kaydirmasi: komsu kutulardan parabolik interpolasyon [-0.5, 0.5]
float parabolic_offset(const float* mag, size_t k, size_t n) {
    if (k == 0 || k + 1 >= n) return 0.0f;
    const float a = mag[k - 1], b = mag[k], c = mag[k + 1];
    const float den = a - 2.0f * b + c;
    if (fabsf(den) < 1e-20f) return 0.0f;
    float d = 0.5f * (a - c) / den;
    if (d > 0.5f) d = 0.5f;
    if (d < -0.5f) d = -0.5f;
    return d;
}

// Hanning + FFT + |X|^2 (ilk n/2 kutu) -> g_mag
void power_spectrum(const float* frame, size_t n) {
    apply_hanning_zero_dc(frame, g_re, n);
    memset(g_im, 0, n * sizeof(float));
    fft_radix2(g_re, g_im, n);
    for (size_t k = 0; k < n / 2; ++k) {
        g_mag[k] = g_re[k] * g_re[k] + g_im[k] * g_im[k];
    }
}
}  // namespace

void fft_radix2(float* re, float* im, size_t n) {
    // Bit-tersleme (bit-reversal) permutasyonu
    size_t j = 0;
    for (size_t i = 0; i < n; ++i) {
        if (i < j) {
            float tr = re[i]; re[i] = re[j]; re[j] = tr;
            float ti = im[i]; im[i] = im[j]; im[j] = ti;
        }
        size_t m = n >> 1;
        while (m >= 1 && j >= m) {
            j -= m;
            m >>= 1;
        }
        j += m;
    }

    // Kelebek (butterfly) kademeleri
    for (size_t m = 2; m <= n; m <<= 1) {
        const size_t half = m >> 1;
        const float theta = -2.0f * kPi / static_cast<float>(m);
        for (size_t k = 0; k < n; k += m) {
            for (size_t i = 0; i < half; ++i) {
                // Twiddle her adimda dogrudan hesaplanir; tekrarli carpimin
                // 1024 noktada biriktirdigi faz hatasi olmaz.
                const float w_r = cosf(theta * static_cast<float>(i));
                const float w_i = sinf(theta * static_cast<float>(i));
                const size_t t_idx = k + i + half;
                const size_t u_idx = k + i;
                const float t_r = w_r * re[t_idx] - w_i * im[t_idx];
                const float t_i = w_r * im[t_idx] + w_i * re[t_idx];
                const float u_r = re[u_idx];
                const float u_i = im[u_idx];
                re[u_idx] = u_r + t_r;
                im[u_idx] = u_i + t_i;
                re[t_idx] = u_r - t_r;
                im[t_idx] = u_i - t_i;
            }
        }
    }
}

void apply_hanning_zero_dc(const float* input, float* output, size_t n) {
    float mean = 0.0f;
    for (size_t i = 0; i < n; ++i) {
        mean += input[i];
    }
    mean /= static_cast<float>(n);

    const float denom = static_cast<float>(n > 1 ? n - 1 : 1);
    for (size_t i = 0; i < n; ++i) {
        const float w = 0.5f * (1.0f - cosf(2.0f * kPi * static_cast<float>(i) / denom));
        output[i] = (input[i] - mean) * w;
    }
}

void cfar_tpsw_whiten(const float* mag_sq, float* snr_linear, size_t n_bins,
                      size_t window_half, size_t gap_half) {
    for (size_t i = 0; i < n_bins; ++i) {
        float sum = 0.0f;
        size_t count = 0;
        for (size_t d = gap_half + 1; d <= window_half; ++d) {
            if (i >= d) {
                sum += mag_sq[i - d];
                ++count;
            }
            if (i + d < n_bins) {
                sum += mag_sq[i + d];
                ++count;
            }
        }
        const float local_mean = (count > 0) ? (sum / static_cast<float>(count)) : 1e-9f;

        // Ikinci gecis: komsu tepelerin gurultu tabani kestirimini sisirmesini onle (clipping)
        float clipped_sum = 0.0f;
        size_t clipped_cnt = 0;
        const float clip_thresh = 2.5f * local_mean;
        for (size_t d = gap_half + 1; d <= window_half; ++d) {
            if (i >= d) {
                const float v = mag_sq[i - d];
                clipped_sum += (v > clip_thresh) ? local_mean : v;
                ++clipped_cnt;
            }
            if (i + d < n_bins) {
                const float v = mag_sq[i + d];
                clipped_sum += (v > clip_thresh) ? local_mean : v;
                ++clipped_cnt;
            }
        }
        float noise_floor = (clipped_cnt > 0)
                                ? (clipped_sum / static_cast<float>(clipped_cnt))
                                : 1e-9f;
        if (noise_floor < 1e-20f) {
            noise_floor = 1e-20f;
        }
        snr_linear[i] = mag_sq[i] / noise_floor;
    }
}

// ----------------------------------------------------------------------------
// LOFAR
// ----------------------------------------------------------------------------
LofarProcessor::LofarProcessor() {
    dec1_.configure(kAdcSampleRateHz, 2000.0f, 16);
    dec2_.configure(kAdcSampleRateHz / 16.0f, 700.0f, 6);
    reset();
}

void LofarProcessor::reset() {
    dec1_.reset();
    dec2_.reset();
    fill_ = 0;
    n_avg_ = 0;
    memset(acc_, 0, sizeof(acc_));
}

bool LofarProcessor::push(float x) {
    float y1, y2;
    if (!dec1_.push(x, &y1)) return false;
    if (!dec2_.push(y1, &y2)) return false;
    frame_[fill_++] = y2;
    if (fill_ < kLofarFftSize) return false;
    fill_ = 0;

    power_spectrum(frame_, kLofarFftSize);
    for (size_t k = 0; k < kLofarFftSize / 2; ++k) {
        acc_[k] += g_mag[k];
    }
    if (++n_avg_ < kLofarAverages) return false;
    n_avg_ = 0;
    analyze();
    memset(acc_, 0, sizeof(acc_));
    return true;
}

void LofarProcessor::analyze() {
    const size_t half = kLofarFftSize / 2;
    cfar_tpsw_whiten(acc_, g_snr, half, 14, 2);

    const float bin_hz = dec2_.fs_out() / static_cast<float>(kLofarFftSize);
    size_t k0 = static_cast<size_t>(ceilf(kLofarMinHz / bin_hz));
    size_t k1 = static_cast<size_t>(floorf(kLofarMaxHz / bin_hz));
    if (k1 >= half - 1) k1 = half - 2;

    size_t best = k0;
    for (size_t k = k0; k <= k1; ++k) {
        if (g_snr[k] > g_snr[best]) best = k;
    }
    const float d = parabolic_offset(acc_, best, half);
    result_.peak_hz = (static_cast<float>(best) + d) * bin_hz;
    result_.peak_snr_db = to_db(g_snr[best]);
}

// ----------------------------------------------------------------------------
// DEMON
// ----------------------------------------------------------------------------
DemonProcessor::DemonProcessor() {
    hp_.set_highpass(kAdcSampleRateHz, kDemonBandLoHz);
    lp_.set_lowpass(kAdcSampleRateHz, kDemonBandHiHz);
    box_.configure(64);
    dec_.configure(kAdcSampleRateHz / 64.0f, 150.0f, 8);
    reset();
}

void DemonProcessor::reset() {
    hp_.reset();
    lp_.reset();
    box_.reset();
    dec_.reset();
    fill_ = 0;
}

bool DemonProcessor::push(float x) {
    const float band = lp_.process(hp_.process(x));
    float e1, e2;
    if (!box_.push(band * band, &e1)) return false;
    if (!dec_.push(e1, &e2)) return false;
    frame_[fill_++] = e2;
    if (fill_ < kDemonFftSize) return false;
    fill_ = 0;
    analyze();
    return true;
}

void DemonProcessor::analyze() {
    const size_t half = kDemonFftSize / 2;
    power_spectrum(frame_, kDemonFftSize);
    cfar_tpsw_whiten(g_mag, g_snr, half, 10, 1);

    const float bin_hz = dec_.fs_out() / static_cast<float>(kDemonFftSize);
    size_t s0 = static_cast<size_t>(ceilf(kShaftMinHz / bin_hz));
    size_t s1 = static_cast<size_t>(floorf(kShaftMaxHz / bin_hz));
    if (s1 >= half - 1) s1 = half - 2;

    size_t shaft = s0;
    for (size_t k = s0; k <= s1; ++k) {
        if (g_snr[k] > g_snr[shaft]) shaft = k;
    }
    const float shaft_bin_f = static_cast<float>(shaft) + parabolic_offset(g_mag, shaft, half);

    result_ = DemonResult();
    result_.shaft_hz = shaft_bin_f * bin_hz;
    result_.shaft_snr_db = to_db(g_snr[shaft]);

    // N = 3..7 kanat: N * f_shaft civarinda (+-1 kutu) en guclu cizgi
    float best_snr = 0.0f;
    size_t best_bin = 0;
    uint8_t best_n = 0;
    for (uint8_t n = 3; n <= 7; ++n) {
        const size_t c = static_cast<size_t>(lroundf(shaft_bin_f * static_cast<float>(n)));
        for (size_t k = (c > 0 ? c - 1 : 0); k <= c + 1 && k < half; ++k) {
            if (g_snr[k] > best_snr) {
                best_snr = g_snr[k];
                best_bin = k;
                best_n = n;
            }
        }
    }
    result_.blade_snr_db = to_db(best_snr);
    // Beyazlatilmis gurultu gucu ustel dagilir: tek kutuda P(> 10 dB) = e^-10 = 4.5e-5.
    // 15 aday kutu (5 harmonik x 3) icin yanlis alarm ~7e-4; 6 dB esik %24 verirdi.
    if (best_n != 0 && result_.blade_snr_db >= 10.0f && result_.shaft_snr_db >= 6.0f) {
        result_.blades = best_n;
        result_.blade_hz = (static_cast<float>(best_bin) + parabolic_offset(g_mag, best_bin, half)) *
                           bin_hz;
    }
}

// ----------------------------------------------------------------------------
// IFF karari
// ----------------------------------------------------------------------------
AcousticSignature classify_signature(const LofarResult& lofar, const DemonResult& demon,
                                     float friendly_beacon_hz) {
    AcousticSignature sig;
    sig.lofar = lofar;
    sig.demon = demon;

    if (lofar.peak_snr_db < 8.0f && demon.blades == 0) {
        sig.iff_class = IFF_AMBIENT_NOISE;
        sig.confidence = 0.90f;
        return sig;
    }

    const float lofar_bin_hz = 2000.0f / static_cast<float>(kLofarFftSize);
    const bool beacon_match = lofar.peak_snr_db >= 8.0f &&
                              fabsf(lofar.peak_hz - friendly_beacon_hz) <= 2.5f * lofar_bin_hz;
    if (beacon_match && demon.blades == 3) {
        sig.iff_class = IFF_FRIENDLY_UUV;
        sig.confidence = fminf(0.99f, lofar.peak_snr_db / 25.0f);
    } else if (demon.blades >= 5) {
        sig.iff_class = IFF_HOSTILE_TRACK;
        sig.confidence = fminf(0.99f, (demon.blade_snr_db + 10.0f) / 30.0f);
    } else {
        sig.iff_class = IFF_UNKNOWN_TONAL;
        sig.confidence = 0.60f;
    }
    return sig;
}

// ----------------------------------------------------------------------------
// Cift kazancli AFE
// ----------------------------------------------------------------------------
float DualGainSelector::convert(uint16_t lo_counts, uint16_t hi_counts) {
    const bool hi_clipped = hi_counts < kClipMargin || hi_counts > 4095 - kClipMargin;
    if (hi_clipped) {
        hold_ = kHoldSamples;
    }
    constexpr float kLsb = kVref / 4096.0f;
    if (hold_ > 0) {
        --hold_;
        return (static_cast<float>(lo_counts) - 2048.0f) * kLsb / kGainLo;
    }
    return (static_cast<float>(hi_counts) - 2048.0f) * kLsb / kGainHi;
}

}  // namespace acoustic_node
