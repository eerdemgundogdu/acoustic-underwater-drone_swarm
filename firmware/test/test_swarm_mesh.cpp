// swarm_mesh (CRC-16, SipHash-2-4 etiketi, cerceve kodlama, cok atlamali yonlendirme)
// icin host testleri.

#include "minitest.h"
#include "swarm_mesh.h"

#include <cstring>

using namespace acoustic_node;

namespace {

const uint8_t kKey[kSwarmKeySize] = {0x10, 0x32, 0x54, 0x76, 0x98, 0xBA, 0xDC, 0xFE,
                                     0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF};

SwarmAcousticPacket sample(uint8_t src, uint8_t seq, uint8_t ttl)
{
    SwarmAcousticPacket p{};
    p.src_node_id = src;
    p.seq_num = seq;
    p.ttl = ttl;
    p.iff_class = 2;
    p.blade_count = 5;
    p.lofar_hz_q2 = static_cast<uint16_t>(145.25f * 4);
    p.snr_db_q2 = 4 * 18;
    p.soc_pct = 64;
    p.flags = kFlagHarvestOk;
    return p;
}

}  // namespace

TEST(crc16_ccitt_check_value)
{
    const uint8_t msg[] = {'1', '2', '3', '4', '5', '6', '7', '8', '9'};
    CHECK_EQ(crc16_ccitt(msg, sizeof(msg)), 0x29B1);
}

TEST(siphash24_reference_vectors)
{
    // Aumasson & Bernstein, SipHash makalesi Ek A: anahtar 00..0f
    uint8_t key[16], msg[64];
    for (int i = 0; i < 16; ++i) key[i] = static_cast<uint8_t>(i);
    for (int i = 0; i < 64; ++i) msg[i] = static_cast<uint8_t>(i);
    CHECK(siphash24(key, msg, 0) == 0x726fdb47dd0e0e31ULL);
    CHECK(siphash24(key, msg, 15) == 0xa129ca6149be45e5ULL);
}

TEST(encode_decode_roundtrip)
{
    uint8_t f[kSwarmFrameSize];
    encode_swarm_frame(sample(3, 42, 2), kKey, f);
    CHECK_EQ(f[0], 0xA5);
    CHECK_EQ(f[1], 0x5A);
    SwarmAcousticPacket out{};
    CHECK(decode_swarm_frame(f, kKey, &out));
    CHECK_EQ(out.src_node_id, 3);
    CHECK_EQ(out.seq_num, 42);
    CHECK_EQ(out.lofar_hz_q2, 581);
    CHECK_EQ(out.flags, kFlagHarvestOk);
}

TEST(any_single_bit_error_rejected)
{
    uint8_t f[kSwarmFrameSize];
    encode_swarm_frame(sample(3, 1, 1), kKey, f);
    int accepted = 0;
    for (size_t byte = 0; byte < kSwarmFrameSize; ++byte) {
        for (int bit = 0; bit < 8; ++bit) {
            uint8_t g[kSwarmFrameSize];
            std::memcpy(g, f, sizeof(g));
            g[byte] ^= static_cast<uint8_t>(1u << bit);
            accepted += decode_swarm_frame(g, kKey, nullptr) ? 1 : 0;
        }
    }
    CHECK_EQ(accepted, 0);
}

TEST(forgery_without_key_rejected)
{
    // Saldirgan yukte degisiklik yapip CRC'yi yeniden hesaplar ama anahtari bilmez
    uint8_t f[kSwarmFrameSize];
    encode_swarm_frame(sample(3, 1, 1), kKey, f);
    f[6] = 1;  // "hedef" -> "dost"
    const uint16_t crc = crc16_ccitt(f, 18);
    f[18] = static_cast<uint8_t>(crc & 0xFF);
    f[19] = static_cast<uint8_t>(crc >> 8);
    CHECK(!decode_swarm_frame(f, kKey, nullptr));

    // Yanlis anahtarla uretilmis cerceve de reddedilir
    uint8_t other[kSwarmKeySize] = {};
    encode_swarm_frame(sample(3, 1, 1), other, f);
    CHECK(!decode_swarm_frame(f, kKey, nullptr));
}

TEST(router_relays_with_ttl_and_dedups)
{
    SwarmMeshRouter r(7, kKey);
    uint8_t f[kSwarmFrameSize], relay[kSwarmFrameSize];
    encode_swarm_frame(sample(3, 50, 2), kKey, f);

    SwarmAcousticPacket got{};
    bool should_relay = false;
    CHECK(r.process_incoming(f, &got, relay, &should_relay));
    CHECK(should_relay);
    SwarmAcousticPacket rp{};
    CHECK(decode_swarm_frame(relay, kKey, &rp));
    CHECK_EQ(rp.hop_count, 1);
    CHECK_EQ(rp.ttl, 1);
    CHECK_EQ(rp.src_node_id, 3);

    // Ayni (kaynak, sira) tekrar gelirse: islenmez, tekrar yayinlanmaz
    CHECK(!r.process_incoming(f, &got, relay, &should_relay));
    CHECK(!should_relay);
    // Tekrar yayinlanmis kopya da (hop=1) ayni anahtarla elenir
    CHECK(!r.process_incoming(relay, &got, relay, &should_relay));
}

TEST(router_ttl_zero_not_relayed_and_own_ignored)
{
    SwarmMeshRouter r(7, kKey);
    uint8_t f[kSwarmFrameSize], relay[kSwarmFrameSize];
    bool should_relay = true;
    encode_swarm_frame(sample(3, 60, 0), kKey, f);
    CHECK(r.process_incoming(f, nullptr, relay, &should_relay));
    CHECK(!should_relay);

    encode_swarm_frame(sample(7, 61, 3), kKey, f);
    CHECK(!r.process_incoming(f, nullptr, relay, &should_relay));
}

TEST(tdma_slots_do_not_overlap_frame)
{
    // 176 bit @ 1 kbps = 176 ms < 250 ms yuva
    SwarmMeshRouter a(1, kKey), b(2, kKey);
    CHECK(b.tdma_backoff_ms() - a.tdma_backoff_ms() >= 176u + 50u);
}

TEST_MAIN()
