"""H-009: H-006 V0 entries with cost-efficient brackets.  python3 h009.py dev  |  H005_DATA=<dir> python3 h009.py final V?"""
import sys, os, json
import numpy as np, pandas as pd
import h006
from h006 import load_seconds, load_m1, Context, HTFZones, run_day, outcome_x, mids, T930, T1130, T1145, NEWS
COST = 0.5625
DEV = ('2025-07-01', '2026-03-31'); SECOND = ('2026-04-01', '2026-10-16'); FINAL = ('2023-01-01', '2025-06-30')
VAR = {'A': dict(stop_pts=12.5, tgt_pts=25.0), 'B': dict(stop_atr=0.5, tgt_mult=2.0),
       'C': dict(stop_pts=8.0, tgt_pts=20.0), 'D': dict(stop_pts=12.5, tgt_pts=25.0, tf_only=('D',))}
CAP = 4 * 3600


def run(days, Z, C, a, b, v, **kw):
    sel = [d for d in sorted(days) if a <= d <= b]
    return pd.DataFrame([x for d in sel for x in run_day(days[d], Z, C, d, 'V0', cap_secs=CAP, **VAR[v], **kw)])


def stats(tr, cost=COST):
    if tr.empty: return dict(trades=0)
    R = tr.R.values; F = R - cost / tr.stop.values
    pf = lambda x: float(x[x > 0].sum() / -x[x < 0].sum()) if (x < 0).any() else float('inf')
    rng = np.random.default_rng(3); boot = [rng.choice(F, len(F)).mean() for _ in range(5000)]
    return dict(trades=int(len(R)), win_rate=float((R > 0).mean()), gross_R=float(R.mean()), fut_R=float(F.mean()), fut_PF=pf(F),
                fut_R_ci95=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))], median_stop=float(tr.stop.median()))


def null(days, tr, n=10000, seed=31, per=60):
    rng = np.random.default_rng(seed)
    secs_all = np.r_[np.arange(T930, NEWS[0]), np.arange(NEWS[1], T1130)]
    P = []
    for _, x in tr.iterrows():
        D = days[x.date]; t = D['t']; mo, mh, ml, mc = mids(D)
        idx = np.clip(np.searchsorted(t, rng.choice(secs_all, per)), 0, len(t) - 2)
        P.append([outcome_x(t, mh, ml, mc, i, int(x.side), mo[i], x.stop, x.tgt, min(CAP, T1145 - int(t[i])), 0.0, 0.0)[0] for i in idx])
    P = np.array(P)
    return np.array([P[np.arange(len(P)), rng.integers(0, per, len(P))].mean() for _ in range(n)])


if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'final':
        pass  # run as: H005_DATA=<dir> python3 h009.py final V?
    days = load_seconds(); m1 = load_m1(); C = Context(m1); Z = HTFZones(m1)
    os.makedirs('results/h009', exist_ok=True)
    if mode == 'dev':
        res = {}
        for v in VAR:
            tr = run(days, Z, C, *DEV, v); tr.to_csv(f'results/h009/dev_{v}.csv', index=False)
            res[v] = stats(tr); print(v, json.dumps(res[v]))
        ok = {v: s for v, s in res.items() if s['trades'] >= 40}
        res['pick'] = max(ok, key=lambda v: ok[v]['fut_R']); print('PICK', res['pick'])
        for v in VAR:
            s2 = stats(run(days, Z, C, *SECOND, v)); res[f'second_descriptive_{v}'] = s2
            print('Apr-Oct 2026 (descriptive)', v, json.dumps({k: s2[k] for k in ('trades', 'win_rate', 'fut_R', 'fut_PF')}))
        json.dump(res, open('results/h009/dev.json', 'w'), indent=1)
    elif mode == 'final':
        f = f'results/h009/final_{sys.argv[2]}.json'
        if os.path.exists(f): sys.exit('already run once')
        v = sys.argv[2]
        tr = run(days, Z, C, *FINAL, v); tr.to_csv(f'results/h009/final_{v}.csv', index=False)
        s = stats(tr); s['stress'] = stats(run(days, Z, C, *FINAL, v, through=0.25, slip=0.5), cost=2 * COST)
        nl = null(days, tr); s.update(null_p95=float(np.percentile(nl, 95)), percentile_vs_null=float((nl < s['gross_R']).mean()))
        s['null_p975'] = float(np.percentile(nl, 97.5))
        c = [s['trades'] >= 100, s['fut_PF'] >= 1.2, s['fut_R'] >= 0.10, s['gross_R'] > s['null_p975'], s['stress']['fut_R'] > 0]
        s['verdict'] = ('PASS' if all(c) else 'FAIL') + str(c); print(json.dumps(s, indent=1)); json.dump(s, open(f, 'w'), indent=1)
