#include "piezo_harvester.h"

#include <math.h>

namespace pelagos {

uint8_t PiezoHarvesterFSM::soc_percent() const {
    if (v_bus_ <= cfg_.v_min_sleep) return 0;
    if (v_bus_ >= cfg_.v_max_clamp) return 100;
    float ratio = (v_bus_ - cfg_.v_min_sleep) / (cfg_.v_max_clamp - cfg_.v_min_sleep);
    return static_cast<uint8_t>(ratio * 100.0f + 0.5f);
}

NodePowerState PiezoHarvesterFSM::step(float dt_sec,
                                       float piezo_input_mw,
                                       bool acoustic_wake_trig,
                                       bool hostile_confirmed,
                                       bool mag_arm_closed,
                                       bool hull_leak_detected) {
    // 1. Donanimsal emniyet ve su sizintisi kontrolu
    if (hull_leak_detected || !mag_arm_closed) {
        state_ = STATE_FAULT_LOCKOUT;
    } else {
        switch (state_) {
            case STATE_FAULT_LOCKOUT:
                state_ = STATE_DEEP_SLEEP_HARVEST;
                break;
            case STATE_DEEP_SLEEP_HARVEST:
                if (v_bus_ >= cfg_.v_wake_ready && acoustic_wake_trig) {
                    state_ = STATE_PASSIVE_LISTEN;
                }
                break;
            case STATE_PASSIVE_LISTEN:
                if (v_bus_ < cfg_.v_min_sleep) {
                    state_ = STATE_DEEP_SLEEP_HARVEST;
                } else if (acoustic_wake_trig) {
                    state_ = STATE_DSP_CLASSIFY;
                } else {
                    state_ = STATE_DEEP_SLEEP_HARVEST;
                }
                break;
            case STATE_DSP_CLASSIFY:
                if (v_bus_ < cfg_.v_min_sleep) {
                    state_ = STATE_DEEP_SLEEP_HARVEST;
                } else if (hostile_confirmed) {
                    state_ = STATE_SWARM_TX_ALERT;
                } else {
                    state_ = STATE_DEEP_SLEEP_HARVEST;
                }
                break;
            case STATE_SWARM_TX_ALERT:
                state_ = STATE_DEEP_SLEEP_HARVEST;
                break;
        }
    }

    // 2. Enerji dengesi: dE = (P_harvest - P_load) * dt
    float load_mw = cfg_.sleep_load_mw;
    if (state_ == STATE_PASSIVE_LISTEN) {
        load_mw = cfg_.listen_load_mw;
    } else if (state_ == STATE_DSP_CLASSIFY) {
        load_mw = cfg_.dsp_load_mw;
    } else if (state_ == STATE_SWARM_TX_ALERT) {
        load_mw = cfg_.acoustic_tx_mw;
    }

    const float e_in_mj = (piezo_input_mw > 0.0f ? piezo_input_mw : 0.0f) * dt_sec;
    harvested_mj_ += e_in_mj;
    const float net_mj = (piezo_input_mw - load_mw) * dt_sec;

    // E = 0.5 * C * V^2  (C [F] = cap_uf * 1e-6, E [J] = E [mJ] * 1e-3)
    const float c_farad = cfg_.cap_uf * 1e-6f;
    float e_curr_j = 0.5f * c_farad * v_bus_ * v_bus_;
    float e_next_j = e_curr_j + net_mj * 1e-3f;
    if (e_next_j < 0.0f) e_next_j = 0.0f;

    v_bus_ = sqrtf(2.0f * e_next_j / c_farad);
    if (v_bus_ > cfg_.v_max_clamp) v_bus_ = cfg_.v_max_clamp;
    if (v_bus_ < cfg_.v_min_sleep && state_ != STATE_FAULT_LOCKOUT) {
        state_ = STATE_DEEP_SLEEP_HARVEST;
    }

    return state_;
}

}  // namespace pelagos
