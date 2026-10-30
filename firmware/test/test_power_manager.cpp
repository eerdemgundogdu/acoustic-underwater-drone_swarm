// PowerManager (uyanma mandali / PWR_HOLD durum makinesi) icin host testleri.

#include "minitest.h"
#include "power_manager.h"

using namespace acoustic_node;

namespace {

PowerInputs at(uint32_t t, float v = 15.0f)
{
    PowerInputs in;
    in.now_ms = t;
    in.batt_v = v;
    return in;
}

}  // namespace

TEST(boot_holds_power_and_listens)
{
    PowerManager pm;
    const PowerOutputs o = pm.step(at(0));
    CHECK(o.hold_power);
    CHECK_EQ(pm.state(), NODE_LISTEN);
}

TEST(listen_window_expires_then_releases_power)
{
    PowerManager pm;
    pm.step(at(0));
    CHECK(pm.step(at(29999)).hold_power);
    const PowerOutputs o = pm.step(at(30000));
    CHECK(!o.hold_power);
    CHECK_EQ(pm.state(), NODE_SHUTDOWN);
}

TEST(activity_extends_window)
{
    PowerManager pm;
    pm.step(at(0));
    PowerInputs in = at(20000);
    in.wake_cmp = true;
    pm.step(in);
    CHECK(pm.step(at(45000)).hold_power);
    CHECK(!pm.step(at(50000)).hold_power);
}

TEST(still_powered_after_release_returns_to_listen)
{
    // Karsilastirici hala aktifse RC mandal buck'i tutar; Teensy yeniden dinlemeli
    PowerManager pm;
    pm.step(at(0));
    pm.step(at(30000));
    CHECK(!pm.step(at(32000)).hold_power);
    CHECK(pm.step(at(33000)).hold_power);
    CHECK_EQ(pm.state(), NODE_LISTEN);
}

TEST(hostile_alert_rate_limited)
{
    PowerManager pm;
    pm.step(at(0));
    PowerInputs in = at(1000);
    in.hostile = true;
    CHECK(pm.step(in).request_alert);
    in.now_ms = 5000;
    CHECK(!pm.step(in).request_alert);
    in.now_ms = 11000;
    CHECK(pm.step(in).request_alert);
}

TEST(leak_enters_fault_and_alerts_periodically)
{
    PowerManager pm;
    pm.step(at(0));
    PowerInputs in = at(100);
    in.leak = true;
    PowerOutputs o = pm.step(in);
    CHECK_EQ(pm.state(), NODE_FAULT_LEAK);
    CHECK(o.hold_power);
    CHECK(o.request_alert);
    in.now_ms = 30000;
    CHECK(!pm.step(in).request_alert);
    in.now_ms = 60100;
    CHECK(pm.step(in).request_alert);
    // Pencere dolsa da sizintida uyanik kalir
    in.now_ms = 200000;
    CHECK(pm.step(in).hold_power);
}

TEST(low_battery_shuts_down)
{
    PowerManager pm;
    pm.step(at(0));
    const PowerOutputs o = pm.step(at(100, 12.1f));
    CHECK(!o.hold_power);
    CHECK_EQ(pm.state(), NODE_LOW_BATT);
}

TEST(soc_mapping)
{
    PowerManager pm;
    CHECK_EQ(pm.soc_percent(11.5f), 0);
    CHECK_EQ(pm.soc_percent(14.4f), 50);
    CHECK_EQ(pm.soc_percent(17.0f), 100);
}

TEST_MAIN()
