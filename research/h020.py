"""H-020: AMD at the New York open - sweep / gap tap, then reverse (research/hypotheses.md, H-020).

  python3 h020.py dev   <US100_M1_2025_2026.csv>   # 2025-07-01..2026-03-31, seen once
  python3 h020.py final <US100_M1_2022_2025.csv>   # ONCE, 2023-01-01..2025-06-30, only if dev futures expectancy > 0
  python3 h020.py day   <csv> 2025-10-23           # trace one day (levels, signal, trade) for hand-checking

US100 1-minute bars from mt5/ExportData.mq5 (server = NY + 7 h). New York time throughout.
"""
import sys, os, json
import numpy as np, pandas as pd

COST, CFD_COST = 0.5625, 1.45
DEV = ('2025-07-01', '2026-03-31')
FINAL = ('2023-01-01', '2025-06-30')
OUT = 'results/h020'
TICK, MIN_STOP, RR, FVG_MIN, FVG_DAYS, SWING_N = 0.25, 5.0, 2.0, 5.0, 5, 2
A0, B0, B_LAST, FLAT = 9 * 60 + 25, 9 * 60 + 30, 9 * 60 + 32, 10 * 60 + 29   # bar-open minutes after NY midnight
NEED = (9 * 60 + 20, 9 * 60 + 35)                                             # every bar in this range must exist
M = lambda day, mins: day + pd.Timedelta(minutes=mins)


def load_m1(path):
    m = pd.read_csv(path)
    m['ny'] = pd.to_datetime(m.time, format='%Y.%m.%d %H:%M') - pd.Timedelta(hours=7)
    return m.set_index('ny')[['open', 'high', 'low', 'close']].sort_index()


class Data:
    def __init__(self, m1):
        self.m1 = m1
        agg = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
        self.m5 = m1.resample('5min').agg(agg).dropna()
        self.days = sorted({d for d in m1.index.normalize().unique() if d.weekday() < 5})

    def _after(self, t0, t):
        """1-minute bars that open at or after t0 and close by t."""
        return self.m1.loc[t0:t - pd.Timedelta(minutes=1)]

    def lines(self, day, t, p):
        """Untaken liquidity and untapped gaps at time t, split by side of the reference price p.
        Returns (sell_lines, buy_lines) as lists of (price, kind, strict); strict=True means price must go beyond it."""
        cand = []                                                   # (price, 'high'|'low', kind, formed_at)
        i = self.days.index(day)
        if i > 0:
            pd_ = self.days[i - 1]
            r = self.m1.loc[M(pd_, 570):M(pd_, 959)]
            if len(r):
                cand += [(r.high.max(), 'high', 'prev_day', M(pd_, 960)), (r.low.min(), 'low', 'prev_day', M(pd_, 960))]
            for a, b, k in ((-240, 180, 'asia'), (180, 540, 'london')):
                if M(day, b) <= t:
                    s = self.m1.loc[M(day, a):M(day, b - 1)]
                    if len(s):
                        cand += [(s.high.max(), 'high', k, M(day, b)), (s.low.min(), 'low', k, M(day, b))]
            w = self.m5.loc[M(pd_, 570):t - pd.Timedelta(minutes=5)]
            hh, ll, n = w.high.to_numpy(), w.low.to_numpy(), SWING_N
            for j in range(n, len(w) - n):
                conf = w.index[j + n] + pd.Timedelta(minutes=5)
                if conf > t:
                    break
                if hh[j] > max(hh[j - n:j].max(), hh[j + 1:j + n + 1].max()):
                    cand.append((hh[j], 'high', 'swing', w.index[j] + pd.Timedelta(minutes=5)))
                if ll[j] < min(ll[j - n:j].min(), ll[j + 1:j + n + 1].min()):
                    cand.append((ll[j], 'low', 'swing', w.index[j] + pd.Timedelta(minutes=5)))
        sell, buy = [], []
        for lv, side, kind, t0 in cand:
            a = self._after(t0, t)
            if side == 'high' and lv > p and not (len(a) and a.high.max() > lv):
                sell.append((lv, kind, True))
            if side == 'low' and lv < p and not (len(a) and a.low.min() < lv):
                buy.append((lv, kind, True))
        # untapped 5-minute fair value gaps from the last FVG_DAYS trading days
        start = self.days[max(0, i - FVG_DAYS)]
        g = self.m5.loc[start:t - pd.Timedelta(minutes=5)]
        gh, gl = g.high.to_numpy(), g.low.to_numpy()
        for j in range(2, len(g)):
            if gl[j] - gh[j - 2] >= FVG_MIN:
                lo, hi = gh[j - 2], gl[j]
            elif gl[j - 2] - gh[j] >= FVG_MIN:
                lo, hi = gh[j], gl[j - 2]
            else:
                continue
            a = self._after(g.index[j] + pd.Timedelta(minutes=5), t)
            if len(a) and ((a.low.to_numpy() <= hi) & (a.high.to_numpy() >= lo)).any():
                continue                                            # tapped
            if lo > p:
                sell.append((lo, 'fvg', False))
            elif hi < p:
                buy.append((hi, 'fvg', False))
        return sell, buy


def hit(x, line, strict, up):
    return (x > line if strict else x >= line) if up else (x < line if strict else x <= line)


def run_day(D, day, slip=0.0, trace=False):
    w = D.m1.loc[M(day, NEED[0]):M(day, FLAT)]
    mins = ((w.index - day).total_seconds() // 60).astype(int)
    if not set(range(NEED[0], NEED[1] + 1)) <= set(mins):
        return None
    t1 = w.index
    o, h, l, c = (w[x].to_numpy() for x in ('open', 'high', 'low', 'close'))
    k_of = {m: k for k, m in enumerate(mins)}
    sig = None
    # Scenario A: 09:25-09:29, enter at the close of the first bar that reaches a line
    sell, buy = D.lines(day, M(day, A0), c[k_of[A0 - 1]])
    if trace: print('A lines  sell:', sorted(sell), '\n         buy:', sorted(buy))
    for m in range(A0, B0):
        k = k_of[m]
        s = [x for x in sell if hit(h[k], x[0], x[2], True)]
        b = [x for x in buy if hit(l[k], x[0], x[2], False)]
        if s and b:
            return []
        if s or b:
            ka = k_of[A0]
            d = -1 if s else 1
            ext = h[ka:k + 1].max() + TICK if d < 0 else l[ka:k + 1].min() - TICK
            sig = dict(scen='A', k=k, d=d, ext=ext, kind=(s or b)[0][1], line=(s or b)[0][0])
            break
    # Scenario B: 09:30-09:32, a line is crossed, then a bar closes back on the other side of it
    if sig is None:
        sell, buy = D.lines(day, M(day, B0), c[k_of[B0 - 1]])
        if trace: print('B lines  sell:', sorted(sell), '\n         buy:', sorted(buy))
        swept_s, swept_b = [], []
        kb = k_of[B0]
        for m in range(B0, B_LAST + 1):
            k = k_of[m]
            swept_s += [x for x in sell if x not in swept_s and hit(h[k], x[0], x[2], True)]
            swept_b += [x for x in buy if x not in swept_b and hit(l[k], x[0], x[2], False)]
            s = [x for x in swept_s if c[k] < x[0]]
            b = [x for x in swept_b if c[k] > x[0]]
            if s and b:
                return []
            if s or b:
                d = -1 if s else 1
                ext = h[kb:k + 1].max() + TICK if d < 0 else l[kb:k + 1].min() - TICK
                sig = dict(scen='B', k=k, d=d, ext=ext, kind=(s or b)[0][1], line=(s or b)[0][0])
                break
    if sig is None:
        return []
    k0, d, e = sig['k'], sig['d'], c[sig['k']]
    stop = sig['ext']
    if d * (e - stop) < MIN_STOP:
        stop = e - d * MIN_STOP
    risk = d * (e - stop)
    tr = dict(day=str(day.date()), scen=sig['scen'], kind=sig['kind'], line=round(sig['line'], 2),
              entry_t=str(t1[k0]), dir=d, fill=e, stop=stop, tgt=e + d * RR * risk, risk=risk)
    tr.update(manage(o, h, l, c, k0, d, e, stop, tr['tgt'], t1, slip))
    tr['R_hold'] = manage(o, h, l, c, k0, d, e, stop, None, t1, slip)['R']      # no target, hold to 10:30
    # the same trade in the other direction, same entry and stop distance (for the random-direction null)
    st2 = e + d * risk
    tr['R_flip'] = manage(o, h, l, c, k0, -d, e, st2, e - d * RR * risk, t1, 0.0)['R']
    if trace: print(json.dumps(tr, indent=1, default=str))
    return [tr]


def manage(o, h, l, c, k0, d, e, stop, tgt, t1, slip):
    risk = d * (e - stop)
    for k in range(k0 + 1, len(c)):
        if (l[k] <= stop) if d > 0 else (h[k] >= stop):
            x = (min(stop, o[k]) if d > 0 else max(stop, o[k])) - d * slip
            return dict(exit=x, how='stop', R=d * (x - e) / risk, exit_t=str(t1[k]))
        if tgt is not None and ((h[k] >= tgt) if d > 0 else (l[k] <= tgt)):
            return dict(exit=tgt, how='target', R=RR, exit_t=str(t1[k]))
    return dict(exit=c[-1], how='time', R=d * (c[-1] - e) / risk, exit_t=str(t1[-1]))


def run(D, a, b, **kw):
    out, used = [], 0
    for day in D.days:
        if pd.Timestamp(a) <= day <= pd.Timestamp(b):
            r = run_day(D, day, **kw)
            if r is not None:
                used += 1; out += r
    return pd.DataFrame(out), used


def stats(tr, cost=COST, col='R'):
    if tr.empty: return dict(trades=0)
    R = tr[col].values; F = R - cost / tr.risk.values
    pf = lambda x: float(x[x > 0].sum() / -x[x < 0].sum()) if (x < 0).any() else float('inf')
    rng = np.random.default_rng(3); boot = [rng.choice(F, len(F)).mean() for _ in range(5000)]
    return dict(trades=int(len(R)), win_rate=round(float((R > 0).mean()), 3),
                gross_R=round(float(R.mean()), 3), net_R=round(float(F.mean()), 3), net_PF=round(pf(F), 3),
                net_R_ci95=[round(float(np.percentile(boot, 2.5)), 3), round(float(np.percentile(boot, 97.5)), 3)],
                median_stop=round(float(np.median(tr.risk)), 2))


def null_direction(tr, n=10000, seed=20):
    """Mean gross R when each trade's direction is a coin flip (same entry, stop distance, target, exit time)."""
    rng = np.random.default_rng(seed)
    P = np.stack([tr.R.values, tr.R_flip.values])
    return P[rng.integers(0, 2, (n, len(tr))), np.arange(len(tr))].mean(axis=1)


def report(D, tr, used, a, b):
    s = stats(tr)
    s.update(days_with_data=used, period=[a, b])
    if not s['trades']:
        return s
    s['exits'] = {k: int(v) for k, v in tr.how.value_counts().items()}
    st, _ = run(D, a, b, slip=0.25)
    s['stress'] = stats(st, cost=2 * COST)
    nl = null_direction(tr)
    s.update(null_mean=round(float(nl.mean()), 3), null_p95=round(float(np.percentile(nl, 95)), 3),
             percentile_vs_null=round(float((nl < s['gross_R']).mean()), 3))
    c = [s['trades'] >= 100, s['net_PF'] >= 1.2, s['net_R'] >= 0.10, s['gross_R'] > s['null_p95'], s['stress']['net_R'] > 0]
    s['verdict'] = ('PASS' if all(c) else 'FAIL') + f" (>=100 {c[0]}, PF {c[1]}, exp {c[2]}, null {c[3]}, stress {c[4]})"
    # reported, not part of the verdict
    s['cfd_cost'] = stats(tr, cost=CFD_COST)
    s['hold_no_target'] = stats(tr, col='R_hold')
    y = pd.to_datetime(tr.day).dt.year
    s['by'] = {'scenario': {k: stats(g) for k, g in tr.groupby('scen')},
               'side': {('long' if k > 0 else 'short'): stats(g) for k, g in tr.groupby('dir')},
               'trigger': {k: stats(g) for k, g in tr.groupby('kind')},
               'year': {int(k): stats(g) for k, g in tr.groupby(y)}}
    s['longest_win_streak'] = int(max((len(x) for x in ''.join('w' if r > 0 else ' ' for r in tr.R).split()), default=0))
    return s


if __name__ == '__main__':
    mode, path = sys.argv[1], os.path.abspath(sys.argv[2])
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    D = Data(load_m1(path))
    if mode == 'day':
        r = run_day(D, pd.Timestamp(sys.argv[3]), trace=True)
        print('no data for that day' if r is None else ('no trade' if not r else ''))
        sys.exit()
    os.makedirs(OUT, exist_ok=True)
    f = f'{OUT}/{mode}.json'
    if os.path.exists(f) and mode in ('dev', 'final'):
        sys.exit(f'{mode} already run once: {f}')
    if mode == 'final' and not os.path.exists(f'{OUT}/dev.json'):
        sys.exit('Run dev first: the final period is only spent if development expectancy is above zero.')
    if mode == 'final' and not json.load(open(f'{OUT}/dev.json')).get('net_R', -1) > 0:
        sys.exit('Development expectancy not above zero: final not spent (as registered).')
    a, b = {'dev': DEV, 'final': FINAL}[mode]
    tr, used = run(D, a, b)
    tr.to_csv(f'{OUT}/{mode}_trades.csv', index=False)
    s = report(D, tr, used, a, b)
    print(json.dumps(s, indent=1)); json.dump(s, open(f, 'w'), indent=1)
