import numpy as np, pandas as pd
from h006 import load_seconds, load_m1, Context, HTFZones, run_day, DEV, mids, T930, T1130, T1145, NEWS
from h005 import outcome
days = load_seconds(); m1 = load_m1(); C = Context(m1); Z = HTFZones(m1)
sel = [d for d in sorted(days) if DEV[0] <= d <= DEV[1]]
tr = pd.DataFrame([x for d in sel for x in run_day(days[d], Z, C, d, 'V0')])
COST = 0.5625
secs_all = np.r_[np.arange(T930, NEWS[0]), np.arange(NEWS[1], T1130)]
rng = np.random.default_rng(4)
for S, T in [(6.25, 6.25), (4, 25), (4, 15), (6.25, 15), (8, 20)]:
    sig = []
    for _, r in tr.iterrows():
        D = days[r.date]; t = D['t']; mo, mh, ml, mc = mids(D)
        R, k, a = outcome(t, mh, ml, mc, int(r.i), int(r.side), r.fill, S, T, min(900, T1145 - int(t[int(r.i)])))
        sig.append(R * S)
    sig = np.array(sig)
    # null: 20 random entries per signal, same day, same direction
    nul = []
    for _, r in tr.iterrows():
        D = days[r.date]; t = D['t']; mo, mh, ml, mc = mids(D)
        for s in rng.choice(secs_all, 20):
            i = min(np.searchsorted(t, s), len(t) - 2)
            R, k, a = outcome(t, mh, ml, mc, i, int(r.side), mo[i], S, T, min(900, T1145 - int(t[i])))
            nul.append(R * S)
    nul = np.array(nul)
    f = lambda p: (p - COST).mean() / S
    print(f'stop {S:5} target {T:5}: signals {f(sig):+.3f}R (win {(sig>0).mean():.0%})   random same day/dir {f(nul):+.3f}R (win {(nul>0).mean():.0%})   difference {f(sig)-f(nul):+.3f}R')
