// acoustic_dsp + dsp_filter icin host birim testleri.
//
// Sentetik hidrofon sinyalleri 192 kHz'de uretilir (kartin ADC hizi); LOFAR ve
// DEMON zincirleri firmware'deki ayni akisli islemcilerden gecirilir.

#include "minitest.h"
#include "acoustic_dsp.h"
#include "dsp_filter.h"

#include <cmath>
#include <random>
#include <vector>

using namespace acoustic_node;

namespace {

constexpr double kPi = 3.14159265358979323846;
constexpr float kFs = kAdcSampleRateHz;

// Pervane kaynakli gurultu modeli: genis bant kavitasyon gurultusu, saft ve
// kanat gecis frekanslariyla genlik modulasyonlu + dar bant makine tonu + ortam gurultusu.
struct ShipModel {
    double tonal_hz = 145.0;
    double tonal_amp = 0.0;
    double shaft_hz = 6.0;
    int blades = 5;
    double cav_amp = 1.0;
    double m_shaft = 0.3;
    double m_blade = 0.7;
    double ambient = 0.3;
};

template <typename Sink>
void synthesize(const ShipModel& s, size_t n, uint32_t seed, Sink sink)
{
    std::mt19937 rng(seed);
    std::normal_distribution<float> g(0.0f, 1.0f);
    const double blade_hz = s.shaft_hz * s.blades;
    for (size_t i = 0; i < n; ++i) {
        const double t = static_cast<double>(i) / kFs;
        const double env = 1.0 + s.m_shaft * std::sin(2 * kPi * s.shaft_hz * t) +
                           s.m_blade * std::sin(2 * kPi * blade_hz * t);
        const double x = s.tonal_amp * std::sin(2 * kPi * s.tonal_hz * t) +
                         s.cav_amp * env * g(rng) + s.ambient * g(rng);
        sink(static_cast<float>(x));
    }
}

constexpr size_t kLofarSamples = kLofarFftSize * kLofarAverages * 96;   // 2.05 s
constexpr size_t kDemonSamples = kDemonFftSize * 64 * 8;                // 2.73 s

}  // namespace

TEST(fft_matches_naive_dft)
{
    constexpr size_t n = 64;
    std::vector<float> re(n), im(n, 0.0f);
    std::mt19937 rng(7);
    std::uniform_real_distribution<float> u(-1.0f, 1.0f);
    for (auto &v : re) v = u(rng);
    std::vector<float> x = re;
    fft_radix2(re.data(), im.data(), n);
    double max_err = 0.0;
    for (size_t k = 0; k < n; ++k) {
        double dr = 0.0, di = 0.0;
        for (size_t i = 0; i < n; ++i) {
            const double a = -2.0 * kPi * static_cast<double>(k * i) / static_cast<double>(n);
            dr += x[i] * std::cos(a);
            di += x[i] * std::sin(a);
        }
        max_err = std::fmax(max_err, std::fabs(dr - re[k]) + std::fabs(di - im[k]));
    }
    CHECK(max_err < 1e-4);
}

TEST(butterworth4_corner_and_stopband)
{
    Butterworth4 lp;
    lp.set_lowpass(kFs, 2000.0f);
    const float at_fc = biquad_magnitude(lp.s1, kFs, 2000.0f) * biquad_magnitude(lp.s2, kFs, 2000.0f);
    const float at_2fc = biquad_magnitude(lp.s1, kFs, 4000.0f) * biquad_magnitude(lp.s2, kFs, 4000.0f);
    // -3 dB kosesi ve 4. derece icin oktav basina -24 dB
    CHECK(std::fabs(20.0f * std::log10(at_fc) + 3.01f) < 0.2f);
    CHECK(std::fabs(20.0f * std::log10(at_2fc) + 24.1f) < 0.6f);
}

TEST(decimator_rejects_alias_band)
{
    // LOFAR ilk kademe: 192 kHz -> 12 kHz. 11 kHz'deki ton 1 kHz'e katlanir;
    // en az 50 dB bastirilmali.
    Decimator d;
    d.configure(kFs, 2000.0f, 16);
    double p_in = 0.0, p_out = 0.0;
    size_t n_out = 0;
    for (size_t i = 0; i < 192000; ++i) {
        const float x = static_cast<float>(std::sin(2 * kPi * 11000.0 * static_cast<double>(i) / kFs));
        float y;
        p_in += x * x;
        if (d.push(x, &y) && i > 19200) {
            p_out += y * y;
            ++n_out;
        }
    }
    const double att_db = 10.0 * std::log10((p_out / static_cast<double>(n_out)) / (p_in / 192000.0));
    CHECK(att_db < -50.0);
}

TEST(dual_gain_selector_switches_on_clip)
{
    DualGainSelector s;
    // HI kanal dogrusal bolgede: HI kullanilir
    const float v_hi = s.convert(2048 + 10, 2048 + 100);
    CHECK(!s.using_low_gain());
    CHECK(std::fabs(v_hi - 100.0f * (3.3f / 4096.0f) / DualGainSelector::kGainHi) < 1e-9f);
    // HI raya dayandi: LO'ya gec ve tutma suresi boyunca LO'da kal
    const float v_lo = s.convert(2048 + 300, 4095);
    CHECK(s.using_low_gain());
    CHECK(std::fabs(v_lo - 300.0f * (3.3f / 4096.0f) / DualGainSelector::kGainLo) < 1e-9f);
    for (int i = 0; i < DualGainSelector::kHoldSamples - 2; ++i) s.convert(2048, 2048);
    CHECK(s.using_low_gain());
    s.convert(2048, 2048);
    s.convert(2048, 2048);
    CHECK(!s.using_low_gain());
}

TEST(lofar_finds_machinery_tone)
{
    LofarProcessor lofar;
    ShipModel m;
    m.tonal_amp = 0.25;
    m.cav_amp = 0.0;
    m.ambient = 1.0;            // Tonal, genis bant gurultunun ~33 dB altinda (192 kHz bantta)
    m.tonal_hz = 145.0;
    bool ready = false;
    synthesize(m, kLofarSamples, 11, [&](float x) { ready |= lofar.push(x); });
    CHECK(ready);
    const LofarResult &r = lofar.result();
    std::printf("  LOFAR: %.2f Hz, %.1f dB\n", r.peak_hz, r.peak_snr_db);
    CHECK(std::fabs(r.peak_hz - 145.0f) < 1.0f);
    CHECK(r.peak_snr_db > 15.0f);
}

TEST(lofar_noise_only_stays_below_detection)
{
    LofarProcessor lofar;
    ShipModel m;
    m.cav_amp = 0.0;
    m.ambient = 1.0;
    synthesize(m, kLofarSamples, 12, [&](float x) { lofar.push(x); });
    std::printf("  LOFAR gurultu: %.1f dB\n", lofar.result().peak_snr_db);
    CHECK(lofar.result().peak_snr_db < 8.0f);
}

TEST(demon_hostile_five_blade)
{
    DemonProcessor demon;
    ShipModel m;
    m.shaft_hz = 6.0;
    m.blades = 5;
    bool ready = false;
    synthesize(m, kDemonSamples, 21, [&](float x) { ready |= demon.push(x); });
    CHECK(ready);
    const DemonResult &r = demon.result();
    std::printf("  DEMON: shaft %.2f Hz (%.1f dB), blade %.2f Hz (%.1f dB), N=%u\n",
                r.shaft_hz, r.shaft_snr_db, r.blade_hz, r.blade_snr_db, r.blades);
    CHECK(std::fabs(r.shaft_hz - 6.0f) < 0.4f);
    CHECK_EQ(r.blades, 5);
    CHECK(std::fabs(r.blade_hz - 30.0f) < 0.8f);
}

TEST(demon_friendly_three_blade)
{
    DemonProcessor demon;
    ShipModel m;
    m.shaft_hz = 7.5;
    m.blades = 3;
    synthesize(m, kDemonSamples, 22, [&](float x) { demon.push(x); });
    const DemonResult &r = demon.result();
    std::printf("  DEMON: shaft %.2f Hz, N=%u\n", r.shaft_hz, r.blades);
    CHECK(std::fabs(r.shaft_hz - 7.5f) < 0.4f);
    CHECK_EQ(r.blades, 3);
}

TEST(demon_ambient_has_no_blade_line)
{
    DemonProcessor demon;
    ShipModel m;
    m.m_shaft = 0.0;
    m.m_blade = 0.0;
    synthesize(m, kDemonSamples, 23, [&](float x) { demon.push(x); });
    CHECK_EQ(demon.result().blades, 0);
}

TEST(classify_rules)
{
    LofarResult beacon;
    beacon.peak_hz = 380.5f;
    beacon.peak_snr_db = 20.0f;
    DemonResult three;
    three.blades = 3;
    three.blade_snr_db = 12.0f;
    DemonResult five;
    five.blades = 5;
    five.blade_snr_db = 12.0f;
    LofarResult quiet;
    quiet.peak_snr_db = 4.0f;
    DemonResult none;

    CHECK_EQ(classify_signature(beacon, three).iff_class, IFF_FRIENDLY_UUV);
    CHECK_EQ(classify_signature(quiet, five).iff_class, IFF_HOSTILE_TRACK);
    CHECK_EQ(classify_signature(quiet, none).iff_class, IFF_AMBIENT_NOISE);
    CHECK_EQ(classify_signature(beacon, none).iff_class, IFF_UNKNOWN_TONAL);
    // Pilot tonu yok ama 3 kanat: dost sayilmaz
    LofarResult other = beacon;
    other.peak_hz = 210.0f;
    CHECK_EQ(classify_signature(other, three).iff_class, IFF_UNKNOWN_TONAL);
}

TEST_MAIN()
