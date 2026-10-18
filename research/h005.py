"""H-005: where does her edge live?  Engine for Q1-Q4 (see research/hypotheses.md, H-005).

Data: FP Markets US100 1-second bid/ask bars 09:00-11:45 NY (built from real ticks by h005 conversion),
      US100 M1 bars (server time = NY + 7h) for zones and pre-open features.
Scoring: mid prices, 6.25/6.25 bracket, 15-minute cap.  'gross' = mid-to-mid; futures estimate = gross - 0.09R.
Same-second stop/target ambiguity counts as a loss (conservative) and is reported.
"""
import glob, os
import numpy as np, pandas as pd
from numba import njit

DATA = os.environ.get('H005_DATA', '/home/claude/h005data')
STOP = TGT = 6.25
CAP = 900
FUT_COST_R = 0.09
DEV = ('2025-07-01', '2026-03-31')
HOLD = ('2026-04-01', '2026-10-16')


# ---------------------------------------------------------------- data
def load_seconds():
    """dict date -> structured arrays (t = seconds since NY midnight)."""
    days = {}
    for f in sorted(glob.glob(f'{DATA}/sec/S1_*.parquet')):
        s = pd.read_parquet(f).reset_index()
        s['date'] = s.s.dt.strftime('%Y-%m-%d')
        s['t'] = (s.s - s.s.dt.normalize()).dt.total_seconds().astype(np.int64)
        for d, g in s.groupby('date'):
            days[d] = {k: g[k].to_numpy() for k in ['t', 'bo', 'bh', 'bl', 'bc', 'ao', 'ah', 'al', 'ac']}
    return days


def load_m1():
    m = pd.read_csv(f'{DATA}/US100_M1.csv')
    m['time'] = pd.to_datetime(m.time, format='%Y.%m.%d %H:%M')
    m['ny'] = m.time - pd.Timedelta(hours=7)
    return m.set_index('ny')


# ---------------------------------------------------------------- outcome engine
@njit(cache=True)
def outcome(t, mh, ml, mc, i0, side, e, stop, tgt, cap):
    """Scan from second index i0+1. Returns (R, exit index, ambiguous flag)."""
    n = len(t)
    last = i0
    for k in range(i0 + 1, n):
        if t[k] - t[i0] > cap:
            break
        last = k
        if side > 0:
            up = mh[k] - e >= tgt
            dn = e - ml[k] >= stop
        else:
            up = e - ml[k] >= tgt
            dn = mh[k] - e >= stop
        if up and dn:
            return -1.0, k, 1
        if up:
            return tgt / stop, k, 0
        if dn:
            return -1.0, k, 0
    return side * (mc[last] - e) / stop, last, 0


def mids(D):
    mo = (D['bo'] + D['ao']) / 2
    mh = (D['bh'] + D['ah']) / 2
    ml = (D['bl'] + D['al']) / 2
    mc = (D['bc'] + D['ac']) / 2
    return mo, mh, ml, mc


def surface(D, t_from=9 * 3600 + 1800, t_to=11 * 3600):
    """R of entering at mid at every second in [t_from, t_to) for long and short. Returns (secs, R_long, R_short)."""
    mo, mh, ml, mc = mids(D)
    t = D['t']
    secs = np.arange(t_from, t_to)
    idx = np.searchsorted(t, secs)
    RL = np.full(len(secs), np.nan)
    RS = np.full(len(secs), np.nan)
    for j, i in enumerate(idx):
        if i >= len(t) - 1:
            continue
        RL[j] = outcome(t, mh, ml, mc, i, 1, mo[i], STOP, TGT, CAP)[0]
        RS[j] = outcome(t, mh, ml, mc, i, -1, mo[i], STOP, TGT, CAP)[0]
    return secs, RL, RS


def tsec(hhmmss):
    p = [int(x) for x in hhmmss.split(':')]
    return p[0] * 3600 + p[1] * 60 + (p[2] if len(p) > 2 else 0)


# ---------------------------------------------------------------- context: M15 zones, ATR, EMA, London
class Context:
    def __init__(self, m1):
        self.m1 = m1
        b = m1[['open', 'high', 'low', 'close']].resample('15min', label='left', closed='left').agg(
            {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
        pc = b.close.shift(1)
        tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
        tr.iloc[0] = b.high.iloc[0] - b.low.iloc[0]
        b['atr_prev'] = tr.rolling(14).mean().shift(1)      # ATR of the 14 bars before (as SD_Scalp)
        b['atr'] = tr.rolling(14).mean()                     # ATR including this bar (iATR on the closed bar)
        b['ema20'] = b.close.ewm(span=20, adjust=False).mean()
        self.m15 = b

    def zones(self, date, max_zones=6, imp_atr=1.5, imp_body=0.6):
        b = self.m15
        day = pd.Timestamp(date)
        ws, we = day - pd.Timedelta(hours=6), day + pd.Timedelta(hours=9, minutes=30)
        w = b[(b.index >= ws - pd.Timedelta(hours=6)) & (b.index < we)]
        out = []
        idx = list(w.index)
        for j in range(1, len(idx)):
            ts = idx[j]
            if ts < ws or ts + pd.Timedelta(minutes=15) > we:
                continue
            r = w.iloc[j]; a = r.atr_prev
            body, rng = abs(r.close - r.open), r.high - r.low
            if not (a > 0 and rng > 0 and body >= imp_atr * a and body >= imp_body * rng):
                continue
            p = w.iloc[j - 1]
            if idx[j - 1] != ts - pd.Timedelta(minutes=15):
                continue
            z = dict(lo=p.low, hi=p.high, type=1 if r.close > r.open else -1, formed=ts, active=True)
            later = w[(w.index > ts) & (w.index + pd.Timedelta(minutes=15) <= we)]
            if z['type'] > 0 and (later.close < z['lo']).any():
                continue
            if z['type'] < 0 and (later.close > z['hi']).any():
                continue
            out.append(z)
        keep, nd, ns = [], 0, 0
        for z in reversed(out):                                 # newest first
            if z['type'] > 0 and nd >= max_zones: continue
            if z['type'] < 0 and ns >= max_zones: continue
            nd += z['type'] > 0; ns += z['type'] < 0
            keep.append(z)
        return keep

    def atr_at(self, ts):
        """ATR(14) of the last closed M15 bar at time ts."""
        b = self.m15
        k = b.index.searchsorted(ts - pd.Timedelta(minutes=15), side='right') - 1
        return b.atr.iloc[k], b.close.iloc[k], b.ema20.iloc[k]

    def london(self, date):
        day = pd.Timestamp(date)
        m = self.m1
        lon = m[(m.index >= day + pd.Timedelta(hours=3)) & (m.index < day + pd.Timedelta(hours=8))]
        if lon.empty:
            return None
        pre = m[(m.index >= day + pd.Timedelta(hours=8)) & (m.index < day + pd.Timedelta(hours=9, minutes=30))]
        return dict(hi=lon.high.max(), lo=lon.low.min(), hi_taken=bool((pre.high > lon.high.max()).any()),
                    lo_taken=bool((pre.low < lon.low.min()).any()))


def candles15(D, t_from, t_to, sec=15):
    """Bid candles of `sec` seconds from 1-second bars: DataFrame start,o,h,l,c."""
    t = D['t']; m = (t >= t_from) & (t < t_to)
    k = (t[m] - t_from) // sec
    df = pd.DataFrame({'k': k, 'o': D['bo'][m], 'h': D['bh'][m], 'l': D['bl'][m], 'c': D['bc'][m]})
    g = df.groupby('k').agg(o=('o', 'first'), h=('h', 'max'), l=('l', 'min'), c=('c', 'last'))
    g['start'] = t_from + g.index * sec
    return g.reset_index(drop=True)


# ---------------------------------------------------------------- Q3 features at each 15-second candle close
FEATURES = ['zone_dist', 'in_zone', 'rejection', 'break_prev', 'ema_side', 'london', 'minutes', 'move5', 'range30', 'from_open']


def features_day(D, C, date, t_from=9 * 3600 + 1800, t_to=11 * 3600):
    day = pd.Timestamp(date)
    cd = candles15(D, t_from, t_to)
    zones = C.zones(date)
    lon = C.london(date)
    t = D['t']; mid = (D['bc'] + D['ac']) / 2
    open930 = mid[np.searchsorted(t, t_from)]
    rows = []
    for k in range(len(cd)):
        r = cd.iloc[k]; close_t = int(r.start) + 15
        ts = day + pd.Timedelta(seconds=close_t)
        atr, c15, ema = C.atr_at(ts)
        # zones broken so far by 15-s closes
        for z in zones:
            if z['active'] and ((z['type'] > 0 and r.c < z['lo']) or (z['type'] < 0 and r.c > z['hi'])):
                z['active'] = False
        i_now = np.searchsorted(t, close_t) - 1
        i5 = np.searchsorted(t, close_t - 300); i30 = np.searchsorted(t, close_t - 1800)
        hi30 = max(D['bh'][i30:i_now + 1].max(), 0) if i_now >= i30 else np.nan
        lo30 = D['bl'][i30:i_now + 1].min() if i_now >= i30 else np.nan
        prev = cd.iloc[k - 1] if k > 0 else r
        for d in (1, -1):
            zt = [z for z in zones if z['active'] and z['type'] == d]
            if zt:
                dist = min(0.0 if z['lo'] <= r.c <= z['hi'] else min(abs(r.c - z['lo']), abs(r.c - z['hi'])) for z in zt) / atr
                inz = any(r.l <= z['hi'] and r.h >= z['lo'] for z in zt)
                rej = any((d < 0 and r.h >= z['lo'] and r.c < r.o and r.c < z['lo']) or
                          (d > 0 and r.l <= z['hi'] and r.c > r.o and r.c > z['hi']) for z in zt)
            else:
                dist, inz, rej = 10.0, False, False
            lb = 0
            if lon:
                if lon['hi_taken'] and not lon['lo_taken']: lb = -1
                elif lon['lo_taken'] and not lon['hi_taken']: lb = 1
            rows.append(dict(date=date, close_t=close_t, side=d,
                             zone_dist=min(dist, 10.0), in_zone=int(inz), rejection=int(rej),
                             break_prev=int((d > 0 and r.c > prev.h) or (d < 0 and r.c < prev.l)),
                             ema_side=int(np.sign(c15 - ema)) * d, london=lb * d,
                             minutes=(close_t - t_from) / 60.0,
                             move5=d * (mid[i_now] - mid[max(i5, 0)]) / atr,
                             range30=(hi30 - lo30) / atr,
                             from_open=d * (mid[i_now] - open930) / atr))
    return pd.DataFrame(rows)
