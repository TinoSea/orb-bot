"""H-007: New York X bias + BPB / BOS entries on 5-minute bars (research/hypotheses.md, H-007).

  python3 h007.py gate                      # the registered gate (checkable trades), prints day traces
  python3 h007.py dev                       # V0-V3 on the development period, picks one
  python3 h007.py second V?                 # the pick on 2026-04-01..2026-10-16 (secondary check)
  python3 h007.py final V? <M1 csv>         # ONCE, on 2023-01-01..2025-06-30
Data: FP Markets US100 1-minute bars (server time = New York + 7 h).
"""
import sys, os, json
import numpy as np, pandas as pd

COST_PTS = 0.5625                 # futures cost estimate per round trip, index points
TICK = 0.25
DEV = ('2025-07-01', '2026-03-31')
SECOND = ('2026-04-01', '2026-10-16')
FINAL = ('2023-01-01', '2025-06-30')
T = lambda hhmm: pd.Timedelta(hours=int(hhmm[:2]), minutes=int(hhmm[3:]))
FILL_FROM, FILL_TO, NEWS_A, NEWS_B, FLAT = T('08:00'), T('11:00'), T('09:57'), T('10:03'), T('12:00')
OUT = 'results/h007'


def load_m1(path='/home/claude/h005data/US100_M1.csv'):
    m = pd.read_csv(path)
    m['time'] = pd.to_datetime(m.time, format='%Y.%m.%d %H:%M')
    m['ny'] = m.time - pd.Timedelta(hours=7)
    return m.set_index('ny')[['open', 'high', 'low', 'close']].sort_index()


class Data:
    def __init__(self, m1):
        self.m1 = m1
        b = m1.resample('5min', label='left', closed='left').agg(
            {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
        pc = b.close.shift(1)
        tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
        b['atr'] = tr.rolling(14).mean()
        self.m5 = b
        self.days = sorted({d for d in m1.index.normalize().unique()
                            if len(m1.loc[d + FILL_FROM:d + FLAT]) > 100})

    def levels(self, day):
        m = self.m1
        g = lambda a, b: m.loc[a:b - pd.Timedelta(minutes=1)]
        lon = g(day + T('03:00'), day + T('08:00'))
        if lon.empty:
            return None
        asia = g(day - pd.Timedelta(hours=4), day)
        six = g(day + T('06:00'), day + T('07:00'))
        prev = [d for d in self.days if d < day]
        L = dict(LH=lon.high.max(), LL=lon.low.min())
        L['L50'] = (L['LH'] + L['LL']) / 2
        if not asia.empty:
            L.update(AH=asia.high.max(), AL=asia.low.min())
        if not six.empty:
            L.update(H6=six.high.max(), L6=six.low.min())
        if prev:
            ny = g(prev[-1] + T('09:30'), prev[-1] + T('16:00'))
            if not ny.empty:
                L.update(PH=ny.high.max(), PL=ny.low.min(), P50=(ny.high.max() + ny.low.min()) / 2)
        return L


# ---------------------------------------------------------------- bias: London extremes
class Bias:
    """Per extreme: None / swept / broken / held / failed. Most recent event sets the bias."""
    def __init__(self, LH, LL):
        self.lv = {'H': LH, 'L': LL}
        self.st = {'H': None, 'L': None}
        self.event = (None, 0, '')        # (bar start, direction, text)

    def update(self, ts, o, h, l, c, atr):
        for side in ('H', 'L'):
            lv, s, sgn = self.lv[side], self.st[side], (1 if side == 'H' else -1)
            beyond_close = (c > lv) if sgn > 0 else (c < lv)
            beyond_trade = (h > lv) if sgn > 0 else (l < lv)
            near = (l <= lv + 0.25 * atr) if sgn > 0 else (h >= lv - 0.25 * atr)
            if s in ('broken', 'held') and not beyond_close:
                self.st[side] = 'failed'; self.event = (ts, -sgn, f'London {side} failed')
            elif s == 'broken' and beyond_close and near:
                self.st[side] = 'held'; self.event = (ts, sgn, f'London {side} broken and held')
            elif s not in ('broken', 'held') and beyond_close:
                self.st[side] = 'broken'; self.event = (ts, 0, f'London {side} broken')
            elif s not in ('broken', 'held') and beyond_trade:
                self.st[side] = 'swept'; self.event = (ts, -sgn, f'London {side} swept, closed back inside')

    @property
    def dir(self):
        return self.event[1]


# ---------------------------------------------------------------- one day (amendment H-007/1)
def make_order(kind, d, price, stop, cancel, expiry, why, atr, levels, variant):
    risk = abs(price - stop)
    if not (max(4.0, 0.25 * atr) <= risk <= 3 * atr):
        return None, f'risk {risk:.1f} outside limits ({why})'
    if variant == 'V1':
        beyond = [v for v in levels if d * (v - price) >= risk]
        target = (min(beyond) if d > 0 else max(beyond)) if beyond else price + d * 2 * risk
    else:
        target = price + d * 2 * risk
    return dict(kind=kind, dir=d, price=price, stop=stop, cancel=cancel, expiry=expiry, why=why, target=target), None


def run_day(D, day, variant, trace=False):
    L = D.levels(day)
    if L is None:
        return [], []
    m5 = D.m5.loc[day + FILL_FROM - pd.Timedelta(minutes=30):day + FLAT - pd.Timedelta(minutes=5)]
    m1 = D.m1.loc[day + FILL_FROM:day + FLAT]
    levels = list(L.values())
    bias = Bias(L['LH'], L['LL'])
    log, trades = [], []
    pend, pos = [], None
    last_exit = day + FILL_FROM - pd.Timedelta(minutes=30)
    k5 = 0
    bars5 = m5[m5.index >= day + FILL_FROM]
    for t, r in m1.iterrows():
        while k5 < len(bars5) and bars5.index[k5] + pd.Timedelta(minutes=5) <= t:
            ts = bars5.index[k5]; b = bars5.iloc[k5]; k5 += 1
            close_t = ts + pd.Timedelta(minutes=5)
            before = bias.event
            bias.update(ts, b.open, b.high, b.low, b.close, b.atr)
            if trace and variant == 'V3' and bias.event is not before:
                log.append(f'{close_t.time()} {bias.event[2]} -> bias {bias.dir:+d}')
            keep = []
            for o in pend:
                dead = o['cancel'] is not None and ((o['dir'] > 0 and b.close < o['cancel']) or (o['dir'] < 0 and b.close > o['cancel']))
                if variant == 'V3' and bias.dir != o['dir']:
                    dead = True
                if dead and trace: log.append(f"{close_t.time()} {'BUY' if o['dir'] > 0 else 'SELL'} order cancelled")
                if not dead: keep.append(o)
            pend = keep
            if pos or pend or len(trades) >= 2 or close_t >= day + FILL_TO:
                continue
            if variant == 'V3' and bias.dir == 0:
                continue
            atr = b.atr
            hist = m5.loc[:ts]
            after = hist[hist.index >= last_exit]
            if variant == 'V3':
                after = after[after.index > bias.event[0]]
            orders = []
            if variant in ('V0', 'V1', 'V3'):
                for n in (3, 2):
                    if len(after) < n:
                        continue
                    p = after.iloc[-n:]
                    lo, hi = p.low.min(), p.high.max()
                    if hi - lo > 1.5 * atr:
                        continue
                    dist = min(0.0 if lo <= v <= hi else min(abs(lo - v), abs(hi - v)) for v in levels)
                    if dist > 0.5 * atr:
                        continue
                    why = f'pause {n} bars {lo:.2f}-{hi:.2f}'
                    exp = close_t + pd.Timedelta(minutes=15)
                    sides = [bias.dir] if variant == 'V3' else [1, -1]
                    for d in sides:
                        o, err = make_order('stop', d, hi + TICK if d > 0 else lo - TICK, lo - TICK if d > 0 else hi + TICK,
                                            None, exp, why, atr, levels, variant)
                        if o: orders.append(o)
                        elif trace: log.append(f'{close_t.time()} setup skipped: {err}')
                    break
            else:   # V2 BOS, either direction
                if len(after) >= 7:
                    prev6, cur = after.iloc[-7:-1], after.iloc[-1]
                    d = 1 if cur.close > prev6.high.max() else (-1 if cur.close < prev6.low.min() else 0)
                    if d:
                        opp = prev6[(prev6.close < prev6.open)] if d > 0 else prev6[(prev6.close > prev6.open)]
                        if len(opp):
                            z = opp.iloc[-1]
                            o, err = make_order('limit', d, z.high if d > 0 else z.low, (z.low - TICK) if d > 0 else (z.high + TICK),
                                                z.low if d > 0 else z.high, close_t + pd.Timedelta(minutes=30),
                                                f'BOS, zone {z.low:.2f}-{z.high:.2f}', atr, levels, variant)
                            if o: orders.append(o)
                            elif trace: log.append(f'{close_t.time()} setup skipped: {err}')
            pend = orders
            if trace:
                for o in orders:
                    log.append(f"{close_t.time()} {o['kind']} order {'BUY' if o['dir'] > 0 else 'SELL'} {o['price']:.2f} "
                               f"stop {o['stop']:.2f} target {o['target']:.2f} ({o['why']})")
        if pos:
            d = pos['dir']
            hit_stop = (r.low <= pos['stop']) if d > 0 else (r.high >= pos['stop'])
            hit_tgt = (r.high >= pos['target']) if d > 0 else (r.low <= pos['target'])
            ex = None
            if hit_stop:
                ex = (min(pos['stop'], r.open) if d > 0 else max(pos['stop'], r.open), 'stop')
            elif hit_tgt:
                ex = (pos['target'], 'target')
            elif t >= day + FLAT - pd.Timedelta(minutes=1):
                ex = (r.close, 'time')
            if ex:
                pos.update(exit=ex[0], how=ex[1], exit_t=t)
                pos['R'] = d * (ex[0] - pos['fill']) / pos['risk']
                trades.append(pos); last_exit = t
                if trace: log.append(f"{t.time()} EXIT {ex[1]} at {ex[0]:.2f}  R {pos['R']:+.2f}")
                pos = None
            continue
        if not pend:
            continue
        if t >= pend[0]['expiry']:
            if trace: log.append(f'{t.time()} order(s) expired')
            pend = []
            continue
        if not (day + FILL_FROM <= t < day + FILL_TO) or (day + NEWS_A <= t < day + NEWS_B):
            continue
        for o in pend:
            d = o['dir']
            if o['kind'] == 'stop':
                filled = (r.high >= o['price']) if d > 0 else (r.low <= o['price'])
                fill = (max(o['price'], r.open) if d > 0 else min(o['price'], r.open)) if filled else None
            else:
                filled = (r.low <= o['price']) if d > 0 else (r.high >= o['price'])
                fill = (min(o['price'], r.open) if d > 0 else max(o['price'], r.open)) if filled else None
            if not filled:
                continue
            pend = []
            risk = d * (fill - o['stop'])
            if risk <= 0:
                break
            pos = dict(day=str(day.date()), entry_t=t, dir=d, fill=fill, stop=o['stop'], target=o['target'],
                       risk=risk, kind=o['kind'], why=o['why'], bias=bias.event[2])
            if trace: log.append(f"{t.time()} FILLED {'LONG' if d > 0 else 'SHORT'} at {fill:.2f} risk {risk:.1f}")
            if (r.low <= pos['stop']) if d > 0 else (r.high >= pos['stop']):
                pos.update(exit=pos['stop'], how='stop', exit_t=t, R=-1.0)
                trades.append(pos); last_exit = t; pos = None
                if trace: log.append(f'{t.time()} EXIT stop on the fill bar  R -1.00')
            break
    return trades, log


def run(D, a, b, variant):
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    out = []
    for day in D.days:
        if a <= day <= b:
            out += run_day(D, day, variant)[0]
    return pd.DataFrame(out)


# ---------------------------------------------------------------- statistics
def null_dist(D, tr, n=10000, seed=17, per=40):
    rng = np.random.default_rng(seed)
    pools = []
    for _, x in tr.iterrows():
        day = pd.Timestamp(x.day)
        m1 = D.m1.loc[day + FILL_FROM:day + FLAT]
        ok = m1[(m1.index < day + FILL_TO) & ~((m1.index >= day + NEWS_A) & (m1.index < day + NEWS_B))]
        rs = []
        tgt = x.dir * (x.target - x.fill)
        for t in rng.choice(ok.index, per):
            seg = m1.loc[t:]
            e = seg.open.iloc[0]; d = x.dir
            st, tg = e - d * x.risk, e + d * tgt
            R = None
            for j, (tt, r) in enumerate(seg.iterrows()):
                hs = (r.low <= st) if d > 0 else (r.high >= st)
                ht = (r.high >= tg) if d > 0 else (r.low <= tg)
                if hs:
                    R = -1.0; break
                if ht and j > 0:
                    R = tgt / x.risk; break
                if tt >= day + FLAT - pd.Timedelta(minutes=1):
                    R = d * (r.close - e) / x.risk; break
            rs.append(R if R is not None else d * (seg.close.iloc[-1] - e) / x.risk)
        pools.append(np.array(rs))
    P = np.array(pools)
    out = np.empty(n)
    for j in range(n):
        out[j] = P[np.arange(len(P)), rng.integers(0, per, len(P))].mean()
    return out


def stats(tr, D=None, label='', with_null=False):
    if tr is None or tr.empty:
        return dict(variant=label, trades=0)
    R = tr.R.values
    F = R - COST_PTS / tr.risk.values
    F2 = R - 2 * COST_PTS / tr.risk.values
    pf = lambda x: float(x[x > 0].sum() / -x[x < 0].sum()) if (x < 0).any() else float('inf')
    rng = np.random.default_rng(3)
    boot = [rng.choice(F, len(F)).mean() for _ in range(5000)]
    s = dict(variant=label, trades=int(len(R)), days=int(tr.day.nunique()), win_rate=float((R > 0).mean()),
             gross_R=float(R.mean()), fut_R=float(F.mean()), fut_PF=pf(F), fut_R_2xcost=float(F2.mean()),
             fut_R_ci95=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
             median_risk_pts=float(np.median(tr.risk)), longs=int((tr.dir > 0).sum()), shorts=int((tr.dir < 0).sum()),
             exits={k: int(v) for k, v in tr.how.value_counts().items()})
    if with_null:
        nl = null_dist(D, tr)
        s.update(null_mean=float(nl.mean()), null_p95=float(np.percentile(nl, 95)), percentile_vs_null=float((nl < R.mean()).mean()))
    return s


def verdict(s):
    if s['trades'] == 0:
        return 'FAIL (no trades)'
    c = [s['trades'] >= 100, s['fut_PF'] >= 1.2, s['fut_R'] >= 0.10, s['gross_R'] > s['null_p95']]
    return ('PASS' if all(c) else 'FAIL') + f" (>=100 trades {c[0]}, PF>=1.2 {c[1]}, exp>=+0.10R {c[2]}, beats null 95% {c[3]})"


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    mode = sys.argv[1]
    if mode == 'final':
        f = f'{OUT}/final.json'
        if os.path.exists(f):
            sys.exit('Final test already run once: ' + f)
        D = Data(load_m1(sys.argv[3]))
    else:
        D = Data(load_m1())
    if mode == 'gate':
        for day, v in [('2026-06-09', 'V0'), ('2026-10-05', 'V0'), ('2026-06-09', 'V2'), ('2026-10-05', 'V2'),
                       ('2025-10-31', 'V0'), ('2025-11-03', 'V0'), ('2026-10-12', 'V0')]:
            tr, log = run_day(D, pd.Timestamp(day), v, trace=True)
            L = D.levels(pd.Timestamp(day))
            print(f'===== {day} {v}  London H {L["LH"]:.2f} L {L["LL"]:.2f} 50% {L["L50"]:.2f}')
            print('\n'.join('   ' + x for x in log) or '   (no events)')
    elif mode == 'dev':
        res = {}
        for v in ('V0', 'V1', 'V2', 'V3'):
            tr = run(D, *DEV, v)
            tr.to_csv(f'{OUT}/dev_{v}_trades.csv', index=False)
            res[v] = stats(tr, label=v); print(json.dumps(res[v]))
        ok = {v: s for v, s in res.items() if s['trades'] >= 60}
        res['pick'] = max(ok, key=lambda v: ok[v]['fut_R']) if ok else None
        print('PICK', res['pick'])
        json.dump(res, open(f'{OUT}/dev.json', 'w'), indent=1)
    elif mode in ('second', 'final'):
        v = sys.argv[2]
        a, b = SECOND if mode == 'second' else FINAL
        tr = run(D, a, b, v)
        tr.to_csv(f'{OUT}/{mode}_{v}_trades.csv', index=False)
        s = stats(tr, D, v, with_null=True); s['verdict'] = verdict(s); s['period'] = [a, b]
        print(json.dumps(s, indent=1))
        json.dump(s, open(f'{OUT}/{mode}.json', 'w'), indent=1)
