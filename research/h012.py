"""H-012: H-011 plus two selection rules (research/hypotheses.md, H-012):
  1. only gaps formed on earlier trading days (before 00:00 NY of the trading day);
  2. in the first 15 minutes (signals closing 09:30-09:45), no trade against the move since the 09:30 open
     when that move is at least 0.5 x ATR(14) of 15-minute bars (the last closed bar before 09:30).

  python3 h012.py gate  <M1 csv>... --ticks <tick csv>...        # 2025-10-23 trace (her filmed day)
  python3 h012.py dev   <M1 csv>... --ticks <tick csv>...        # 2025-07-01..2026-03-31
  python3 h012.py test  <M1 csv>... --ticks <tick csv>...        # ONCE, 2026-04-01..2026-10-16

Data: FP Markets US100. M1 bars (time, open, high, low, close; server = NY + 7 h) for the zones; real bid/ask ticks
(time_msc, bid, ask; ExportTicks.mq5, 09:00-11:45 NY) for 15-second candles and fills. Prices are mid; costs are the
futures estimate.
"""
import sys, os, json
import numpy as np, pandas as pd

COST = 0.5625                     # futures estimate, points per round trip (H-004..H-010)
STOP = TGT = 6.25                 # her 25 NQ ticks
MIN_GAP = 5.0                     # smallest gap kept (points); her smallest drawn gap on 2025-10-23 was ~7
LOOKBACK_DAYS = 5                 # gaps formed in the last 5 trading days (her chart reached back to the Friday)
ARM_SEC, TICK = 45, 0.25          # trigger 1 tick beyond the rejection candle, valid 3 candles
CAP_SEC = 15 * 60                 # 15-minute time cap
E0, E1 = 9 * 3600 + 30 * 60, 11 * 3600 + 30 * 60   # new entries 09:30-11:30
NEWS = (9 * 3600 + 57 * 60, 10 * 3600 + 3 * 60)    # no new entries 09:57-10:03 (no news calendar: every day)
FLAT = 11 * 3600 + 45 * 60
MAX_TRADES, MAX_LOSSES = 7, 2
DEV = ('2025-07-01', '2026-03-31')
TEST = ('2026-04-01', '2026-10-16')
OUT = 'results/h012'
OPEN_K, OPEN_END = 0.5, 9 * 3600 + 45 * 60


# ---------------------------------------------------------------- data
def load_m1(paths):
    m = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    m['t'] = pd.to_datetime(m.time, format='%Y.%m.%d %H:%M') - pd.Timedelta(hours=7)
    return m.drop_duplicates('t').sort_values('t').set_index('t')[['open', 'high', 'low', 'close']]


def load_ticks(paths):
    """dict date -> (seconds since NY midnight as float, mid price)."""
    days = {}
    for p in paths:
        t = pd.read_csv(p)
        ts = pd.to_datetime(t.time_msc, unit='ms') - pd.Timedelta(hours=7)
        mid = ((t.bid + t.ask) / 2).to_numpy()
        sec = ((ts - ts.dt.normalize()).dt.total_seconds()).to_numpy()
        for d, idx in pd.Series(np.arange(len(t))).groupby(ts.dt.strftime('%Y-%m-%d').to_numpy()):
            i = idx.to_numpy()
            days[d] = (sec[i], mid[i])
    return days


def candles15(sec, mid):
    """15-second mid candles: start second, open, high, low, close."""
    k = (sec // 15).astype(np.int64)
    s = pd.DataFrame(dict(k=k, p=mid)).groupby('k').p.agg(['first', 'max', 'min', 'last'])
    return s.index.to_numpy() * 15, s['first'].to_numpy(), s['max'].to_numpy(), s['min'].to_numpy(), s['last'].to_numpy()


# ---------------------------------------------------------------- zones
def gaps(m1, tf):
    """Every fair value gap on `tf` bars: three candles where candle 3 does not overlap candle 1.
    Returns rows (kind, lo, hi, formed = close time of candle 3, dead = first later close beyond the far edge)."""
    b = m1.resample(tf).agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    step = pd.Timedelta(tf)
    H, L, C, T = b.high.to_numpy(), b.low.to_numpy(), b.close.to_numpy(), b.index
    rows = []
    for i in range(2, len(b)):
        if L[i] > H[i - 2]:
            kind, lo, hi = 'demand', H[i - 2], L[i]
        elif H[i] < L[i - 2]:
            kind, lo, hi = 'supply', H[i], L[i - 2]
        else:
            continue
        if hi - lo < MIN_GAP:
            continue
        later = C[i + 1:]
        j = np.flatnonzero(later > hi) if kind == 'supply' else np.flatnonzero(later < lo)
        dead = T[i + 1 + j[0]] + step if len(j) else pd.Timestamp.max
        rows.append((kind, lo, hi, T[i] + step, dead, tf))
    return pd.DataFrame(rows, columns=['kind', 'lo', 'hi', 'formed', 'dead', 'tf'])


ATR15 = None


def atr15(m1):
    b = m1.resample('15min').agg({'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
    tr = np.maximum(b.high - b.low, np.maximum((b.high - b.close.shift()).abs(), (b.low - b.close.shift()).abs()))
    return tr.rolling(14).mean()   # value at bar start = ATR including that bar


def all_gaps(m1):
    return pd.concat([gaps(m1, '5min'), gaps(m1, '15min')], ignore_index=True)


# ---------------------------------------------------------------- one day
def first_cross(mid, start, level, below):
    x = np.flatnonzero(mid[start:] <= level) if below else np.flatnonzero(mid[start:] >= level)
    return start + x[0] if len(x) else None


def manage(sec, mid, j, d, fill, slip=0.0):
    """From tick j: stop/target on mid, 15-minute cap, flat 11:45. Returns R, how, exit second."""
    stop, tgt = fill - d * STOP, fill + d * TGT
    end = np.searchsorted(sec, min(sec[j] + CAP_SEC, FLAT))
    seg = mid[j:end]
    hs = np.flatnonzero(seg <= stop) if d > 0 else np.flatnonzero(seg >= stop)
    ht = np.flatnonzero(seg >= tgt) if d > 0 else np.flatnonzero(seg <= tgt)
    a = hs[0] if len(hs) else np.inf
    b = ht[0] if len(ht) else np.inf
    if a == np.inf and b == np.inf:
        k = max(end - 1, j)
        return d * (mid[k] - fill) / STOP, 'time', float(sec[k])
    if a <= b:   # stop first (same tick counts as a loss)
        return -(STOP + slip) / STOP, 'stop', float(sec[j + int(a)])
    return TGT / STOP, 'target', float(sec[j + int(b)])


def day(date, sec, mid, G, trading_days, slip=0.0, trace=False):
    D = pd.Timestamp(date)
    i = trading_days.index(date)
    since = pd.Timestamp(trading_days[max(0, i - LOOKBACK_DAYS)])
    g = G[(G.formed >= since) & (G.formed < D) & (G.dead > D + pd.Timedelta(seconds=E0 - 300))]
    gk, glo, ghi = g.kind.to_numpy(), g.lo.to_numpy(), g.hi.to_numpy()
    gf = ((g.formed - D).dt.total_seconds()).to_numpy()
    gd = np.array([(x - D).total_seconds() if x != pd.Timestamp.max else 1e9 for x in g.dead])
    cs, co, ch, cl, cc = candles15(sec, mid)
    j0 = np.searchsorted(sec, E0)
    open930 = mid[j0] if j0 < len(sec) else np.nan
    atr = ATR15.asof(D + pd.Timedelta(seconds=E0 - 900)) if ATR15 is not None else np.nan
    log, trades, busy_until, losses = [], [], -1.0, 0
    armed = None                                     # (direction, trigger, expiry second, candle start, zone)
    for n in range(len(cs)):
        t0, t1 = cs[n], cs[n] + 15
        # an armed trigger can fill during this candle
        if armed and t0 >= busy_until:
            dirn, trig, exp, src, z = armed
            a, b = np.searchsorted(sec, max(t0, src + 15)), np.searchsorted(sec, min(t1, exp))
            if t0 >= exp:
                armed = None
            elif b > a:
                j = first_cross(mid[:b], a, trig, below=(dirn < 0))
                if j is not None:
                    fill = mid[j]
                    R, how, xs = manage(sec, mid, j, dirn, fill, slip)
                    tr = dict(date=date, dir=dirn, entry_s=float(sec[j]), fill=float(fill), R=R, how=how, exit_s=xs,
                              zone_tf=z[0], zone_lo=float(z[1]), zone_hi=float(z[2]))
                    trades.append(tr); armed = None; busy_until = xs
                    losses += R < 0
                    if trace:
                        log.append(f"{hhmmss(sec[j])} FILLED {'SHORT' if dirn < 0 else 'LONG'} {fill:.2f} "
                                   f"({z[0]} {z[1]:.2f}-{z[2]:.2f})  -> {how} {hhmmss(xs)}  R {R:+.2f}")
                    if len(trades) >= MAX_TRADES or losses >= MAX_LOSSES:
                        break
        # signal at this candle's close
        if not (E0 <= t0 < E1) or NEWS[0] <= t1 < NEWS[1] or t1 < busy_until:
            continue
        o, h, l, c = co[n], ch[n], cl[n], cc[n]
        act = (gf <= t0) & (gd > t1)
        for dirn, kind in ((-1, 'supply'), (1, 'demand')):
            body = (o - c) * -dirn
            wick = (h - max(o, c)) if dirn < 0 else (min(o, c) - l)
            tip = h if dirn < 0 else l
            if body <= 0 or wick < body:
                continue
            if t1 <= OPEN_END and np.isfinite(atr) and -dirn * (c - open930) >= OPEN_K * atr:
                if trace:
                    log.append(f"{hhmmss(t1)} skip {'sell' if dirn < 0 else 'buy'}: against the opening move "
                               f"({c - open930:+.1f} since 09:30, limit {OPEN_K * atr:.1f})")
                continue
            z = np.flatnonzero(act & (gk == kind) & (glo <= tip) & (tip <= ghi))
            if len(z):
                k = z[0]
                trig = (l - TICK) if dirn < 0 else (h + TICK)
                armed = (dirn, trig, t1 + ARM_SEC, t0, (g.tf.iloc[k], glo[k], ghi[k]))
                if trace:
                    log.append(f"{hhmmss(t1)} rejection candle in {kind} gap {glo[k]:.2f}-{ghi[k]:.2f} ({g.tf.iloc[k]}) "
                               f"-> {'sell' if dirn < 0 else 'buy'} stop {trig:.2f}")
                break
    return trades, log


def hhmmss(s):
    s = int(s); return f'{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}'


def run(T, G, trading_days, a, b, **kw):
    out = []
    for d in sorted(T):
        if a <= d <= b and pd.Timestamp(d).weekday() != 4 and d in trading_days:   # no Fridays (her rule)
            out += day(d, *T[d], G, trading_days, **kw)[0]
    return pd.DataFrame(out)


# ---------------------------------------------------------------- statistics
def null_dist(T, tr, n=10000, per=40, seed=11):
    rng = np.random.default_rng(seed)
    P = []
    for _, x in tr.iterrows():
        sec, mid = T[x.date]
        ok = np.flatnonzero((sec >= E0) & (sec < E1) & ~((sec >= NEWS[0]) & (sec < NEWS[1])))
        js = ok[rng.integers(0, len(ok), per)]
        P.append([manage(sec, mid, j, int(x.dir), mid[j])[0] for j in js])
    P = np.array(P)
    return np.array([P[np.arange(len(P)), rng.integers(0, per, len(P))].mean() for _ in range(n)])


def stats(tr, cost=COST):
    if tr.empty:
        return dict(trades=0)
    R = tr.R.values; F = R - cost / STOP
    pf = lambda x: float(x[x > 0].sum() / -x[x < 0].sum()) if (x < 0).any() else float('inf')
    rng = np.random.default_rng(3)
    boot = [rng.choice(F, len(F)).mean() for _ in range(5000)]
    return dict(trades=int(len(R)), days=int(tr.date.nunique()), win_rate=round(float((R > 0).mean()), 3),
                gross_R=round(float(R.mean()), 3), fut_R=round(float(F.mean()), 3), fut_PF=round(pf(F), 3),
                fut_R_ci95=[round(float(np.percentile(boot, 2.5)), 3), round(float(np.percentile(boot, 97.5)), 3)],
                shorts=int((tr.dir < 0).sum()), longs=int((tr.dir > 0).sum()),
                exits={k: int(v) for k, v in tr.how.value_counts().items()})


def full(T, G, td, a, b):
    tr = run(T, G, td, a, b)
    s = stats(tr)
    if s['trades']:
        s['stress'] = stats(run(T, G, td, a, b, slip=0.25), cost=2 * COST)
        nl = null_dist(T, tr)
        s.update(null_mean=round(float(nl.mean()), 3), null_p95=round(float(np.percentile(nl, 95)), 3),
                 percentile_vs_null=round(float((nl < s['gross_R']).mean()), 3))
        c = [s['trades'] >= 100, s['fut_PF'] >= 1.2, s['fut_R'] >= 0.10, s['gross_R'] > s['null_p95'], s['stress']['fut_R'] > 0]
        s['verdict'] = ('PASS' if all(c) else 'FAIL') + f' (>=100 {c[0]}, PF {c[1]}, exp {c[2]}, null {c[3]}, stress {c[4]})'
    return tr, s


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(OUT, exist_ok=True)
    mode, args = sys.argv[1], sys.argv[2:]
    k = args.index('--ticks')
    m1 = load_m1(args[:k]); T = load_ticks(args[k + 1:])
    G = all_gaps(m1)
    ATR15 = atr15(m1)
    td = sorted({str(d.date()) for d in m1.index.normalize().unique() if d.weekday() < 5})
    if mode == 'gate':
        tr, log = day('2025-10-23', *T['2025-10-23'], G, td, trace=True)
        print('===== 2025-10-23'); print('\n'.join('   ' + x for x in log))
    else:
        f = f'{OUT}/{mode}.json'
        if mode == 'test' and os.path.exists(f):
            sys.exit('Test already run once: ' + f)
        a, b = DEV if mode == 'dev' else TEST
        tr, s = full(T, G, td, a, b)
        tr.to_csv(f'{OUT}/{mode}_trades.csv', index=False)
        s['period'] = [a, b]; s['tick_days'] = len([d for d in T if a <= d <= b])
        print(json.dumps(s, indent=1)); json.dump(s, open(f, 'w'), indent=1)
