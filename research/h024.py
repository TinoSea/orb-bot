"""H-024: do ICT "macro" windows (HH:50-HH:10) move more than the rest of the hour? Descriptive (hypotheses.md, H-024).

  python3 h024.py dev <US100_M1.csv>     # 2025-07-01..2026-03-31, run once

US100 1-minute bars from mt5/ExportData.mq5 (server = NY + 7 h). New York time throughout.
"""
import sys, os, json
import numpy as np, pandas as pd
from h020 import load_m1

DEV = ('2025-07-01', '2026-03-31')
OUT = 'results/h024'
BLOCK_HOURS = range(2, 15)          # blocks HH:50 -> HH+1:50 for HH = 02..14
MAX_MISSING = 2
NAMED = {'PM 13:10-13:40 vs 13:40-14:10': ((790, 820), [(820, 850)]),
         'last hour 15:15-15:45 vs 14:45-15:15': ((915, 945), [(885, 915)])}


def day_grid(g):
    mins = ((g.index - g.index[0].normalize()).total_seconds() // 60).astype(int).to_numpy()
    H, L = np.full(1440, np.nan), np.full(1440, np.nan)
    H[mins], L[mins] = g.high.to_numpy(float), g.low.to_numpy(float)
    return H, L


def window(H, L, a, b):
    """(range, swept prior 60-min high/low) for minutes [a, b), or None if too many bars missing."""
    h, l = H[a:b], L[a:b]
    ph, pl = H[max(0, a - 60):a], L[max(0, a - 60):a]
    if np.isnan(h).sum() > MAX_MISSING or (~np.isnan(ph)).sum() < 50:
        return None
    rh, rl = np.nanmax(h), np.nanmin(l)
    return rh - rl, float(rh > np.nanmax(ph) or rl < np.nanmin(pl))


def compare(G, macro, controls):
    rows = []
    for day, (H, L) in G.items():
        m = window(H, L, *macro)
        cs = [window(H, L, *c) for c in controls]
        if m is None or any(c is None for c in cs) or m[0] <= 0 or any(c[0] <= 0 for c in cs):
            continue
        cr = np.mean([c[0] for c in cs]); csw = np.mean([c[1] for c in cs])
        rows.append((np.log(m[0] / cr), m[1] - csw, m[0], cr, m[1], csw))
    a = np.array(rows)
    if not len(a):
        return dict(days=0)
    rng = np.random.default_rng(24)
    idx = rng.integers(0, len(a), (5000, len(a)))
    lr, sw = a[idx, 0].mean(1), a[idx, 1].mean(1)
    r = dict(days=len(a), macro_range_pts=round(a[:, 2].mean(), 1), control_range_pts=round(a[:, 3].mean(), 1),
             log_ratio=round(a[:, 0].mean(), 3), log_ratio_ci95=[round(np.percentile(lr, 2.5), 3), round(np.percentile(lr, 97.5), 3)],
             pct_larger=round(100 * (np.exp(a[:, 0].mean()) - 1), 1),
             macro_sweep_rate=round(a[:, 4].mean(), 3), control_sweep_rate=round(a[:, 5].mean(), 3),
             sweep_diff=round(a[:, 1].mean(), 3), sweep_diff_ci95=[round(np.percentile(sw, 2.5), 3), round(np.percentile(sw, 97.5), 3)])
    r['range_supports'] = bool(r['log_ratio'] >= 0.095 and r['log_ratio_ci95'][0] > 0)
    r['sweep_supports'] = bool(r['sweep_diff_ci95'][0] > 0)
    return r


if __name__ == '__main__':
    mode, path = sys.argv[1], os.path.abspath(sys.argv[2])
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(OUT, exist_ok=True)
    f = f'{OUT}/{mode}.json'
    if os.path.exists(f):
        sys.exit(f'{mode} already run once: {f}')
    m1 = load_m1(path)
    a, b = DEV
    G = {d: day_grid(g) for d, g in m1.groupby(m1.index.normalize())
         if d.weekday() < 5 and pd.Timestamp(a) <= d <= pd.Timestamp(b)}
    blocks, n_ok = {}, 0
    for hh in BLOCK_HOURS:
        s = hh * 60 + 50
        ctr = [(s + 20, s + 40)] if hh == 8 else [(s + 20, s + 40), (s + 40, s + 60)]
        r = compare(G, (s, s + 20), ctr)
        blocks[f'{hh:02d}:50-{hh + 1:02d}:10'] = r
        n_ok += r.get('range_supports', False) and r.get('sweep_supports', False)
    out = dict(period=[a, b], days=len(G), blocks=blocks, blocks_supporting=int(n_ok),
               verdict='SUPPORTED' if n_ok >= 9 else 'NOT SUPPORTED',
               named={k: compare(G, m, c) for k, (m, c) in NAMED.items()},
               note='09:50-10:10 holds 10:00 US data releases; no news calendar used.')
    print(json.dumps(out, indent=1)); json.dump(out, open(f, 'w'), indent=1)
