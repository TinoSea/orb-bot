"""H-006: higher-time-frame supply/demand zones + failed-extreme entry (see research/hypotheses.md, H-006).

  python3 h006.py dev        # V0, V1, V2 on the development period; prints the pick
  python3 h006.py test V?    # the chosen variant, ONCE, on the test period
"""
import sys, os, json
import numpy as np, pandas as pd
from h005 import load_seconds, load_m1, Context, candles15, outcome, mids, tsec, FUT_COST_R, DEV, HOLD

T930, T1130, T1145 = tsec('09:30'), tsec('11:30'), tsec('11:45')
NEWS = (tsec('09:57'), tsec('10:03'))
STOP = 6.25
TICK = 0.01
MAX_SPREAD = 0.30 * STOP
TFS = {'D': ('1D', 60), 'H4': ('4h', 30), 'H1': ('1h', 10)}      # rule, look-back days


# ---------------------------------------------------------------- higher-time-frame zones
class HTFZones:
    def __init__(self, m1, imp_atr=1.5, lb_scale=1.0):
        srv = m1.reset_index().set_index('time')[['open', 'high', 'low', 'close']]
        self.tf = {}
        for name, (rule, lb) in TFS.items():
            b = srv.resample(rule, label='left', closed='left').agg(
                {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna()
            pc = b.close.shift(1)
            tr = np.maximum(b.high - b.low, np.maximum((b.high - pc).abs(), (b.low - pc).abs()))
            atr_prev = tr.rolling(14, min_periods=5).mean().shift(1)
            dur = pd.Timedelta(rule)
            body, rng = (b.close - b.open).abs(), b.high - b.low
            imp = (atr_prev > 0) & (rng > 0) & (body >= imp_atr * atr_prev) & (body >= 0.6 * rng)
            zs = []
            closes = b.close.values
            ends = (b.index + dur).values
            for j in np.where(imp.values)[0]:
                if j == 0:
                    continue
                typ = 1 if b.close.iloc[j] > b.open.iloc[j] else -1
                lo, hi = b.low.iloc[j - 1], b.high.iloc[j - 1]
                later = closes[j + 1:]
                brk = np.where(later < lo)[0] if typ > 0 else np.where(later > hi)[0]
                broken_at = ends[j + 1 + brk[0]] if len(brk) else np.datetime64('2100-01-01')
                zs.append(dict(tf=name, type=typ, lo=lo, hi=hi, start=b.index[j], end=ends[j], broken_at=broken_at, lb=lb * lb_scale))
            self.tf[name] = zs

    def zones(self, date):
        cut = pd.Timestamp(date) + pd.Timedelta(hours=16, minutes=30)      # 09:30 NY in server time
        out = []
        for name in ('D', 'H4', 'H1'):
            for z in self.tf[name]:
                if z['end'] <= cut and z['start'] >= cut - pd.Timedelta(days=z['lb']) and z['broken_at'] > cut:
                    out.append(dict(z, active=True))
        return out


# ---------------------------------------------------------------- outcome with stress options
from numba import njit


@njit(cache=True)
def outcome_x(t, mh, ml, mc, i0, side, e, stop, tgt, cap, through, slip):
    """As h005.outcome, but the target must trade `through` beyond it and a stop fills `slip` worse.
    R is in units of the planned stop. Same-second stop and target counts as a loss."""
    n = len(t)
    last = i0
    for k in range(i0 + 1, n):
        if t[k] - t[i0] > cap:
            break
        last = k
        if side > 0:
            up = mh[k] - e >= tgt + through
            dn = e - ml[k] >= stop
        else:
            up = e - ml[k] >= tgt + through
            dn = mh[k] - e >= stop
        if dn:
            return -(stop + slip) / stop, k, 1 if up else 0
        if up:
            return tgt / stop, k, 0
    return side * (mc[last] - e) / stop, last, 0


# ---------------------------------------------------------------- one day
def run_day(D, Z, C, date, variant, stop_pts=None, tgt_pts=None, through=0.0, slip=0.0):
    zones = Z.zones(date)
    if not zones:
        return []
    t = D['t']
    mo, mh, ml, mc = mids(D)
    cd = candles15(D, T930 - 8 * 15, T1130)
    trades, losses, out = 0, 0, []
    arm = None          # dict(dir, price, expiry, ext, zone)
    pos_end = -1
    ci = 8
    i = np.searchsorted(t, T930)
    while i < len(t) and t[i] < T1130:
        now = int(t[i])
        while ci < len(cd) and cd.start.iloc[ci] + 15 <= now:
            r = cd.iloc[ci]; close_t = int(r.start) + 15
            win = cd.iloc[ci - 7:ci + 1]
            ci += 1
            for z in zones:
                if z['active'] and ((z['type'] > 0 and r.c < z['lo']) or (z['type'] < 0 and r.c > z['hi'])):
                    z['active'] = False
                    if arm and arm['zone'] is z:
                        arm = None
            if arm is not None:
                if (arm['dir'] < 0 and r.h > arm['ext']) or (arm['dir'] > 0 and r.l < arm['ext']):
                    arm = None                                   # new extreme: cancel, may re-arm below
                else:
                    continue
            if close_t < pos_end or trades >= 4 or losses >= 2 or NEWS[0] <= close_t < NEWS[1]:
                continue
            if variant == 'V1':
                a, _, _ = C.atr_at(pd.Timestamp(date) + pd.Timedelta(seconds=close_t))
                k0 = np.searchsorted(t, close_t - 600); k1 = np.searchsorted(t, close_t)
                if k1 > k0 and (D['bh'][k0:k1].max() - D['bl'][k0:k1].min()) < 0.75 * a:
                    continue
            for z in zones:
                if not z['active'] or not (r.h >= z['lo'] and r.l <= z['hi']):
                    continue
                if z['type'] < 0 and r.h >= win.h.max():
                    arm = dict(dir=-1, price=r.l - TICK, expiry=close_t + 4 * 15, ext=r.h, zone=z); break
                if z['type'] > 0 and r.l <= win.l.min():
                    arm = dict(dir=1, price=r.h + TICK, expiry=close_t + 4 * 15, ext=r.l, zone=z); break
        if arm is not None and now >= pos_end:
            if now >= arm['expiry']:
                arm = None
            elif not (NEWS[0] <= now < NEWS[1]):
                d = arm['dir']
                hit = (D['ah'][i] >= arm['price']) if d > 0 else (D['bl'][i] <= arm['price'])
                spread = D['ao'][i] - D['bo'][i]
                if hit and spread <= MAX_SPREAD:
                    fill = (max(arm['price'], D['ao'][i]) - spread / 2) if d > 0 else (min(arm['price'], D['bo'][i]) + spread / 2)
                    stop = STOP if stop_pts is None else stop_pts
                    if variant == 'V2':
                        stop = (fill - (arm['ext'] - 0.25)) if d > 0 else ((arm['ext'] + 0.25) - fill)
                        if stop < 3 or stop > 12.5:
                            arm = None; i += 1; continue
                    cap = min(900, T1145 - now)
                    tgt = stop if tgt_pts is None else tgt_pts
                    R, k, amb = outcome_x(t, mh, ml, mc, i, d, fill, stop, tgt, cap, through, slip)
                    out.append(dict(date=date, t=now, side=d, R=R, amb=amb, secs=int(t[k]) - now, stop=stop, tgt=tgt,
                                    tf=arm['zone']['tf'], fill=fill, i=int(i)))
                    trades += 1; losses += R < 0
                    arm['zone']['active'] = False
                    arm = None
                    pos_end = int(t[k])
        i += 1
    return out


# ---------------------------------------------------------------- statistics
def null_dist(days, tr, n=10000, seed=11):
    rng = np.random.default_rng(seed)
    secs_all = np.r_[np.arange(T930, NEWS[0]), np.arange(NEWS[1], T1130)]
    pools = []
    for (date, side), g in tr.groupby(['date', 'side']):
        D = days[date]; t = D['t']; mo, mh, ml, mc = mids(D)
        idx = np.clip(np.searchsorted(t, secs_all[::5]), 0, len(t) - 2)
        for stop in g.stop.values:
            R = np.array([outcome(t, mh, ml, mc, i, side, mo[i], stop, stop, min(900, T1145 - int(t[i])))[0] for i in idx[::3]])
            pools.append(R)
    out = np.empty(n)
    for j in range(n):
        out[j] = np.mean([rng.choice(p) for p in pools])
    return out


def stats(tr, days, label, with_null=True):
    if tr.empty:
        return dict(variant=label, trades=0)
    R = tr.R.values; F = R - FUT_COST_R
    pf = lambda x: float(x[x > 0].sum() / -x[x < 0].sum()) if (x < 0).any() else float('inf')
    rng = np.random.default_rng(3)
    boot = [rng.choice(F, len(F)).mean() for _ in range(5000)]
    s = dict(variant=label, trades=int(len(R)), days=int(tr.date.nunique()), win_rate=float((R > 0).mean()),
             gross_R=float(R.mean()), fut_R=float(F.mean()), fut_PF=pf(F),
             fut_R_ci95=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
             by_tf={k: [int(len(g)), float(g.R.mean())] for k, g in tr.groupby('tf')},
             median_secs=float(np.median(tr.secs)), ambiguous=int(tr.amb.sum()))
    if with_null:
        nl = null_dist(days, tr)
        s.update(null_mean=float(nl.mean()), null_p95=float(np.percentile(nl, 95)),
                 percentile_vs_null=float((nl < R.mean()).mean()))
    return s


def verdict(s):
    if s['trades'] == 0:
        return 'FAIL (no trades)'
    c = [s['trades'] >= 100, s['fut_PF'] >= 1.2, s['fut_R'] >= 0.10, s['gross_R'] > s['null_p95']]
    return ('PASS' if all(c) else 'FAIL') + f" (>=100 trades {c[0]}, PF>=1.2 {c[1]}, exp>=+0.10R {c[2]}, beats null 95% {c[3]})"


HER = [('2025-11-03', '09:34:30', -1), ('2025-11-03', '09:35:40', -1), ('2025-11-03', '09:38:05', -1),
       ('2025-10-31', '09:31:30', -1), ('2025-10-31', '09:35:45', 1), ('2025-10-31', '09:36:20', -1),
       ('2025-10-31', '09:39:15', -1), ('2025-10-31', '09:41:00', -1)]


def her_recall(tr):
    hits = 0
    for d, t0, side in HER:
        g = tr[(tr.date == d) & (tr.side == side)]
        hits += bool(((g.t - tsec(t0)).abs() <= 30).any())
    return hits


if __name__ == '__main__':
    mode = sys.argv[1]
    days = load_seconds(); m1 = load_m1(); C = Context(m1); Z = HTFZones(m1)
    os.makedirs('results/h006', exist_ok=True)
    if mode == 'dev':
        a, b = DEV
        sel = [d for d in sorted(days) if a <= d <= b]
        res = {}
        for v in ('V0', 'V1', 'V2'):
            tr = pd.DataFrame([x for d in sel for x in run_day(days[d], Z, C, d, v)])
            tr.to_csv(f'results/h006/dev_{v}_trades.csv', index=False)
            s = stats(tr, days, v, with_null=False); s['her_trades_taken_of_8'] = her_recall(tr) if len(tr) else 0
            res[v] = s; print(json.dumps(s))
        pick = max(res, key=lambda v: res[v].get('fut_R', -9) if res[v]['trades'] else -9)
        res['pick'] = pick; print('PICK', pick)
        json.dump(res, open('results/h006/dev.json', 'w'), indent=1)
    else:
        v = sys.argv[2]
        f = 'results/h006/test.json'
        if os.path.exists(f):
            sys.exit('Test period already run once: ' + f)
        a, b = HOLD
        sel = [d for d in sorted(days) if a <= d <= b]
        tr = pd.DataFrame([x for d in sel for x in run_day(days[d], Z, C, d, v)])
        tr.to_csv(f'results/h006/test_{v}_trades.csv', index=False)
        s = stats(tr, days, v); s['verdict'] = verdict(s)
        print(json.dumps(s, indent=1)); json.dump(s, open(f, 'w'), indent=1)
