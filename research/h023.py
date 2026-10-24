"""H-023: ICT 2022 model at the New York open (research/hypotheses.md, H-023).

  python3 h023.py dev   <US100_M1.csv>             # 2025-07-01..2026-03-31, seen once
  python3 h023.py final <US100_M1_2022_2025.csv>   # ONCE, 2023-01-01..2025-06-30, only if dev futures expectancy > 0
  python3 h023.py day   <csv> 2025-10-23           # trace one day for hand-checking

Overnight range 00:00-09:29 -> first sweep 09:30-10:59 -> 5-minute MSS -> 5-minute FVG in the shift leg ->
limit at the gap's near edge -> stop beyond the sweep extreme, target the other end of the range (skip if < 2R), flat 11:59.
US100 1-minute bars from mt5/ExportData.mq5 (server = NY + 7 h). New York time throughout.
"""
import sys, os, json
from collections import Counter
import numpy as np, pandas as pd
from h020 import load_m1, stats, null_direction, COST, CFD_COST

DEV = ('2025-07-01', '2026-03-31')
FINAL = ('2023-01-01', '2025-06-30')
OUT = 'results/h023'
TICK, MIN_STOP, MIN_RR, FVG_MIN = 0.25, 5.0, 2.0, 5.0
OPEN, SWEEP_LAST, ORDER_LAST, FLAT = 570, 659, 659, 719      # minutes after NY midnight (bar opens)
MSS_LAST_SLOT = 131                                          # 5-minute slot 10:55-10:59, closes 11:00
NEED = (560, 575)                                            # every 1-minute bar 09:20-09:35 must exist
RANGE_MIN_BARS = 400


class Day:
    """One day's 1-minute bars 00:00-11:59 on a minute grid (NaN where a bar is missing) and 5-minute bars."""
    def __init__(self, g):
        mins = ((g.index - g.index[0].normalize()).total_seconds() // 60).astype(int).to_numpy()
        keep = mins <= FLAT
        mins = mins[keep]
        self.have = np.zeros(FLAT + 1, bool); self.have[mins] = True
        self.o, self.h, self.l, self.c = (np.full(FLAT + 1, np.nan) for _ in range(4))
        for arr, col in ((self.o, 'open'), (self.h, 'high'), (self.l, 'low'), (self.c, 'close')):
            arr[mins] = g[col].to_numpy(float)[keep]
        n5 = (FLAT + 1) // 5
        H = self.h.reshape(n5, 5); L = self.l.reshape(n5, 5); C = self.c.reshape(n5, 5)
        with np.errstate(all='ignore'):
            self.h5, self.l5 = np.nanmax(H, 1), np.nanmin(L, 1)
        self.c5 = np.array([r[~np.isnan(r)][-1] if (~np.isnan(r)).any() else np.nan for r in C])


def swing_ref(D, ext_slot, d):
    """Most recent 5-minute swing low (d<0) / high (d>0), N=1, whose right neighbour is at or before ext_slot."""
    for j in range(ext_slot - 1, 0, -1):
        if d < 0:
            a, b, x = D.l5[j - 1], D.l5[j + 1], D.l5[j]
            if x < a and x < b: return x
        else:
            a, b, x = D.h5[j - 1], D.h5[j + 1], D.h5[j]
            if x > a and x > b: return x
    return None


def run_day(D, prev, trace=False):
    """Returns (trade dict or None, reason)."""
    if not D.have[NEED[0]:NEED[1] + 1].all() or D.have[:OPEN].sum() < RANGE_MIN_BARS:
        return None, 'data'
    RH, RL = np.nanmax(D.h[:OPEN]), np.nanmin(D.l[:OPEN])
    if trace: print(f'range {RL:.2f} - {RH:.2f} ({RH - RL:.1f} pts)')
    d = ks = None
    for k in range(OPEN, SWEEP_LAST + 1):
        if not D.have[k]: continue
        up, dn = D.h[k] > RH, D.l[k] < RL
        if up and dn: return None, 'both_sides'
        if up or dn:
            d, ks = (-1 if up else 1), k; break
    if d is None: return None, 'no_sweep'
    if trace: print('sweep', 'high' if d < 0 else 'low', 'at', f'{ks // 60:02d}:{ks % 60:02d}')
    # walk forward: track the extreme, test MSS at each 5-minute close
    ext, ext_k, mss = (D.h[ks] if d < 0 else D.l[ks]), ks, None
    for k in range(ks, MSS_LAST_SLOT * 5 + 5):
        if D.have[k] and ((D.h[k] >= ext) if d < 0 else (D.l[k] <= ext)):
            ext, ext_k = (D.h[k] if d < 0 else D.l[k]), k
        if k % 5 == 4:
            s, es = k // 5, ext_k // 5
            ref = swing_ref(D, es, d)
            c5 = D.c5[s]
            if ref is not None and not np.isnan(c5) and ((c5 < ref) if d < 0 else (c5 > ref)):
                mss = s; break
    if mss is None: return None, 'no_mss'
    es = ext_k // 5
    gap = None
    for j in range(mss, es + 1, -1):                       # latest gap with first candle >= es, third <= mss
        if j - 2 < es: break
        if d < 0 and D.l5[j - 2] - D.h5[j] >= FVG_MIN: gap = (D.h5[j], D.l5[j - 2], j); break
        if d > 0 and D.l5[j] - D.h5[j - 2] >= FVG_MIN: gap = (D.h5[j - 2], D.l5[j], j); break
    if trace: print('MSS slot close', f'{(mss * 5 + 5) // 60:02d}:{(mss * 5 + 5) % 60:02d}', 'extreme', ext, 'gap', gap)
    if gap is None: return None, 'no_gap'
    e = gap[0] if d < 0 else gap[1]                         # near edge
    stop = ext + d * -TICK
    if d * (e - stop) < MIN_STOP: stop = e - d * MIN_STOP
    risk = d * (e - stop)
    tgt = RL if d < 0 else RH
    tgtR = d * (tgt - e) / risk
    if tgtR < MIN_RR: return None, 'under_2R'
    fk = None
    for k in range(mss * 5 + 5, ORDER_LAST + 1):
        if not D.have[k]: continue
        if (D.h[k] >= e + TICK) if d < 0 else (D.l[k] <= e - TICK):
            fk = k; break
        if (D.l[k] <= tgt) if d < 0 else (D.h[k] >= tgt):
            return None, 'no_fill'
    if fk is None: return None, 'no_fill'
    tr = dict(day=None, dir=d, range_hi=RH, range_lo=RL, sweep_t=ks, ext=ext, mss_close=mss * 5 + 5,
              gap_lo=gap[0], gap_hi=gap[1], fill_t=fk, fill=e, stop=stop, tgt=tgt, risk=risk, tgt_R=tgtR)
    tr.update(manage(D, fk, d, e, stop, tgt))
    tr['R_2R'] = manage(D, fk, d, e, stop, e + d * 2 * risk)['R']
    tr['R_3R'] = manage(D, fk, d, e, stop, e + d * 3 * risk)['R']
    tr['R_flip'] = manage(D, fk, -d, e, e + d * risk, e - d * tgtR * risk)['R']
    if prev is not None:
        tr['bias_ok'] = bool(d == (1 if prev[0] > prev[1] else -1))
    if trace: print(json.dumps(tr, indent=1, default=str))
    return tr, 'trade'


def manage(D, fk, d, e, stop, tgt):
    risk = d * (e - stop)
    if (D.h[fk] >= stop) if d < 0 else (D.l[fk] <= stop):     # fill bar also reaches the stop
        return dict(exit=stop, how='stop', R=-1.0, exit_t=fk)
    last = fk
    for k in range(fk + 1, FLAT + 1):
        if not D.have[k]: continue
        last = k
        if (D.h[k] >= stop) if d < 0 else (D.l[k] <= stop):
            x = max(stop, D.o[k]) if d < 0 else min(stop, D.o[k])
            return dict(exit=x, how='stop', R=d * (x - e) / risk, exit_t=k)
        if (D.l[k] <= tgt) if d < 0 else (D.h[k] >= tgt):
            return dict(exit=tgt, how='target', R=d * (tgt - e) / risk, exit_t=k)
    return dict(exit=D.c[last], how='time', R=d * (D.c[last] - e) / risk, exit_t=last)


def days_of(m1, a, b):
    out = {}
    for day, g in m1.groupby(m1.index.normalize()):
        if day.weekday() < 5 and pd.Timestamp(a) - pd.Timedelta(days=7) <= day <= pd.Timestamp(b):
            out[day] = g
    return out


def prev_bias(g):
    """Previous NYSE day's 15:59 close and 09:30-15:59 midpoint, or None."""
    m = g.between_time('09:30', '15:59')
    if len(m) < 300: return None
    return float(m.close.iloc[-1]), float((m.high.max() + m.low.min()) / 2)


def run(m1, a, b):
    G = days_of(m1, a, b)
    keys = sorted(G)
    out, why, used, prev = [], Counter(), 0, None
    for day in keys:
        g = G[day]
        if pd.Timestamp(a) <= day <= pd.Timestamp(b):
            tr, r = run_day(Day(g.loc[:day + pd.Timedelta(minutes=FLAT)]), prev)
            why[r] += 1
            if r != 'data': used += 1
            if tr:
                tr['day'] = str(day.date()); out.append(tr)
        prev = prev_bias(g) or prev
    return pd.DataFrame(out), used, why


def stress(tr):
    """Stops 0.25 worse (only trades that ended at the stop), costs doubled."""
    t = tr.copy()
    t['R'] = np.where(t.how == 'stop', t.R - TICK / t.risk, t.R)
    return stats(t, cost=2 * COST)


def report(tr, used, why, a, b):
    s = stats(tr)
    s.update(days_with_data=used, period=[a, b], setups={k: int(v) for k, v in why.items()})
    if not s['trades']: return s
    s['exits'] = {k: int(v) for k, v in tr.how.value_counts().items()}
    s['median_target_R'] = round(float(tr.tgt_R.median()), 2)
    s['stress'] = stress(tr)
    nl = null_direction(tr)
    s.update(null_mean=round(float(nl.mean()), 3), null_p95=round(float(np.percentile(nl, 95)), 3),
             percentile_vs_null=round(float((nl < s['gross_R']).mean()), 3))
    c = [s['trades'] >= 100, s['net_PF'] >= 1.2, s['net_R'] >= 0.10, s['gross_R'] > s['null_p95'], s['stress']['net_R'] > 0]
    s['verdict'] = ('PASS' if all(c) else 'FAIL') + f" (>=100 {c[0]}, PF {c[1]}, exp {c[2]}, null {c[3]}, stress {c[4]})"
    s['cfd_cost'] = stats(tr, cost=CFD_COST)
    s['fixed_2R'] = stats(tr, col='R_2R'); s['fixed_3R'] = stats(tr, col='R_3R')
    if 'bias_ok' in tr:
        s['bias_aligned'] = stats(tr[tr.bias_ok == True]); s['bias_against'] = stats(tr[tr.bias_ok == False])
    y = pd.to_datetime(tr.day).dt.year
    s['by'] = {'side': {('long' if k > 0 else 'short'): stats(g) for k, g in tr.groupby('dir')},
               'year': {int(k): stats(g) for k, g in tr.groupby(y)}}
    return s


if __name__ == '__main__':
    mode, path = sys.argv[1], os.path.abspath(sys.argv[2])
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    m1 = load_m1(path)
    if mode == 'day':
        day = pd.Timestamp(sys.argv[3])
        g = m1.loc[day:day + pd.Timedelta(minutes=FLAT)]
        tr, r = run_day(Day(g), None, trace=True)
        print('result:', r); sys.exit()
    os.makedirs(OUT, exist_ok=True)
    f = f'{OUT}/{mode}.json'
    if os.path.exists(f) and mode in ('dev', 'final'):
        sys.exit(f'{mode} already run once: {f}')
    if mode == 'final' and not (os.path.exists(f'{OUT}/dev.json') and json.load(open(f'{OUT}/dev.json')).get('net_R', -1) > 0):
        sys.exit('Development expectancy not above zero (or dev not run): final not spent (as registered).')
    a, b = {'dev': DEV, 'final': FINAL}[mode]
    tr, used, why = run(m1, a, b)
    tr.to_csv(f'{OUT}/{mode}_trades.csv', index=False)
    s = report(tr, used, why, a, b)
    print(json.dumps(s, indent=1)); json.dump(s, open(f, 'w'), indent=1)
