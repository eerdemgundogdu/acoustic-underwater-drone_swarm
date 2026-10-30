#include "bfsk_modem.h"

#include <math.h>
#include <string.h>

namespace acoustic_node {

namespace {
constexpr float kPi = 3.14159265358979323846f;
}  // namespace

size_t bfsk_build_bits(const uint8_t frame[kSwarmFrameSize], uint8_t* bits_out) {
    size_t n = 0;
    for (int b = 15; b >= 0; --b) {
        bits_out[n++] = static_cast<uint8_t>((kBfskPreamble >> b) & 1u);
    }
    for (size_t i = 0; i < kSwarmFrameSize; ++i) {
        for (int b = 7; b >= 0; --b) {
            bits_out[n++] = static_cast<uint8_t>((frame[i] >> b) & 1u);
        }
    }
    return n;
}

float goertzel_power(const float* x, size_t n, float fs_hz, float f_hz) {
    const float coef = 2.0f * cosf(2.0f * kPi * f_hz / fs_hz);
    float s1 = 0.0f, s2 = 0.0f;
    for (size_t i = 0; i < n; ++i) {
        const float s0 = x[i] + coef * s1 - s2;
        s2 = s1;
        s1 = s0;
    }
    return s1 * s1 + s2 * s2 - coef * s1 * s2;
}

BfskDemodulator::BfskDemodulator(float fs_hz, float gate_ratio)
    : fs_(fs_hz), gate_ratio_(gate_ratio) {
    const float freqs[4] = {kBfskF0Hz, kBfskF1Hz, kBfskNoiseLoHz, kBfskNoiseHiHz};
    for (size_t i = 0; i < 4; ++i) {
        coef_[i] = 2.0f * cosf(2.0f * kPi * freqs[i] / fs_);
    }
    reset();
}

void BfskDemodulator::reset() {
    memset(ring_, 0, sizeof(ring_));
    ring_pos_ = 0;
    filled_ = 0;
    since_hop_ = 0;
    hop_index_ = 0;
    blank_ = 0;
    for (Lane& l : lanes_) {
        l.shift = 0;
        l.collecting = false;
        l.bit_count = 0;
    }
    q_head_ = 0;
    q_count_ = 0;
    have_last_ = false;
}

void BfskDemodulator::push(const float* x, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        push(x[i]);
    }
}

void BfskDemodulator::push(float x) {
    if (blank_ > 0) {
        --blank_;
        x = 0.0f;
    }
    ring_[ring_pos_] = x;
    ring_pos_ = (ring_pos_ + 1) % kBfskSymbolSamples;
    if (filled_ < kBfskSymbolSamples) ++filled_;
    if (++since_hop_ >= kBfskHop) {
        since_hop_ = 0;
        if (filled_ == kBfskSymbolSamples) on_hop();
    }
}

void BfskDemodulator::on_hop() {
    // Son 192 ornek uzerinde dort Goertzel (en eski ornekten baslayarak)
    float s1[4] = {0, 0, 0, 0}, s2[4] = {0, 0, 0, 0};
    for (size_t k = 0; k < kBfskSymbolSamples; ++k) {
        const float v = ring_[(ring_pos_ + k) % kBfskSymbolSamples];
        for (size_t t = 0; t < 4; ++t) {
            const float s0 = v + coef_[t] * s1[t] - s2[t];
            s2[t] = s1[t];
            s1[t] = s0;
        }
    }
    float e[4];
    for (size_t t = 0; t < 4; ++t) {
        e[t] = s1[t] * s1[t] + s2[t] * s2[t] - coef_[t] * s1[t] * s2[t];
    }
    const float tone = e[0] > e[1] ? e[0] : e[1];
    const float noise = 0.5f * (e[2] + e[3]);
    const bool valid = tone > 1e-12f && tone > gate_ratio_ * noise;
    const bool bit = e[1] > e[0];

    lane_bit(lanes_[hop_index_ % kBfskLanes], valid, bit);
    ++hop_index_;
}

void BfskDemodulator::lane_bit(Lane& lane, bool valid, bool bit) {
    if (!valid) {
        // Enerji kapisi kapali: senkron aramasi bastan, toplanan cerceve iptal
        lane.shift = 0;
        lane.collecting = false;
        return;
    }
    if (!lane.collecting) {
        lane.shift = static_cast<uint16_t>((lane.shift << 1) | (bit ? 1u : 0u));
        if (lane.shift == kBfskSync) {
            lane.collecting = true;
            lane.bytes[0] = kSwarmSyncByte1;
            lane.bytes[1] = kSwarmSyncByte2;
            lane.bit_count = 16;
        }
        return;
    }
    const size_t byte_idx = lane.bit_count / 8;
    if (lane.bit_count % 8 == 0) lane.bytes[byte_idx] = 0;
    lane.bytes[byte_idx] = static_cast<uint8_t>((lane.bytes[byte_idx] << 1) | (bit ? 1u : 0u));
    if (++lane.bit_count == 8 * kSwarmFrameSize) {
        emit(lane.bytes);
        lane.collecting = false;
        lane.shift = 0;
    }
}

void BfskDemodulator::emit(const uint8_t frame[kSwarmFrameSize]) {
    // Komsu zamanlama seritleri ayni cerceveyi bir-iki adim arayla cozer; tekrari at
    if (have_last_ && hop_index_ - last_hop_ <= 2 * kBfskLanes &&
        memcmp(frame, last_, kSwarmFrameSize) == 0) {
        return;
    }
    memcpy(last_, frame, kSwarmFrameSize);
    last_hop_ = hop_index_;
    have_last_ = true;
    ++frames_detected_;

    const size_t slot = (q_head_ + q_count_) % kQueue;
    memcpy(queue_[slot], frame, kSwarmFrameSize);
    if (q_count_ < kQueue) {
        ++q_count_;
    } else {
        q_head_ = (q_head_ + 1) % kQueue;  // Dolu: en eskiyi dusur
    }
}

bool BfskDemodulator::pop_frame(uint8_t out[kSwarmFrameSize]) {
    if (q_count_ == 0) return false;
    memcpy(out, queue_[q_head_], kSwarmFrameSize);
    q_head_ = (q_head_ + 1) % kQueue;
    --q_count_;
    return true;
}

}  // namespace acoustic_node
