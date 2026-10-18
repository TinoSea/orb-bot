"""H-005 Q4: the two clone rules fixed in amendment H-005/2.

  python3 h005_q4.py dev          # development period, may be repeated (bug fixes only)
  python3 h005_q4.py holdout      # runs ONCE: refuses if results/h005/q4_holdout.json exists
"""
import sys, os, json, copy
import numpy as np, pandas as pd
from h005 import (load_seconds, load_m1, Context, candles15, outcome, mids, tsec,
                  STOP, TGT, CAP, FUT_COST_R, DEV, HOLD)

T930, T941, T1100, T1130 = tsec('09:30'), tsec('09:41'), tsec('11:00'), tsec('11:30')
TICK = 0.01
MAX_SPREAD = 0.30 * STOP


def day_arrays(D):
    mo, mh, ml, mc = mids(D)
    return D['t'], mo, mh, ml, mc


def run_position(D, i, side, e):
    t, mo, mh, ml, mc = day_arrays(D)
    cap = min(CAP, T1130 - int(t[i]))
    R, k, amb = outcome(t, mh, ml, mc, i, side, e, STOP, TGT, cap)
    return R, k, amb


# ---------------------------------------------------------------- Q4a: H-004 V1, arming only 09:30-09:41
def rule_a(D, C, date):
    if pd.Timestamp(date).dayofweek == 4:
        return []
    zones = copy.deepcopy(C.zones(date))
    if not zones:
        return []
    t, mo, mh, ml, mc = day_arrays(D)
    cd = candles15(D, T930, T1100)
    trades, losses, out = 0, 0, []
    arm = None            # (dir, price, expiry, zone index)
    pos_end = -1          # time the open position ends
    ci = 0
    i = np.searchsorted(t, T930)
    while i < len(t) and t[i] < T1100:
        now = int(t[i])
        # candle closes up to now
        while ci < len(cd) and cd.start.iloc[ci] + 15 <= now:
            r = cd.iloc[ci]; close_t = int(r.start) + 15; ci += 1
            for zi, z in enumerate(zones):
                if z['active'] and ((z['type'] > 0 and r.c < z['lo']) or (z['type'] < 0 and r.c > z['hi'])):
                    z['active'] = False
                    if arm and arm[3] == zi:
                        arm = None
            if arm is not None or close_t < pos_end or close_t > T941:
                continue
            for zi, z in enumerate(zones):
                if not z['active']:
                    continue
                d = 0
                if z['type'] < 0 and r.h >= z['lo'] and r.c < r.o and r.c < z['lo']:
                    d = -1
                elif z['type'] > 0 and r.l <= z['hi'] and r.c > r.o and r.c > z['hi']:
                    d = 1
                if d:
                    arm = (d, (r.h + TICK) if d > 0 else (r.l - TICK), int(r.start) + 4 * 15, zi)
                    break
        if arm is not None and now >= pos_end:
            d, price, expiry, zi = arm
            if now >= expiry:
                arm = None
            elif trades < 4 and losses < 2:
                hit = (D['ah'][i] >= price) if d > 0 else (D['bl'][i] <= price)
                spread = D['ao'][i] - D['bo'][i]
                if hit and spread <= MAX_SPREAD:
                    if d > 0:
                        fill = max(price, D['ao'][i]) - spread / 2
                    else:
                        fill = min(price, D['bo'][i]) + spread / 2
                    R, k, amb = run_position(D, i, d, fill)
                    out.append(dict(date=date, t=now, side=d, R=R, amb=amb, secs=int(t[k]) - now))
                    trades += 1; losses += R < 0
                    zones[zi]['active'] = False
                    arm = None
                    pos_end = int(t[k])
        i += 1
    return out


# ---------------------------------------------------------------- Q4b: London bias + first 11 minutes + 15-s break
def rule_b(D, C, date):
    lon = C.london(date)
    if not lon:
        return []
    if lon['hi_taken'] and not lon['lo_taken']:
        d = -1
    elif lon['lo_taken'] and not lon['hi_taken']:
        d = 1
    else:
        return []
    t, mo, mh, ml, mc = day_arrays(D)
    cd = candles15(D, T930 - 15, T941)
    trades, losses, out, pos_end = 0, 0, [], -1
    for k in range(1, len(cd)):
        r, p = cd.iloc[k], cd.iloc[k - 1]
        close_t = int(r.start) + 15
        if close_t > T941 or trades >= 4 or losses >= 2 or close_t < pos_end:
            continue
        if (d < 0 and r.c < p.l) or (d > 0 and r.c > p.h):
            i = np.searchsorted(t, close_t)
            if i >= len(t) - 1:
                break
            R, kk, amb = run_position(D, i, d, mo[i])
            out.append(dict(date=date, t=int(t[i]), side=d, R=R, amb=amb, secs=int(t[kk]) - int(t[i])))
            trades += 1; losses += R < 0
            pos_end = int(t[kk])
    return out


# ---------------------------------------------------------------- statistics
def null_dist(days, trades, n=10000, seed=7):
    """Random entries 09:30-09:41 on the same days, same count and directions."""
    rng = np.random.default_rng(seed)
    pools = []
    for (date, side), g in trades.groupby(['date', 'side']):
        D = days[date]; t, mo, mh, ml, mc = day_arrays(D)
        secs = np.arange(T930, T941)
        idx = np.unique(np.clip(np.searchsorted(t, secs), 0, len(t) - 2))
        R = np.array([outcome(t, mh, ml, mc, i, side, mo[i], STOP, TGT, min(CAP, T1130 - int(t[i])))[0] for i in idx])
        pools.append((R, len(g)))
    tot = sum(c for _, c in pools)
    out = np.empty(n)
    for j in range(n):
        out[j] = sum(rng.choice(R, c).sum() for R, c in pools) / tot
    return out


def stats(tr, days, label):
    if tr.empty:
        return dict(rule=label, trades=0)
    R = tr.R.values; F = R - FUT_COST_R
    pf = lambda x: x[x > 0].sum() / -x[x < 0].sum() if (x < 0).any() else np.inf
    rng = np.random.default_rng(3)
    boot = [rng.choice(F, len(F)).mean() for _ in range(5000)]
    nl = null_dist(days, tr)
    return dict(rule=label, trades=int(len(R)), days=int(tr.date.nunique()), win_rate=float((R > 0).mean()),
                gross_R=float(R.mean()), gross_PF=float(pf(R)), fut_R=float(F.mean()), fut_PF=float(pf(F)),
                fut_R_ci95=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                ambiguous=int(tr.amb.sum()), median_secs=float(np.median(tr.secs)),
                null_mean=float(nl.mean()), null_p975=float(np.percentile(nl, 97.5)),
                percentile_vs_null=float((nl < R.mean()).mean()))


def verdict(s):
    if s['trades'] == 0:
        return 'FAIL (no trades)'
    c = [s['trades'] >= 100, s['fut_PF'] >= 1.2, s['fut_R'] >= 0.10, s['gross_R'] > s['null_p975']]
    return ('PASS' if all(c) else 'FAIL') + f" (>=100 trades {c[0]}, PF>=1.2 {c[1]}, exp>=+0.10R {c[2]}, beats null 97.5% {c[3]})"


if __name__ == '__main__':
    period = sys.argv[1]
    a, b = DEV if period == 'dev' else HOLD
    out_json = f'results/h005/q4_{period}.json'
    if period == 'holdout' and os.path.exists(out_json):
        sys.exit('Holdout already run once: ' + out_json)
    days = load_seconds(); C = Context(load_m1())
    sel = [d for d in sorted(days) if a <= d <= b]
    res = {}
    for name, fn in [('Q4a', rule_a), ('Q4b', rule_b)]:
        tr = pd.DataFrame([x for d in sel for x in fn(days[d], C, d)])
        tr.to_csv(f'results/h005/q4_{period}_{name}_trades.csv', index=False)
        s = stats(tr, days, name); s['verdict'] = verdict(s); res[name] = s
        print(json.dumps(s, indent=1))
    res['period'] = [a, b]; res['days_in_period'] = len(sel)
    json.dump(res, open(out_json, 'w'), indent=1)
