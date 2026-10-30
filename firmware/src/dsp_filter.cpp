#include "dsp_filter.h"

#include <math.h>

namespace acoustic_node {

namespace {
constexpr float kPi = 3.14159265358979323846f;
constexpr float kButterQ1 = 0.54119610f;
constexpr float kButterQ2 = 1.30656296f;
}  // namespace

void Biquad::set_lowpass(float fs_hz, float fc_hz, float q) {
    const float w0 = 2.0f * kPi * fc_hz / fs_hz;
    const float cw = cosf(w0);
    const float alpha = sinf(w0) / (2.0f * q);
    const float a0 = 1.0f + alpha;
    b0 = (1.0f - cw) * 0.5f / a0;
    b1 = (1.0f - cw) / a0;
    b2 = b0;
    a1 = -2.0f * cw / a0;
    a2 = (1.0f - alpha) / a0;
    reset();
}

void Biquad::set_highpass(float fs_hz, float fc_hz, float q) {
    const float w0 = 2.0f * kPi * fc_hz / fs_hz;
    const float cw = cosf(w0);
    const float alpha = sinf(w0) / (2.0f * q);
    const float a0 = 1.0f + alpha;
    b0 = (1.0f + cw) * 0.5f / a0;
    b1 = -(1.0f + cw) / a0;
    b2 = b0;
    a1 = -2.0f * cw / a0;
    a2 = (1.0f - alpha) / a0;
    reset();
}

void Butterworth4::set_lowpass(float fs_hz, float fc_hz) {
    s1.set_lowpass(fs_hz, fc_hz, kButterQ1);
    s2.set_lowpass(fs_hz, fc_hz, kButterQ2);
}

void Butterworth4::set_highpass(float fs_hz, float fc_hz) {
    s1.set_highpass(fs_hz, fc_hz, kButterQ1);
    s2.set_highpass(fs_hz, fc_hz, kButterQ2);
}

float biquad_magnitude(const Biquad& bq, float fs_hz, float f_hz) {
    // H(z) = (b0 + b1 z^-1 + b2 z^-2) / (1 + a1 z^-1 + a2 z^-2), z = e^{jw}
    const float w = 2.0f * kPi * f_hz / fs_hz;
    const float c1 = cosf(w), s1 = sinf(w);
    const float c2 = cosf(2.0f * w), s2 = sinf(2.0f * w);
    const float nr = bq.b0 + bq.b1 * c1 + bq.b2 * c2;
    const float ni = -(bq.b1 * s1 + bq.b2 * s2);
    const float dr = 1.0f + bq.a1 * c1 + bq.a2 * c2;
    const float di = -(bq.a1 * s1 + bq.a2 * s2);
    return sqrtf((nr * nr + ni * ni) / (dr * dr + di * di));
}

void Decimator::configure(float fs_in_hz, float fc_hz, uint16_t factor) {
    factor_ = factor > 0 ? factor : 1;
    fs_out_ = fs_in_hz / static_cast<float>(factor_);
    lp_.set_lowpass(fs_in_hz, fc_hz);
    reset();
}

void Decimator::reset() {
    lp_.reset();
    count_ = 0;
}

}  // namespace acoustic_node
