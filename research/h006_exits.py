"""H-006 step 2: what happens after each V0 entry (development period only)? MFE/MAE and an exit map."""
import json, numpy as np, pandas as pd
from h006 import load_seconds, load_m1, Context, HTFZones, run_day, DEV, mids, T1145
COST_PTS = 0.09 * 6.25          # futures cost estimate in index points per round trip (0.5625)
days = load_seconds(); m1 = load_m1(); C = Context(m1); Z = HTFZones(m1)
sel = [d for d in sorted(days) if DEV[0] <= d <= DEV[1]]
tr = pd.DataFrame([x for d in sel for x in run_day(days[d], Z, C, d, 'V0')])
paths = []
for _, r in tr.iterrows():
    D = days[r.date]; t = D['t']; mo, mh, ml, mc = mids(D)
    i = int(r.i); end = np.searchsorted(t, min(t[i] + 900, T1145), side='right')
    seg = slice(i + 1, end)
    fav = (mh[seg] - r.fill) if r.side > 0 else (r.fill - ml[seg])
    adv = (r.fill - ml[seg]) if r.side > 0 else (mh[seg] - r.fill)
    last = r.side * (mc[end - 1] - r.fill)
    paths.append((np.maximum.accumulate(fav), np.maximum.accumulate(adv), last))
def bracket(S, T):
    out = []
    for fav, adv, last in paths:
        kf = np.argmax(fav >= T) if (fav >= T).any() else 10**9
        ka = np.argmax(adv >= S) if (adv >= S).any() else 10**9
        if ka == kf == 10**9: pts = last
        elif ka <= kf: pts = -S
        else: pts = T
        out.append(pts)
    p = np.array(out)
    return dict(win=(p > 0).mean(), gross_R=p.mean() / S, fut_R=(p - COST_PTS).mean() / S, pts=p.mean() - COST_PTS)
# 1. what the 6.25/6.25 trades looked like
b = np.array([[f[-1] if len(f) else 0, a[-1] if len(a) else 0] for f, a, _ in paths])
win = tr.R.values > 0
def first_hit(arr, x): return np.argmax(arr >= x) if (arr >= x).any() else 10**9
mae_before_win = [a[:first_hit(f, 6.25) + 1].max() for (f, a, _), w in zip(paths, win) if w]
mfe_before_loss = [f[:first_hit(a, 6.25) + 1].max() for (f, a, _), w in zip(paths, win) if not w]
mfe15 = [f.max() if len(f) else 0 for f, a, _ in paths]
print('trades', len(tr), 'wins', win.sum())
print('winners: worst point against before +6.25 hit -> median %.2f, 75th pct %.2f, 90th %.2f' % tuple(np.percentile(mae_before_win, [50, 75, 90])))
print('losers: best point in favour before -6.25 hit -> median %.2f, 75th pct %.2f' % tuple(np.percentile(mfe_before_loss, [50, 75])))
print('all trades: furthest in favour within 15 min -> median %.2f, 75th %.2f, 90th %.2f' % tuple(np.percentile(mfe15, [50, 75, 90])))
for x in (6.25, 10, 15, 20, 30):
    print(f'  reached +{x} pts before -6.25: {np.mean([first_hit(f,x) < first_hit(a,6.25) for f,a,_ in paths]):.1%}')
# 2. exit map
S_ = [4, 5, 6.25, 8, 10, 12.5]; T_ = [4, 6.25, 8, 10, 12.5, 15, 20, 25]
grid = pd.DataFrame([[bracket(S, T)['fut_R'] for T in T_] for S in S_], index=S_, columns=T_)
wins = pd.DataFrame([[bracket(S, T)['win'] for T in T_] for S in S_], index=S_, columns=T_)
print('\nexpectancy after futures costs, R per trade (rows = stop pts, cols = target pts):'); print(grid.round(3).to_string())
print('\nwin rate:'); print(wins.round(2).to_string())
# plateau-smoothed pick: average of each cell and its neighbours
sm = grid.copy()
for a in range(len(S_)):
    for c in range(len(T_)):
        sm.iloc[a, c] = grid.iloc[max(0, a-1):a+2, max(0, c-1):c+2].values.mean()
a, c = np.unravel_index(np.nanargmax(sm.values), sm.shape)
print(f'\nneighbourhood-smoothed best: stop {S_[a]} / target {T_[c]} (smoothed {sm.iloc[a,c]:+.3f}R, raw {grid.iloc[a,c]:+.3f}R)')
grid.to_csv('results/h006/exitmap_dev.csv'); json.dump(dict(stop=S_[a], target=T_[c], smoothed=float(sm.iloc[a, c]), raw=float(grid.iloc[a, c])), open('results/h006/exit_pick.json', 'w'))
