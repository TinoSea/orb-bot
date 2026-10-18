"""H-005 Q1: her aligned entries vs random entries on the same days (same count, same direction)."""
import numpy as np, pandas as pd, json
from h005 import load_seconds, surface, tsec, FUT_COST_R
HER = [('2025-11-03','09:34:30',20,-1,1.0),('2025-11-03','09:35:40',15,-1,1.0),('2025-11-03','09:38:05',15,-1,0.5),
       ('2025-10-31','09:31:30',30,-1,1.0),('2025-10-31','09:35:45',30,1,-1.0),('2025-10-31','09:36:20',20,-1,-1.0),
       ('2025-10-31','09:39:15',20,-1,2.0/2),('2025-10-31','09:41:00',20,-1,1.0)]
if __name__ == '__main__':
  days = load_seconds()
  S = {d: surface(days[d]) for d in {h[0] for h in HER}}
  rows = []
  for d, t, tol, side, her in HER:
      secs, RL, RS = S[d]; R = RL if side > 0 else RS
      c = tsec(t); w = (secs >= c - tol) & (secs <= c + tol)
      rows.append(dict(date=d, time=t, side=side, her_R=her, R_centre=R[secs == c][0], R_window=np.nanmean(R[w]),
                       win_share=np.nanmean(R[w] > 0)))
  df = pd.DataFrame(rows); print(df.round(3).to_string(index=False))
  her_mean = df.R_window.mean()
  rng = np.random.default_rng(5)
  def null(t_from, t_to, n=10000):
      out = np.empty(n)
      pools = []
      for d, t, tol, side, _ in HER:
          secs, RL, RS = S[d]; R = RL if side > 0 else RS
          p = R[(secs >= t_from) & (secs < t_to)]; pools.append(p[~np.isnan(p)])
      for k in range(n):
          out[k] = np.mean([rng.choice(p) for p in pools])
      return out
  res = {}
  for name, a, b in [('09:30-11:00 (registered)', tsec('09:30'), tsec('11:00')), ('09:30-09:45 (descriptive)', tsec('09:30'), tsec('09:45'))]:
      nl = null(a, b)
      res[name] = dict(null_mean=nl.mean(), null_p95=np.percentile(nl, 95), her_percentile=(nl < her_mean).mean())
      print(f'{name}: random mean {nl.mean():+.3f}R, 95th pct {np.percentile(nl,95):+.3f}R; her {her_mean:+.3f}R -> percentile {100*(nl<her_mean).mean():.0f}')
  print(f'her gross {her_mean:+.3f}R, futures estimate {her_mean-FUT_COST_R:+.3f}R  (her own reported mean {df.her_R.mean():+.3f}R)')
  df.to_csv('results/h005/q1_her_trades.csv', index=False)
  json.dump({k: {kk: float(vv) for kk, vv in v.items()} | {'her_mean_R': float(her_mean)} for k, v in res.items()}, open('results/h005/q1.json', 'w'), indent=1)
