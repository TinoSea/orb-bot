"""H-010: New York opening-range break, entry on the break close, up to two trades a day (research/hypotheses.md, H-010).

  python3 h010.py trace YYYY-MM-DD <M1 csv> [<M1 csv> ...]   # one day, step by step
  python3 h010.py run <M1 csv> [<M1 csv> ...]                # 2023-01-01..2026-10-16, reported by year

Data: FP Markets US100 1-minute bars exported from MT5 (columns time, open, high, low, close; server time = NY + 7 h).
Several files (e.g. the 2022-2025 and 2025-2026 exports) are merged; duplicate minutes keep the first copy.
"""
import sys, os, json
import numpy as np, pandas as pd

COST = 0.5625                       # futures estimate, points per round trip (same as H-008/H-009)
PERIOD = ('2023-01-01', '2026-10-16')
JUDGE = ('2023-01-01', '2024-12-31')  # the pass/fail period; 2025-26 is a check only
OUT = 'results/h010'
RS, RE = 9 * 60 + 30, 9 * 60 + 45   # opening range 09:30-09:45 New York
LAST_ENTRY = 11 * 60 + 30           # no new entries after 11:30 (a 5-minute bar closing at 11:30 still counts)
FLAT = 12 * 60                      # anything open is closed at 12:00 (close of the 11:59 bar)


def load_m1(paths):
    m = pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)
    t = pd.to_datetime(m.time, format='%Y.%m.%d %H:%M') - pd.Timedelta(hours=7)
    m = m.assign(t=t).drop_duplicates('t').sort_values('t')
    mins = (m.t.astype('datetime64[ns]').astype('int64') // 60_000_000_000).to_numpy()
    return dict(t=mins, o=m.open.to_numpy(float), h=m.high.to_numpy(float), l=m.low.to_numpy(float),
                c=m.close.to_numpy(float), dates=sorted(set(m.t.dt.normalize())))


def hhmm(x):
    return f'{x // 60 % 24:02d}:{x % 60:02d}'


def manage(M, j0, d, fill, S, end, slip=0.0):
    """Run one position from 1-minute bar j0 (the entry bar) until stop, target or 12:00.
    A bar touching both stop and target counts as a loss. Returns (R, how, exit index)."""
    t, o, h, l, c = M['t'], M['o'], M['h'], M['l'], M['c']
    stop, tgt = fill - d * S, fill + d * 2 * S
    for j in range(j0, end):
        if (l[j] <= stop) if d > 0 else (h[j] >= stop):
            ex = (min(stop, o[j]) if d > 0 else max(stop, o[j])) - d * slip
            return d * (ex - fill) / S, 'stop', j
        if (h[j] >= tgt) if d > 0 else (l[j] <= tgt):
            return 2.0, 'target', j
    return d * (c[end - 1] - fill) / S, 'time', end - 1


def day(M, date, slip=0.0, trace=False):
    t, o, h, l, c = M['t'], M['o'], M['h'], M['l'], M['c']
    base = int(pd.Timestamp(date).value // 60_000_000_000)
    a, b = np.searchsorted(t, base + RS), np.searchsorted(t, base + RE)
    end = np.searchsorted(t, base + FLAT)          # bars before 12:00
    log, trades = [], []
    if b - a < 0.5 * (RE - RS) or end - b < 30:
        return trades, ['no range data']
    RH, RL = h[a:b].max(), l[a:b].min()
    S = RH - RL
    if S < 5 or S > 150:
        return trades, [f'range {S:.1f} outside 5-150']
    if trace: log.append(f'range {RH:.2f} / {RL:.2f} ({S:.1f} pts): stop {S:.1f}, target {2 * S:.1f}')

    # closed 5-minute bars from 09:45: bar k = minutes [RE+5k, RE+5k+5); its close is the last 1-minute close in it
    k5 = (t[b:end] - base - RE) // 5
    closes = []                                   # (close time in minutes after midnight, close price, last bar index)
    for k in np.unique(k5):
        idx = b + np.flatnonzero(k5 == k)
        closes.append((RE + 5 * int(k) + 5, c[idx[-1]], int(idx[-1])))

    d, after = 0, -1                              # direction; earliest 1-minute index a new signal may come from
    for n in (1, 2):
        sig = None
        for ct, cl, jl in closes:
            if ct > LAST_ENTRY:
                break
            if jl <= after:
                continue
            if d == 0 and (cl > RH or cl < RL):
                sig = (ct, cl, jl); d = 1 if cl > RH else -1; break
            if d != 0 and ((cl > RH) if d > 0 else (cl < RL)):
                sig = (ct, cl, jl); break
        if sig is None or sig[2] + 1 >= end:
            break
        ct, cl, jl = sig
        j0 = jl + 1                                # market order on the close: filled at the next 1-minute open
        fill = o[j0]
        R, how, jx = manage(M, j0, d, fill, S, end, slip)
        tr = dict(date=str(pd.Timestamp(date).date()), n=n, dir=d, signal=hhmm(ct), fill=fill, entry_min=int(t[j0] - base),
                  risk=S, R=R, how=how, exit_min=int(t[jx] - base))
        trades.append(tr)
        if trace:
            log.append(f'{hhmm(ct)} 5-min close {cl:.2f} {"above" if d > 0 else "below"} the range -> '
                       f'trade {n} {"LONG" if d > 0 else "SHORT"} filled {fill:.2f} at {hhmm(tr["entry_min"])}')
            log.append(f'{hhmm(tr["exit_min"])} exit {how}  R {R:+.2f}')
        if how != 'stop':
            break
        after = jx
    return trades, log


def run(M, a, b, **kw):
    out = []
    for date in M['dates']:
        if pd.Timestamp(a) <= date <= pd.Timestamp(b) and date.weekday() < 5:
            out += day(M, date, **kw)[0]
    return pd.DataFrame(out)


def null_mean(M, tr, n=5000, per=40, seed=31):
    """Random-entry comparison (descriptive): same days, directions and bracket; entry at a random minute
    09:45-11:30; flat 12:00."""
    rng = np.random.default_rng(seed)
    t, o = M['t'], M['o']
    P = []
    for _, x in tr.iterrows():
        base = int(pd.Timestamp(x.date).value // 60_000_000_000)
        a, b = np.searchsorted(t, base + RE), np.searchsorted(t, base + LAST_ENTRY)
        end = np.searchsorted(t, base + FLAT)
        P.append([manage(M, j, int(x.dir), o[j], x.risk, end)[0] for j in rng.integers(a, max(a + 1, b), per)])
    P = np.array(P)
    sims = np.array([P[np.arange(len(P)), rng.integers(0, per, len(P))].mean() for _ in range(n)])
    return float(sims.mean()), float(np.percentile(sims, 95))


def stats(tr, cost=COST):
    if tr.empty:
        return dict(trades=0)
    R = tr.R.values; F = R - cost / tr.risk.values
    pf = lambda x: float(x[x > 0].sum() / -x[x < 0].sum()) if (x < 0).any() else float('inf')
    rng = np.random.default_rng(3)
    boot = [rng.choice(F, len(F)).mean() for _ in range(5000)]
    return dict(trades=int(len(R)), win_rate=round(float((R > 0).mean()), 3), gross_R=round(float(R.mean()), 3),
                fut_R=round(float(F.mean()), 3), fut_PF=round(pf(F), 2),
                fut_R_ci95=[round(float(np.percentile(boot, 2.5)), 3), round(float(np.percentile(boot, 97.5)), 3)],
                longs=int((tr.dir > 0).sum()), shorts=int((tr.dir < 0).sum()),
                exits={k: int(v) for k, v in tr.how.value_counts().items()})


def report(M, tr, st):
    tr = tr.assign(year=tr.date.str[:4])
    res = {}
    for name, sub in [('judge_2023_24', tr[tr.date <= JUDGE[1]]), ('all_2023_26', tr)] + \
                     [(y, g) for y, g in tr.groupby('year')]:
        s = stats(sub)
        for k in (1, 2):
            s[f'trade{k}'] = stats(sub[sub.n == k])
        s['long'] = stats(sub[sub.dir > 0]); s['short'] = stats(sub[sub.dir < 0])
        res[name] = s
    j = tr[tr.date <= JUDGE[1]]
    res['judge_2023_24']['random_entry_mean_R'], res['judge_2023_24']['random_entry_p95'] = null_mean(M, j)
    st = st.assign(year=st.date.str[:4])
    res['judge_2023_24']['stress'] = stats(st[st.date <= JUDGE[1]], cost=2 * COST)
    jj = res['judge_2023_24']
    ok = jj['trades'] >= 300 and jj['fut_R'] > 0
    res['verdict'] = ('PASS' if ok else 'FAIL') + f" (2023-24: {jj['trades']} trades, {jj['fut_R']:+.3f}R after costs)"
    return res


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(OUT, exist_ok=True)
    mode = sys.argv[1]
    if mode == 'trace':
        M = load_m1(sys.argv[3:])
        tr, log = day(M, sys.argv[2], trace=True)
        print(f'===== {sys.argv[2]}'); print('\n'.join('   ' + x for x in log))
    elif mode == 'run':
        f = f'{OUT}/run.json'
        if os.path.exists(f):
            sys.exit('H-010 already run once: ' + f)
        M = load_m1(sys.argv[2:])
        tr = run(M, *PERIOD)
        st = run(M, *PERIOD, slip=1.0)
        tr.to_csv(f'{OUT}/trades.csv', index=False)
        res = report(M, tr, st)
        res['data'] = dict(files=[os.path.basename(p) for p in sys.argv[2:]],
                           first=str(M['dates'][0].date()), last=str(M['dates'][-1].date()))
        print(json.dumps(res, indent=1)); json.dump(res, open(f, 'w'), indent=1)
