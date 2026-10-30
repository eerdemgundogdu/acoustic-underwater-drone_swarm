// Akustik suru dugumu — Teensy 4.1 (Cortex-M7, 600 MHz) firmware
// Donanim: acoustic-swarm-node Rev A (hardware/)
//
// Akis:
//   ADC0 (pin 17, AFE HI) + ADC1 (pin 16, AFE LO), 192 kHz zamanlayici tetikli DMA
//     -> DualGainSelector (kirpilmayan kanal, hidrofon girisine indirgenmis volt)
//     -> LofarProcessor (dar bant makine tonu, ~2 s)
//     -> DemonProcessor (pervane saft / kanat, ~2.7 s) -> classify_signature
//     -> BfskDemodulator (24/28 kHz suru cerceveleri) -> SwarmMeshRouter
//   PowerManager: PWR_HOLD ile buck'i tutar, dinleme penceresi bitince birakir.
//   Verici: DRV8871 IN1'de FlexPWM %50 kare dalga; sembol basina frekans degisir.

#include <Arduino.h>
#include <ADC.h>
#include <AnalogBufferDMA.h>
#include <IntervalTimer.h>

#include "acoustic_dsp.h"
#include "bfsk_modem.h"
#include "node_config.h"
#include "power_manager.h"
#include "swarm_mesh.h"

using namespace acoustic_node;

namespace {

constexpr size_t kDmaBuf = 1920;   // 10 ms @ 192 kHz (yarim tampon)

DMAMEM static volatile uint16_t __attribute__((aligned(32))) g_hi_a[kDmaBuf];
DMAMEM static volatile uint16_t __attribute__((aligned(32))) g_hi_b[kDmaBuf];
DMAMEM static volatile uint16_t __attribute__((aligned(32))) g_lo_a[kDmaBuf];
DMAMEM static volatile uint16_t __attribute__((aligned(32))) g_lo_b[kDmaBuf];

ADC g_adc;
AnalogBufferDMA g_dma_hi(g_hi_a, kDmaBuf, g_hi_b, kDmaBuf);
AnalogBufferDMA g_dma_lo(g_lo_a, kDmaBuf, g_lo_b, kDmaBuf);

const uint8_t kSwarmKey[kSwarmKeySize] = {SWARM_KEY_BYTES};

DualGainSelector g_gain;
LofarProcessor g_lofar;
DemonProcessor g_demon;
BfskDemodulator g_modem(static_cast<float>(kAdcRateHz));
SwarmMeshRouter g_router(kNodeId, kSwarmKey);
PowerManager g_power;

AcousticSignature g_sig;
bool g_hostile_pending = false;
float g_batt_v = 0.0f;
bool g_leak = false;
uint8_t g_seq = 0;
uint32_t g_last_housekeeping = 0;

// ---- Verici: kesme ile sembol sembol BFSK -------------------------------------
IntervalTimer g_tx_timer;
uint8_t g_tx_bits[kBfskFrameBits];
volatile size_t g_tx_nbits = 0;
volatile size_t g_tx_idx = 0;
volatile bool g_tx_busy = false;

uint8_t g_pending_frame[kSwarmFrameSize];
bool g_pending = false;
uint32_t g_pending_at_ms = 0;

void tx_symbol_isr() {
    if (g_tx_idx >= g_tx_nbits) {
        analogWrite(kPinTxIn1, 0);
        g_tx_timer.end();
        g_tx_busy = false;
        return;
    }
    analogWriteFrequency(kPinTxIn1, g_tx_bits[g_tx_idx] ? kBfskF1Hz : kBfskF0Hz);
    analogWrite(kPinTxIn1, 128);   // 8 bit cozunurlukte %50
    ++g_tx_idx;
}

void start_tx(const uint8_t frame[kSwarmFrameSize]) {
    g_tx_nbits = bfsk_build_bits(frame, g_tx_bits);
    g_tx_idx = 0;
    g_tx_busy = true;
    // Kendi yayinimiz AFE'yi doyurur: yayin + 20 ms yankida alim kapali
    g_modem.blank(static_cast<uint32_t>((g_tx_nbits + 20) * kBfskSymbolSamples));
    g_tx_timer.begin(tx_symbol_isr, 1000);   // 1 ms sembol
}

// TDMA: kendi yuvamiz gelene kadar beklet
void schedule_tx(const uint8_t frame[kSwarmFrameSize], uint32_t now) {
    memcpy(g_pending_frame, frame, kSwarmFrameSize);
    g_pending = true;
    g_pending_at_ms = now + g_router.tdma_backoff_ms();
}

void send_alert(uint32_t now) {
    SwarmAcousticPacket p{};
    p.src_node_id = kNodeId;
    p.seq_num = ++g_seq;
    p.ttl = kAlertTtl;
    p.iff_class = static_cast<uint8_t>(g_sig.iff_class);
    p.blade_count = g_sig.demon.blades;
    p.lofar_hz_q2 = static_cast<uint16_t>(g_sig.lofar.peak_hz * 4.0f);
    const float snr_q2 = g_sig.lofar.peak_snr_db * 4.0f;
    p.snr_db_q2 = static_cast<uint8_t>(snr_q2 < 0 ? 0 : (snr_q2 > 255 ? 255 : snr_q2));
    p.soc_pct = g_power.soc_percent(g_batt_v);
    p.flags = static_cast<uint8_t>((digitalReadFast(kPinHarvestPg) ? kFlagHarvestOk : 0) |
                                   (g_leak ? kFlagLeak : 0));
    uint8_t frame[kSwarmFrameSize];
    encode_swarm_frame(p, kSwarmKey, frame);
    g_router.note_own(p.seq_num);
    schedule_tx(frame, now);
}

// ---- ADC ----------------------------------------------------------------------
void start_sampling() {
    g_dma_hi.init(&g_adc, ADC_0);
    g_dma_lo.init(&g_adc, ADC_1);
    g_adc.adc0->startSingleRead(kPinAdcHi);
    g_adc.adc1->startSingleRead(kPinAdcLo);
    // Iki zamanlayici ayni saatten turetilir; tamponlar ayni hizda dolar
    g_adc.adc0->startTimer(kAdcRateHz);
    g_adc.adc1->startTimer(kAdcRateHz);
}

void stop_sampling() {
    g_adc.adc0->stopTimer();
    g_adc.adc1->stopTimer();
}

void configure_adc() {
    for (ADC_Module* m : {g_adc.adc0, g_adc.adc1}) {
        m->setAveraging(1);
        m->setResolution(12);
        m->setConversionSpeed(ADC_CONVERSION_SPEED::HIGH_SPEED);
        m->setSamplingSpeed(ADC_SAMPLING_SPEED::HIGH_SPEED);
    }
}

// Pil ve sizinti: DMA ornekleme ~0.2 ms durdurulur (5 s'de bir)
void housekeeping() {
    stop_sampling();
    digitalWriteFast(kPinBattEn, HIGH);
    delayMicroseconds(200);   // 100k/15k + 100 nF yerlesme ~ 5 tau
    uint32_t acc = 0;
    for (int i = 0; i < 8; ++i) acc += static_cast<uint32_t>(g_adc.adc0->analogRead(kPinBattAdc));
    digitalWriteFast(kPinBattEn, LOW);
    g_batt_v = (static_cast<float>(acc) / 8.0f) * (3.3f / 4096.0f) * kBattDivRatio;
    g_leak = g_adc.adc0->analogRead(kPinLeakAdc) > kLeakThreshold;
    start_sampling();
}

void process_block(const volatile uint16_t* hi, const volatile uint16_t* lo, size_t n) {
    for (size_t i = 0; i < n; ++i) {
        const float x = g_gain.convert(lo[i], hi[i]);
        g_lofar.push(x);
        if (g_demon.push(x)) {
            g_sig = classify_signature(g_lofar.result(), g_demon.result());
            if (g_sig.iff_class == IFF_HOSTILE_TRACK) g_hostile_pending = true;
            Serial.printf("LOFAR %.1f Hz %.1f dB | DEMON %.2f Hz N=%u | IFF %u (%.2f)\n",
                          g_sig.lofar.peak_hz, g_sig.lofar.peak_snr_db, g_sig.demon.shaft_hz,
                          g_sig.demon.blades, g_sig.iff_class, g_sig.confidence);
        }
        g_modem.push(x);
    }
}

bool take_buffers() {
    if (!g_dma_hi.interrupted() || !g_dma_lo.interrupted()) return false;
    volatile uint16_t* hi = g_dma_hi.bufferLastISRFilled();
    volatile uint16_t* lo = g_dma_lo.bufferLastISRFilled();
    const size_t n = min(g_dma_hi.bufferCountLastISRFilled(), g_dma_lo.bufferCountLastISRFilled());
    // DMAMEM (OCRAM) onbellekli: CPU okumadan once satirlari gecersiz kil
    arm_dcache_delete((void*)hi, sizeof(g_hi_a));
    arm_dcache_delete((void*)lo, sizeof(g_lo_a));
    process_block(hi, lo, n);
    g_dma_hi.clearInterrupt();
    g_dma_lo.clearInterrupt();
    return true;
}

}  // namespace

void setup() {
    // Ilk is: gucu tut. Karsilastirici darbesi + RC mandal ~1 s; acilis ~0.4 s.
    pinMode(kPinPwrHold, OUTPUT);
    digitalWriteFast(kPinPwrHold, HIGH);

    pinMode(kPinBattEn, OUTPUT);
    digitalWriteFast(kPinBattEn, LOW);
    pinMode(kPinTxIn1, OUTPUT);
    pinMode(kPinTxIn2, OUTPUT);
    digitalWriteFast(kPinTxIn1, LOW);
    digitalWriteFast(kPinTxIn2, LOW);   // DRV8871 uykuda
    pinMode(kPinLed, OUTPUT);
    pinMode(kPinWake, INPUT);
    pinMode(kPinHarvestPg, INPUT);

    Serial.begin(115200);
    configure_adc();
    housekeeping();
    Serial.printf("dugum %u, pil %.2f V, uyanma=%d, hasat=%d\n", kNodeId, g_batt_v,
                  digitalReadFast(kPinWake), digitalReadFast(kPinHarvestPg));
}

void loop() {
    const uint32_t now = millis();
    take_buffers();

    uint8_t rx[kSwarmFrameSize], relay[kSwarmFrameSize];
    bool rx_activity = false;
    while (g_modem.pop_frame(rx)) {
        SwarmAcousticPacket pkt;
        bool should_relay = false;
        if (g_router.process_incoming(rx, &pkt, relay, &should_relay)) {
            rx_activity = true;
            Serial.printf("RX dugum %u sira %u hop %u IFF %u\n", pkt.src_node_id, pkt.seq_num,
                          pkt.hop_count, pkt.iff_class);
            if (should_relay && !g_pending) schedule_tx(relay, now);
        }
    }

    if (now - g_last_housekeeping >= kHousekeepingMs && !g_tx_busy) {
        g_last_housekeeping = now;
        housekeeping();
    }

    PowerInputs in;
    in.now_ms = now;
    in.wake_cmp = digitalReadFast(kPinWake);
    in.batt_v = g_batt_v;
    in.leak = g_leak;
    in.hostile = g_hostile_pending;
    in.rx_activity = rx_activity;
    g_hostile_pending = false;
    const PowerOutputs out = g_power.step(in);

    if (out.request_alert && !g_pending) send_alert(now);
    if (g_pending && !g_tx_busy && static_cast<int32_t>(now - g_pending_at_ms) >= 0) {
        g_pending = false;
        start_tx(g_pending_frame);
    }

    digitalWriteFast(kPinLed, out.led ? HIGH : LOW);
    // Yayin surerken gucu birakma
    bool hold = out.hold_power || g_tx_busy || g_pending;
#if defined(NODE_BENCH) && NODE_BENCH
    hold = true;
#endif
    digitalWriteFast(kPinPwrHold, hold ? HIGH : LOW);
}
