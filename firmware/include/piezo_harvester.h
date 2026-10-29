#ifndef ACOUSTIC_NODE_PIEZO_HARVESTER_H
#define ACOUSTIC_NODE_PIEZO_HARVESTER_H

#include <stdint.h>

namespace acoustic_node {

enum NodePowerState : uint8_t {
    STATE_DEEP_SLEEP_HARVEST = 0,  // < 15 uA uyku, piezo dalga/akinti enerji hasadi
    STATE_PASSIVE_LISTEN     = 1,  // Hidrofon AFE aktif, DMA ornekleme
    STATE_DSP_CLASSIFY       = 2,  // LOFAR + DEMON FFT ve IFF siniflandirma
    STATE_SWARM_TX_ALERT     = 3,  // TDMA akustik suru yayini ve kontaktor hazirligi
    STATE_FAULT_LOCKOUT      = 4   // Su sizintisi veya manyetik emniyet kilidi acik
};

struct HarvesterConfig {
    float cap_uf             = 47000.0f;  // Esdeger superkapasitor / Li-Ion tampon kapasitesi (uF)
    float v_min_sleep        = 12.5f;     // Bu gerilimin altinda zorunlu derin uyku (V)
    float v_wake_ready       = 16.5f;     // DSP + akustik yayin icin gereken minimum esik (V)
    float v_max_clamp        = 25.2f;     // Tam dolu bara / Zener-TVS siniri (V)
    float sleep_load_mw      = 0.15f;     // Derin uykuda toplam sukunet gucu (mW)
    float listen_load_mw     = 45.0f;     // Hidrofon AFE + DMA dinleme gucu (mW)
    float dsp_load_mw        = 180.0f;    // Cortex-M7 1024-pt FFT/DEMON gucu (mW)
    float acoustic_tx_mw     = 850.0f;    // Ultrasonik BFSK akustik modem yayin gucu (mW)
};

class PiezoHarvesterFSM {
public:
    explicit PiezoHarvesterFSM(const HarvesterConfig& cfg = HarvesterConfig())
        : cfg_(cfg),
          v_bus_(14.0f),
          state_(STATE_DEEP_SLEEP_HARVEST),
          harvested_mj_(0.0f) {}

    void set_bus_voltage(float v) { v_bus_ = v; }
    float bus_voltage() const { return v_bus_; }
    NodePowerState state() const { return state_; }
    float total_harvested_mj() const { return harvested_mj_; }

    uint8_t soc_percent() const;

    // dt_sec adiminda piezoelektrik dalga gucu (piezo_input_mw) ve durum gecislerini gunceller
    NodePowerState step(float dt_sec,
                        float piezo_input_mw,
                        bool acoustic_wake_trig,
                        bool hostile_confirmed,
                        bool mag_arm_closed,
                        bool hull_leak_detected);

private:
    HarvesterConfig cfg_;
    float v_bus_;
    NodePowerState state_;
    float harvested_mj_;
};

}  // namespace acoustic_node

#endif  // ACOUSTIC_NODE_PIEZO_HARVESTER_H
