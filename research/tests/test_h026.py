"""Checks for research/h026.py on data where the right answer is known.

  python3 research/tests/test_h026.py          # or: pytest research/tests/test_h026.py

1. Unit checks: UTC session assignment across the US clock change, gap detection and death, the outcome race.
2. Null market (no edge at any level): the study must say NOT SUPPORTED.
3. Planted market (price is pushed back after touching an Asia/London extreme): the study must say SUPPORTED.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import h026  # noqa: E402


def minute_grid(start, end, price=100.0):
    idx = pd.date_range(start, end, freq='1min', inclusive='left')
    return pd.DataFrame({'open': price, 'high': price + 1, 'low': price - 1, 'close': price}, index=idx)


# ---------------------------------------------------------------- unit checks
def test_sessions_utc_summer_and_winter():
    # Summer (EDT, UTC-4): Asia 23:00-07:00 UTC = 19:00-03:00 NY; London 07:00-13:00 UTC = 03:00-09:00 NY.
    m = minute_grid('2025-07-07 17:00', '2025-07-08 12:00')
    m.loc['2025-07-07 18:59', 'high'] = 500      # 22:59 UTC: before Asia
    m.loc['2025-07-07 19:00', 'high'] = 300      # 23:00 UTC: first Asia minute
    m.loc['2025-07-08 03:00', 'high'] = 400      # 07:00 UTC: London, not Asia
    m.loc['2025-07-08 09:00', 'low'] = 1         # 13:00 UTC: after London
    lv = h026.session_levels(m, h026.SESSION_DEFS['utc']).loc[pd.Timestamp('2025-07-08')]
    assert lv.asia_high == 300 and lv.london_high == 400 and lv.london_low == 99
    # Winter (EST, UTC-5): 23:00 UTC = 18:00 NY; 07:00 UTC = 02:00 NY.
    w = minute_grid('2025-12-08 17:00', '2025-12-09 12:00')
    w.loc['2025-12-08 18:00', 'high'] = 300      # 23:00 UTC: Asia
    w.loc['2025-12-09 02:00', 'high'] = 400      # 07:00 UTC: London
    w.loc['2025-12-09 08:00', 'high'] = 700      # 13:00 UTC: after London
    lv = h026.session_levels(w, h026.SESSION_DEFS['utc']).loc[pd.Timestamp('2025-12-09')]
    assert lv.asia_high == 300 and lv.london_high == 400


def test_gap_found_and_killed():
    m = minute_grid('2025-07-08 09:00', '2025-07-08 10:00', 100.0)
    m.loc['2025-07-08 09:00':'2025-07-08 09:04', ['high', 'low', 'close']] = [100, 95, 96]   # candle 1
    m.loc['2025-07-08 09:05':'2025-07-08 09:09', ['high', 'low', 'close']] = [96, 84, 85]    # candle 2 (drop)
    m.loc['2025-07-08 09:10':'2025-07-08 09:14', ['high', 'low', 'close']] = [89, 84, 86]    # candle 3: high 89 < 95
    m.loc['2025-07-08 09:15':'2025-07-08 09:19', ['high', 'low', 'close']] = [92, 86, 90]    # inside the gap
    m.loc['2025-07-08 09:20':'2025-07-08 09:24', ['high', 'low', 'close']] = [97, 90, 96]    # closes above 95: dead
    m['open'] = m.close
    g = h026.gaps(m.loc[:'2025-07-08 09:24'], '5min')
    sup = g[g.supply & (g.lo == 89) & (g.hi == 95)]
    assert len(sup) == 1 and sup.dead.iloc[0] == pd.Timestamp('2025-07-08 09:25')


def fake_days(H, L, C, X=10.0):
    d = h026.Days.__new__(h026.Days)
    n = h026.N_GRID
    pad = lambda a: np.concatenate([a, np.full(n - len(a), a[-1])])
    d.H, d.L, d.C = np.array([pad(H)]), np.array([pad(L)]), np.array([pad(C)])
    d.A = np.full((1, n), X)
    return d


def test_outcome_race():
    # Level 110 above; touched at minute 3; then falls to 99 (= level - X) at minute 6: reversal.
    C = np.array([100, 104, 108, 109, 105, 102, 99.5, 98, 98, 98], float)
    H, L = C + 1, C - 1
    d = fake_days(H, L, C)
    ev = h026.evaluate(d, 0, 110.0, +1)
    assert ev['touch_min'] == 3 and ev['outcome'] == 'rev'
    # Same, but price runs to 120 (= level + X) first: continuation.
    C2 = np.array([100, 104, 108, 109, 113, 117, 120, 99, 98, 98], float)
    ev2 = h026.evaluate(fake_days(C2 + 1, C2 - 1, C2), 0, 110.0, +1)
    assert ev2['outcome'] == 'cont'
    # Untouched level: no event.
    assert h026.evaluate(d, 0, 200.0, +1) is None


# ---------------------------------------------------------------- synthetic markets
def synth(n_days=220, edge=0.0, seed=1, start='2025-07-07'):
    """1-minute bars, 18:00 (prior evening) to 16:59 New York each weekday. With edge > 0, after the New York window
    first touches a live Asia/London high (low), price drifts down (up) by `edge` points a minute for 30 minutes."""
    rng = np.random.default_rng(seed)
    price, frames = 20000.0, []
    for D in pd.bdate_range(start, periods=n_days):
        idx = pd.date_range(D - pd.Timedelta(hours=6), D + pd.Timedelta(hours=17), freq='1min', inclusive='left')
        mins = (idx - D).total_seconds() // 60
        sig = np.where((mins >= 570) & (mins < 690), 5.0, np.where(mins >= 570, 3.5, 2.0))
        n_pre = int((mins < 570).sum())
        o = np.empty(len(idx)); c = np.empty(len(idx))
        steps = sig[:n_pre] * rng.standard_normal(n_pre)
        c[:n_pre] = price + np.cumsum(steps)
        o[:n_pre] = np.concatenate([[price], c[:n_pre - 1]])
        wick = np.abs(rng.standard_normal((2, len(idx)))) * sig * 0.6
        pre = pd.DataFrame({'open': o[:n_pre], 'high': np.maximum(o[:n_pre], c[:n_pre]) + wick[0, :n_pre],
                            'low': np.minimum(o[:n_pre], c[:n_pre]) - wick[1, :n_pre], 'close': c[:n_pre]}, index=idx[:n_pre])
        lv = h026.session_levels(pre, h026.SESSION_DEFS['utc'])
        live = []
        if D in lv.index:
            op = c[n_pre - 1]
            for n in h026.EXTREMES:
                p = lv.at[D, n]
                if n.endswith('high') and p > op:
                    live.append([p, 1])
                elif n.endswith('low') and p < op:
                    live.append([p, -1])
        drift, left, last = 0.0, 0, c[n_pre - 1]
        for k in range(n_pre, len(idx)):
            o[k] = last
            c[k] = o[k] + (drift if left > 0 else 0.0) + sig[k] * rng.standard_normal()
            hi, lo = max(o[k], c[k]) + wick[0, k], min(o[k], c[k]) - wick[1, k]
            left -= 1
            if edge > 0 and mins[k] < 720:
                for lvl in live:
                    if lvl[1] and ((lvl[1] == 1 and hi >= lvl[0]) or (lvl[1] == -1 and lo <= lvl[0])):
                        drift, left, lvl[1] = -lvl[1] * edge, 30, 0
            frames.append((idx[k], o[k], hi, lo, c[k]))
            last = c[k]
        frames.extend(zip(pre.index, pre.open, pre.high, pre.low, pre.close))
        price = last
    m = pd.DataFrame(frames, columns=['t', 'open', 'high', 'low', 'close']).set_index('t').sort_index()
    return m


def test_null_market_not_supported():
    m = synth(edge=0.0, seed=3)
    r, _ = h026.study(m, '2025-07-07', '2026-12-31', n_rep=300, secondary=False)
    p = r['primary']
    print('null:', {k: p[k] for k in ('touches', 'reversal_rate', 'placebo_mean', 'percentile_vs_placebo', 'edge_pp')})
    assert p['touches'] >= 150
    assert r['verdict'] == 'NOT SUPPORTED'
    assert abs(p['edge_pp']) < 5


def test_planted_market_supported():
    m = synth(edge=1.0, seed=4)
    r, _ = h026.study(m, '2025-07-07', '2026-12-31', n_rep=300, secondary=False)
    p = r['primary']
    print('planted:', {k: p[k] for k in ('touches', 'reversal_rate', 'placebo_mean', 'percentile_vs_placebo', 'edge_pp')})
    assert r['verdict'] == 'SUPPORTED' and p['edge_pp'] > 10


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok', name)
