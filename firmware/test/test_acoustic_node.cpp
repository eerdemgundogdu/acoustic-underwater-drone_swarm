#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "acoustic_dsp.h"
#include "piezo_harvester.h"
#include "swarm_mesh.h"

namespace {

constexpr float kPi = 3.14159265358979323846f;

// Sentetik su alti hidrofon sinyali uretici:
// - Dar-bant makine tonali (lofar_hz)
// - Saft + N-kanatli pervane tarafindan genlik modüle edilmis yuksek frekans kavitasyon tasiyicisi
void synthesize_underwater_signature(float* out, size_t n, float fs,
                                     float lofar_hz, float shaft_hz,
                                     uint8_t n_blades, float noise_amp) {
    uint32_t rng = 0x13579BDFu;
    const float blade_hz = shaft_hz * static_cast<float>(n_blades);
    for (size_t i = 0; i < n; ++i) {
        float t = static_cast<float>(i) / fs;
        rng = rng * 1664525u + 1013904223u;
        float white = (static_cast<float>((rng >> 8) & 0xFFFF) / 32768.0f) - 1.0f;

        // Dar-bant LOFAR tonali
        float tonal = 1.25f * sinf(2.0f * kPi * lofar_hz * t);

        // Pervane kavitasyon zarfi (saft + kanat gecis harmonigi)
        float env = 1.0f + 0.45f * sinf(2.0f * kPi * shaft_hz * t) +
                    0.85f * sinf(2.0f * kPi * blade_hz * t);
        // Yuksek frekans kavitasyon tasiyicisi (fs * 0.35)
        float cav_carrier = sinf(2.0f * kPi * (0.35f * fs) * t);

        out[i] = tonal + 1.4f * env * cav_carrier + noise_amp * white;
    }
}

void test_hostile_5blade_detection() {
    float buf[pelagos::kFftSize];
    const float fs = 1024.0f;
    // Dusman profili: 145 Hz makine tonali, 5.0 Hz saft devri, 5 kanat (25.0 Hz kanat gecis)
    synthesize_underwater_signature(buf, pelagos::kFftSize, fs, 145.0f, 5.0f, 5, 0.15f);

    pelagos::AcousticSignature sig =
        pelagos::analyze_hydrophone_frame(buf, pelagos::kFftSize, fs, 380.0f);

    assert(fabsf(sig.lofar_peak_hz - 145.0f) <= 1.5f);
    assert(sig.lofar_snr_db > 15.0f);
    assert(fabsf(sig.shaft_rate_hz - 5.0f) <= 1.0f);
    assert(sig.estimated_blades == 5);
    assert(fabsf(sig.blade_rate_hz - 25.0f) <= 2.0f);
    assert(sig.iff_class == pelagos::IFF_HOSTILE_TRACK);
    printf("[ OK ] test_hostile_5blade_detection (f_lofar=%.1f Hz, f_shaft=%.1f Hz, blades=%u)\n",
           sig.lofar_peak_hz, sig.shaft_rate_hz, sig.estimated_blades);
}

void test_friendly_3blade_uuv_detection() {
    float buf[pelagos::kFftSize];
    const float fs = 1024.0f;
    // Dost UUV profili: 380 Hz dost akustik beacon, 6.0 Hz saft devri, 3 kanat (18.0 Hz)
    synthesize_underwater_signature(buf, pelagos::kFftSize, fs, 380.0f, 6.0f, 3, 0.12f);

    pelagos::AcousticSignature sig =
        pelagos::analyze_hydrophone_frame(buf, pelagos::kFftSize, fs, 380.0f);

    assert(fabsf(sig.lofar_peak_hz - 380.0f) <= 1.5f);
    assert(sig.estimated_blades == 3);
    assert(sig.iff_class == pelagos::IFF_FRIENDLY_UUV);
    printf("[ OK ] test_friendly_3blade_uuv_detection (f_lofar=%.1f Hz, blades=%u)\n",
           sig.lofar_peak_hz, sig.estimated_blades);
}

void test_swarm_mesh_codec_and_multihop_dedup() {
    const uint32_t key = 0xCAFEBABEu;
    pelagos::SwarmAcousticPacket pkt{};
    pkt.src_node_id = 1;
    pkt.seq_num     = 42;
    pkt.hop_count   = 0;
    pkt.ttl         = 2;
    pkt.iff_class   = pelagos::IFF_HOSTILE_TRACK;
    pkt.blade_count = 5;
    pkt.lofar_hz_q2 = 145 * 4;
    pkt.snr_db_q2   = 22 * 4;
    pkt.soc_pct     = 84;

    uint8_t wire[pelagos::kSwarmFrameSize];
    pelagos::encode_swarm_frame(pkt, key, wire);

    // Yanlis anahtarla sahte paket reddedilmeli
    pelagos::SwarmAcousticPacket decoded{};
    assert(!pelagos::decode_swarm_frame(wire, key ^ 0x01u, &decoded));

    // Dugum 2 paketi alir, dogrular ve TTL azaltarak relay eder
    pelagos::SwarmMeshRouter node2(2, key, 120);
    uint8_t relay_wire[pelagos::kSwarmFrameSize];
    bool should_relay = false;
    assert(node2.process_incoming(wire, &decoded, relay_wire, &should_relay));
    assert(should_relay);
    assert(decoded.src_node_id == 1 && decoded.blade_count == 5);

    // Ayni paket tekrar geldiginde (yanki / coklu yol) reddedilmeli (dedup)
    assert(!node2.process_incoming(wire, &decoded, relay_wire, &should_relay));

    // Dugum 3 relay edilen paketi alir (hop_count=1, ttl=1)
    pelagos::SwarmMeshRouter node3(3, key, 120);
    pelagos::SwarmAcousticPacket hop_pkt{};
    assert(node3.process_incoming(relay_wire, &hop_pkt, nullptr, nullptr));
    assert(hop_pkt.hop_count == 1 && hop_pkt.ttl == 1);
    printf("[ OK ] test_swarm_mesh_codec_and_multihop_dedup\n");
}

void test_piezo_harvester_fsm() {
    pelagos::PiezoHarvesterFSM fsm;
    fsm.set_bus_voltage(14.5f);

    // 1. Dalga enerjisi ile derin uykuda sarj olma (120 mW net giris, 180 saniye)
    for (int i = 0; i < 180; ++i) {
        fsm.step(1.0f, 120.0f, false, false, true, false);
    }
    assert(fsm.bus_voltage() > 17.5f);
    assert(fsm.state() == pelagos::STATE_DEEP_SLEEP_HARVEST);

    // 2. Akustik uyandirma -> Pasif dinleme -> DSP siniflandirma -> Akustik Suru Alarmi
    assert(fsm.step(0.5f, 10.0f, true, false, true, false) == pelagos::STATE_PASSIVE_LISTEN);
    assert(fsm.step(0.5f, 10.0f, true, true, true, false)  == pelagos::STATE_DSP_CLASSIFY);
    assert(fsm.step(0.5f, 10.0f, true, true, true, false)  == pelagos::STATE_SWARM_TX_ALERT);

    // 3. Su sizintisi veya manyetik emniyet kilidi acildiginda FAULT_LOCKOUT
    assert(fsm.step(0.5f, 10.0f, true, true, true, true)   == pelagos::STATE_FAULT_LOCKOUT);
    printf("[ OK ] test_piezo_harvester_fsm (V_bus=%.2f V, SoC=%u%%)\n",
           fsm.bus_voltage(), fsm.soc_percent());
}

}  // namespace

int main() {
    test_hostile_5blade_detection();
    test_friendly_3blade_uuv_detection();
    test_swarm_mesh_codec_and_multihop_dedup();
    test_piezo_harvester_fsm();
    printf("ALL PELAGOS FIRMWARE TESTS PASSED\n");
    return 0;
}
