"""H-026: do Asia/London session extremes and fair value gaps mark New York reversals more than placebo levels?
Descriptive, no trading rule (research/hypotheses.md, H-026). Registered before this file was written.

  python3 h026.py dev  <US100_M1.csv> [more.csv ...]   # 2025-07-01..2026-03-31, run once
  python3 h026.py conf <US100_M1.csv> [more.csv ...]   # 2023-01-01..2025-06-30, once, only if dev is SUPPORTED

US100 1-minute bars from mt5/ExportData.mq5 (server = NY + 7 h), loaded with h020.load_m1. New York time throughout.
Writes results/h026/<mode>.json, <mode>_events.csv and <mode>.md. Refuses to run a mode twice.
Not financial advice: this measures how price behaves at levels; it is not a trading rule.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

PERIODS = {'dev': ('2025-07-01', '2026-03-31'), 'conf': ('2023-01-01', '2025-06-30')}
OUT = 'results/h026'
NY = 'America/New_York'
# Session definitions: timezone, (start, end) in minutes after local midnight. Primary = UTC (the indicator's).
SESSION_DEFS = {
    'utc': {'tz': 'UTC', 'asia': (1380, 420), 'london': (420, 780)},
    'ny': {'tz': NY, 'asia': (1200, 180), 'london': (180, 540)},
    'london_local': {'tz': 'Europe/London', 'asia': (1380, 420), 'london': (420, 780)},
}
PRIMARY = 'utc'
MIN_COVER = 0.60            # a session needs bars on >= 60% of its minutes
OPEN = 570                  # 09:30 New York, minutes after midnight
N_WIN = 150                 # touches counted on bars 09:30..11:59
HORIZON = 60                # outcome race length, minutes after the touch
N_GRID = N_WIN + HORIZON    # bars kept per day: 09:30..12:59
ATR_N = 14
MIN_GAP = 5.0
GAP_DAYS = 7
N_PLACEBO = 1000            # replicates for the primary test
N_PLACEBO_SECONDARY = 200   # replicates for reported-only families
MIN_TOUCHES = 150
MIN_EDGE = 0.05
AGG = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
EXTREMES = ('asia_high', 'asia_low', 'london_high', 'london_low')
MIDS = ('asia_mid', 'london_mid')


# ------------------------------------------------------------------ data
def load(paths: list[str]) -> pd.DataFrame:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from h020 import load_m1
    m = pd.concat([load_m1(p) for p in paths])
    return m[~m.index.duplicated(keep='last')].sort_index()


def session_levels(m1: pd.DataFrame, sdef: dict) -> pd.DataFrame:
    """Per New York date: Asia and London high/low/mid under one session definition (NaN if coverage too thin)."""
    idx = m1.index.tz_localize(NY, ambiguous='NaT', nonexistent='NaT')
    ok = ~idx.isna()
    loc = idx[ok].tz_convert(sdef['tz'])
    mins = np.asarray(loc.hour * 60 + loc.minute)
    ldate = loc.tz_localize(None).normalize()
    hi, lo = m1.high.to_numpy(float)[ok], m1.low.to_numpy(float)[ok]
    cols = {}
    for name in ('asia', 'london'):
        a, b = sdef[name]
        if a < b:
            ins, day = (mins >= a) & (mins < b), ldate
        else:   # spans midnight: the evening part belongs to the next date
            ins = (mins >= a) | (mins < b)
            day = ldate + pd.to_timedelta(np.where(mins >= a, 1, 0), unit='D')
        expected = (b - a) % 1440
        df = pd.DataFrame({'h': hi[ins], 'l': lo[ins], 'd': np.asarray(day)[ins]})
        g = df.groupby('d').agg(h=('h', 'max'), l=('l', 'min'), n=('h', 'size'))
        g = g[g.n >= MIN_COVER * expected]
        cols[f'{name}_high'], cols[f'{name}_low'] = g.h, g.l
        cols[f'{name}_mid'] = (g.h + g.l) / 2
    return pd.DataFrame(cols)


def atr5(m1: pd.DataFrame) -> pd.Series:
    """ATR(14) of clock-aligned 5-minute bars, indexed by bucket start, using only bars completed before that bucket."""
    b = m1.resample('5min').agg(AGG).dropna()
    pc = b.close.shift(1)
    tr = pd.concat([b.high - b.low, (b.high - pc).abs(), (b.low - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(ATR_N).mean().shift(1)


def gaps(m1: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Every fair value gap >= MIN_GAP on `tf` bars, with the close time of the candle that first closed beyond its far edge."""
    b = m1.resample(tf).agg(AGG).dropna()
    h, l, c = b.high.to_numpy(float), b.low.to_numpy(float), b.close.to_numpy(float)
    tclose = (b.index + pd.Timedelta(tf)).to_numpy()
    # A gap only matters up to GAP_DAYS after it forms, so look for its death within GAP_DAYS + 1 days.
    horizon = np.searchsorted(tclose, tclose + np.timedelta64(GAP_DAYS + 1, 'D'))
    rows = []
    for i in range(2, len(b)):
        if h[i] < l[i - 2]:
            glo, ghi, sup = h[i], l[i - 2], True
        elif l[i] > h[i - 2]:
            glo, ghi, sup = h[i - 2], l[i], False
        else:
            continue
        if ghi - glo < MIN_GAP:
            continue
        later = c[i + 1:horizon[i]]
        beyond = later > ghi if sup else later < glo
        j = int(np.argmax(beyond)) if beyond.any() else -1
        dead = tclose[i + 1 + j] if j >= 0 else np.datetime64('NaT')
        rows.append((tclose[i], glo, ghi, sup, dead, tf))
    return pd.DataFrame(rows, columns=['formed', 'lo', 'hi', 'supply', 'dead', 'tf'])


class Days:
    """Per-day arrays for the New York window plus the facts each level and split needs."""

    def __init__(self, m1: pd.DataFrame, a: str, b: str):
        atr = atr5(m1)
        rows, self.H, self.L, self.C, self.A = [], [], [], [], []
        dates = sorted({d for d in m1.index.normalize().unique()
                        if d.weekday() < 5 and pd.Timestamp(a) <= d <= pd.Timestamp(b)})
        for d in dates:
            t0 = d + pd.Timedelta(minutes=OPEN)
            w = m1.loc[t0:t0 + pd.Timedelta(minutes=N_GRID - 1)]
            first = w.loc[t0:t0 + pd.Timedelta(minutes=N_WIN - 1)]
            if t0 not in m1.index or len(first) < 140:
                continue
            mins = ((w.index - t0).total_seconds() // 60).astype(int).to_numpy()
            H, L, C = (np.full(N_GRID, np.nan) for _ in range(3))
            H[mins], L[mins], C[mins] = w.high.to_numpy(float), w.low.to_numpy(float), w.close.to_numpy(float)
            buckets = (t0 + pd.to_timedelta(np.arange(N_GRID), unit='min')).floor('5min')
            A = atr.reindex(buckets).to_numpy(float)
            atr0 = atr.get(t0, np.nan)
            if not atr0 > 0:
                continue
            rth = m1.loc[t0:d + pd.Timedelta(minutes=959)]
            b830 = m1.loc[d + pd.Timedelta(minutes=510):d + pd.Timedelta(minutes=514)]
            rows.append(dict(date=d, open=float(m1.loc[t0, 'open']), atr0=float(atr0),
                             rth_trend=float(abs(rth.close.iloc[-1] - rth.open.iloc[0]) / max(rth.high.max() - rth.low.min(), 1e-9)),
                             r830=float(b830.high.max() - b830.low.min()) if len(b830) else np.nan))
            self.H.append(H); self.L.append(L); self.C.append(C); self.A.append(A)
        self.info = pd.DataFrame(rows).set_index('date')
        self.H, self.L, self.C, self.A = map(np.array, (self.H, self.L, self.C, self.A))
        self.pos = {d: i for i, d in enumerate(self.info.index)}
        r = self.info.r830
        self.info['news_proxy'] = r > r.shift(1).rolling(60, min_periods=20).quantile(0.8)
        self.info['day_type'] = np.where(self.info.rth_trend >= 0.5, 'trend', 'range')

    def add_session_facts(self, lv: pd.DataFrame):
        """Overnight-range tercile and open-inside-London, from the primary session levels."""
        lv = lv.reindex(self.info.index)
        rng = pd.concat([lv.asia_high, lv.london_high], axis=1).max(axis=1) - \
            pd.concat([lv.asia_low, lv.london_low], axis=1).min(axis=1)
        ratio = rng / rng.shift(1).rolling(20, min_periods=10).mean()
        self.info['on_range_tercile'] = pd.qcut(ratio, 3, labels=['small', 'medium', 'large'])
        self.info['open_in_london'] = (self.info.open >= lv.london_low) & (self.info.open <= lv.london_high)


# ------------------------------------------------------------------ events
def evaluate(days: Days, i: int, level: float, kind: int) -> dict | None:
    """Touch and outcome of one level on day index i. kind = +1 for a high level, -1 for a low level."""
    H, L, C, A = days.H[i], days.L[i], days.C[i], days.A[i]
    hits = H[:N_WIN] >= level if kind == 1 else L[:N_WIN] <= level
    if not hits.any():
        return None
    t = int(np.argmax(hits))
    X = A[t]
    if not X > 0:
        return None
    rb, cb = level - kind * X, level + kind * X
    end = t + 1 + HORIZON
    sh, sl = H[t + 1:end], L[t + 1:end]
    if (kind == 1 and H[t] >= cb) or (kind == -1 and L[t] <= cb):
        outcome, bars = 'cont', 0
    else:
        rev = sl <= rb if kind == 1 else sh >= rb
        con = sh >= cb if kind == 1 else sl <= cb
        ir = int(np.argmax(rev)) if rev.any() else HORIZON
        ic = int(np.argmax(con)) if con.any() else HORIZON
        if ic <= ir and ic < HORIZON:
            outcome, bars = 'cont', ic + 1
        elif ir < HORIZON:
            outcome, bars = 'rev', ir + 1
        else:
            outcome, bars = 'timeout', HORIZON
    ev = dict(touch_min=t, X=float(X), outcome=outcome, bars=bars)
    for k in (5, 15, 30, 60):
        ev[f'move{k}'] = float(kind * (level - C[t + k]) / X) if t + k < N_GRID and not np.isnan(C[t + k]) else np.nan
    with np.errstate(all='ignore'):
        ev['best60'] = float(kind * (level - (np.nanmin(sl) if kind == 1 else np.nanmax(sh))) / X) if len(sl) else np.nan
        ev['worst60'] = float(kind * ((np.nanmax(sh) if kind == 1 else np.nanmin(sl)) - level) / X) if len(sh) else np.nan
    return ev


def live_levels(days: Days, lv: pd.DataFrame, names: tuple, gap_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Every live level: (day index, name, price, kind, distance from the open in 09:30 ATR units)."""
    rows = []
    lv = lv.reindex(days.info.index)
    for d, info in days.info.iterrows():
        i, o = days.pos[d], info.open
        for n in names:
            p = lv.at[d, n]
            if pd.isna(p):
                continue
            kind = 1 if p > o else -1 if p < o else 0
            if n.endswith('_high') and kind != 1 or n.endswith('_low') and kind != -1 or kind == 0:
                continue
            rows.append((i, n, float(p), kind, abs(p - o) / info.atr0))
        if gap_df is not None:
            t930 = d + pd.Timedelta(minutes=OPEN)
            g = gap_df[(gap_df.formed < d) & (gap_df.formed >= d - pd.Timedelta(days=GAP_DAYS))
                       & ~(gap_df.dead <= t930)]
            for r in g.itertuples():
                if r.lo > o:
                    rows.append((i, f'gap_{r.tf}', float(r.lo), 1, (r.lo - o) / info.atr0))
                elif r.hi < o:
                    rows.append((i, f'gap_{r.tf}', float(r.hi), -1, (o - r.hi) / info.atr0))
    return pd.DataFrame(rows, columns=['i', 'name', 'price', 'kind', 'dist'])


def run_levels(days: Days, levels: pd.DataFrame, placebo_rep: int | None = None) -> pd.DataFrame:
    out = []
    for r in levels.itertuples():
        ev = evaluate(days, r.i, r.price, r.kind)
        if ev is not None:
            ev.update(i=r.i, name=r.name, kind=r.kind, rep=placebo_rep)
            out.append(ev)
    return pd.DataFrame(out)


def placebo(days: Days, levels: pd.DataFrame, n_rep: int, seed: int) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    """Null distribution: each live level moved to a random other day at the same side and ATR-scaled distance."""
    rng = np.random.default_rng(seed)
    n_days = len(days.info)
    opens, atr0 = days.info.open.to_numpy(), days.info.atr0.to_numpy()
    rates, touch_rates, keep = np.full(n_rep, np.nan), np.full(n_rep, np.nan), []
    src = levels.i.to_numpy()
    for k in range(n_rep):
        j = rng.integers(0, n_days - 1, len(levels))
        j = j + (j >= src)                                  # never the level's own day
        pl = pd.DataFrame({'i': j, 'name': levels.name.to_numpy(), 'kind': levels.kind.to_numpy(),
                           'price': opens[j] + levels.kind.to_numpy() * levels.dist.to_numpy() * atr0[j]})
        ev = run_levels(days, pl, k)
        if len(ev):
            rates[k] = (ev.outcome == 'rev').mean()
            touch_rates[k] = len(ev) / len(pl)
            if k < 200:
                keep.append(ev)
    return rates, touch_rates, (pd.concat(keep, ignore_index=True) if keep else pd.DataFrame())


# ------------------------------------------------------------------ statistics
def boot_rate(ev: pd.DataFrame, n: int = 2000, seed: int = 26) -> list[float]:
    """95% interval of the reversal rate, resampling whole days."""
    if not len(ev):
        return [np.nan, np.nan]
    g = ev.groupby('i').outcome.agg(rev=lambda s: (s == 'rev').sum(), n='size')
    rev, cnt = g.rev.to_numpy(), g.n.to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(g), (n, len(g)))
    r = rev[idx].sum(1) / cnt[idx].sum(1)
    return [round(float(np.percentile(r, 2.5)), 4), round(float(np.percentile(r, 97.5)), 4)]


def family_test(days: Days, levels: pd.DataFrame, n_rep: int, seed: int) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    ev = run_levels(days, levels)
    if not len(ev):
        empty = dict(live_levels=int(len(levels)), touches=0, touch_rate=0.0, placebo_touch_rate=np.nan,
                     reversal_rate=np.nan, reversal_ci95=[np.nan, np.nan], placebo_mean=np.nan, placebo_p95=np.nan,
                     percentile_vs_placebo=np.nan, edge_pp=np.nan, placebo_reps=0)
        return empty, pd.DataFrame(columns=['i', 'name', 'kind', 'outcome', 'touch_min']), pd.DataFrame()
    rates, trates, pev = placebo(days, levels, n_rep, seed)
    rr = float((ev.outcome == 'rev').mean()) if len(ev) else np.nan
    pm, p95 = float(np.nanmean(rates)), float(np.nanpercentile(rates, 95))
    res = dict(live_levels=int(len(levels)), touches=int(len(ev)),
               touch_rate=round(len(ev) / max(len(levels), 1), 4),
               placebo_touch_rate=round(float(np.nanmean(trates)), 4),
               reversal_rate=round(rr, 4), reversal_ci95=boot_rate(ev),
               continuation_rate=round(float((ev.outcome == 'cont').mean()), 4) if len(ev) else np.nan,
               timeout_rate=round(float((ev.outcome == 'timeout').mean()), 4) if len(ev) else np.nan,
               placebo_mean=round(pm, 4), placebo_p95=round(p95, 4),
               percentile_vs_placebo=round(float(100 * np.nanmean(rates < rr)), 1),
               edge_pp=round(100 * (rr - pm), 2), placebo_reps=int(n_rep))
    if len(ev):
        for c in ('move5', 'move15', 'move30', 'move60', 'best60', 'worst60'):
            res[f'mean_{c}_X'] = round(float(ev[c].mean()), 3)
    return res, ev, pev


def verdict(r: dict) -> str:
    ok = r['touches'] >= MIN_TOUCHES and r['reversal_rate'] > r['placebo_p95'] and r['edge_pp'] >= 100 * MIN_EDGE
    return 'SUPPORTED' if ok else 'NOT SUPPORTED'


def splits(days: Days, ev: pd.DataFrame, pev: pd.DataFrame) -> dict:
    """Reversal rate by condition: real events vs placebo events tagged with the day they landed on."""
    out = {}

    def tag(e):
        e = e.copy()
        info = days.info.iloc[e.i.to_numpy()]
        e['touch_slot'] = np.where(e.touch_min < 30, '09:30-10:00', '10:00-12:00')
        for c in ('on_range_tercile', 'open_in_london', 'news_proxy', 'day_type'):
            e[c] = info[c].astype(str).to_numpy()
        return e
    if not len(ev):
        return out
    e, p = tag(ev), tag(pev) if len(pev) else None
    for c in ('touch_slot', 'on_range_tercile', 'open_in_london', 'news_proxy', 'day_type'):
        rows = {}
        for v, g in e.groupby(c):
            pr = p[p[c] == v] if p is not None else pd.DataFrame()
            rows[v] = dict(touches=int(len(g)), reversal_rate=round(float((g.outcome == 'rev').mean()), 4),
                           ci95=boot_rate(g), placebo_rate=round(float((pr.outcome == 'rev').mean()), 4) if len(pr) else None)
        out[c + (' (hindsight)' if c == 'day_type' else '')] = rows
    return out


# ------------------------------------------------------------------ the study
def study(m1: pd.DataFrame, a: str, b: str, n_rep: int = N_PLACEBO, n_rep2: int = N_PLACEBO_SECONDARY,
          secondary: bool = True, seed: int = 26) -> tuple[dict, pd.DataFrame]:
    days = Days(m1, a, b)
    lvs = {k: session_levels(m1, s) for k, s in SESSION_DEFS.items()}
    days.add_session_facts(lvs[PRIMARY])
    out = dict(period=[a, b], days=int(len(days.info)), first_day=str(days.info.index.min().date()),
               last_day=str(days.info.index.max().date()))
    prim_levels = live_levels(days, lvs[PRIMARY], EXTREMES)
    prim, ev, pev = family_test(days, prim_levels, n_rep, seed)
    prim['verdict'] = verdict(prim)
    out['primary'] = prim
    out['verdict'] = prim['verdict']
    out['splits'] = splits(days, ev, pev)
    ev['family'] = 'extremes_' + PRIMARY
    events = [ev]
    if secondary:
        rep = {}
        for n in EXTREMES:
            rep[n] = family_test(days, prim_levels[prim_levels.name == n], n_rep2, seed + 1)[0]
        r, e2, _ = family_test(days, live_levels(days, lvs[PRIMARY], MIDS), n_rep2, seed + 2)
        rep['mid_lines'] = r
        e2['family'] = 'mids'
        events.append(e2)
        G = pd.concat([gaps(m1, '5min'), gaps(m1, '15min')], ignore_index=True)
        gl = live_levels(days, lvs[PRIMARY], (), G)
        for tf in ('gap_5min', 'gap_15min'):
            r, e3, _ = family_test(days, gl[gl.name == tf], n_rep2, seed + 3)
            rep[tf] = r
            e3['family'] = tf
            events.append(e3)
        for k in SESSION_DEFS:
            if k != PRIMARY:
                r, _, _ = family_test(days, live_levels(days, lvs[k], EXTREMES), n_rep2, seed + 4)
                rep[f'extremes_sessions_{k}'] = r
        out['reported_only'] = rep
    ev_all = pd.concat(events, ignore_index=True)
    ev_all['date'] = days.info.index[ev_all.i.to_numpy()].date
    return out, ev_all


def summary_md(mode: str, r: dict) -> str:
    p = r['primary']
    lines = [f"# H-026 {mode}: {r['period'][0]} → {r['period'][1]}", '',
             f"**Verdict: {r['verdict']}** ({r['days']} days, {r['first_day']} → {r['last_day']})", '',
             '## Primary: Asia/London highs and lows (UTC sessions)', '',
             '| | Real levels | Placebo levels |', '|---|---|---|',
             f"| Touched in 09:30-12:00 | {p['touch_rate']:.1%} of {p['live_levels']} | {p['placebo_touch_rate']:.1%} |",
             f"| Reversal rate (X before −X, 60 min) | {p['reversal_rate']:.1%} (95% {p['reversal_ci95'][0]:.1%}–{p['reversal_ci95'][1]:.1%}) | mean {p['placebo_mean']:.1%}, 95th pct {p['placebo_p95']:.1%} |",
             f"| Touches | {p['touches']} (needs ≥ {MIN_TOUCHES}) | |",
             f"| Edge | {p['edge_pp']:+.1f} pp (needs ≥ +{100 * MIN_EDGE:.0f}) | real at {p['percentile_vs_placebo']:.1f}th pct |", '']
    if 'reported_only' in r:
        lines += ['## Reported only', '', '| Family | Touches | Reversal | Placebo mean | Pct vs placebo |', '|---|---|---|---|---|']
        for k, v in r['reported_only'].items():
            lines.append(f"| {k} | {v['touches']} | {v['reversal_rate']:.1%} | {v['placebo_mean']:.1%} | {v['percentile_vs_placebo']:.0f} |")
        lines.append('')
    if r.get('splits'):
        lines += ['## Splits (primary family; reported only)', '', '| Condition | Value | Touches | Reversal (95%) | Placebo |', '|---|---|---|---|---|']
        for c, rows in r['splits'].items():
            for v, s in rows.items():
                pr = f"{s['placebo_rate']:.1%}" if s['placebo_rate'] is not None else '–'
                lines.append(f"| {c} | {v} | {s['touches']} | {s['reversal_rate']:.1%} ({s['ci95'][0]:.0%}–{s['ci95'][1]:.0%}) | {pr} |")
    lines += ['', '*Descriptive study, not a trading rule. Not financial advice.*']
    return '\n'.join(lines)


if __name__ == '__main__':
    if len(sys.argv) < 3 or sys.argv[1] not in PERIODS:
        sys.exit(__doc__)
    mode, paths = sys.argv[1], [os.path.abspath(p) for p in sys.argv[2:]]
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(OUT, exist_ok=True)
    f = f'{OUT}/{mode}.json'
    if os.path.exists(f):
        sys.exit(f'{mode} already run once: {f}')
    if mode == 'conf':
        dev = f'{OUT}/dev.json'
        if not os.path.exists(dev) or json.load(open(dev))['verdict'] != 'SUPPORTED':
            sys.exit('Confirmation runs only after a SUPPORTED development result (as registered).')
    res, ev = study(load(paths), *PERIODS[mode])
    json.dump(res, open(f, 'w'), indent=1, default=str)
    ev.to_csv(f'{OUT}/{mode}_events.csv', index=False)
    open(f'{OUT}/{mode}.md', 'w').write(summary_md(mode, res))
    print(summary_md(mode, res))
