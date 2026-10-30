#ifndef ACOUSTIC_NODE_CONFIG_H
#define ACOUSTIC_NODE_CONFIG_H

#include <stdint.h>

// acoustic-swarm-node Rev A pin atamalari (hardware/gen/design.py TEENSY_NETS ile ayni)
constexpr uint8_t kPinTxIn1     = 6;    // DRV8871 IN1, FlexPWM2.2A, BFSK tasiyici
constexpr uint8_t kPinTxIn2     = 9;    // DRV8871 IN2, FlexPWM2.2B (yarim kopru modunda LOW)
constexpr uint8_t kPinLed       = 13;   // Kart LED'i D13 + Teensy dahili LED
constexpr uint8_t kPinHarvestPg = 12;   // V_HARV var (10k uzerinden; R44 1M cekme)
constexpr uint8_t kPinWake      = 21;   // TLV7031 cikisi (10k uzerinden), uyanma nedeni
constexpr uint8_t kPinBattEn    = 22;   // HIGH = Q1/Q2 pil bolucusunu bagla
constexpr uint8_t kPinPwrHold   = 23;   // HIGH = buck'i acik tut (D6 uzerinden BUCK_EN)
constexpr uint8_t kPinLeakAdc   = 14;   // A0
constexpr uint8_t kPinBattAdc   = 15;   // A1
constexpr uint8_t kPinAdcLo     = 16;   // A2, AFE 20 dB
constexpr uint8_t kPinAdcHi     = 17;   // A3, AFE 40 dB

// Pil bolucu: 100k / 15k -> (100 + 15) / 15
constexpr float kBattDivRatio   = 115.0f / 15.0f;
// Sizinti: 10k cekme + 47k bolucu; kuru = 0 V, su ile ~1.2 V ustu
constexpr uint16_t kLeakThreshold = 1500;

#ifndef NODE_ID
#define NODE_ID 3
#endif
constexpr uint8_t kNodeId = NODE_ID;

// Suru anahtari: sahada her suru icin rastgele 16 bayt uretilip
// -D SWARM_KEY_BYTES=... ile derlenir. Asagidaki deger sadece tezgah testi icindir.
#ifndef SWARM_KEY_BYTES
#define SWARM_KEY_BYTES 0x6E, 0x6F, 0x64, 0x65, 0x2D, 0x62, 0x65, 0x6E, \
                        0x63, 0x68, 0x2D, 0x6B, 0x65, 0x79, 0x2D, 0x31
#endif

constexpr uint32_t kAdcRateHz      = 192000;
constexpr uint32_t kHousekeepingMs = 5000;   // Pil + sizinti olcumu araligi
constexpr uint8_t kAlertTtl        = 3;

#endif  // ACOUSTIC_NODE_CONFIG_H
