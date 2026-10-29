#include "swarm_mesh.h"

namespace pelagos {

uint16_t crc16_ccitt(const uint8_t* data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; ++i) {
        crc ^= static_cast<uint16_t>(data[i]) << 8;
        for (uint8_t b = 0; b < 8; ++b) {
            if (crc & 0x8000) {
                crc = static_cast<uint16_t>((crc << 1) ^ 0x1021);
            } else {
                crc = static_cast<uint16_t>(crc << 1);
            }
        }
    }
    return crc;
}

uint16_t compute_swarm_mac16(const uint8_t* payload, size_t len, uint32_t swarm_key) {
    uint32_t hash = 2166136261u ^ swarm_key;
    for (size_t i = 0; i < len; ++i) {
        hash ^= payload[i];
        hash *= 16777619u;
    }
    hash ^= (swarm_key >> 16);
    hash *= 16777619u;
    return static_cast<uint16_t>((hash >> 16) ^ (hash & 0xFFFFu));
}

void encode_swarm_frame(const SwarmAcousticPacket& pkt, uint32_t swarm_key,
                        uint8_t out_frame[kSwarmFrameSize]) {
    out_frame[0] = kSwarmSyncByte1;
    out_frame[1] = kSwarmSyncByte2;
    out_frame[2] = pkt.src_node_id;
    out_frame[3] = pkt.seq_num;
    out_frame[4] = pkt.hop_count;
    out_frame[5] = pkt.ttl;
    out_frame[6] = pkt.iff_class;
    out_frame[7] = pkt.blade_count;
    out_frame[8] = static_cast<uint8_t>(pkt.lofar_hz_q2 & 0xFF);
    out_frame[9] = static_cast<uint8_t>((pkt.lofar_hz_q2 >> 8) & 0xFF);
    out_frame[10] = pkt.snr_db_q2;
    out_frame[11] = pkt.soc_pct;

    // 16-bit anahtarli dogrulama etiketi (MAC): src_node_id, seq_num ve akustik veri uzerinden
    uint8_t mac_input[8] = {
        pkt.src_node_id, pkt.seq_num, pkt.iff_class, pkt.blade_count,
        out_frame[8], out_frame[9], pkt.snr_db_q2, pkt.soc_pct
    };
    uint16_t mac = compute_swarm_mac16(mac_input, sizeof(mac_input), swarm_key);
    out_frame[12] = static_cast<uint8_t>(mac & 0xFF);
    out_frame[13] = static_cast<uint8_t>((mac >> 8) & 0xFF);

    uint16_t crc = crc16_ccitt(out_frame, 14);
    out_frame[14] = static_cast<uint8_t>(crc & 0xFF);
    out_frame[15] = static_cast<uint8_t>((crc >> 8) & 0xFF);
}

bool decode_swarm_frame(const uint8_t frame[kSwarmFrameSize], uint32_t swarm_key,
                        SwarmAcousticPacket* out_pkt) {
    if (frame[0] != kSwarmSyncByte1 || frame[1] != kSwarmSyncByte2) {
        return false;
    }
    uint16_t rx_crc = static_cast<uint16_t>(frame[14]) |
                      (static_cast<uint16_t>(frame[15]) << 8);
    if (crc16_ccitt(frame, 14) != rx_crc) {
        return false;
    }

    uint8_t mac_input[8] = {
        frame[2], frame[3], frame[6], frame[7],
        frame[8], frame[9], frame[10], frame[11]
    };
    uint16_t expected_mac = compute_swarm_mac16(mac_input, sizeof(mac_input), swarm_key);
    uint16_t rx_mac = static_cast<uint16_t>(frame[12]) |
                      (static_cast<uint16_t>(frame[13]) << 8);
    if (expected_mac != rx_mac) {
        return false;
    }

    if (out_pkt) {
        out_pkt->src_node_id = frame[2];
        out_pkt->seq_num     = frame[3];
        out_pkt->hop_count   = frame[4];
        out_pkt->ttl         = frame[5];
        out_pkt->iff_class   = frame[6];
        out_pkt->blade_count = frame[7];
        out_pkt->lofar_hz_q2 = static_cast<uint16_t>(frame[8]) |
                               (static_cast<uint16_t>(frame[9]) << 8);
        out_pkt->snr_db_q2   = frame[10];
        out_pkt->soc_pct     = frame[11];
    }
    return true;
}

bool SwarmMeshRouter::is_duplicate(uint8_t src_id, uint8_t seq) const {
    uint16_t key = (static_cast<uint16_t>(src_id) << 8) | seq;
    for (size_t i = 0; i < kDedupRingSize; ++i) {
        if (seen_keys_[i] == key) {
            return true;
        }
    }
    return false;
}

void SwarmMeshRouter::record_seen(uint8_t src_id, uint8_t seq) {
    uint16_t key = (static_cast<uint16_t>(src_id) << 8) | seq;
    seen_keys_[dedup_head_] = key;
    dedup_head_ = (dedup_head_ + 1) % kDedupRingSize;
}

bool SwarmMeshRouter::process_incoming(const uint8_t rx_frame[kSwarmFrameSize],
                                       SwarmAcousticPacket* decoded_out,
                                       uint8_t relay_frame_out[kSwarmFrameSize],
                                       bool* should_relay) {
    if (should_relay) *should_relay = false;
    SwarmAcousticPacket pkt;
    if (!decode_swarm_frame(rx_frame, swarm_key_, &pkt)) {
        return false;
    }
    if (pkt.src_node_id == node_id_ || is_duplicate(pkt.src_node_id, pkt.seq_num)) {
        return false;
    }
    record_seen(pkt.src_node_id, pkt.seq_num);
    if (decoded_out) {
        *decoded_out = pkt;
    }
    if (pkt.ttl > 0 && relay_frame_out && should_relay) {
        SwarmAcousticPacket relay_pkt = pkt;
        relay_pkt.hop_count = static_cast<uint8_t>(pkt.hop_count + 1);
        relay_pkt.ttl       = static_cast<uint8_t>(pkt.ttl - 1);
        encode_swarm_frame(relay_pkt, swarm_key_, relay_frame_out);
        *should_relay = true;
    }
    return true;
}

}  // namespace pelagos
