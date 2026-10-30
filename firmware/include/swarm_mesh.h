#ifndef ACOUSTIC_NODE_SWARM_MESH_H
#define ACOUSTIC_NODE_SWARM_MESH_H

#include <stddef.h>
#include <stdint.h>

namespace acoustic_node {

constexpr uint8_t kSwarmSyncByte1 = 0xA5;
constexpr uint8_t kSwarmSyncByte2 = 0x5A;
constexpr size_t kSwarmFrameSize  = 20;
constexpr size_t kSwarmKeySize    = 16;
constexpr size_t kDedupRingSize   = 16;

// flags alani
constexpr uint8_t kFlagHarvestOk  = 0x01;   // Piezo hasat cikisi (V_HARV) var
constexpr uint8_t kFlagLeak       = 0x02;   // Govde su sizintisi
constexpr uint8_t kFlagLowBatt    = 0x04;

// Cerceve (20 bayt, cok baytli alanlar little-endian):
//  0  0xA5   1  0x5A   2 src   3 seq   4 hop   5 ttl   6 iff   7 blades
//  8..9 lofar_hz_q2   10 snr_db_q2   11 soc_pct   12 flags   13 ayrilmis (0)
//  14..17 SipHash-2-4(anahtar, bayt 2..13) dusuk 32 bit
//  18..19 CRC-16-CCITT(bayt 0..17)
struct SwarmAcousticPacket {
    uint8_t src_node_id;      // Kaynak dugum kimligi (1..254)
    uint8_t seq_num;          // Paket sira numarasi
    uint8_t hop_count;        // Gecilen atlama (hop) sayisi
    uint8_t ttl;              // Kalan maksimum atlama (Time-To-Live)
    uint8_t iff_class;        // TargetIFF (0=Ortam, 1=Dost UUV, 2=Hedef iz, 3=Bilinmeyen)
    uint8_t blade_count;      // DEMON kestirilen kanat sayisi
    uint16_t lofar_hz_q2;     // LOFAR tepe frekansi (0.25 Hz cozunurluk)
    uint8_t snr_db_q2;        // LOFAR SNR (0.25 dB cozunurluk, 63.75 dB'de doyar)
    uint8_t soc_pct;          // Pil doluluk orani (%)
    uint8_t flags;            // kFlag*
};

// CRC-16-CCITT (polinom 0x1021, baslangic 0xFFFF). Kanal bit hatalarini yakalar.
uint16_t crc16_ccitt(const uint8_t* data, size_t len);

// SipHash-2-4 (Aumasson & Bernstein). 128 bit anahtarli PRF; kisa mesajlarda
// mesaj dogrulama etiketi olarak kullanilir. Anahtarsiz bir dugum gecerli
// etiket uretemez (CRC tek basina sahteciligi engellemez).
uint64_t siphash24(const uint8_t key[kSwarmKeySize], const uint8_t* data, size_t len);

void encode_swarm_frame(const SwarmAcousticPacket& pkt, const uint8_t key[kSwarmKeySize],
                        uint8_t out_frame[kSwarmFrameSize]);

// CRC ve etiket dogrulanirsa true doner
bool decode_swarm_frame(const uint8_t frame[kSwarmFrameSize], const uint8_t key[kSwarmKeySize],
                        SwarmAcousticPacket* out_pkt);

// Cok atlamali (multi-hop) TDMA akustik suru yonlendiricisi.
// Yinelenen paketleri (kaynak, sira) halka tamponu ile eler; TTL > 0 ise
// hop+1 / ttl-1 ile yeniden etiketleyip tekrar yayin cercevesi uretir.
class SwarmMeshRouter {
public:
    SwarmMeshRouter(uint8_t node_id, const uint8_t key[kSwarmKeySize],
                    uint16_t tdma_slot_ms = 250);

    bool process_incoming(const uint8_t rx_frame[kSwarmFrameSize],
                          SwarmAcousticPacket* decoded_out,
                          uint8_t relay_frame_out[kSwarmFrameSize],
                          bool* should_relay);

    // Kendi paketimizi kaydet (yankisi geri geldiginde tekrar yayinlanmasin)
    void note_own(uint8_t seq) { record_seen(node_id_, seq); }

    // Dugume ozel TDMA gecikmesi: 8 yuva, yuva >= cerceve suresi (176 ms) + yayilma payi
    uint32_t tdma_backoff_ms() const {
        return static_cast<uint32_t>(node_id_ % 8) * static_cast<uint32_t>(tdma_slot_ms_);
    }

    uint8_t node_id() const { return node_id_; }

private:
    bool is_duplicate(uint8_t src_id, uint8_t seq) const;
    void record_seen(uint8_t src_id, uint8_t seq);

    uint8_t node_id_;
    uint8_t key_[kSwarmKeySize];
    uint16_t tdma_slot_ms_;
    uint16_t seen_keys_[kDedupRingSize];
    size_t dedup_head_;
};

}  // namespace acoustic_node

#endif  // ACOUSTIC_NODE_SWARM_MESH_H
