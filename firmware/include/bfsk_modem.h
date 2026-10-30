#ifndef ACOUSTIC_NODE_BFSK_MODEM_H
#define ACOUSTIC_NODE_BFSK_MODEM_H

#include <stddef.h>
#include <stdint.h>

#include "swarm_mesh.h"

namespace acoustic_node {

// Ultrasonik BFSK: bit 0 = 24 kHz, bit 1 = 28 kHz, 1 kbps (192 ornek / sembol @ 192 kHz).
// Ton araligi (4 kHz) sembol hizinin 4 katidir; 192 noktalik Goertzel'de iki ton
// tam olarak 24. ve 28. kutuya duser, birbirine sizinti yapmaz.
constexpr float kBfskF0Hz = 24000.0f;
constexpr float kBfskF1Hz = 28000.0f;
constexpr float kBfskNoiseLoHz = 20000.0f;   // Bant disi gurultu referansi
constexpr float kBfskNoiseHiHz = 32000.0f;
constexpr size_t kBfskSymbolSamples = 192;
constexpr size_t kBfskLanes = 4;             // Ceyrek sembol adimli zamanlama fazlari
constexpr size_t kBfskHop = kBfskSymbolSamples / kBfskLanes;
constexpr uint16_t kBfskPreamble = 0xAAAA;   // 16 bit 1010... (AGC/enerji kapisi oturur)
constexpr uint16_t kBfskSync =
    static_cast<uint16_t>((kSwarmSyncByte1 << 8) | kSwarmSyncByte2);
constexpr size_t kBfskFrameBits = 16 + 8 * kSwarmFrameSize;

// Yayin bit dizisi: 16 bit preamble + cerceve (MSB once). bits_out en az kBfskFrameBits.
size_t bfsk_build_bits(const uint8_t frame[kSwarmFrameSize], uint8_t* bits_out);

// Tek pencere Goertzel enerjisi (|X(f)|^2)
float goertzel_power(const float* x, size_t n, float fs_hz, float f_hz);

class BfskDemodulator {
public:
    explicit BfskDemodulator(float fs_hz = 192000.0f, float gate_ratio = 4.0f);

    void reset();
    void push(const float* x, size_t n);
    void push(float x);

    // Verici calisirken (kendi sinyalimiz AFE'yi doyurur) alimi kapat
    void blank(uint32_t samples) { blank_ = samples; }

    // Sirada aday cerceve varsa true. CRC/MAC dogrulamasi cagirana aittir.
    bool pop_frame(uint8_t out[kSwarmFrameSize]);

    uint32_t frames_detected() const { return frames_detected_; }

private:
    struct Lane {
        uint16_t shift;
        bool collecting;
        size_t bit_count;
        uint8_t bytes[kSwarmFrameSize];
    };

    void on_hop();
    void lane_bit(Lane& lane, bool valid, bool bit);
    void emit(const uint8_t frame[kSwarmFrameSize]);

    float fs_;
    float gate_ratio_;
    float coef_[4];               // 2 cos(2 pi f / fs): F0, F1, NoiseLo, NoiseHi
    float ring_[kBfskSymbolSamples];
    size_t ring_pos_ = 0;
    size_t filled_ = 0;
    size_t since_hop_ = 0;
    size_t hop_index_ = 0;
    uint32_t blank_ = 0;
    Lane lanes_[kBfskLanes];

    static constexpr size_t kQueue = 4;
    uint8_t queue_[kQueue][kSwarmFrameSize];
    size_t q_head_ = 0, q_count_ = 0;
    uint8_t last_[kSwarmFrameSize];
    size_t last_hop_ = 0;
    bool have_last_ = false;
    uint32_t frames_detected_ = 0;
};

}  // namespace acoustic_node

#endif  // ACOUSTIC_NODE_BFSK_MODEM_H
