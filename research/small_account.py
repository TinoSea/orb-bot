#!/usr/bin/env python3
"""
H-002 amendment 16: can a small account trade the gold strategy safely?

Takes a trade list written by ms_replica.py (any deposit; it is converted to per-ounce terms)
and replays it on a real-dollar account with the broker's lot granularity:

  P1 textbook : 1% risk, skip a trade if the smallest position would risk more than 1%
  P2 min lot  : at least the smallest position on every signal, more only when 1% allows
  P3 capped   : like P2, but skip if the smallest position would risk more than --cap %

Runs: historical prices, rescaled to --price (today's gold), plus an extra cost per ounce,
and a Monte Carlo of random trade orderings. Margin and stop-out are checked at several leverages.

  python research/small_account.py --trades research/results/h002/gate0/replica_XAUUSD_M1_IS.csv \
      --deposit 200 --price 4190 --stress 0.30 --out research/small_account.md

Limitation: the trade list comes from a run that took every signal. When a policy skips a trade,
the real EA would be flat during that time and could take a setup the list doesn't contain. For the
exact answer, run ms_replica.py with --min-lot-policy on the raw bars (same rules as here).

Not financial advice. In-sample evidence only.
"""
from __future__ import annotations

import argparse
import math

import numpy as np
import pandas as pd

OZ_PER_LOT = 100.0        # XAUUSD.r contract size (research/contracts.md)
MIN_OZ = 1.0              # 0.01 lot = 1 oz; CME 1-Ounce Gold is the same size
STEP_OZ = 1.0             # volume step 0.01 lot = 1 oz
STOP_OUT = 0.50           # margin level at which the broker closes positions (assumed 50%)


def per_ounce(tr: pd.DataFrame) -> pd.DataFrame:
    """Everything a trade did, per ounce held, in price units (= USD for gold)."""
    oz = tr["lots"] * OZ_PER_LOT
    d = np.where(tr["side"] == "LONG", 1.0, -1.0)
    risk = (tr["entry"] - tr["sl"]).abs()
    out = pd.DataFrame({
        "entry_time": pd.to_datetime(tr["entry_time"]),
        "side": tr["side"],
        "price": tr["entry"],
        "risk": risk,                                     # stop distance, $ per oz
        "move": (tr["exit"] - tr["entry"]) * d,           # gross $ per oz
        "swap": tr["swap"] / oz,
        "comm": tr["commission"] / oz,                    # round trip, $ per oz
        # worst open loss, $ per oz. The replica's mae_R (before v1.12) counted the bar's extreme even when the
        # stop filled inside that bar, overstating it on stopped trades; cap it at the larger of the stop
        # distance and the actual exit loss (a gap through the stop still shows in full).
        "mae": np.minimum(tr["mae_R"] * risk, np.maximum(risk, -(tr["exit"] - tr["entry"]) * d)),
        "reason": tr["reason"],
    })
    return out


def rescale(po: pd.DataFrame, price: float | None) -> pd.DataFrame:
    """Move every trade to a common gold price, keeping its size in % of price.
    Commission is per lot, so it does not scale."""
    if not price:
        return po.copy()
    f = price / po["price"]
    out = po.copy()
    for c in ("risk", "move", "swap", "mae"):
        out[c] = po[c] * f
    out["price"] = price
    return out


def size_oz(balance: float, risk: float, policy: str, cap_pct: float) -> float:
    """Ounces to trade (0 = skip)."""
    if balance <= 0:
        return 0.0
    one_pct = math.floor(balance * 0.01 / risk / STEP_OZ + 1e-9) * STEP_OZ
    if one_pct >= MIN_OZ:
        return one_pct
    if policy == "P1":
        return 0.0
    if policy == "P3" and MIN_OZ * risk > balance * cap_pct / 100.0:
        return 0.0
    return MIN_OZ


def replay(po: pd.DataFrame, deposit: float, policy: str, cap_pct: float, stress: float,
           leverages=(20, 100, 500)) -> tuple[pd.DataFrame, dict]:
    bal, peak, max_dd, low = deposit, deposit, 0.0, deposit
    rows = []
    margin_breach = {L: 0 for L in leverages}     # margin for the position > 50% of equity at entry
    stop_outs = {L: 0 for L in leverages}         # worst open loss would hit the stop-out level
    for r in po.itertuples(index=False):
        oz = size_oz(bal, r.risk, policy, cap_pct)
        if oz == 0:
            rows.append({"entry_time": r.entry_time, "taken": False, "oz": 0, "risk_pct": np.nan,
                         "pnl": 0.0, "R": np.nan, "balance": bal})
            continue
        notional = oz * r.price
        for L in leverages:
            m = notional / L
            if m > 0.5 * bal:
                margin_breach[L] += 1
            if (bal - oz * r.mae) < STOP_OUT * m:
                stop_outs[L] += 1
        risk_usd = oz * r.risk
        pnl = oz * (r.move + r.swap - r.comm - stress)
        bal += pnl
        peak = max(peak, bal)
        low = min(low, bal)
        max_dd = max(max_dd, (peak - bal) / peak)
        rows.append({"entry_time": r.entry_time, "taken": True, "oz": oz,
                     "risk_pct": 100 * risk_usd / (bal - pnl), "pnl": pnl, "R": pnl / risk_usd, "balance": bal})
    path = pd.DataFrame(rows)
    taken = path[path["taken"]]
    years = max((po["entry_time"].max() - po["entry_time"].min()).days / 365.25, 1e-9)
    stats = {
        "signals": len(po), "taken": len(taken),
        "median_risk_%": round(taken["risk_pct"].median(), 1) if len(taken) else np.nan,
        "max_risk_%": round(taken["risk_pct"].max(), 1) if len(taken) else np.nan,
        "expectancy_R": round(taken["R"].mean(), 3) if len(taken) else np.nan,
        "end_balance": round(bal, 2), "lowest_balance": round(low, 2),
        "max_drawdown_%": round(100 * max_dd, 1),
        "usd_per_month": round(taken["pnl"].sum() / years / 12, 2) if len(taken) else 0.0,
        **{f"margin>50%eq_1:{L}": v for L, v in margin_breach.items()},
        **{f"stop_out_1:{L}": v for L, v in stop_outs.items()},
    }
    return path, stats


def monte_carlo(po: pd.DataFrame, deposit: float, policy: str, cap_pct: float, stress: float,
                n_trades: int, n_sims: int, target: float, seed: int = 7) -> dict:
    rng = np.random.default_rng(seed)
    risk, net = po["risk"].values, (po["move"] + po["swap"] - po["comm"]).values - stress
    half, ends, dds, reach = 0, [], [], 0
    for _ in range(n_sims):
        idx = rng.integers(0, len(po), n_trades)
        bal, peak, dd, hit_half, hit_target = deposit, deposit, 0.0, False, False
        for i in idx:
            oz = size_oz(bal, risk[i], policy, cap_pct)
            if oz:
                bal += oz * net[i]
            peak = max(peak, bal)
            dd = max(dd, (peak - bal) / peak) if peak > 0 else 1.0
            hit_half |= bal <= deposit / 2
            hit_target |= bal >= target
            if bal <= 0:
                break
        half += hit_half
        reach += hit_target
        ends.append(bal)
        dds.append(dd)
    ends = np.array(ends)
    return {
        "P(lose half)_%": round(100 * half / n_sims, 1),
        "P(end below start)_%": round(100 * (ends < deposit).mean(), 1),
        f"P(reach ${target:,.0f})_%": round(100 * reach / n_sims, 1),
        "end_p5": round(np.percentile(ends, 5), 0), "end_median": round(np.median(ends), 0),
        "end_p95": round(np.percentile(ends, 95), 0),
        "median_max_dd_%": round(100 * np.median(dds), 1),
    }


def edge_check(tr: pd.DataFrame, n_null: int, seed: int = 11) -> list[str]:
    """Is there an edge worth sizing? Trade-level bootstrap of expectancy, and the same rules run on
    random walks (markets with no edge by construction) over the same length of time."""
    r = tr["R"].dropna().values
    rng = np.random.default_rng(seed)
    boots = rng.choice(r, (10000, len(r)), replace=True).mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    wins, losses = r[r > 0].sum(), -r[r <= 0].sum()
    longs = tr.loc[tr["side"] == "LONG", "R"]
    shorts = tr.loc[tr["side"] == "SHORT", "R"]
    out = ["## Is there an edge to size? (in-sample, every signal, $5,000 research run)", "",
           f"- {len(r)} trades, expectancy **{r.mean():+.3f}R**, profit factor {wins / losses:.2f}, "
           f"win rate {100 * (r > 0).mean():.0f}%.",
           f"- 95% bootstrap range for expectancy: **{lo:+.3f}R to {hi:+.3f}R**"
           f" ({100 * (boots <= 0).mean():.0f}% of resamples at or below zero).",
           f"- Longs: {len(longs)} trades, {longs.mean():+.3f}R each. Shorts: {len(shorts)} trades, "
           f"{shorts.mean():+.3f}R each."]
    if n_null > 0:
        import ms_replica as M
        spec = M.Spec("RW", 2, 0.01, 0.01, 1.0, 100.0, 0.01, 0.01, 100.0, 0, 0, 0.0, 0.0, 3, "USD")
        mkt = M.Market("RW", "null", "NEW_YORK", 8 * 60, 17 * 60, False)
        start = pd.Timestamp(tr["entry_time"].min()).normalize() - pd.Timedelta(days=60)
        end = pd.Timestamp(tr["entry_time"].max()).normalize() + pd.Timedelta(days=7)
        t = pd.date_range(start, end, freq="5min")
        t = t[t.dayofweek < 5]
        exps = []
        for k in range(n_null):
            g = np.random.default_rng(1000 + k)
            close = 2000 + np.cumsum(g.normal(0, 0.6, len(t)))
            open_ = np.concatenate([[close[0]], close[:-1]])
            bars = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + np.abs(g.normal(0, 0.3, len(t))),
                                 "low": np.minimum(open_, close) - np.abs(g.normal(0, 0.3, len(t))),
                                 "close": close, "spread": 0.0}, index=t)
            rt = M.Replica(bars, spec, mkt, M.Params(), deposit=100000.0).run(start + pd.Timedelta(days=60), end)
            if len(rt):
                exps.append(rt["R"].mean())
        exps = np.array(exps)
        p5, p50, p95 = np.percentile(exps, [5, 50, 95])
        beat = 100 * (exps >= r.mean()).mean()
        out += [f"- Same rules on {len(exps)} random walks (no edge possible, no costs), same span: expectancy "
                f"5th–95th percentile **{p5:+.3f}R to {p95:+.3f}R** (median {p50:+.3f}R). "
                f"{beat:.0f}% of them did at least as well as gold."]
    return out + [""]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", required=True)
    ap.add_argument("--deposit", type=float, default=200.0)
    ap.add_argument("--price", type=float, default=4190.0, help="today's gold price for the rescaled runs")
    ap.add_argument("--stress", type=float, default=0.30, help="extra $ per oz per round trip")
    ap.add_argument("--cap", type=float, default=5.0, help="P3: max % risk on the smallest position")
    ap.add_argument("--n-trades", type=int, default=100)
    ap.add_argument("--sims", type=int, default=10000)
    ap.add_argument("--out", default=None, help="write a markdown report here")
    ap.add_argument("--null", type=int, default=0, help="random-walk runs for the edge check (e.g. 40)")
    a = ap.parse_args()

    tr = pd.read_csv(a.trades)
    po = per_ounce(tr)
    today = rescale(po, a.price)
    years = (po["entry_time"].max() - po["entry_time"].min()).days / 365.25
    target = round(today["risk"].median() * MIN_OZ / 0.01, -2)   # account where 1 oz = 1% at the median stop

    lines = [f"# $ {a.deposit:,.0f} gold account — H-002 amendment 16 (in-sample only)", "",
             f"Trade list: `{a.trades}` ({len(po)} signals, {po['entry_time'].min():%Y-%m-%d} → "
             f"{po['entry_time'].max():%Y-%m-%d}, {len(po) / years:.0f} a year). Produced by `research/small_account.py`.",
             f"Smallest position 1 oz. Today's price used: ${a.price:,.0f}. Cost stress: +${a.stress:.2f}/oz per trade. "
             f"P3 cap: {a.cap:g}%. Stop-out assumed at {int(STOP_OUT * 100)}% margin level.", ""]

    lines += edge_check(tr, a.null)
    lines += ["## Stop size: what one ounce risks", "",
              "| | historical prices | at today's price |", "|---|---|---|"]
    for q, lab in ((0.25, "25th percentile"), (0.5, "median"), (0.9, "90th percentile")):
        h, t = po["risk"].quantile(q), today["risk"].quantile(q)
        lines.append(f"| {lab} stop | ${h:,.2f} ({100 * h / a.deposit:.0f}% of ${a.deposit:,.0f}) | "
                     f"${t:,.2f} ({100 * t / a.deposit:.0f}% of ${a.deposit:,.0f}) |")
    lines += ["", f"Account needed for 1 oz = 1% at the median stop today: about **${target:,.0f}**.", ""]

    runs = [("a historical", po, 0.0), ("b today's price", today, 0.0), ("c today + cost stress", today, a.stress)]
    table = []
    for name, data, stress in runs:
        for pol in ("P1", "P2", "P3"):
            _, st = replay(data, a.deposit, pol, a.cap, stress)
            table.append({"run": name, "policy": pol, **st})
    df = pd.DataFrame(table)
    lines += ["## Replays (one pass through the in-sample trades, in order)", "", df.to_markdown(index=False), "",
              "A replay stops when the balance reaches zero (a broker stop-out would usually come earlier). "
              "`taken` below `signals` for P2 means the account was wiped out; for P3 it means wide-stop trades "
              "were skipped. margin>50%eq counts trades whose margin needed more than half the equity; "
              "stop_out counts trades whose worst open loss would have triggered the broker's stop-out.", ""]

    mc = []
    for pol in ("P2", "P3"):
        mc.append({"policy": pol, "trades": a.n_trades,
                   **monte_carlo(today, a.deposit, pol, a.cap, a.stress, a.n_trades, a.sims, target)})
        mc.append({"policy": pol, "trades": round(len(po) / years),
                   **monte_carlo(today, a.deposit, pol, a.cap, a.stress, round(len(po) / years), a.sims, target)})
    mcdf = pd.DataFrame(mc)
    lines += [f"## Monte Carlo (run d): {a.sims:,} random orderings at today's price with cost stress", "",
              mcdf.to_markdown(index=False), ""]

    # serial dependence check for the Monte Carlo assumption
    r = (po["move"] + po["swap"] - po["comm"]) / po["risk"]
    lines += [f"Lag-1 autocorrelation of trade results: {r.autocorr(1):+.2f} "
              "(near zero supports drawing trades independently).", ""]

    # pre-registered decision rule
    c_p = {p: df[(df["run"] == "c today + cost stress") & (df["policy"] == p)].iloc[0] for p in ("P2", "P3")}
    d_p = {p: mcdf[(mcdf["policy"] == p) & (mcdf["trades"] == a.n_trades)].iloc[0] for p in ("P2", "P3")}
    lines += ["## Decision rule (amendment 16)", "", "| Test | P2 | P3 |", "|---|---|---|"]
    t1 = {p: d_p[p]["P(lose half)_%"] <= 10 for p in c_p}
    t2 = {p: c_p[p]["median_risk_%"] <= 5 for p in c_p}
    lines.append("| 1. P(lose half in 100 trades) ≤ 10% | " +
                 " | ".join(f"{d_p[p]['P(lose half)_%']}% {'pass' if t1[p] else 'FAIL'}" for p in c_p) + " |")
    lines.append("| 2. Median risk per trade ≤ 5% | " +
                 " | ".join(f"{c_p[p]['median_risk_%']}% {'pass' if t2[p] else 'FAIL'}" for p in c_p) + " |")
    for L in (20, 100, 500):
        lines.append(f"| 3. Margin ≤ 50% of equity at 1:{L} (trades breaching) | " +
                     " | ".join(f"{c_p[p][f'margin>50%eq_1:{L}']} {'pass' if c_p[p][f'margin>50%eq_1:{L}'] == 0 else 'FAIL'}"
                                for p in c_p) + " |")
    lines += ["", "Test 3 depends on the account's real leverage (MT5: right-click the account in Navigator, or "
              "the account details at FP Markets).", ""]
    rep = "\n".join(lines)
    print(rep)
    if a.out:
        with open(a.out, "w") as f:
            f.write(rep + "\n")


if __name__ == "__main__":
    main()
