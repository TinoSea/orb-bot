"""H-008: opening-range break-and-retest on Nasdaq (research/hypotheses.md, H-008).

  python3 h008.py gate                    # 2026-08-12 Asia session trace
  python3 h008.py dev                     # V0-V3 on the development period, picks one
  python3 h008.py second V?               # the pick on 2026-04-01..2026-10-16
  python3 h008.py final V? <M1 csv>       # ONCE, on 2023-01-01..2025-06-30
"""
import sys, os, json
import numpy as np, pandas as pd

COST = 0.5625
DEV = ('2025-07-01', '2026-03-31')
SECOND = ('2026-04-01', '2026-10-16')
FINAL = ('2023-01-01', '2025-06-30')
OUT = 'results/h008'
H = lambda h, m=0: h * 60 + m      # minutes after the session date's midnight

# session: (range start, range end, entry end, flat) in minutes from the session date's midnight
SESS = {'asia': (H(18), H(19), H(25), H(24 + 15, 55)),
        'ny': (H(9, 30), H(9, 45), H(11, 30), H(15, 55))}
VARIANTS = {'V0': ('asia', 'fixed'), 'V1': ('ny', 'fixed'), 'V2': ('asia', 'range'), 'V3': ('ny', 'range')}


def load_m1(path='/home/claude/h005data/US100_M1.csv'):
    m = pd.read_csv(path)
    t = pd.to_datetime(m.time, format='%Y.%m.%d %H:%M') - pd.Timedelta(hours=7)
    mins = (t.astype('datetime64[ns]').astype('int64') // 60_000_000_000).to_numpy()
    return dict(t=mins, o=m.open.to_numpy(float), h=m.high.to_numpy(float), l=m.low.to_numpy(float),
                c=m.close.to_numpy(float), dates=sorted(set(t.dt.normalize())))


def session(M, date, variant, through=0.0, slip=0.0, trace=False):
    """Returns (trade dict or None, log)."""
    sess, mode = VARIANTS[variant]
    rs, re, ee, fl = SESS[sess]
    base = int(pd.Timestamp(date).value // 60_000_000_000)
    t, o, h, l, c = M['t'], M['o'], M['h'], M['l'], M['c']
    a, b = np.searchsorted(t, base + rs), np.searchsorted(t, base + re)
    log = []
    if b - a < 0.5 * (re - rs):
        return None, ['no range data']
    RH, RL = h[a:b].max(), l[a:b].min()
    rng = RH - RL
    if mode == 'fixed':
        S, TG = 37.5, 75.0
    else:
        if rng < 5 or rng > 150:
            return None, [f'range {rng:.1f} outside 5-150']
        S, TG = rng, 2 * rng
    if trace: log.append(f'range {RH:.2f} / {RL:.2f} ({rng:.1f} pts); stop {S:.2f} target {TG:.2f}')
    end = np.searchsorted(t, base + fl, side='right')
    d, edge, pos = 0, None, None
    cur5, b5h, b5l, b5c = None, None, None, None
    for j in range(b, end):
        tm = t[j] - base
        # 5-minute bar aggregation (bars aligned to multiples of 5 minutes from the range end)
        k5 = (tm - re) // 5
        if pos is None and cur5 is not None and k5 != cur5 and b5c is not None:
            close_t = re + (cur5 + 1) * 5
            if close_t <= ee:
                if b5c > RH and d != 1:
                    d, edge = 1, RH
                    if trace: log.append(f'{close_t // 60 % 24:02d}:{close_t % 60:02d} break up (5-min close {b5c:.2f}) -> buy limit {RH:.2f}')
                elif b5c < RL and d != -1:
                    d, edge = -1, RL
                    if trace: log.append(f'{close_t // 60 % 24:02d}:{close_t % 60:02d} break down (5-min close {b5c:.2f}) -> sell limit {RL:.2f}')
        if k5 != cur5:
            cur5, b5h, b5l = k5, h[j], l[j]
        b5c = c[j]
        if pos is None:
            if d == 0 or tm >= ee:
                continue
            # limit at the edge, only after the break bar has closed (d set before this bar)
            touched = (l[j] <= edge) if d > 0 else (h[j] >= edge)
            if not touched:
                continue
            fill = min(edge, o[j]) if d > 0 else max(edge, o[j])
            pos = dict(date=str(pd.Timestamp(date).date()), variant=variant, dir=d, fill=fill, entry_min=int(tm),
                       stop=fill - d * S, target=fill + d * TG, risk=S, range=rng)
            if trace: log.append(f'{tm // 60 % 24:02d}:{tm % 60:02d} FILLED {"LONG" if d > 0 else "SHORT"} at {fill:.2f}')
            if (l[j] <= pos['stop']) if d > 0 else (h[j] >= pos['stop']):
                pos.update(R=-(S + slip) / S, how='stop', exit_min=int(tm))
                return pos, log
            continue
        hs = (l[j] <= pos['stop']) if d > 0 else (h[j] >= pos['stop'])
        ht = (h[j] >= pos['target'] + through) if d > 0 else (l[j] <= pos['target'] - through)
        if hs:
            ex = (min(pos['stop'], o[j]) if d > 0 else max(pos['stop'], o[j])) - d * slip
            pos.update(R=d * (ex - pos['fill']) / S, how='stop', exit_min=int(tm))
        elif ht:
            pos.update(R=TG / S, how='target', exit_min=int(tm))
        elif j == end - 1:
            pos.update(R=d * (c[j] - pos['fill']) / S, how='time', exit_min=int(tm))
        if 'R' in pos:
            if trace: log.append(f"{tm // 60 % 24:02d}:{tm % 60:02d} EXIT {pos['how']}  R {pos['R']:+.2f}")
            return pos, log
    if pos is not None:
        pos.update(R=d * (c[end - 1] - pos['fill']) / S, how='time', exit_min=int(t[end - 1] - base))
        return pos, log
    return None, log


def run(M, a, b, variant, **kw):
    out = []
    for date in M['dates']:
        if pd.Timestamp(a) <= date <= pd.Timestamp(b):
            tr, _ = session(M, date, variant, **kw)
            if tr:
                out.append(tr)
    return pd.DataFrame(out)


def null_dist(M, tr, n=10000, seed=29, per=60):
    rng = np.random.default_rng(seed)
    t, o, h, l, c = M['t'], M['o'], M['h'], M['l'], M['c']
    P = []
    for _, x in tr.iterrows():
        sess, _ = VARIANTS[x.variant]
        rs, re, ee, fl = SESS[sess]
        base = int(pd.Timestamp(x.date).value // 60_000_000_000)
        a, b, end = np.searchsorted(t, base + re), np.searchsorted(t, base + ee), np.searchsorted(t, base + fl, side='right')
        rs_ = []
        for j0 in rng.integers(a, max(a + 1, b), per):
            e = o[j0]; d = int(x.dir)
            st, tg = e - d * x.risk, e + (x.target - x.fill)
            R = None
            for j in range(j0, end):
                if (l[j] <= st) if d > 0 else (h[j] >= st):
                    R = -1.0; break
                if j > j0 and ((h[j] >= tg) if d > 0 else (l[j] <= tg)):
                    R = d * (tg - e) / x.risk; break
            rs_.append(R if R is not None else d * (c[end - 1] - e) / x.risk)
        P.append(rs_)
    P = np.array(P)
    return np.array([P[np.arange(len(P)), rng.integers(0, per, len(P))].mean() for _ in range(n)])


def stats(tr, cost=COST):
    if tr.empty:
        return dict(trades=0)
    R = tr.R.values; F = R - cost / tr.risk.values
    pf = lambda x: float(x[x > 0].sum() / -x[x < 0].sum()) if (x < 0).any() else float('inf')
    rng = np.random.default_rng(3)
    boot = [rng.choice(F, len(F)).mean() for _ in range(5000)]
    return dict(trades=int(len(R)), win_rate=float((R > 0).mean()), gross_R=float(R.mean()), fut_R=float(F.mean()),
                fut_PF=pf(F), fut_R_ci95=[float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                longs=int((tr.dir > 0).sum()), shorts=int((tr.dir < 0).sum()),
                exits={k: int(v) for k, v in tr.how.value_counts().items()}, median_risk=float(tr.risk.median()))


def full(M, a, b, v):
    tr = run(M, a, b, v)
    s = stats(tr)
    if s['trades']:
        s['stress'] = stats(run(M, a, b, v, through=0.25, slip=1.0), cost=2 * COST)
        nl = null_dist(M, tr)
        s.update(null_mean=float(nl.mean()), null_p95=float(np.percentile(nl, 95)),
                 percentile_vs_null=float((nl < s['gross_R']).mean()))
        c = [s['trades'] >= 100, s['fut_PF'] >= 1.2, s['fut_R'] >= 0.10, s['gross_R'] > s['null_p95'], s['stress']['fut_R'] > 0]
        s['verdict'] = ('PASS' if all(c) else 'FAIL') + f' (>=100 {c[0]}, PF {c[1]}, exp {c[2]}, null {c[3]}, stress {c[4]})'
    return tr, s


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    mode = sys.argv[1]
    if mode == 'final':
        f = f'{OUT}/final.json'
        if os.path.exists(f):
            sys.exit('Final test already run once: ' + f)
        M = load_m1(sys.argv[3])
    else:
        M = load_m1()
    if mode == 'gate':
        for v in ('V0', 'V2'):
            tr, log = session(M, '2026-08-12', v, trace=True)
            print(f'===== 2026-08-12 Asia {v}'); print('\n'.join('   ' + x for x in log))
    elif mode == 'dev':
        res = {}
        for v in VARIANTS:
            tr = run(M, *DEV, v)
            tr.to_csv(f'{OUT}/dev_{v}_trades.csv', index=False)
            res[v] = stats(tr); print(v, json.dumps(res[v]))
        ok = {v: s for v, s in res.items() if s['trades'] >= 60}
        res['pick'] = max(ok, key=lambda v: ok[v]['fut_R']) if ok else None
        print('PICK', res['pick']); json.dump(res, open(f'{OUT}/dev.json', 'w'), indent=1)
    else:
        v = sys.argv[2]
        a, b = SECOND if mode == 'second' else FINAL
        tr, s = full(M, a, b, v)
        tr.to_csv(f'{OUT}/{mode}_{v}_trades.csv', index=False)
        s['period'] = [a, b]; s['variant'] = v
        print(json.dumps(s, indent=1)); json.dump(s, open(f'{OUT}/{mode}.json', 'w'), indent=1)
