"""H-006 step 3: does V0's development result survive small changes to the zone settings? (development period only)"""
import json, numpy as np, pandas as pd
from h006 import load_seconds, load_m1, Context, HTFZones, run_day, DEV, FUT_COST_R
days = load_seconds(); m1 = load_m1(); C = Context(m1)
sel = [d for d in sorted(days) if DEV[0] <= d <= DEV[1]]
rows = []
for imp in (1.25, 1.5, 1.75):
    for lbs in (0.5, 1.0, 2.0):
        Z = HTFZones(m1, imp_atr=imp, lb_scale=lbs)
        tr = pd.DataFrame([x for d in sel for x in run_day(days[d], Z, C, d, 'V0')])
        R = tr.R.values
        rows.append(dict(impulse_atr=imp, lookback_x=lbs, trades=len(R), win=round((R > 0).mean(), 3),
                         gross_R=round(R.mean(), 3), fut_R=round(R.mean() - FUT_COST_R, 3),
                         se=round(R.std() / np.sqrt(len(R)), 3)))
        print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv('results/h006/plateau_dev.csv', index=False)
