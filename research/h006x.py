"""H-006/1: H-006 V0 entries with the 4 / 25 exit.  python3 h006x.py dev | test (test runs ONCE)."""
import sys, os, json
import numpy as np, pandas as pd
from h006 import (load_seconds, load_m1, Context, HTFZones, run_day, outcome_x, mids, DEV, HOLD,
                  T930, T1130, T1145, NEWS)
COST = 0.5625
S, TG = 4.0, 25.0


def run(days, Z, C, a, b, through=0.0, slip=0.0):
    sel = [d for d in sorted(days) if a <= d <= b]
    return pd.DataFrame([x for d in sel for x in run_day(days[d], Z, C, d, 'V0', S, TG, through, slip)])


def null(days, tr, n=10000, seed=23, per=60):
    rng = np.random.default_rng(seed)
    secs_all = np.r_[np.arange(T930, NEWS[0]), np.arange(NEWS[1], T1130)]
    P = []
    for _, x in tr.iterrows():
        D = days[x.date]; t = D['t']; mo, mh, ml, mc = mids(D)
        idx = np.clip(np.searchsorted(t, rng.choice(secs_all, per)), 0, len(t) - 2)
        P.append([outcome_x(t, mh, ml, mc, i, int(x.side), mo[i], S, TG, min(900, T1145 - int(t[i])), 0.0, 0.0)[0] for i in idx])
    P = np.array(P)
    return np.array([P[np.arange(len(P)), rng.integers(0, per, len(P))].mean() for _ in range(n)])


def stats(tr, cost=COST):
    R = tr.R.values; F = R - cost / S
    pf = lambda x: float(x[x > 0].sum() / -x[x < 0].sum()) if (x < 0).any() else float('inf')
    rng = np.random.default_rng(3)
    boot = [rng.choice(F, len(F)).mean() for _ in range(5000)]
    return dict(trades=int(len(R)), days=int(tr.date.nunique()), win_rate=float((R > 0).mean()), gross_R=float(R.mean()),
                fut_R=float(F.mean()), fut_PF=pf(F), fut_R_ci95=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                time_exits=int(((R > -1) & (R < TG / S)).sum()), ambiguous=int(tr.amb.sum()))


if __name__ == '__main__':
    mode = sys.argv[1]
    days = load_seconds(); m1 = load_m1(); C = Context(m1); Z = HTFZones(m1)
    a, b = DEV if mode == 'dev' else HOLD
    f = f'results/h006/x_{mode}.json'
    if mode == 'test' and os.path.exists(f):
        sys.exit('already run once: ' + f)
    tr = run(days, Z, C, a, b)
    tr.to_csv(f'results/h006/x_{mode}_trades.csv', index=False)
    s = stats(tr)
    st = run(days, Z, C, a, b, through=0.25, slip=0.25)
    s['stress'] = stats(st, cost=2 * COST)
    nl = null(days, tr)
    s.update(null_mean=float(nl.mean()), null_p95=float(np.percentile(nl, 95)), percentile_vs_null=float((nl < s['gross_R']).mean()))
    c = [s['trades'] >= 100, s['fut_PF'] >= 1.2, s['fut_R'] >= 0.10, s['gross_R'] > s['null_p95'], s['stress']['fut_R'] > 0]
    s['verdict'] = ('PASS' if all(c) else 'FAIL') + f' (>=100 {c[0]}, PF {c[1]}, exp {c[2]}, null {c[3]}, stress {c[4]})'
    s['period'] = [a, b]
    print(json.dumps(s, indent=1)); json.dump(s, open(f, 'w'), indent=1)
