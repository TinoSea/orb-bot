#!/usr/bin/env python3
"""
H-002 baselines (hypotheses.md, H-002 deepening protocol item 7), in-sample.

  python research/h002_baselines.py --data data/export --from 2023-01-01 --to 2025-06-30

B1 Random entries: per market, random in-session H1 bar opens, random direction, stop distance drawn from the
   strategy's own stops (in ATR(1H) units at entry), the strategy's target rule (nearest earlier 4H swing >= 1R,
   else 2R), 5-day max hold and Friday 16:30 NY close. A pool of random trades per market is simulated once and
   resampled (each run draws the strategy's trade count per market) to build the null distribution.
B2 Simple trend rule: at each new 4H bar, if flat: daily close above its 50-day average -> buy (below -> sell) at the
   next in-session H1 open; stop 1.5 x ATR(1H); target 2R; same max hold and Friday close.
Both use the replica's market data, calibrated spreads and commissions. Simplifications (stated): fills at bar open
plus spread; a bar touching stop and target counts as a stop; swaps are not charged; B1 trades are independent (no
one-position-at-a-time overlap). A calibration check re-simulates the strategy's own trades with this simulator.
"""
import argparse, os, sys, json
from datetime import timedelta
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ms_replica as R  # noqa: E402

EXCLUDED = {"BOND", "AGRI"}          # cost filter (research/cost_filter.md)
POOL, RUNS = 3000, 10000


class Sim:
    def __init__(self, data, lab, specs, markets, comm, smult, fx, prm):
        bars = R.load_bars(os.path.join(data, f"{lab}_M5.csv"))
        self.rep = R.Replica(bars, specs[lab], markets[lab], prm, 5000.0, comm.get(lab, 0.0), fx, smult.get(lab, 1.0))
        self.t = bars.index
        self.o, self.h, self.l, self.c = (bars[x].values for x in ("open", "high", "low", "close"))
        raw = bars["spread"].values.astype(float)
        if self.rep.spread_mult != 1.0:
            raw = np.maximum(raw, 1.0) * self.rep.spread_mult
        self.spr = raw * specs[lab].point
        self.comm = comm.get(lab, 0.0)
        ny = self.t - pd.Timedelta(hours=R.SERVER_MINUS_NY)
        self.fri_close = np.asarray((ny.weekday == 4) & (ny.hour * 60 + ny.minute >= prm.friday_close_ny))
        self.ns = self.t.values.astype("datetime64[s]").astype(np.int64)
        self.hold = prm.max_hold_bars * 3600

    def h1_opens(self, a, b):
        t = self.t
        first = np.r_[True, t.floor("1h")[1:] != t.floor("1h")[:-1]]
        idx = np.flatnonzero(first & (t >= pd.Timestamp(a)) & (t <= pd.Timestamp(b)))
        return np.array([i for i in idx if self.rep.in_session(t[i])])

    def atr1(self, i):
        j = self.rep.h1_j1(self.t[i])
        return self.rep.atr1[j] if j >= 1 else np.nan

    def trade(self, i0, d, risk, tp=None):
        """Returns (net R, exit index)."""
        o, h, l, spr = self.o, self.h, self.l, self.spr
        entry = o[i0] + spr[i0] if d > 0 else o[i0]
        stop = entry - d * risk
        if tp is None:
            tp = self.rep.find_target(d, entry, risk, self.rep.h4_k1(self.t[i0]))
        t_end = self.ns[i0] + self.hold
        n = len(o)
        j = i0
        while j < n:
            if j > i0 and (self.ns[j] >= t_end or (self.fri_close[j] and not self.rep.mkt.mode_24x7)):
                ex = o[j] if d > 0 else o[j] + spr[j]
                break
            if d > 0:
                if l[j] <= stop:
                    ex = min(stop, o[j]) if j > i0 else stop; break
                if h[j] >= tp:
                    ex = tp; break
            else:
                if h[j] + spr[j] >= stop:
                    ex = max(stop, o[j] + spr[j]) if j > i0 else stop; break
                if l[j] + spr[j] <= tp:
                    ex = tp; break
            j += 1
        else:
            j = n - 1; ex = self.c[j] if d > 0 else self.c[j] + spr[j]
        vpp = self.rep.vpp(self.t[i0])
        cost = 2 * self.comm / (risk * vpp) if vpp > 0 else 0.0
        return d * (ex - entry) / risk - cost, j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--variant", default="V0-registered")
    a = ap.parse_args()
    markets, specs = R.load_markets(), R.load_specs(os.path.join(a.data, "specs.csv"))
    comm, smult, fx, prm = R.load_commissions(), R.load_spread_mults(), R.fx_table(a.data, "M5"), R.Params()
    runs = pd.read_csv(os.path.join(HERE, "h002_runs.csv"))
    runs = runs[(runs.variant == a.variant) & (runs.base_tf == "M5") & (runs["from"] == a.start) & (runs["to"] == a.end)]
    rng = np.random.default_rng(2002)
    out, pools, strat = {}, {}, {}
    for lab in [m for m in markets if m in specs and m not in EXCLUDED]:
        row = runs[runs.label == lab].tail(1)
        if row.empty:
            continue
        tr = pd.read_csv(os.path.join(HERE, row.trades_file.iloc[0]))
        S = Sim(a.data, lab, specs, markets, comm, smult, fx, prm)
        idx_t = {t: i for i, t in enumerate(S.t)}
        # calibration: the strategy's own trades through this simulator
        ks, cal = [], []
        for _, x in tr.iterrows():
            i0 = idx_t.get(pd.Timestamp(x.entry_time))
            if i0 is None:
                continue
            d = 1 if x.side == "LONG" else -1
            risk = abs(x.entry - x.sl)
            atr = S.atr1(i0)
            if risk > 0 and atr > 0:
                ks.append(risk / atr)
            cal.append((x.R, S.trade(i0, d, risk, tp=x.tp)[0]))
        cal = np.array(cal)
        # B1 pool
        opens = S.h1_opens(a.start, a.end)
        pool = []
        for _ in range(POOL):
            i0 = int(rng.choice(opens)); d = int(rng.choice([-1, 1])); atr = S.atr1(i0)
            if not atr > 0:
                continue
            pool.append(S.trade(i0, d, float(rng.choice(ks)) * atr)[0])
        pools[lab] = np.array(pool); strat[lab] = tr.R.values
        # B2 trend rule
        daily = S.rep.b["close"].resample("1D").last().dropna()
        sma = daily.rolling(50).mean()
        h4 = np.flatnonzero(np.r_[True, S.t.floor("4h")[1:] != S.t.floor("4h")[:-1]] &
                            (S.t >= pd.Timestamp(a.start)) & (S.t <= pd.Timestamp(a.end)))
        oset = set(opens.tolist()); b2, free = [], -1
        for i in h4:
            if i <= free:
                continue
            day = S.t[i].normalize() - pd.Timedelta(days=1)
            dc, ds = daily.asof(day), sma.asof(day)
            if not (np.isfinite(dc) and np.isfinite(ds)) or dc == ds:
                continue
            d = 1 if dc > ds else -1
            j = next((k for k in opens[np.searchsorted(opens, i):][:200]), None)
            if j is None:
                continue
            atr = S.atr1(j)
            if not atr > 0:
                continue
            risk = 1.5 * atr
            entry = S.o[j] + S.spr[j] if d > 0 else S.o[j]
            r, ex = S.trade(j, d, risk, tp=entry + d * 2 * risk)
            b2.append(r); free = ex
        b2 = np.array(b2)
        null = np.array([rng.choice(pools[lab], len(strat[lab])).mean() for _ in range(2000)])
        out[lab] = dict(sector=markets[lab].sector, trades=len(strat[lab]), strategy_R=round(float(strat[lab].mean()), 3),
                        B1_random_mean=round(float(pools[lab].mean()), 3), B1_p95=round(float(np.percentile(null, 95)), 3),
                        strategy_pct_vs_B1=round(float((null < strat[lab].mean()).mean()), 3),
                        B2_trades=len(b2), B2_R=round(float(b2.mean()), 3) if len(b2) else None,
                        calib_corr=round(float(np.corrcoef(cal[:, 0], cal[:, 1])[0, 1]), 3) if len(cal) > 2 else None,
                        calib_mean_diff=round(float((cal[:, 1] - cal[:, 0]).mean()), 3) if len(cal) else None)
        print(lab, out[lab], flush=True)
    # portfolio
    allR = np.concatenate(list(strat.values()))
    nulls = np.array([np.concatenate([rng.choice(pools[k], len(strat[k])) for k in strat]).mean() for _ in range(RUNS)])
    out["PORTFOLIO"] = dict(trades=int(len(allR)), strategy_R=round(float(allR.mean()), 3),
                            B1_random_mean=round(float(nulls.mean()), 3), B1_p95=round(float(np.percentile(nulls, 95)), 3),
                            strategy_pct_vs_B1=round(float((nulls < allR.mean()).mean()), 3))
    print("PORTFOLIO", out["PORTFOLIO"])
    os.makedirs(os.path.join(HERE, "results", "h002"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "results", "h002", f"baselines_{a.variant}_{a.start}_{a.end}.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
