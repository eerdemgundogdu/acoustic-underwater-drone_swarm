#include "acoustic_dsp.h"

#include <math.h>
#include <string.h>

namespace pelagos {

namespace {
constexpr float kPi = 3.14159265358979323846f;
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
    for (size_t s = 1; (1ULL << s) <= n; ++s) {
        size_t m = 1ULL << s;
        size_t half = m >> 1;
        float theta = -2.0f * kPi / static_cast<float>(m);
        float w_m_r = cosf(theta);
        float w_m_i = sinf(theta);

        for (size_t k = 0; k < n; k += m) {
            float w_r = 1.0f;
            float w_i = 0.0f;
            for (size_t m_idx = 0; m_idx < half; ++m_idx) {
                size_t t_idx = k + m_idx + half;
                size_t u_idx = k + m_idx;
                float t_r = w_r * re[t_idx] - w_i * im[t_idx];
                float t_i = w_r * im[t_idx] + w_i * re[t_idx];
                float u_r = re[u_idx];
                float u_i = im[u_idx];
                re[u_idx] = u_r + t_r;
                im[u_idx] = u_i + t_i;
                re[t_idx] = u_r - t_r;
                im[t_idx] = u_i - t_i;

                float next_wr = w_r * w_m_r - w_i * w_m_i;
                float next_wi = w_r * w_m_i + w_i * w_m_r;
                w_r = next_wr;
                w_i = next_wi;
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
        float w = 0.5f * (1.0f - cosf(2.0f * kPi * static_cast<float>(i) / denom));
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
        float local_mean = (count > 0) ? (sum / static_cast<float>(count)) : 1e-9f;

        // Ikinci gecis: tepe degerlerin arka plan kestirimini saptirmasini onle (clipping)
        float clipped_sum = 0.0f;
        size_t clipped_cnt = 0;
        const float clip_thresh = 2.5f * local_mean;
        for (size_t d = gap_half + 1; d <= window_half; ++d) {
            if (i >= d) {
                float v = mag_sq[i - d];
                clipped_sum += (v > clip_thresh) ? local_mean : v;
                ++clipped_cnt;
            }
            if (i + d < n_bins) {
                float v = mag_sq[i + d];
                clipped_sum += (v > clip_thresh) ? local_mean : v;
                ++clipped_cnt;
            }
        }
        float noise_floor = (clipped_cnt > 0)
                                ? (clipped_sum / static_cast<float>(clipped_cnt))
                                : 1e-9f;
        if (noise_floor < 1e-12f) {
            noise_floor = 1e-12f;
        }
        snr_linear[i] = mag_sq[i] / noise_floor;
    }
}

AcousticSignature analyze_hydrophone_frame(
    const float* samples,
    size_t n_samples,
    float sample_rate_hz,
    float friendly_beacon_hz) {
    AcousticSignature sig = {0.0f, 0.0f, 0.0f, 0.0f, 0, IFF_AMBIENT_NOISE, 0.0f};
    if (n_samples < kFftSize) {
        return sig;
    }

    // 1. LOFAR (Dar-bant spektral analiz)
    float re[kFftSize];
    float im[kFftSize];
    apply_hanning_zero_dc(samples, re, kFftSize);
    memset(im, 0, sizeof(im));
    fft_radix2(re, im, kFftSize);

    const size_t half_bins = kFftSize / 2;
    float mag_sq[half_bins];
    float snr_lin[half_bins];
    for (size_t k = 0; k < half_bins; ++k) {
        mag_sq[k] = re[k] * re[k] + im[k] * im[k];
    }
    cfar_tpsw_whiten(mag_sq, snr_lin, half_bins, 14, 2);

    const float bin_hz = sample_rate_hz / static_cast<float>(kFftSize);
    size_t min_bin = static_cast<size_t>(12.0f / bin_hz);
    if (min_bin < 2) min_bin = 2;

    size_t best_bin = min_bin;
    float best_snr = 0.0f;
    for (size_t k = min_bin; k < half_bins - 2; ++k) {
        if (snr_lin[k] > best_snr) {
            best_snr = snr_lin[k];
            best_bin = k;
        }
    }
    sig.lofar_peak_hz = static_cast<float>(best_bin) * bin_hz;
    sig.lofar_snr_db = 10.0f * log10f(best_snr > 1e-6f ? best_snr : 1e-6f);

    // 2. DEMON (Yuksek frekans kavitasyon tasiyicisinin zarf demodulasyonu)
    // 1. derece yuksek geciren fark filtresi + tam dalga dogrultma + 4x desimasyon
    constexpr size_t kDecim = 4;
    float env[kDemonFftSize];
    float env_im[kDemonFftSize];
    for (size_t i = 0; i < kDemonFftSize; ++i) {
        float acc = 0.0f;
        for (size_t m = 0; m < kDecim; ++m) {
            size_t idx = i * kDecim + m;
            if (idx > 0 && idx < kFftSize) {
                float hp = samples[idx] - samples[idx - 1];
                acc += fabsf(hp);
            }
        }
        env[i] = acc / static_cast<float>(kDecim);
    }

    float env_win[kDemonFftSize];
    apply_hanning_zero_dc(env, env_win, kDemonFftSize);
    memset(env_im, 0, sizeof(env_im));
    fft_radix2(env_win, env_im, kDemonFftSize);

    const float demon_fs = sample_rate_hz / static_cast<float>(kDecim);
    const float demon_bin_hz = demon_fs / static_cast<float>(kDemonFftSize);
    const size_t demon_half = kDemonFftSize / 2;

    float demon_mag[demon_half];
    float demon_snr[demon_half];
    for (size_t k = 0; k < demon_half; ++k) {
        demon_mag[k] = env_win[k] * env_win[k] + env_im[k] * env_im[k];
    }
    cfar_tpsw_whiten(demon_mag, demon_snr, demon_half, 8, 1);

    // Saft frekansi arama bandi: [2.5 Hz .. 11.5 Hz]
    size_t shaft_b0 = static_cast<size_t>(ceilf(2.5f / demon_bin_hz));
    size_t shaft_b1 = static_cast<size_t>(floorf(11.5f / demon_bin_hz));
    if (shaft_b0 < 1) shaft_b0 = 1;
    if (shaft_b1 >= demon_half) shaft_b1 = demon_half - 1;

    size_t shaft_bin = shaft_b0;
    float shaft_max = 0.0f;
    for (size_t k = shaft_b0; k <= shaft_b1; ++k) {
        if (demon_mag[k] > shaft_max) {
            shaft_max = demon_mag[k];
            shaft_bin = k;
        }
    }
    sig.shaft_rate_hz = static_cast<float>(shaft_bin) * demon_bin_hz;

    // Kanat gecis frekansi (Blade Pass Frequency) arama: N = 3..7 kanat harmonikleri
    uint8_t best_blades = 0;
    float best_blade_mag = 0.0f;
    size_t best_blade_bin = shaft_bin;
    for (uint8_t n_b = 3; n_b <= 7; ++n_b) {
        size_t b_idx = shaft_bin * n_b;
        if (b_idx < demon_half) {
            if (demon_mag[b_idx] > best_blade_mag) {
                best_blade_mag = demon_mag[b_idx];
                best_blades = n_b;
                best_blade_bin = b_idx;
            }
        }
    }
    sig.blade_rate_hz = static_cast<float>(best_blade_bin) * demon_bin_hz;
    sig.estimated_blades = best_blades;

    // 3. Akustik IFF Karar Mantigi (Sanitized / Sentetik Profil Siniflandirici)
    if (sig.lofar_snr_db < 8.0f) {
        sig.iff_class = IFF_AMBIENT_NOISE;
        sig.confidence = 0.90f;
        return sig;
    }

    // Dost su alti araci (UUV): 3 kanatli pervane + dost akustik pilot tonali
    bool beacon_match = fabsf(sig.lofar_peak_hz - friendly_beacon_hz) <= (2.5f * bin_hz);
    if (beacon_match && best_blades == 3) {
        sig.iff_class = IFF_FRIENDLY_UUV;
        sig.confidence = fminf(0.99f, sig.lofar_snr_db / 25.0f);
    } else if (best_blades >= 5 && demon_snr[best_blade_bin] > 4.0f) {
        // 5+ kanatli agir pervane kavitasyon modülasyonu -> Dusman/Hedef su ustu/alti izi
        sig.iff_class = IFF_HOSTILE_TRACK;
        sig.confidence = fminf(0.99f, (sig.lofar_snr_db + 10.0f) / 30.0f);
    } else {
        sig.iff_class = IFF_UNKNOWN_TONAL;
        sig.confidence = 0.60f;
    }
    return sig;
}

}  // namespace pelagos
