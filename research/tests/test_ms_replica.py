#!/usr/bin/env python3
"""Checks for research/ms_replica.py. Run: python research/tests/test_ms_replica.py"""

import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ms_replica as R  # noqa: E402

SPEC = R.Spec(symbol="TEST", digits=2, point=0.01, tick_size=0.01, tick_value=1.0, contract_size=100.0,
              vol_min=0.01, vol_step=0.01, vol_max=100.0, stops_level=0, swap_mode=0, swap_long=0.0,
              swap_short=0.0, swap_3day=3, currency_profit="USD")


def ea_swings_reference(h, l, n):
    """Literal port of the EA's GetSwings loop (series indexing) for one window ending at the last bar."""
    H, L = h[::-1], l[::-1]
    got = len(H)
    hs, ls = [], []
    for i in range(got - 1 - n, n - 1, -1):
        is_h = all(not (H[i] <= H[i + k] or H[i] < H[i - k]) for k in range(1, n + 1))
        is_l = all(not (L[i] >= L[i + k] or L[i] > L[i - k]) for k in range(1, n + 1))
        if is_h:
            hs.append(got - 1 - i)
        if is_l:
            ls.append(got - 1 - i)
    return hs, ls


def test_fractals_match_ea_loop():
    rng = np.random.default_rng(1)
    for n in (1, 2, 3):
        for _ in range(50):
            h = np.round(rng.normal(0, 1, 60).cumsum(), 1) + 100
            l = h - np.round(rng.uniform(0.1, 1.0, 60), 1)
            fh, fl = R.fractal_flags(h, l, n)
            ref_h, ref_l = ea_swings_reference(h, l, n)
            assert list(np.where(fh)[0]) == ref_h, (n, list(np.where(fh)[0]), ref_h)
            assert list(np.where(fl)[0]) == ref_l
    print("ok  swing detection matches the EA loop exactly (incl. equal highs/lows)")


def test_time_zones():
    # Summer: NY 12:00 EDT = 16:00 UTC -> London 17:00, Frankfurt 18:00, Tokyo 01:00 next day
    ny = datetime(2026, 7, 1, 12, 0)
    assert R.zone_time(ny, "LONDON") == datetime(2026, 7, 1, 17, 0)
    assert R.zone_time(ny, "FRANKFURT") == datetime(2026, 7, 1, 18, 0)
    assert R.zone_time(ny, "TOKYO") == datetime(2026, 7, 2, 1, 0)
    # Gap weeks: US already on summer time (8 Mar 2026), Europe not until 29 Mar 2026
    ny = datetime(2026, 3, 20, 12, 0)
    assert R.zone_time(ny, "LONDON") == datetime(2026, 3, 20, 16, 0)
    assert R.zone_time(ny, "FRANKFURT") == datetime(2026, 3, 20, 17, 0)
    # Winter: NY 12:00 EST = 17:00 UTC
    ny = datetime(2026, 12, 1, 12, 0)
    assert R.zone_time(ny, "LONDON") == datetime(2026, 12, 1, 17, 0)
    assert R.zone_time(ny, "TOKYO") == datetime(2026, 12, 2, 2, 0)
    print("ok  session time zones incl. the US/EU daylight-saving gap weeks")


def test_atr_is_simple_average():
    df = pd.DataFrame({"high": [11, 12, 13, 12, 14] * 4, "low": [9, 10, 11, 10, 12] * 4,
                       "close": [10, 11, 12, 11, 13] * 4})
    a = R.atr_sma(df, 14)
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    tr = [h[0] - l[0]] + [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, 20)]
    assert abs(a[13] - np.mean(tr[:14])) < 1e-12 and abs(a[19] - np.mean(tr[6:20])) < 1e-12
    print("ok  ATR = simple moving average of true range (MT5 iATR)")


def hourly(rows, start="2025-01-06 00:00"):
    t = pd.date_range(start, periods=len(rows), freq="1h")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=t)
    df["spread"] = 10.0                      # 10 points = 0.10
    return df


def test_known_scenario():
    """Hand-built 4H structure: downtrend, higher low, break of the last swing high (106.5),
    1H pullback into the zone, turn up -> exactly one long, stop under the pullback,
    target = the nearest earlier swing high at least 1R away (126.5, where sellers were)."""
    rows = []
    # earlier swing high at 126.5 (sellers' level above), then the downtrend, higher low and break
    path = [130, 128, 126, 124, 122, 120, 122, 124, 126, 124, 122, 120, 118, 116, 114, 112] + \
           [110, 108, 106, 104, 102, 100, 102, 104, 106, 104, 102, 101, 103, 105, 107]
    for p in path:                           # each 4H bar = 4 identical hourly bars
        rows += [[p, p + 0.5, p - 0.5, p + 0.3]] * 4
    rows += [[107.3, 107.4, 107.0, 107.2],   # pullback into the zone (level 106.5)
             [107.2, 107.4, 106.9, 107.0],   # lowest point 106.9
             [107.0, 108.2, 106.95, 108.0],  # closes above the previous hour's high -> trigger
             [108.0, 108.6, 107.9, 108.5]]   # entry at this bar's open (ask 108.10)
    for k in range(35):                      # rally up to the earlier swing high (target)
        p = 108.5 + 0.6 * (k + 1)
        rows += [[p - 0.6, p + 0.2, p - 0.7, p]]
    bars = hourly(rows)
    mkt = R.Market("TEST", "test", "NEW_YORK", 0, 1440, True)
    rep = R.Replica(bars, SPEC, mkt, R.Params(), deposit=100000.0)
    tr = rep.run("2025-01-01", "2025-12-31")
    assert len(tr) == 1, tr
    t = tr.iloc[0]
    assert t["side"] == "LONG" and abs(t["level"] - 106.5) < 1e-9, t
    assert abs(t["entry"] - 108.10) < 1e-9, t["entry"]
    assert t["sl"] < 106.9 and t["sl"] > 106.5, t["sl"]
    assert abs(t["tp"] - 126.5) < 1e-9, t["tp"]
    assert t["reason"] == "target" and t["R"] > 10, (t["reason"], t["R"])
    print(f"ok  known scenario: LONG level 106.50, entry {t['entry']:.2f}, stop {t['sl']:.2f}, "
          f"target {t['tp']:.2f}, result {t['R']:+.2f}R")


def test_random_walk_has_no_edge():
    """No-edge market: the rules should not find profits, and the mechanics must hold
    (stops lose about 1R, entries only in session, no overlapping trades)."""
    rng = np.random.default_rng(7)
    t = pd.date_range("2024-01-01", "2025-06-30", freq="5min")
    t = t[t.dayofweek < 5]
    ret = rng.normal(0, 0.6, len(t))
    close = 2000 + np.cumsum(ret)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.3, len(t)))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.3, len(t)))
    bars = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "spread": 20.0}, index=t)
    mkt = R.Market("TEST", "test", "NEW_YORK", 8 * 60, 17 * 60, False)
    rep = R.Replica(bars, SPEC, mkt, R.Params(), deposit=100000.0)
    tr = rep.run("2024-03-01", "2025-06-30")
    m = R.metrics(tr)
    assert m["trades"] > 30, m
    stops = tr[tr["reason"] == "stop"]["R"]
    assert stops.between(-1.25, -0.9).mean() > 0.9, stops.describe()
    et = pd.to_datetime(tr["entry_time"]) - pd.Timedelta(hours=7)
    assert ((et.dt.hour * 60 + et.dt.minute).between(8 * 60, 17 * 60 - 1)).all()
    assert (et.dt.dayofweek < 5).all()
    assert (pd.to_datetime(tr["entry_time"]).values[1:] >= pd.to_datetime(tr["exit_time"]).values[:-1]).all()
    assert m["expectancy_R"] < 0.15, m
    print(f"ok  random walk: {m['trades']} trades, expectancy {m['expectancy_R']:+.3f}R, PF {m['profit_factor']} "
          f"(no edge found, as it should be); events {rep.events}")


def test_small_account_policy():
    """EA v1.12 small-account mode on the hand-built scenario (stop ~1.31 price units, 100 units per lot):
    textbook 1% skips it on $100; the smallest lot (risk ~$1.31 = 1.3%) is taken with a 5% cap but not a
    1% cap; and at 1:1 leverage the margin check refuses it."""
    rows = []
    path = [130, 128, 126, 124, 122, 120, 122, 124, 126, 124, 122, 120, 118, 116, 114, 112] + \
           [110, 108, 106, 104, 102, 100, 102, 104, 106, 104, 102, 101, 103, 105, 107]
    for p in path:
        rows += [[p, p + 0.5, p - 0.5, p + 0.3]] * 4
    rows += [[107.3, 107.4, 107.0, 107.2], [107.2, 107.4, 106.9, 107.0],
             [107.0, 108.2, 106.95, 108.0], [108.0, 108.6, 107.9, 108.5]]
    for k in range(35):
        p = 108.5 + 0.6 * (k + 1)
        rows += [[p - 0.6, p + 0.2, p - 0.7, p]]
    bars = hourly(rows)
    mkt = R.Market("TEST", "test", "NEW_YORK", 0, 1440, True)

    def run(**kw):
        rep = R.Replica(bars, SPEC, mkt, R.Params(**kw), deposit=100.0)
        return rep.run("2025-01-01", "2025-12-31"), rep.events

    tr, ev = run()
    assert len(tr) == 0 and ev["skip_min_lot"] == 1, (tr, ev)
    tr, ev = run(min_lot_cap_pct=1.0)
    assert len(tr) == 0 and ev["skip_min_lot"] == 1, (tr, ev)
    tr, ev = run(min_lot_cap_pct=5.0)
    assert len(tr) == 1 and abs(tr.iloc[0]["lots"] - 0.01) < 1e-12, tr
    assert 1.0 < 100 * tr.iloc[0]["risk_money"] / 100.0 < 5.0, tr.iloc[0]["risk_money"]
    tr, ev = run(min_lot_cap_pct=5.0, leverage=1.0, max_margin_pct=50.0)
    assert len(tr) == 0 and ev["skip_margin"] == 1, (tr, ev)
    print("ok  small-account mode: skip at 1%, smallest lot at a 5% cap, margin check refuses at 1:1")


def test_friday_cutoff():
    """FTMO gap rule: with a 15:00 New York cutoff there are no Friday entries at or after 15:00 NY."""
    rng = np.random.default_rng(21)
    t = pd.date_range("2024-01-01", "2024-12-31", freq="5min")
    t = t[t.dayofweek < 5]
    close = 2000 + np.cumsum(rng.normal(0, 0.6, len(t)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    bars = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + 0.2,
                         "low": np.minimum(open_, close) - 0.2, "close": close, "spread": 20.0}, index=t)
    mkt = R.Market("TEST", "test", "NEW_YORK", 0, 24 * 60, False)
    tr = R.Replica(bars, SPEC, mkt, R.Params(friday_entry_cutoff_ny=15 * 60), deposit=100000.0).run(
        "2024-02-01", "2024-12-31")
    ny = pd.to_datetime(tr["entry_time"]) - pd.Timedelta(hours=7)
    late = (ny.dt.dayofweek == 4) & (ny.dt.hour >= 15)
    assert len(tr) > 20 and not late.any(), (len(tr), int(late.sum()))
    print(f"ok  Friday cutoff: {len(tr)} trades, none on Friday after 15:00 New York")


if __name__ == "__main__":
    test_fractals_match_ea_loop()
    test_time_zones()
    test_atr_is_simple_average()
    test_known_scenario()
    test_random_walk_has_no_edge()
    test_small_account_policy()
    test_friday_cutoff()
    print("\nAll checks passed.")
