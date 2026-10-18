"""H-019: build-up breakout at support/resistance in the direction of the trend (research/hypotheses.md, H-019).

  python3 h019.py dev   <M1 2025-26 csv>     # 2025-07-01..2026-03-31, seen once
  python3 h019.py final <M1 2022-25 csv>     # ONCE, 2023-01-01..2025-06-30, only if dev futures expectancy > 0

US100 1-minute bars (server = NY + 7 h). New York time throughout.
"""
import sys, os, json
import numpy as np, pandas as pd

COST = 0.5625
DEV = ('2025-07-01', '2026-03-31')
FINAL = ('2023-01-01', '2025-06-30')
OUT = 'results/h019'
N_BUILD, BUILD_ATR, NEAR_ATR, OVER_ATR = 4, 0.75, 0.5, 0.1
TICK, MIN_STOP, RR, VALID_BARS, MAX_TRADES = 0.25, 5.0, 2.0, 3, 2
E0, E1, FLAT = 3 * 60, 15 * 60 + 30, 16 * 60          # minutes after NY midnight


def load_m1(path):
    m = pd.read_csv(path)
    m['ny'] = pd.to_datetime(m.time, format='%Y.%m.%d %H:%M') - pd.Timedelta(hours=7)
    return m.set_index('ny')[['open', 'high', 'low', 'close']].sort_index()


class Data:
    def __init__(self, m1):
        self.m1 = m1
        agg = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
        self.m5 = m1.resample('5min').agg(agg).dropna()
        tr = np.maximum(self.m5.high - self.m5.low, np.maximum((self.m5.high - self.m5.close.shift()).abs(),
                                                                (self.m5.low - self.m5.close.shift()).abs()))
        self.m5['atr'] = tr.rolling(14).mean()
        m15 = m1.resample('15min').agg(agg).dropna()
        m15['ema'] = m15.close.ewm(span=20, adjust=False).mean()
        self.m15 = m15
        self.days = sorted({d for d in m1.index.normalize().unique() if d.weekday() < 5})

    def trend(self, t):
        """Direction from the last CLOSED 15-minute bar before t: close vs a rising/falling EMA20."""
        x = self.m15[self.m15.index + pd.Timedelta(minutes=15) <= t].tail(5)
        if len(x) < 5:
            return 0
        c, e, e4 = x.close.iloc[-1], x.ema.iloc[-1], x.ema.iloc[0]
        return 1 if (c > e and e > e4) else (-1 if (c < e and e < e4) else 0)

    def levels(self, day, t):
        """Previous trading day 09:30-16:00 high/low; Asia 20:00-03:00 and London 03:00-09:00 once complete."""
        out = []
        i = self.days.index(day)
        if i > 0:
            p = self.days[i - 1]
            r = self.m1.loc[p + pd.Timedelta(minutes=570):p + pd.Timedelta(minutes=959)]
            if len(r): out += [r.high.max(), r.low.min()]
        if t >= day + pd.Timedelta(hours=3):
            a = self.m1.loc[day - pd.Timedelta(hours=4):day + pd.Timedelta(minutes=179)]
            if len(a): out += [a.high.max(), a.low.min()]
        if t >= day + pd.Timedelta(hours=9):
            l = self.m1.loc[day + pd.Timedelta(hours=3):day + pd.Timedelta(minutes=539)]
            if len(l): out += [l.high.max(), l.low.min()]
        return out


def run_day(D, day, slip=0.0):
    m5 = D.m5.loc[day + pd.Timedelta(minutes=E0 - 60):day + pd.Timedelta(minutes=FLAT)]
    m1 = D.m1.loc[day + pd.Timedelta(minutes=E0):day + pd.Timedelta(minutes=FLAT - 1)]
    if len(m1) < 100:
        return []
    t1 = m1.index; o, h, l, c = (m1[x].to_numpy() for x in ('open', 'high', 'low', 'close'))
    trades, order, pos = [], None, None
    j5 = 0
    closes5 = m5.index + pd.Timedelta(minutes=5)
    for k in range(len(t1)):
        t = t1[k]
        # new 5-minute closes up to t -> maybe new order / cancel
        while j5 < len(m5) and closes5[j5] <= t:
            ct = closes5[j5]; b = m5.iloc[j5]
            if order and ((order['d'] > 0 and b.close < order['blo']) or (order['d'] < 0 and b.close > order['bhi'])):
                order = None
            if order:
                order['left'] -= 1
                if order['left'] <= 0: order = None
            mm = (ct - day).total_seconds() / 60
            if not order and not pos and len(trades) < MAX_TRADES and E0 <= mm < E1 and j5 + 1 >= N_BUILD:
                bu = m5.iloc[j5 + 1 - N_BUILD:j5 + 1]
                atr = b.atr
                if np.isfinite(atr) and atr > 0:
                    hi, lo = bu.high.max(), bu.low.min()
                    if hi - lo <= BUILD_ATR * atr:
                        d = D.trend(ct)
                        lv = D.levels(day, ct)
                        ok = False
                        if d > 0: ok = any(L - NEAR_ATR * atr <= hi <= L + OVER_ATR * atr for L in lv)
                        if d < 0: ok = any(L - OVER_ATR * atr <= lo <= L + NEAR_ATR * atr for L in lv)
                        if ok:
                            trig = hi + TICK if d > 0 else lo - TICK
                            stop = lo - TICK if d > 0 else hi + TICK
                            if abs(trig - stop) >= MIN_STOP:
                                order = dict(d=d, trig=trig, stop=stop, bhi=hi, blo=lo, left=VALID_BARS)
            j5 += 1
        if pos:
            d = pos['dir']
            hs = (l[k] <= pos['stop']) if d > 0 else (h[k] >= pos['stop'])
            ht = (h[k] >= pos['tgt']) if d > 0 else (l[k] <= pos['tgt'])
            ex = None
            if hs: ex = ((min(pos['stop'], o[k]) if d > 0 else max(pos['stop'], o[k])) - d * slip, 'stop')
            elif ht: ex = (pos['tgt'], 'target')
            elif k == len(t1) - 1: ex = (c[k], 'time')
            if ex:
                pos.update(exit=ex[0], how=ex[1], R=d * (ex[0] - pos['fill']) / pos['risk'], exit_t=str(t))
                trades.append(pos); pos = None
            continue
        if order:
            d = order['d']
            if (h[k] >= order['trig']) if d > 0 else (l[k] <= order['trig']):
                fill = max(order['trig'], o[k]) if d > 0 else min(order['trig'], o[k])
                risk = d * (fill - order['stop'])
                order_ = order; order = None
                if risk <= 0: continue
                pos = dict(day=str(day.date()), entry_t=str(t), dir=d, fill=fill, stop=order_['stop'],
                           tgt=fill + d * RR * risk, risk=risk)
                if (l[k] <= pos['stop']) if d > 0 else (h[k] >= pos['stop']):   # fill bar: stop only
                    pos.update(exit=pos['stop'], how='stop', R=-1.0, exit_t=str(t)); trades.append(pos); pos = None
    return trades


def run(D, a, b, **kw):
    out = []
    for day in D.days:
        if pd.Timestamp(a) <= day <= pd.Timestamp(b):
            out += run_day(D, day, **kw)
    return pd.DataFrame(out)


def null_dist(D, tr, n=10000, per=40, seed=19):
    rng = np.random.default_rng(seed)
    P = []
    for _, x in tr.iterrows():
        day = pd.Timestamp(x.day)
        m1 = D.m1.loc[day + pd.Timedelta(minutes=E0):day + pd.Timedelta(minutes=FLAT - 1)]
        idx = np.flatnonzero((m1.index >= day + pd.Timedelta(minutes=E0)) & (m1.index < day + pd.Timedelta(minutes=E1)))
        o, h, l, c = (m1[k].to_numpy() for k in ('open', 'high', 'low', 'close'))
        rs = []
        for j0 in rng.choice(idx, per):
            d, e = int(x.dir), o[j0]; st, tg = e - d * x.risk, e + d * RR * x.risk; R = None
            for j in range(j0, len(o)):
                if (l[j] <= st) if d > 0 else (h[j] >= st): R = -1.0; break
                if j > j0 and ((h[j] >= tg) if d > 0 else (l[j] <= tg)): R = RR; break
            rs.append(R if R is not None else d * (c[-1] - e) / x.risk)
        P.append(rs)
    P = np.array(P)
    return np.array([P[np.arange(len(P)), rng.integers(0, per, len(P))].mean() for _ in range(n)])


def stats(tr, cost=COST):
    if tr.empty: return dict(trades=0)
    R = tr.R.values; F = R - cost / tr.risk.values
    pf = lambda x: float(x[x > 0].sum() / -x[x < 0].sum()) if (x < 0).any() else float('inf')
    rng = np.random.default_rng(3); boot = [rng.choice(F, len(F)).mean() for _ in range(5000)]
    return dict(trades=int(len(R)), days=int(tr.day.nunique()), win_rate=round(float((R > 0).mean()), 3),
                gross_R=round(float(R.mean()), 3), fut_R=round(float(F.mean()), 3), fut_PF=round(pf(F), 3),
                fut_R_ci95=[round(float(np.percentile(boot, 2.5)), 3), round(float(np.percentile(boot, 97.5)), 3)],
                median_stop=round(float(np.median(tr.risk)), 2), longs=int((tr.dir > 0).sum()), shorts=int((tr.dir < 0).sum()),
                exits={k: int(v) for k, v in tr.how.value_counts().items()})


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(OUT, exist_ok=True)
    mode, path = sys.argv[1], sys.argv[2]
    f = f'{OUT}/{mode}.json'
    if mode == 'final':
        if os.path.exists(f): sys.exit('Final already run once: ' + f)
        if not json.load(open(f'{OUT}/dev.json'))['fut_R'] > 0:
            sys.exit('Development expectancy not above zero: final not spent (as registered).')
    D = Data(load_m1(path))
    a, b = DEV if mode == 'dev' else FINAL
    tr = run(D, a, b)
    tr.to_csv(f'{OUT}/{mode}_trades.csv', index=False)
    s = stats(tr)
    if s['trades']:
        s['stress'] = stats(run(D, a, b, slip=0.25), cost=2 * COST)
        nl = null_dist(D, tr)
        s.update(null_mean=round(float(nl.mean()), 3), null_p95=round(float(np.percentile(nl, 95)), 3),
                 percentile_vs_null=round(float((nl < s['gross_R']).mean()), 3))
        c = [s['trades'] >= 100, s['fut_PF'] >= 1.2, s['fut_R'] >= 0.10, s['gross_R'] > s['null_p95'], s['stress']['fut_R'] > 0]
        s['verdict'] = ('PASS' if all(c) else 'FAIL') + f' (>=100 {c[0]}, PF {c[1]}, exp {c[2]}, null {c[3]}, stress {c[4]})'
    s['period'] = [a, b]
    print(json.dumps(s, indent=1)); json.dump(s, open(f, 'w'), indent=1)
