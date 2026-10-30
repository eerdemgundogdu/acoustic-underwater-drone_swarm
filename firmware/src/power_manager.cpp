#include "power_manager.h"

namespace acoustic_node {

uint8_t PowerManager::soc_percent(float batt_v) const {
    // Li-ion dinlenme egrisinin kaba dogrusal yaklasimi (yuk altinda olculur)
    if (batt_v <= cfg_.batt_empty_v) return 0;
    if (batt_v >= cfg_.batt_full_v) return 100;
    const float r = (batt_v - cfg_.batt_empty_v) / (cfg_.batt_full_v - cfg_.batt_empty_v);
    return static_cast<uint8_t>(r * 100.0f + 0.5f);
}

PowerOutputs PowerManager::step(const PowerInputs& in) {
    PowerOutputs out;
    const uint32_t now = in.now_ms;

    // Pil ve sizinti her durumda once
    if (in.batt_v > 1.0f && in.batt_v < cfg_.batt_cutoff_v) {
        state_ = NODE_LOW_BATT;
    } else if (in.leak && state_ != NODE_LOW_BATT && state_ != NODE_FAULT_LEAK) {
        state_ = NODE_FAULT_LEAK;
        alerted_ = false;
    }

    switch (state_) {
        case NODE_BOOT:
            last_activity_ms_ = now;
            state_ = NODE_LISTEN;
            out.hold_power = true;
            break;

        case NODE_LISTEN:
            if (in.wake_cmp || in.hostile || in.rx_activity) {
                last_activity_ms_ = now;
            }
            if (in.hostile && (!alerted_ || now - last_alert_ms_ >= cfg_.alert_cooldown_ms)) {
                out.request_alert = true;
                last_alert_ms_ = now;
                alerted_ = true;
            }
            if (now - last_activity_ms_ >= cfg_.listen_window_ms) {
                state_ = NODE_SHUTDOWN;
                shutdown_ms_ = now;
                out.hold_power = false;
            } else {
                out.hold_power = true;
            }
            out.led = (now % 2000u) < 50u;
            break;

        case NODE_SHUTDOWN:
            out.hold_power = false;
            // Buck hala aciksa karsilastirici/RC mandal tutuyordur: yeniden dinle
            if (now - shutdown_ms_ >= cfg_.shutdown_grace_ms) {
                state_ = NODE_LISTEN;
                last_activity_ms_ = now;
                out.hold_power = true;
            }
            break;

        case NODE_FAULT_LEAK:
            out.hold_power = true;
            if (!alerted_ || now - last_alert_ms_ >= cfg_.leak_alert_ms) {
                out.request_alert = true;
                last_alert_ms_ = now;
                alerted_ = true;
            }
            out.led = (now % 500u) < 250u;
            break;

        case NODE_LOW_BATT:
            out.hold_power = false;
            break;
    }
    return out;
}

}  // namespace acoustic_node
