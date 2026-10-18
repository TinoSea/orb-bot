"""H-003: market intraday momentum on the S&P 500 (research/hypotheses.md, H-003).

  python3 h003.py run <US500 M5 csv> [more csvs]     # once, 2023-01-01..2026-10-16

Data: FP Markets US500 5-minute bars exported from MT5 (columns time, open, high, low, close[, ...];
server time = NY + 7 h). Several files are merged; duplicate bars keep the first copy.
Rule: sign(price at 10:00 - previous 16:00 close) -> trade 15:30 open to 16:00 close. No stop, no target.
"""
import sys, os, json
import numpy as np, pandas as pd

COST, STRESS = 0.50, 1.00          # index points per round trip
PERIOD = ('2023-01-01', '2026-10-16')
OUT = 'results/h003'


def load(paths):
    m = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    m['t'] = pd.to_datetime(m.time, format='%Y.%m.%d %H:%M') - pd.Timedelta(hours=7)
    m = m.drop_duplicates('t').sort_values('t').set_index('t')
    return m[['open', 'high', 'low', 'close']]


def nyse_days(a, b):
    """NYSE trading days and their closing minute (16:00, or 13:00 on half days)."""
    import pandas_market_calendars as mc
    s = mc.get_calendar('NYSE').schedule(a, b)
    close = s.market_close.dt.tz_convert('America/New_York')
    return {pd.Timestamp(d): int(c.hour * 60 + c.minute) for d, c in zip(s.index, close)}


def days(m):
    """One row per NYSE trading day with the prices the rule needs. Exchange holidays are not trading days
    (the CFD may still print bars); half days are skipped as trade days but their 13:00 close is the next
    day's previous close."""
    m = m.assign(date=m.index.normalize(), hm=m.index.hour * 60 + m.index.minute)
    cal = nyse_days('2022-11-01', PERIOD[1])
    rows, prev_close = [], None
    for date, g in m.groupby('date'):
        if date not in cal:
            continue
        g = g.set_index('hm')
        cm = cal[date]
        pc = prev_close
        prev_close = float(g.close.loc[cm - 5]) if cm - 5 in g.index else None   # the bar ending at the close
        late = g[(g.index >= 15 * 60 + 30) & (g.index <= 15 * 60 + 55)]
        if cm < 16 * 60 or pc is None or 9 * 60 + 55 not in g.index or len(late) < 6:
            continue
        p10 = float(g.close.loc[9 * 60 + 55])
        entry, exit_ = float(g.open.loc[15 * 60 + 30]), float(g.close.loc[15 * 60 + 55])
        r12 = (float(g.close.loc[15 * 60 + 25]) - float(g.open.loc[15 * 60])) if {15 * 60, 15 * 60 + 25} <= set(g.index) else np.nan
        rows.append(dict(date=str(date.date()), prev_close=pc, p10=p10, sig=p10 - pc, r1_pct=100 * (p10 / pc - 1),
                         r12=r12, entry=entry, exit=exit_, move=exit_ - entry))
    d = pd.DataFrame(rows)
    d = d[(d.date >= PERIOD[0]) & (d.date <= PERIOD[1]) & (d.sig != 0)].reset_index(drop=True)
    d['dir'] = np.sign(d.sig).astype(int)
    d['pts'] = d.dir * d.move
    return d


def stats(pts, price, cost=COST):
    n = len(pts)
    if n == 0:
        return dict(trades=0)
    F = pts - cost
    rng = np.random.default_rng(3)
    boot = [rng.choice(F, n).mean() for _ in range(5000)]
    pf = float(F[F > 0].sum() / -F[F < 0].sum()) if (F < 0).any() else float('inf')
    return dict(trades=int(n), win_rate=round(float((F > 0).mean()), 3), gross_pts=round(float(pts.mean()), 3),
                net_pts=round(float(F.mean()), 3), net_ci95=[round(float(np.percentile(boot, 2.5)), 3),
                                                            round(float(np.percentile(boot, 97.5)), 3)],
                net_PF=round(pf, 3), net_usd_per_MES=round(5 * float(F.mean()), 2),
                net_bp=round(float((F / price).mean() * 1e4), 2), total_net_pts=round(float(F.sum()), 1))


def report(d):
    P = d.entry.values
    res = dict(all=stats(d.pts.values, P))
    res['stress'] = stats(d.pts.values, P, cost=STRESS)
    res['always_long'] = stats(d.move.values, P)
    rng = np.random.default_rng(17)
    sims = np.array([(rng.choice([-1, 1], len(d)) * d.move.values).mean() - COST for _ in range(10000)])
    res['random_direction'] = dict(mean=round(float(sims.mean()), 3), p95=round(float(np.percentile(sims, 95)), 3),
                                   rule_percentile=round(float((sims < res['all']['net_pts']).mean()), 3))
    y = d.date.str[:4]
    res['by_year'] = {k: stats(d.pts.values[y == k], P[y == k]) for k in sorted(set(y))}
    res['longs'] = stats(d.pts.values[d.dir > 0], P[d.dir > 0])
    res['shorts'] = stats(d.pts.values[d.dir < 0], P[d.dir < 0])
    big = d.r1_pct.abs() >= d.r1_pct.abs().median()
    res['big_10am_move'] = stats(d.pts.values[big], P[big]); res['small_10am_move'] = stats(d.pts.values[~big], P[~big])
    agree = np.sign(d.r12) == d.dir
    res['r12_agrees'] = stats(d.pts.values[agree], P[agree]); res['r12_disagrees'] = stats(d.pts.values[~agree], P[~agree])
    a = res['all']
    c = [a['trades'] >= 500, a['net_pts'] > 0 and a['net_ci95'][0] > 0,
         a['net_pts'] > res['always_long']['net_pts'] and a['net_pts'] > res['random_direction']['p95'],
         res['stress']['net_pts'] > 0, sum(s['net_pts'] > 0 for s in res['by_year'].values()) >= 3]
    res['verdict'] = ('PASS' if all(c) else 'FAIL') + \
        f' (>=500 {c[0]}, CI>0 {c[1]}, beats benchmarks {c[2]}, stress {c[3]}, 3/4 years {c[4]})'
    return res


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(OUT, exist_ok=True)
    if sys.argv[1] == 'run':
        f = f'{OUT}/run.json'
        if os.path.exists(f):
            sys.exit('H-003 already run once: ' + f)
        m = load(sys.argv[2:])
        d = days(m)
        d.to_csv(f'{OUT}/days.csv', index=False)
        res = report(d)
        res['data'] = dict(files=[os.path.basename(p) for p in sys.argv[2:]], first=str(m.index[0]), last=str(m.index[-1]))
        print(json.dumps(res, indent=1)); json.dump(res, open(f, 'w'), indent=1)
