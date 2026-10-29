// Acoustic Swarm Deniz Tabani Akustik Dugumu — Gomulu Cortex-M7 / Teensy 4.1 Firmware
// Donanim: acoustic-swarm-node Rev A (2 katmanli PCB)
//   - Pin 16 (A2) : Hidrofon AFE ADC girisi (IntervalTimer 1024 Hz cift tamponlu)
//   - Pin 15 (A1) : Piezo enerji hasadi / HV tampon gerilim olcumu (68k/10k)
//   - Pin 14 (A0) : Basinc govdesi su sizinti probu (10k/47k)
//   - Pin 36      : Manyetik kurma/emniyet reed anahtari (NC) geri okumasi
//   - Pin 37      : Akustik ping / hata uyari cikisi (BZ1)
//   - Pin 38      : Eyleyici / modem guc kontaktoru bobin surucusu (Q2 BCP56-16)
//   - Pin 6..7    : Ultrasonik BFSK akustik suru (swarm) tasiyici cikislari
//   - Pin 11      : Akustik IFF kilit LED'i (D9)

#include <Arduino.h>
#include <IntervalTimer.h>

#include "acoustic_dsp.h"
#include "piezo_harvester.h"
#include "swarm_mesh.h"

namespace {

constexpr uint8_t kPinSwarmTx0   = 6;
constexpr uint8_t kPinSwarmTx1   = 7;
constexpr uint8_t kPinStatusLed  = 11;
constexpr uint8_t kPinLeakAdc    = 14;  // A0
constexpr uint8_t kPinBattAdc    = 15;  // A1
constexpr uint8_t kPinHydroAdc   = 16;  // A2
constexpr uint8_t kPinArmSense   = 36;
constexpr uint8_t kPinPingBuzzer = 37;
constexpr uint8_t kPinModemEn    = 38;

constexpr float kSampleRateHz    = 1024.0f;
constexpr uint8_t kNodeId        = 0x03;
constexpr uint32_t kSwarmKey     = 0x50454C41u;  // Demo suru anahtari

// Cift tamponlu (ping-pong) DMA/ISR ses ornekleme dizileri
volatile float g_adc_buf[2][acoustic_node::kFftSize];
volatile uint8_t g_active_buf = 0;
volatile size_t g_sample_idx  = 0;
volatile bool g_frame_ready   = false;
volatile uint8_t g_ready_buf  = 0;

IntervalTimer g_adc_timer;
acoustic_node::PiezoHarvesterFSM g_power_fsm;
acoustic_node::SwarmMeshRouter g_mesh_router(kNodeId, kSwarmKey);
uint8_t g_seq_counter = 0;

void adc_isr() {
    int raw = analogRead(kPinHydroAdc);
    // 12-bit ADC [0..4095] -> [-1.0 .. +1.0] normalize akustik basinc
    float norm = (static_cast<float>(raw) - 2048.0f) * (1.0f / 2048.0f);
    uint8_t b = g_active_buf;
    size_t idx = g_sample_idx;
    g_adc_buf[b][idx] = norm;
    ++idx;
    if (idx >= acoustic_node::kFftSize) {
        g_ready_buf = b;
        g_frame_ready = true;
        g_active_buf = b ^ 1u;
        g_sample_idx = 0;
    } else {
        g_sample_idx = idx;
    }
}

float read_harvest_voltage() {
    int raw = analogRead(kPinBattAdc);
    float v_adc = (static_cast<float>(raw) / 4095.0f) * 3.3f;
    return v_adc * ((68.0f + 10.0f) / 10.0f);
}

bool read_hull_leak() {
    int raw = analogRead(kPinLeakAdc);
    return raw > 1500;  // ~1.2 V ustu su sizintisi
}

// 16 baytlik akustik paketi BFSK (24 kHz = bit 0, 28 kHz = bit 1) olarak gonder
void transmit_bfsk_packet(const uint8_t frame[acoustic_node::kSwarmFrameSize]) {
    digitalWriteFast(kPinModemEn, HIGH);
    for (size_t i = 0; i < acoustic_node::kSwarmFrameSize; ++i) {
        uint8_t byte_val = frame[i];
        for (int b = 7; b >= 0; --b) {
            bool bit_one = ((byte_val >> b) & 0x01) != 0;
            analogWriteFrequency(kPinSwarmTx0, bit_one ? 28000.0f : 24000.0f);
            analogWrite(kPinSwarmTx0, 128);
            delayMicroseconds(1000);  // 1 kbps akustik sembol suresi
        }
    }
    analogWrite(kPinSwarmTx0, 0);
    digitalWriteFast(kPinModemEn, LOW);
}

}  // namespace

void setup() {
    Serial.begin(115200);
    analogReadResolution(12);
    analogReadAveraging(4);

    pinMode(kPinStatusLed, OUTPUT);
    pinMode(kPinPingBuzzer, OUTPUT);
    pinMode(kPinModemEn, OUTPUT);
    pinMode(kPinSwarmTx0, OUTPUT);
    pinMode(kPinSwarmTx1, OUTPUT);
    pinMode(kPinArmSense, INPUT);

    digitalWriteFast(kPinModemEn, LOW);
    digitalWriteFast(kPinPingBuzzer, LOW);

    const float period_us = 1000000.0f / kSampleRateHz;
    g_adc_timer.begin(adc_isr, period_us);
}

void loop() {
    if (!g_frame_ready) {
        return;
    }

    float local_frame[acoustic_node::kFftSize];
    noInterrupts();
    uint8_t buf_idx = g_ready_buf;
    g_frame_ready = false;
    for (size_t i = 0; i < acoustic_node::kFftSize; ++i) {
        local_frame[i] = g_adc_buf[buf_idx][i];
    }
    interrupts();

    float v_bus = read_harvest_voltage();
    bool leak = read_hull_leak();
    bool arm_ok = digitalReadFast(kPinArmSense) == HIGH;

    g_power_fsm.set_bus_voltage(v_bus);
    acoustic_node::AcousticSignature sig =
        acoustic_node::analyze_hydrophone_frame(local_frame, acoustic_node::kFftSize, kSampleRateHz);

    bool wake_trig = sig.lofar_snr_db >= 8.0f;
    bool hostile = (sig.iff_class == acoustic_node::IFF_HOSTILE_TRACK);

    acoustic_node::NodePowerState st = g_power_fsm.step(
        1.0f, 12.0f, wake_trig, hostile, arm_ok, leak);

    digitalWriteFast(kPinStatusLed, hostile ? HIGH : LOW);

    if (st == acoustic_node::STATE_SWARM_TX_ALERT) {
        acoustic_node::SwarmAcousticPacket pkt{};
        pkt.src_node_id = kNodeId;
        pkt.seq_num     = ++g_seq_counter;
        pkt.hop_count   = 0;
        pkt.ttl         = 3;
        pkt.iff_class   = static_cast<uint8_t>(sig.iff_class);
        pkt.blade_count = sig.estimated_blades;
        pkt.lofar_hz_q2 = static_cast<uint16_t>(sig.lofar_peak_hz * 4.0f);
        pkt.snr_db_q2   = static_cast<uint8_t>(sig.lofar_snr_db * 4.0f);
        pkt.soc_pct     = g_power_fsm.soc_percent();

        uint8_t frame[acoustic_node::kSwarmFrameSize];
        acoustic_node::encode_swarm_frame(pkt, kSwarmKey, frame);
        transmit_bfsk_packet(frame);
    }
}
