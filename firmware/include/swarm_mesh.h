#ifndef ACOUSTIC_NODE_SWARM_MESH_H
#define ACOUSTIC_NODE_SWARM_MESH_H

#include <stddef.h>
#include <stdint.h>

namespace acoustic_node {

constexpr uint8_t kSwarmSyncByte1 = 0xA5;
constexpr uint8_t kSwarmSyncByte2 = 0x5A;
constexpr size_t kSwarmFrameSize  = 16;
constexpr size_t kDedupRingSize   = 16;

struct SwarmAcousticPacket {
    uint8_t src_node_id;      // Kaynak dugum kimligi (1..254)
    uint8_t seq_num;          // Paket sira numarasi
    uint8_t hop_count;        // Gecilen atlama (hop) sayisi
    uint8_t ttl;              // Kalan maksimum atlama (Time-To-Live)
    uint8_t iff_class;        // TargetIFF (0=Ortam, 1=Dost UUV, 2=Dusman Iz)
    uint8_t blade_count;      // DEMON kestirilen kanat sayisi
    uint16_t lofar_hz_q2;     // LOFAR tepe frekansi (0.25 Hz cozunurluk)
    uint8_t snr_db_q2;        // LOFAR SNR (0.25 dB cozunurluk)
    uint8_t soc_pct;          // Piezo hasat / batarya doluluk orani (%)
};

// CRC-16-CCITT (polinom 0x1021, baslangic 0xFFFF)
uint16_t crc16_ccitt(const uint8_t* data, size_t len);

// Akustik sahteciligi (spoofing) onlemek icin 16-bit anahtarli FNV-1a MAC etiketi
uint16_t compute_swarm_mac16(const uint8_t* payload, size_t len, uint32_t swarm_key);

// 16 baytlik akustik BFSK cercevesini paketle
void encode_swarm_frame(const SwarmAcousticPacket& pkt, uint32_t swarm_key,
                        uint8_t out_frame[kSwarmFrameSize]);

// 16 baytlik cerceveyi coz; CRC-16 ve MAC-16 dogrulanirsa true doner
bool decode_swarm_frame(const uint8_t frame[kSwarmFrameSize], uint32_t swarm_key,
                        SwarmAcousticPacket* out_pkt);

// Cok atlamali (multi-hop) TDMA akustik suru yonlendiricisi
class SwarmMeshRouter {
public:
    explicit SwarmMeshRouter(uint8_t node_id, uint32_t swarm_key,
                             uint16_t tdma_slot_ms = 120)
        : node_id_(node_id),
          swarm_key_(swarm_key),
          tdma_slot_ms_(tdma_slot_ms),
          dedup_head_(0) {
        for (size_t i = 0; i < kDedupRingSize; ++i) {
            seen_keys_[i] = 0xFFFF;
        }
    }

    // Gelen cerceveyi dogrular; yeni ve TTL > 0 ise tekrar yayin (relay) cercevesi uretir
    bool process_incoming(const uint8_t rx_frame[kSwarmFrameSize],
                          SwarmAcousticPacket* decoded_out,
                          uint8_t relay_frame_out[kSwarmFrameSize],
                          bool* should_relay);

    // Cakisimsiz su alti akustik iletimi icin dugume ozel TDMA gecikmesi (ms)
    uint32_t tdma_backoff_ms() const {
        return static_cast<uint32_t>(node_id_ % 8) * static_cast<uint32_t>(tdma_slot_ms_);
    }

private:
    bool is_duplicate(uint8_t src_id, uint8_t seq) const;
    void record_seen(uint8_t src_id, uint8_t seq);

    uint8_t node_id_;
    uint32_t swarm_key_;
    uint16_t tdma_slot_ms_;
    uint16_t seen_keys_[kDedupRingSize];
    size_t dedup_head_;
};

}  // namespace acoustic_node

#endif  // ACOUSTIC_NODE_SWARM_MESH_H
