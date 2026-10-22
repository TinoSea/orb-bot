"""Tests for the futures LK_Forward rule engine. Run: python -m pytest futures/tradovate/tests -q"""
import os
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from lk_core import (NY, Bar, Engine, Enter, Exit, Guard, Rules, days_back, find_zones,  # noqa: E402
                     ny_midnight, size)


def ts(y, mo, d, h, mi, s=0):
    return datetime(y, mo, d, h, mi, s, tzinfo=NY).timestamp()


def bar(t, sec, o, h, l, c):
    return Bar(t, sec, o, h, l, c)


# A Tuesday, with the previous Monday as the "earlier day" holding the zone.
TUE = date(2026, 10, 20)
MON_10 = ts(2026, 10, 19, 10, 0)


def supply_bars():
    """Three 5m bars on Monday forming a supply gap 100-110 (bar3 high 100 < bar1 low 110), then bars below it."""
    return [
        bar(MON_10, 300, 115, 120, 110, 112),
        bar(MON_10 + 300, 300, 112, 112, 101, 101),
        bar(MON_10 + 600, 300, 99, 100, 90, 92),
        bar(MON_10 + 900, 300, 92, 102, 88, 94),
    ]


def demand_bars():
    """Demand gap 100-110: bar3 low 110 > bar1 high 100."""
    return [
        bar(MON_10, 300, 95, 100, 90, 98),
        bar(MON_10 + 300, 300, 98, 109, 98, 109),
        bar(MON_10 + 600, 300, 111, 120, 110, 118),
        bar(MON_10 + 900, 300, 118, 122, 108, 116),
    ]


def provider(bars5, bars15=()):
    def f(tf, since):
        return [b for b in (bars5 if tf == "5m" else bars15) if b.t_open >= since]
    return f


def engine(bars5, rules=None):
    return Engine(rules or Rules(), provider(bars5), log=lambda m: None)


# ---------------------------------------------------------------- zones
def test_supply_and_demand_zones_found():
    since, today = ny_midnight(days_back(TUE, 5)), ny_midnight(TUE)
    z = find_zones(supply_bars(), "5m", since, today, 5.0)
    assert len(z) == 1 and z[0].supply and (z[0].lo, z[0].hi) == (100, 110)
    z = find_zones(demand_bars(), "5m", since, today, 5.0)
    assert len(z) == 1 and not z[0].supply and (z[0].lo, z[0].hi) == (100, 110)


def test_small_gap_ignored():
    b = supply_bars()
    b[2].high = 106          # gap 106-110 = 4 points < 5
    assert find_zones(b, "5m", 0, ny_midnight(TUE), 5.0) == []


def test_gap_closed_through_is_dead():
    b = supply_bars()
    b[3].close = 111         # a later close above the supply zone's top kills it
    assert find_zones(b, "5m", 0, ny_midnight(TUE), 5.0) == []


def test_today_gaps_excluded_and_old_gaps_excluded():
    b = supply_bars()
    # formed today (after Tuesday midnight) -> excluded
    shift = ny_midnight(TUE) + 3600 - MON_10
    later = [bar(x.t_open + shift, 300, x.open, x.high, x.low, x.close) for x in b]
    assert find_zones(later, "5m", 0, ny_midnight(TUE), 5.0) == []
    # formed before the lookback start -> excluded
    assert find_zones(b, "5m", ts(2026, 10, 19, 12, 0), ny_midnight(TUE), 5.0) == []


def test_days_back_skips_weekends():
    assert days_back(date(2026, 10, 20), 5) == date(2026, 10, 13)   # Tue -> previous Tue
    assert days_back(date(2026, 10, 19), 1) == date(2026, 10, 16)   # Mon -> Fri


# ---------------------------------------------------------------- signal and entry
def feed(e, start, prices, step=1.0, in_pos=False):
    out = []
    t = start
    for p in prices:
        out += [(t, a) for a in e.on_tick(t, p, in_pos)]
        t += step
    return out, t


def rejection_short(e, t0):
    """A 15-second candle (t0..t0+15) that wicks into the 100-110 supply zone and closes down:
    open 99, high 105, low 97, close 98 -> body 1, upper wick 6. Then the next candle starts."""
    prices = [99, 105, 97, 98] + [98] * 12       # 15 ticks one second apart, then the next candle's first tick
    return feed(e, t0, prices)


def test_short_signal_arms_and_fills():
    e = engine(supply_bars())
    t0 = ts(2026, 10, 20, 9, 0, 0)
    feed(e, t0 - 30, [96, 96])                     # starts the day before the candle
    acts, t = rejection_short(e, t0)
    assert acts == [] and e.arm_dir == -1
    assert e.arm_trig == pytest.approx(97 - 0.25)
    acts, t = feed(e, t, [97.0, 96.5])            # 96.5 <= 96.75 -> fill
    enters = [a for _, a in acts if isinstance(a, Enter)]
    assert len(enters) == 1 and enters[0].side == -1 and enters[0].zone.used


def test_trigger_expires_after_45_seconds():
    e = engine(supply_bars())
    t0 = ts(2026, 10, 20, 9, 0, 0)
    feed(e, t0 - 30, [96, 96])
    _, t = rejection_short(e, t0)
    acts, t = feed(e, t0 + 15 + 46, [97.5, 96.0])  # after expiry: price through the trigger, no fill
    assert not any(isinstance(a, Enter) for _, a in acts)


def test_first_try_only():
    e = engine(supply_bars())
    t0 = ts(2026, 10, 20, 9, 0, 0)
    feed(e, t0 - 30, [96])
    _, t = rejection_short(e, t0)
    acts, t = feed(e, t, [96.5])
    e.on_entry(t)
    e.on_exit(-25.0)
    acts, t = rejection_short(e, t0 + 60)
    acts2, _ = feed(e, t, [96.0])
    assert e.arm_dir == 0 and not any(isinstance(a, Enter) for _, a in acts + acts2)


def test_window_boundaries():
    # candle closing 07:59:45 is outside; 08:00:00 is inside; 14:00:00 is outside (window is [08:00, 14:00)
    for start, armed in ((ts(2026, 10, 20, 7, 59, 30), False), (ts(2026, 10, 20, 7, 59, 45), True),
                         (ts(2026, 10, 20, 13, 59, 30), True), (ts(2026, 10, 20, 13, 59, 45), False)):
        e = engine(supply_bars())
        feed(e, start - 30, [96])
        rejection_short(e, start)
        assert (e.arm_dir == -1) == armed, start


def test_old_window_still_available_as_input():
    r = Rules(sig_from="09:30", sig_to="09:57", flat="11:45")
    e = engine(supply_bars(), r)
    t0 = ts(2026, 10, 20, 9, 0, 0)
    feed(e, t0 - 30, [96])
    rejection_short(e, t0)
    assert e.arm_dir == 0


def test_no_fridays():
    fri = date(2026, 10, 23)
    shift = ny_midnight(fri) - ny_midnight(TUE)
    b = [bar(x.t_open + shift - 86400 * 3, 300, x.open, x.high, x.low, x.close) for x in supply_bars()]  # Tue zone
    e = engine(b)
    t0 = ts(2026, 10, 23, 9, 0, 0)
    feed(e, t0 - 30, [96])
    rejection_short(e, t0)
    assert e.arm_dir == 0
    e2 = engine(b, Rules(no_friday=False))
    feed(e2, t0 - 30, [96])
    rejection_short(e2, t0)
    assert e2.arm_dir == -1


def test_long_signal_on_demand_zone():
    e = engine(demand_bars())
    t0 = ts(2026, 10, 20, 9, 0, 0)
    feed(e, t0 - 30, [113])
    feed(e, t0, [111, 105, 113, 112] + [112] * 12)   # low 105 in zone, close 112 > open 111, lower wick 6 >= body 1
    assert e.arm_dir == 1 and e.arm_trig == pytest.approx(113.25)
    acts, _ = feed(e, t0 + 16, [113.5])
    assert any(isinstance(a, Enter) and a.side == 1 for _, a in acts)


def test_body_bigger_than_wick_is_not_a_signal():
    e = engine(supply_bars())
    t0 = ts(2026, 10, 20, 9, 0, 0)
    feed(e, t0 - 30, [96])
    feed(e, t0, [104, 105, 95, 96] + [96] * 12)       # body 8, upper wick 1
    assert e.arm_dir == 0


def test_zone_killed_by_5m_close_above():
    e = engine(supply_bars())
    t0 = ts(2026, 10, 20, 9, 0, 0)
    feed(e, t0 - 30, [96])
    assert len(e.zones) == 1
    feed(e, ts(2026, 10, 20, 9, 5, 0), [111])          # 5m bar 09:05-09:10 at 111
    feed(e, ts(2026, 10, 20, 9, 10, 0), [111])         # next bar starts -> 09:05 bar closed at 111 > 110
    assert e.zones == []


# ---------------------------------------------------------------- management
def test_time_cap_and_flat():
    e = engine(supply_bars())
    t = ts(2026, 10, 20, 9, 0, 0)
    e.on_tick(t, 96, False)
    e.on_entry(t)
    assert e.on_tick(t + 14 * 60, 96, True) == []
    a = e.on_tick(t + 15 * 60, 96, True)
    assert len(a) == 1 and isinstance(a[0], Exit) and a[0].reason == "cap"
    e.entry_time = None
    a = e.on_tick(ts(2026, 10, 20, 14, 30, 0), 96, True)
    assert a and a[0].reason == "flat"


def test_daily_limits():
    e = engine(supply_bars())
    t = ts(2026, 10, 20, 9, 0, 0)
    e.on_tick(t, 96, False)
    for _ in range(2):
        e.on_entry(t)
        e.on_exit(-30)
    feed(e, t + 30, [96])
    rejection_short(e, t + 45)
    assert e.arm_dir == 0                                # 2 losses -> done for the day


def test_flat_must_follow_window():
    with pytest.raises(ValueError):
        Rules(sig_to="14:00", flat="11:45").check()


# ---------------------------------------------------------------- sizing and guard
def test_size_micro_nasdaq():
    # MNQ: $2 per point; 12.5-point stop = $25 a contract; $100 risk -> 4 contracts
    assert size(100, 12.5, 2.0, 10, 25000) == 4
    assert size(100, 12.5, 2.0, 3, 25000) == 3            # contract cap
    assert size(100, 12.5, 20.0, 10, 25000) == 0          # NQ: $250 a contract > $100 risk -> skip


def test_guard_floor_trails_and_locks():
    g = Guard(start_balance=25000, mll=1000, eod_high=25000)
    assert g.floor() == 24000
    g.record_eod(25400)
    assert g.floor() == 24400
    g.record_eod(26500)
    assert g.floor() == 25000                             # locked at the start balance
    g2 = Guard(eod_high=25300, payout_taken=True)
    assert g2.floor() == 25000
    assert Guard(floor_override=24750).floor() == 24750


def test_guard_shrinks_size_near_floor():
    g = Guard(start_balance=25000, mll=1000, eod_high=25000, buffer=50)
    # balance 24150: room = 24150 - 24000 - 50 = 100 -> 4 contracts at $25
    assert size(100, 12.5, 2.0, 10, 24150, g) == 4
    # balance 24100: room 50 -> 2 contracts
    assert size(100, 12.5, 2.0, 10, 24100, g) == 2
    # balance 24060: room 10 -> none
    assert size(100, 12.5, 2.0, 10, 24060, g) == 0


# ---------------------------------------------------------------- random-walk invariants
def test_random_walk_invariants():
    """A week of random prices around many zones: the engine must respect its own limits."""
    import random
    from lk_core import hhmm, ny_minute
    rnd = random.Random(7)
    # zones: alternating supply/demand gaps around 100..200 on the previous Friday
    fri = ts(2026, 10, 16, 10, 0)
    b5, p = [], 150.0
    for i in range(300):
        o = p
        p += rnd.choice([-1, 1]) * rnd.uniform(0, 8)
        b5.append(bar(fri + 300 * i, 300, o, max(o, p) + rnd.uniform(0, 3), min(o, p) - rnd.uniform(0, 3), p))
    e = Engine(Rules(), provider(b5), log=lambda m: None)
    entries, in_pos, t = [], False, ts(2026, 10, 19, 0, 0)
    end = ts(2026, 10, 24, 0, 0)
    price = 150.0
    while t < end:
        price += rnd.choice([-0.25, 0, 0.25]) * rnd.randint(1, 4)
        for a in e.on_tick(t, price, in_pos):
            if isinstance(a, Enter):
                entries.append(a)
                e.on_entry(t)
                in_pos = True
            elif isinstance(a, Exit):
                e.on_exit(rnd.choice([-25.0, 32.5]))
                in_pos = False
        t += rnd.choice([0.5, 1, 2, 5])
    assert entries, "expected some trades in a random week"
    by_day = {}
    for a in entries:
        d = datetime.fromtimestamp(a.ts, NY).date()
        by_day[d] = by_day.get(d, 0) + 1
        assert d.weekday() < 4                                   # Mon-Thu only
        m = ny_minute(a.ts)
        assert hhmm("08:00") <= m <= hhmm("14:00")               # armed by a candle closing in the window (+45 s)
    assert max(by_day.values()) <= 3
