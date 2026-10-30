#include "swarm_mesh.h"

#include <string.h>

namespace acoustic_node {

namespace {

constexpr size_t kTagFrom = 2;
constexpr size_t kTagLen = 12;   // bayt 2..13

uint64_t rotl(uint64_t x, int b) { return (x << b) | (x >> (64 - b)); }

uint64_t load_le64(const uint8_t* p) {
    uint64_t v = 0;
    for (int i = 7; i >= 0; --i) v = (v << 8) | p[i];
    return v;
}

void sip_round(uint64_t& v0, uint64_t& v1, uint64_t& v2, uint64_t& v3) {
    v0 += v1; v1 = rotl(v1, 13); v1 ^= v0; v0 = rotl(v0, 32);
    v2 += v3; v3 = rotl(v3, 16); v3 ^= v2;
    v0 += v3; v3 = rotl(v3, 21); v3 ^= v0;
    v2 += v1; v1 = rotl(v1, 17); v1 ^= v2; v2 = rotl(v2, 32);
}

uint32_t frame_tag(const uint8_t key[kSwarmKeySize], const uint8_t* frame) {
    return static_cast<uint32_t>(siphash24(key, frame + kTagFrom, kTagLen) & 0xFFFFFFFFu);
}

}  // namespace

uint16_t crc16_ccitt(const uint8_t* data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; ++i) {
        crc ^= static_cast<uint16_t>(data[i] << 8);
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

uint64_t siphash24(const uint8_t key[kSwarmKeySize], const uint8_t* data, size_t len) {
    const uint64_t k0 = load_le64(key);
    const uint64_t k1 = load_le64(key + 8);
    uint64_t v0 = 0x736f6d6570736575ULL ^ k0;
    uint64_t v1 = 0x646f72616e646f6dULL ^ k1;
    uint64_t v2 = 0x6c7967656e657261ULL ^ k0;
    uint64_t v3 = 0x7465646279746573ULL ^ k1;

    const size_t full = len - (len % 8);
    for (size_t i = 0; i < full; i += 8) {
        const uint64_t m = load_le64(data + i);
        v3 ^= m;
        sip_round(v0, v1, v2, v3);
        sip_round(v0, v1, v2, v3);
        v0 ^= m;
    }
    uint64_t b = static_cast<uint64_t>(len & 0xFF) << 56;
    for (size_t i = 0; i < len % 8; ++i) {
        b |= static_cast<uint64_t>(data[full + i]) << (8 * i);
    }
    v3 ^= b;
    sip_round(v0, v1, v2, v3);
    sip_round(v0, v1, v2, v3);
    v0 ^= b;
    v2 ^= 0xFF;
    for (int i = 0; i < 4; ++i) sip_round(v0, v1, v2, v3);
    return v0 ^ v1 ^ v2 ^ v3;
}

void encode_swarm_frame(const SwarmAcousticPacket& pkt, const uint8_t key[kSwarmKeySize],
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
    out_frame[12] = pkt.flags;
    out_frame[13] = 0;

    const uint32_t tag = frame_tag(key, out_frame);
    for (size_t i = 0; i < 4; ++i) {
        out_frame[14 + i] = static_cast<uint8_t>((tag >> (8 * i)) & 0xFF);
    }
    const uint16_t crc = crc16_ccitt(out_frame, 18);
    out_frame[18] = static_cast<uint8_t>(crc & 0xFF);
    out_frame[19] = static_cast<uint8_t>((crc >> 8) & 0xFF);
}

bool decode_swarm_frame(const uint8_t frame[kSwarmFrameSize], const uint8_t key[kSwarmKeySize],
                        SwarmAcousticPacket* out_pkt) {
    if (frame[0] != kSwarmSyncByte1 || frame[1] != kSwarmSyncByte2) {
        return false;
    }
    const uint16_t rx_crc = static_cast<uint16_t>(frame[18] | (frame[19] << 8));
    if (crc16_ccitt(frame, 18) != rx_crc) {
        return false;
    }
    uint32_t rx_tag = 0;
    for (size_t i = 0; i < 4; ++i) {
        rx_tag |= static_cast<uint32_t>(frame[14 + i]) << (8 * i);
    }
    if (frame_tag(key, frame) != rx_tag) {
        return false;
    }

    if (out_pkt) {
        out_pkt->src_node_id = frame[2];
        out_pkt->seq_num     = frame[3];
        out_pkt->hop_count   = frame[4];
        out_pkt->ttl         = frame[5];
        out_pkt->iff_class   = frame[6];
        out_pkt->blade_count = frame[7];
        out_pkt->lofar_hz_q2 = static_cast<uint16_t>(frame[8] | (frame[9] << 8));
        out_pkt->snr_db_q2   = frame[10];
        out_pkt->soc_pct     = frame[11];
        out_pkt->flags       = frame[12];
    }
    return true;
}

SwarmMeshRouter::SwarmMeshRouter(uint8_t node_id, const uint8_t key[kSwarmKeySize],
                                 uint16_t tdma_slot_ms)
    : node_id_(node_id), tdma_slot_ms_(tdma_slot_ms), dedup_head_(0) {
    memcpy(key_, key, kSwarmKeySize);
    for (size_t i = 0; i < kDedupRingSize; ++i) {
        seen_keys_[i] = 0xFFFF;
    }
}

bool SwarmMeshRouter::is_duplicate(uint8_t src_id, uint8_t seq) const {
    const uint16_t key = static_cast<uint16_t>((src_id << 8) | seq);
    for (size_t i = 0; i < kDedupRingSize; ++i) {
        if (seen_keys_[i] == key) {
            return true;
        }
    }
    return false;
}

void SwarmMeshRouter::record_seen(uint8_t src_id, uint8_t seq) {
    seen_keys_[dedup_head_] = static_cast<uint16_t>((src_id << 8) | seq);
    dedup_head_ = (dedup_head_ + 1) % kDedupRingSize;
}

bool SwarmMeshRouter::process_incoming(const uint8_t rx_frame[kSwarmFrameSize],
                                       SwarmAcousticPacket* decoded_out,
                                       uint8_t relay_frame_out[kSwarmFrameSize],
                                       bool* should_relay) {
    if (should_relay) *should_relay = false;
    SwarmAcousticPacket pkt;
    if (!decode_swarm_frame(rx_frame, key_, &pkt)) {
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
        encode_swarm_frame(relay_pkt, key_, relay_frame_out);
        *should_relay = true;
    }
    return true;
}

}  // namespace acoustic_node
