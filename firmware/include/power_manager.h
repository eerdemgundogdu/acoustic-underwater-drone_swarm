#ifndef ACOUSTIC_NODE_POWER_MANAGER_H
#define ACOUSTIC_NODE_POWER_MANAGER_H

#include <stdint.h>

namespace acoustic_node {

// Kartta Teensy'nin kendi beslemesi uyanma mandalina baglidir:
//   BUCK_EN = WAKE_CMP (pasif akustik karsilastirici) VEYA PWR_HOLD (Teensy pin 23)
// Uykuda yalnizca hep acik alan calisir (toplam pil akimi ~7 uA, bkz.
// dsp/node_model.py aon_budget). Teensy acilinca PWR_HOLD'u hemen yukseltir;
// dinleme penceresi bittiginde birakir ve buck kapanir.
enum NodeState : uint8_t {
    NODE_BOOT       = 0,
    NODE_LISTEN     = 1,   // AFE + DMA + LOFAR/DEMON + BFSK alici calisiyor
    NODE_SHUTDOWN   = 2,   // PWR_HOLD birakildi, buck'in dusmesi bekleniyor
    NODE_FAULT_LEAK = 3,   // Govde sizintisi: uyanik kal, periyodik alarm yayini
    NODE_LOW_BATT   = 4    // Pil kesme esiginin altinda: hemen kapan
};

struct PowerConfig {
    uint32_t listen_window_ms = 30000;   // Son aktiviteden sonra uyanik kalma suresi
    uint32_t alert_cooldown_ms = 10000;  // Ayni hedef icin tekrar alarm araligi
    uint32_t leak_alert_ms = 60000;      // Sizinti alarmi tekrar araligi
    uint32_t shutdown_grace_ms = 3000;   // PWR_HOLD birakildiktan sonra hala aciksa
    float batt_cutoff_v = 12.4f;         // 4S, 3.1 V/hucre
    float batt_empty_v = 12.0f;
    float batt_full_v = 16.8f;
};

struct PowerInputs {
    uint32_t now_ms = 0;
    bool wake_cmp = false;      // Pasif karsilastirici hala aktif mi
    float batt_v = 0.0f;
    bool leak = false;
    bool hostile = false;       // Bu dongude IFF_HOSTILE_TRACK karari
    bool rx_activity = false;   // Gecerli suru cercevesi alindi
};

struct PowerOutputs {
    bool hold_power = true;
    bool request_alert = false; // Hedef/sizinti alarm paketi yayinla
    bool led = false;
};

class PowerManager {
public:
    explicit PowerManager(const PowerConfig& cfg = PowerConfig()) : cfg_(cfg) {}

    PowerOutputs step(const PowerInputs& in);
    NodeState state() const { return state_; }
    uint8_t soc_percent(float batt_v) const;

private:
    PowerConfig cfg_;
    NodeState state_ = NODE_BOOT;
    uint32_t last_activity_ms_ = 0;
    uint32_t last_alert_ms_ = 0;
    bool alerted_ = false;
    uint32_t shutdown_ms_ = 0;
};

}  // namespace acoustic_node

#endif  // ACOUSTIC_NODE_POWER_MANAGER_H
