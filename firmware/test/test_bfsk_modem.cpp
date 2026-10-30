// BFSK modem (verici bit plani + Goertzel alici) icin host testleri.
// Verici bit plani sentetik 24/28 kHz tonlara cevrilir, gurultu ve rastgele
// zaman kaymasiyla aliciya verilir; cikan cerceve swarm_mesh ile dogrulanir.

#include "minitest.h"
#include "bfsk_modem.h"
#include "swarm_mesh.h"

#include <cmath>
#include <cstring>
#include <random>
#include <vector>

using namespace acoustic_node;

namespace {

constexpr double kPi = 3.14159265358979323846;
constexpr float kFs = 192000.0f;
const uint8_t kKey[kSwarmKeySize] = {0x10, 0x32, 0x54, 0x76, 0x98, 0xBA, 0xDC, 0xFE,
                                     0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF};

void sample_frame(uint8_t frame[kSwarmFrameSize], uint8_t seq)
{
    SwarmAcousticPacket p{};
    p.src_node_id = 4;
    p.seq_num = seq;
    p.ttl = 2;
    p.iff_class = 2;
    p.blade_count = 5;
    p.lofar_hz_q2 = 580;
    p.snr_db_q2 = 80;
    p.soc_pct = 77;
    p.flags = kFlagHarvestOk;
    encode_swarm_frame(p, kKey, frame);
}

// Faz surekli BFSK dalga bicimi: lead sessizlik + bitler + tail sessizlik
std::vector<float> modulate(const uint8_t frame[kSwarmFrameSize], size_t lead, size_t tail,
                            float amp, float noise, uint32_t seed)
{
    uint8_t bits[kBfskFrameBits];
    const size_t nb = bfsk_build_bits(frame, bits);
    std::vector<float> x(lead + nb * kBfskSymbolSamples + tail, 0.0f);
    double phase = 0.0;
    for (size_t b = 0; b < nb; ++b) {
        const double f = bits[b] ? kBfskF1Hz : kBfskF0Hz;
        for (size_t k = 0; k < kBfskSymbolSamples; ++k) {
            phase += 2 * kPi * f / kFs;
            x[lead + b * kBfskSymbolSamples + k] = amp * static_cast<float>(std::sin(phase));
        }
    }
    std::mt19937 rng(seed);
    std::normal_distribution<float> g(0.0f, noise);
    for (auto &v : x) v += g(rng);
    return x;
}

int count_valid(BfskDemodulator &d, uint8_t out[kSwarmFrameSize])
{
    int n = 0;
    uint8_t f[kSwarmFrameSize];
    while (d.pop_frame(f)) {
        if (decode_swarm_frame(f, kKey, nullptr)) {
            std::memcpy(out, f, kSwarmFrameSize);
            ++n;
        }
    }
    return n;
}

}  // namespace

TEST(bit_plan_preamble_and_msb_first)
{
    uint8_t frame[kSwarmFrameSize];
    sample_frame(frame, 1);
    uint8_t bits[kBfskFrameBits];
    CHECK_EQ(bfsk_build_bits(frame, bits), kBfskFrameBits);
    for (size_t i = 0; i < 16; ++i) CHECK_EQ(bits[i], (i % 2 == 0) ? 1 : 0);
    // 0xA5 = 1010 0101
    const uint8_t a5[8] = {1, 0, 1, 0, 0, 1, 0, 1};
    for (size_t i = 0; i < 8; ++i) CHECK_EQ(bits[16 + i], a5[i]);
}

TEST(goertzel_separates_tones)
{
    std::vector<float> x(kBfskSymbolSamples);
    for (size_t i = 0; i < x.size(); ++i) x[i] = static_cast<float>(std::sin(2 * kPi * 28000.0 * static_cast<double>(i) / kFs));
    const float e0 = goertzel_power(x.data(), x.size(), kFs, kBfskF0Hz);
    const float e1 = goertzel_power(x.data(), x.size(), kFs, kBfskF1Hz);
    CHECK(e1 > 1000.0f * e0);   // Tam kutu: dik tonlar arasi sizinti yok
}

TEST(clean_loopback_any_timing_offset)
{
    uint8_t frame[kSwarmFrameSize];
    sample_frame(frame, 9);
    for (size_t lead : {0u, 7u, 31u, 48u, 101u, 190u}) {
        BfskDemodulator d(kFs);
        const auto x = modulate(frame, 500 + lead, 400, 0.01f, 0.0f, 1);
        d.push(x.data(), x.size());
        uint8_t got[kSwarmFrameSize] = {};
        CHECK_EQ(count_valid(d, got), 1);
        CHECK(std::memcmp(got, frame, kSwarmFrameSize) == 0);
    }
}

TEST(noisy_loopback)
{
    // Ornek basina SNR -3 dB (ton genligi 1, gurultu sigma 1); 192 noktalik
    // Goertzel ~20 dB isleme kazanci saglar.
    uint8_t frame[kSwarmFrameSize];
    sample_frame(frame, 10);
    int ok = 0;
    for (uint32_t seed = 0; seed < 10; ++seed) {
        BfskDemodulator d(kFs);
        const auto x = modulate(frame, 1000 + seed * 13, 500, 1.0f, 1.0f, seed);
        d.push(x.data(), x.size());
        uint8_t got[kSwarmFrameSize];
        ok += count_valid(d, got);
    }
    std::printf("  10 denemede %d cerceve dogru\n", ok);
    CHECK(ok >= 9);
}

TEST(noise_only_produces_no_valid_frame)
{
    BfskDemodulator d(kFs);
    std::mt19937 rng(99);
    std::normal_distribution<float> g(0.0f, 1.0f);
    std::vector<float> x(kFs * 3);
    for (auto &v : x) v = g(rng);
    d.push(x.data(), x.size());
    uint8_t got[kSwarmFrameSize];
    CHECK_EQ(count_valid(d, got), 0);
}

TEST(blanking_suppresses_own_transmission)
{
    uint8_t frame[kSwarmFrameSize];
    sample_frame(frame, 11);
    const auto x = modulate(frame, 200, 200, 0.5f, 0.0f, 3);
    BfskDemodulator d(kFs);
    d.blank(static_cast<uint32_t>(x.size()));
    d.push(x.data(), x.size());
    uint8_t got[kSwarmFrameSize];
    CHECK_EQ(count_valid(d, got), 0);
}

TEST(back_to_back_frames)
{
    uint8_t f1[kSwarmFrameSize], f2[kSwarmFrameSize];
    sample_frame(f1, 20);
    sample_frame(f2, 21);
    auto x = modulate(f1, 300, 0, 0.1f, 0.0f, 4);
    const auto y = modulate(f2, 2000, 300, 0.1f, 0.0f, 5);
    x.insert(x.end(), y.begin(), y.end());
    BfskDemodulator d(kFs);
    d.push(x.data(), x.size());
    int n = 0;
    uint8_t got[kSwarmFrameSize];
    while (d.pop_frame(got)) {
        if (decode_swarm_frame(got, kKey, nullptr)) ++n;
    }
    CHECK_EQ(n, 2);
}

TEST_MAIN()
