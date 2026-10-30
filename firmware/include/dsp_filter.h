#ifndef ACOUSTIC_NODE_DSP_FILTER_H
#define ACOUSTIC_NODE_DSP_FILTER_H

#include <stddef.h>
#include <stdint.h>

namespace acoustic_node {

// Direct-Form II Transposed 2. derece IIR Biquad (RBJ katsayilari)
struct Biquad {
    float b0 = 1.0f, b1 = 0.0f, b2 = 0.0f;
    float a1 = 0.0f, a2 = 0.0f;
    float z1 = 0.0f, z2 = 0.0f;

    void reset() { z1 = 0.0f; z2 = 0.0f; }

    void set_lowpass(float fs_hz, float fc_hz, float q);
    void set_highpass(float fs_hz, float fc_hz, float q);

    float process(float x) {
        const float y = b0 * x + z1;
        z1 = b1 * x - a1 * y + z2;
        z2 = b2 * x - a2 * y;
        return y;
    }
};

// 4. derece Butterworth = iki biquad kaskadi (Q1 = 0.5412, Q2 = 1.3066)
struct Butterworth4 {
    Biquad s1, s2;

    void set_lowpass(float fs_hz, float fc_hz);
    void set_highpass(float fs_hz, float fc_hz);
    void reset() { s1.reset(); s2.reset(); }
    float process(float x) { return s2.process(s1.process(x)); }
};

// Kenar frekansindaki genlik kazanci |H(f)| (testlerde ve tasarim hesaplarinda kullanilir)
float biquad_magnitude(const Biquad& bq, float fs_hz, float f_hz);

// Alcak geciren filtre + M kat seyreltme (decimation). Her M girdide bir cikti uretir.
class Decimator {
public:
    void configure(float fs_in_hz, float fc_hz, uint16_t factor);
    void reset();

    // Cikti hazirsa true doner ve *out yazilir
    bool push(float x, float* out) {
        const float y = lp_.process(x);
        if (++count_ >= factor_) {
            count_ = 0;
            *out = y;
            return true;
        }
        return false;
    }

    uint16_t factor() const { return factor_; }
    float fs_out() const { return fs_out_; }

private:
    Butterworth4 lp_;
    uint16_t factor_ = 1;
    uint16_t count_ = 0;
    float fs_out_ = 0.0f;
};

// Kayan ortalama + seyreltme (CIC benzeri tek kademe). Yuksek orneklemede ucuz on-desimasyon.
class BoxcarDecimator {
public:
    void configure(uint16_t factor) { factor_ = factor; reset(); }
    void reset() { acc_ = 0.0f; count_ = 0; }

    bool push(float x, float* out) {
        acc_ += x;
        if (++count_ >= factor_) {
            *out = acc_ / static_cast<float>(factor_);
            acc_ = 0.0f;
            count_ = 0;
            return true;
        }
        return false;
    }

private:
    float acc_ = 0.0f;
    uint16_t factor_ = 1;
    uint16_t count_ = 0;
};

}  // namespace acoustic_node

#endif  // ACOUSTIC_NODE_DSP_FILTER_H
